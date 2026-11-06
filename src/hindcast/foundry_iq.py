"""Foundry IQ knowledge base against the library search (eval/retrieval/foundry-iq-v1).

    python -m hindcast.foundry_iq index
    python -m hindcast.foundry_iq setup --arm minimal
    python -m hindcast.foundry_iq quality --arm minimal

(each with PYTHONPATH=src uv run --frozen --env-file .env)

`index` builds a second index with the library's chunks and a vectorizer, so
the knowledge base can embed its own queries; the library index stays as
decision 0019 settled it. `setup` creates the knowledge source and the arm's
knowledge base. `quality` runs the frozen library-v1 queries through the
knowledge base, each with its case's date filter, and writes the result.

A comparison only (decision 0004): the investigator keeps its own search.
Prints counts and scores, never document text.
"""

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SearchIndex,
)

from hindcast import index
from hindcast.cases import Case
from hindcast.library import LibraryDocument
from hindcast.search import LibraryLeak, allowed, library_filter

type Arm = Literal["minimal", "planning"]

KB_INDEX = "hindcast-library-1024-kb"
KNOWLEDGE_SOURCE = "hindcast-library-ks"
KNOWLEDGE_BASE: dict[str, str] = {
    "minimal": "hindcast-library-kb",
    "planning": "hindcast-library-kb-planning",
}
# Generally available on 2026-11-05: knowledge sources, knowledge bases, and
# minimal extractive retrieval. Query planning needs the preview, labelled as
# such in every result (decision 0004).
API_VERSION: dict[str, str] = {"minimal": "2026-04-01", "planning": "2026-08-01-preview"}
EMBEDDING_DEPLOYMENT = "text-embedding-3-large"
PLANNER_DEPLOYMENT = "gpt-5.4-mini"
VECTORIZER = "library-vectorizer"
SCOPE = "https://search.azure.com/.default"
# The query set the baseline ran on (library-v1); any other bytes are refused.
QUERIES = Path("eval/retrieval/library-v1/queries.json")
QUERIES_SHA256 = "70ad097a9f2464aae89f3290c294ae3d7fb068145ba05ce2f21cd49893915f43"
RESULTS_DIR = Path("eval/retrieval/foundry-iq-v1")


def frozen_queries(data: bytes) -> list[dict]:
    """The library-v1 queries, refused unless they are the bytes the baseline ran on."""
    if hashlib.sha256(data).hexdigest() != QUERIES_SHA256:
        raise ValueError(f"{QUERIES}: SHA-256 differs from the baseline's query set")
    return json.loads(data)


def kb_index_definition(resource_uri: str) -> SearchIndex:
    """The library index's definition under KB_INDEX, with a vectorizer on its profile.

    No key and no user identity: the search service's system identity calls
    the embedding deployment.
    """
    definition = index.index_definition(KB_INDEX, 1024)
    vectorizer = AzureOpenAIVectorizer(
        vectorizer_name=VECTORIZER,
        parameters=AzureOpenAIVectorizerParameters(
            resource_url=resource_uri.rstrip("/"),
            deployment_name=EMBEDDING_DEPLOYMENT,
            model_name=EMBEDDING_DEPLOYMENT,
        ),
    )
    search = definition.vector_search
    if search is None or not search.profiles:
        raise ValueError("the library index definition has no vector profile")
    search.vectorizers = [vectorizer]
    for profile in search.profiles:
        profile.vectorizer_name = VECTORIZER
    return definition


def ks_body() -> dict:
    return {
        "name": KNOWLEDGE_SOURCE,
        "kind": "searchIndex",
        "description": "The Hindcast postmortem library, for the Foundry IQ comparison.",
        "searchIndexParameters": {
            "searchIndexName": KB_INDEX,
            "semanticConfigurationName": index.SEMANTIC_CONFIG,
            "sourceDataFields": [{"name": "doc_id"}, {"name": "ref"}],
        },
    }


def kb_body(arm: Arm, resource_uri: str) -> dict:
    body: dict[str, Any] = {
        "name": KNOWLEDGE_BASE[arm],
        "knowledgeSources": [{"name": KNOWLEDGE_SOURCE}],
    }
    if arm == "planning":
        body |= {
            "models": [
                {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": resource_uri.rstrip("/"),
                        "deploymentId": PLANNER_DEPLOYMENT,
                        "modelName": PLANNER_DEPLOYMENT,
                    },
                }
            ],
            "retrievalReasoningEffort": {"kind": "low"},
            "outputMode": "extractiveData",
        }
    return body


def retrieve_body(arm: Arm, query: str, query_filter: str) -> dict:
    """One query as the arm sends it, with the case's filter on the source."""
    params = {
        "knowledgeSourceName": KNOWLEDGE_SOURCE,
        "kind": "searchIndex",
        "filterAddOn": query_filter,
        "includeReferences": True,
        "includeReferenceSourceData": True,
    }
    if arm == "minimal":
        return {
            "intents": [{"type": "semantic", "search": query}],
            "knowledgeSourceParams": [params],
        }
    return {
        "messages": [{"role": "user", "content": [{"type": "text", "text": query}]}],
        "retrievalReasoningEffort": {"kind": "low"},
        "outputMode": "extractiveData",
        "knowledgeSourceParams": [params],
    }


def ranked_docs(response: Mapping[str, Any]) -> list[str]:
    """The documents of the index references, highest reranker score first."""
    references = [r for r in response.get("references", []) if r.get("type") == "searchIndex"]
    # A stable sort: references without a score keep the order they came in.
    references.sort(key=lambda r: -(r.get("rerankerScore") or 0.0))
    docs = []
    for reference in references:
        doc_id = (reference.get("sourceData") or {}).get("doc_id")
        if not doc_id:
            raise ValueError(f"reference {reference.get('id')!r} carries no doc_id")
        docs.append(doc_id)
    return docs


def compare(
    queries: list[dict],
    *,
    arm: Arm,
    cases: Mapping[str, Case],
    library: Mapping[str, LibraryDocument],
    call: Callable[[dict], Mapping[str, Any]],
) -> dict:
    """Recall at 5 and reciprocal rank per scored query, scored as the baseline was."""
    rows = []
    empty = 0
    for q in queries:
        case = cases[q["case_id"]]
        query_filter = library_filter(case, library, picks_only=False)
        response = call(retrieve_body(arm, q["query"], query_filter))
        ranked = ranked_docs(response)
        # The baseline raises on a hit outside the case's filter
        # (hindcast.search._check); a knowledge base that ignored the filter
        # would otherwise score as if it had kept it (#85).
        for doc_id in ranked:
            doc = library.get(doc_id)
            if doc is None:
                raise LibraryLeak(f"{case.case_id}: reference to {doc_id}, not in the library")
            if not allowed(case, doc, picks_only=False):
                raise LibraryLeak(f"{case.case_id}: reference to {doc_id}, which it may not read")
        # Counted, so a run of empty answers is visible next to the scores.
        empty += not ranked
        rows.append(
            {
                "query_id": q["query_id"],
                "scored": bool(q["relevant"]),
                "top": list(dict.fromkeys(ranked))[: index.QUALITY_K],
                "recall_at_5": index.recall_at(ranked, q["relevant"]),
                "reciprocal_rank": index.reciprocal_rank(ranked, q["relevant"]),
            }
        )
    scored = [r for r in rows if r["scored"]]
    return {
        "queries": len(rows),
        "scored": len(scored),
        "empty_responses": empty,
        "mean_recall_at_5": sum(r["recall_at_5"] for r in scored) / len(scored) if scored else 0.0,
        "mean_reciprocal_rank": (
            sum(r["reciprocal_rank"] for r in scored) / len(scored) if scored else 0.0
        ),
        "rows": rows,
    }


def result_record(
    arm: Arm,
    result: dict,
    *,
    provenance: Mapping[str, str],
    embedding: Mapping[str, str],
    planner: Mapping[str, str] | None,
    run_at: str,
) -> dict:
    return {
        "arm": arm,
        "api_version": API_VERSION[arm],
        "preview": API_VERSION[arm].endswith("-preview"),
        "index": KB_INDEX,
        "knowledge_source": KNOWLEDGE_SOURCE,
        "knowledge_base": KNOWLEDGE_BASE[arm],
        "embedding": dict(embedding),
        "planner": dict(planner) if planner else {"deployment": None},
        "queries_sha256": QUERIES_SHA256,
        **provenance,
        "run_at": run_at,
    } | result


def rest(endpoint: str, api_version: str) -> Callable[[str, str, dict | None], dict]:
    """A JSON call to the search service with an Entra token; no key exists to use."""
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()

    def call(method: str, path: str, body: dict | None) -> dict:
        token = credential.get_token(SCOPE).token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if method == "PUT":
            # The 2026-04-01 reference marks it required on create or update.
            headers["Prefer"] = "return=representation"
        request = urllib.request.Request(  # noqa: S310 (the configured https endpoint)
            f"{endpoint.rstrip('/')}/{path}?api-version={api_version}",
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                text = response.read()
        except urllib.error.HTTPError as error:
            # The service's error message names the field; it holds no secret.
            raise RuntimeError(f"{method} {path}: {error.code} {error.read()[:2000]!r}") from error
        return json.loads(text) if text else {}

    return call


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.foundry_iq")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("index", help="build the knowledge base's index")
    for name in ("setup", "quality"):
        command = commands.add_parser(name)
        command.add_argument("--arm", choices=sorted(KNOWLEDGE_BASE), required=True)
    args = parser.parse_args(argv)

    from hindcast.config import SearchSettings, load_settings

    settings = load_settings(SearchSettings)
    if args.command == "index":
        cases, library, _ = index.quality_inputs()
        index_client, search_client = index.clients(KB_INDEX)
        count = index.build(
            KB_INDEX,
            1024,
            index.load_chunks(library),
            replace=False,
            index_client=index_client,
            search_client=search_client,
            embed=index.embedder(1024),
            definition=kb_index_definition(settings.embedding_endpoint),
        )
        print(f"{KB_INDEX}: {count} chunks")
        return 0

    arm: Arm = args.arm
    call = rest(settings.search_endpoint, API_VERSION[arm])
    if args.command == "setup":
        call("PUT", f"knowledgesources/{KNOWLEDGE_SOURCE}", ks_body())
        call(
            "PUT",
            f"knowledgebases/{KNOWLEDGE_BASE[arm]}",
            kb_body(arm, settings.embedding_endpoint),
        )
        print(f"{KNOWLEDGE_SOURCE} and {KNOWLEDGE_BASE[arm]} at {API_VERSION[arm]}")
        return 0

    from hindcast.models import deployment_model

    queries = frozen_queries(QUERIES.read_bytes())
    cases, library, _ = index.quality_inputs()
    result = compare(
        queries,
        arm=arm,
        cases=cases,
        library=library,
        call=lambda body: call("POST", f"knowledgebases/{KNOWLEDGE_BASE[arm]}/retrieve", body),
    )
    planner = None
    if arm == "planning":
        name, version = deployment_model(PLANNER_DEPLOYMENT)
        planner = {"deployment": PLANNER_DEPLOYMENT, "name": name, "version": version}
    record = result_record(
        arm,
        result,
        provenance={
            "queries_commit": index._git("log", "-1", "--format=%H", "--", str(QUERIES)),
            "library_commit": index._git("log", "-1", "--format=%H", "--", "data/library.yaml"),
            "code_commit": index._git("rev-parse", "HEAD"),
        },
        embedding=index.embedding_model(),
        planner=planner,
        run_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    out = RESULTS_DIR / f"results-{arm}.json"
    with out.open("x", encoding="utf-8") as file:
        file.write(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    print(
        f"{arm}: {result['scored']} of {result['queries']} queries scored, "
        f"mean recall@5 {result['mean_recall_at_5']:.3f}, "
        f"MRR {result['mean_reciprocal_rank']:.3f}, {result['empty_responses']} with no reference; "
        f"written to {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

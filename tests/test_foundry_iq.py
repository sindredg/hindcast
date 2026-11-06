"""The Foundry IQ comparison's requests and scoring, with stubs (eval/retrieval/foundry-iq-v1)."""

import json
from pathlib import Path

import pytest
from azure.search.documents.indexes.models import AzureOpenAIVectorizer

from hindcast import foundry_iq, index
from hindcast.cases import load_cases
from hindcast.search import LibraryLeak, library_filter
from test_search import doc

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "eval/retrieval/library-v1/queries.json"


def test_frozen_queries_refuses_changed_bytes():
    data = QUERIES.read_bytes()
    assert foundry_iq.frozen_queries(data) == json.loads(data)
    with pytest.raises(ValueError, match="SHA-256"):
        foundry_iq.frozen_queries(data + b" ")


def test_kb_index_definition_adds_a_vectorizer():
    definition = foundry_iq.kb_index_definition("https://example.services.ai.azure.com/")
    assert definition.name == foundry_iq.KB_INDEX
    search = definition.vector_search
    assert search is not None and search.vectorizers and search.profiles
    vectorizer = search.vectorizers[0]
    assert isinstance(vectorizer, AzureOpenAIVectorizer) and vectorizer.parameters is not None
    assert vectorizer.parameters.deployment_name == "text-embedding-3-large"
    assert vectorizer.parameters.model_name == "text-embedding-3-large"
    # No key and no user identity: the search service's system identity.
    assert vectorizer.parameters.auth_identity is None
    assert search.profiles[0].vectorizer_name == vectorizer.vectorizer_name
    # Everything else is the library index's definition.
    library = index.index_definition("x", 1024)
    assert [f.name for f in definition.fields] == [f.name for f in library.fields]


def test_retrieve_body_carries_the_case_filter():
    cases = load_cases()
    case = cases["cloudflare-2026-02-20"]
    expected = library_filter(case, {}, picks_only=False)
    for mode in ("minimal", "planning"):
        body = foundry_iq.retrieve_body(mode, "packet loss", expected)
        (params,) = body["knowledgeSourceParams"]
        assert params["filterAddOn"] == expected
        assert params["kind"] == "searchIndex"
        assert params["includeReferenceSourceData"] is True
    assert foundry_iq.retrieve_body("minimal", "packet loss", expected)["intents"] == [
        {"type": "semantic", "search": "packet loss"}
    ]
    planning = foundry_iq.retrieve_body("planning", "packet loss", expected)
    assert planning["messages"][0]["content"] == [{"type": "text", "text": "packet loss"}]
    assert planning["retrievalReasoningEffort"] == {"kind": "low"}


def test_kb_body_has_a_model_only_when_planning():
    minimal = foundry_iq.kb_body("minimal", "https://example.services.ai.azure.com/")
    planning = foundry_iq.kb_body("planning", "https://example.services.ai.azure.com/")
    assert "models" not in minimal
    assert planning["models"][0]["azureOpenAIParameters"]["deploymentId"] == "gpt-5.4-mini"
    assert (
        minimal["knowledgeSources"]
        == planning["knowledgeSources"]
        == [{"name": foundry_iq.KNOWLEDGE_SOURCE}]
    )


def test_ranked_docs_orders_by_reranker_score():
    response = {
        "references": [
            {"type": "searchIndex", "rerankerScore": 2.6, "sourceData": {"doc_id": "b"}},
            {"type": "web", "rerankerScore": 3.9, "sourceData": {"doc_id": "web"}},
            {"type": "searchIndex", "rerankerScore": 3.1, "sourceData": {"doc_id": "a"}},
            {"type": "searchIndex", "rerankerScore": 2.9, "sourceData": {"doc_id": "a"}},
        ]
    }
    assert foundry_iq.ranked_docs(response) == ["a", "a", "b"]


def test_ranked_docs_refuses_a_reference_without_a_document():
    with pytest.raises(ValueError, match="doc_id"):
        foundry_iq.ranked_docs({"references": [{"type": "searchIndex", "sourceData": {}}]})


def test_compare_scores_like_the_library_check():
    cases = load_cases()
    queries = [
        {"query_id": "q1", "case_id": "cloudflare-2026-02-20", "query": "x", "relevant": ["a"]},
        {"query_id": "q2", "case_id": "cloudflare-2026-02-20", "query": "y", "relevant": []},
    ]
    seen: list[dict] = []

    def call(body: dict) -> dict:
        seen.append(body)
        return {
            "references": [
                {"type": "searchIndex", "rerankerScore": 3.0, "sourceData": {"doc_id": "b"}},
                {"type": "searchIndex", "rerankerScore": 2.8, "sourceData": {"doc_id": "a"}},
            ]
        }

    library = {d: doc(d, "2024-01-01", ()) for d in ("a", "b")}
    result = foundry_iq.compare(queries, arm="minimal", cases=cases, library=library, call=call)
    assert len(seen) == 2
    assert result["scored"] == 1
    assert result["mean_recall_at_5"] == 1.0
    assert result["mean_reciprocal_rank"] == 0.5
    assert result["rows"][0]["top"] == ["b", "a"]
    assert result["empty_responses"] == 0


@pytest.mark.parametrize(
    ("library", "match"),
    [
        # Published on the case's start day: the date filter excludes it.
        ({"a": doc("a", "2026-02-20", ())}, "may not read"),
        ({}, "not in the library"),
    ],
)
def test_compare_refuses_a_document_the_case_filter_excludes(library: dict, match: str) -> None:
    # The baseline raises on such a hit; a knowledge base that ignored the
    # filter would otherwise go unnoticed (#85).
    queries = [{"query_id": "q1", "case_id": "cloudflare-2026-02-20", "query": "x", "relevant": []}]

    def call(body: dict) -> dict:
        return {"references": [{"type": "searchIndex", "sourceData": {"doc_id": "a"}}]}

    with pytest.raises(LibraryLeak, match=match):
        foundry_iq.compare(queries, arm="minimal", cases=load_cases(), library=library, call=call)


def test_compare_counts_responses_with_no_references() -> None:
    queries = [
        {"query_id": "q1", "case_id": "cloudflare-2026-02-20", "query": "x", "relevant": ["a"]}
    ]
    result = foundry_iq.compare(
        queries, arm="minimal", cases=load_cases(), library={}, call=lambda body: {}
    )
    assert result["empty_responses"] == 1
    assert result["mean_recall_at_5"] == 0.0


def test_results_name_every_version():
    record = foundry_iq.result_record(
        "planning",
        {"queries": 0, "scored": 0, "rows": []},
        provenance={"queries_commit": "c", "library_commit": "l", "code_commit": "k"},
        embedding={"deployment": "text-embedding-3-large", "version": "1"},
        planner={"deployment": "gpt-5.4-mini", "version": "2026-03-17"},
        run_at="2026-11-06T00:00:00Z",
    )
    for key in (
        "arm",
        "api_version",
        "index",
        "knowledge_base",
        "embedding",
        "planner",
        "queries_sha256",
        "queries_commit",
        "library_commit",
        "code_commit",
        "run_at",
    ):
        assert record[key], key
    assert record["api_version"] == "2026-08-01-preview"


def test_rest_sends_prefer_on_put_and_a_bearer_token(monkeypatch):
    import contextlib
    from types import SimpleNamespace

    import azure.identity

    sent: list = []

    class Credential:
        def get_token(self, scope):
            assert scope == foundry_iq.SCOPE
            return SimpleNamespace(token="t")  # noqa: S106 (a stub, not a credential)

    @contextlib.contextmanager
    def urlopen(request, timeout):
        sent.append(request)
        yield SimpleNamespace(read=lambda: b"{}")

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", Credential)
    monkeypatch.setattr(foundry_iq.urllib.request, "urlopen", urlopen)
    call = foundry_iq.rest("https://search.example", "2026-04-01")
    call("PUT", "knowledgesources/ks", {"name": "ks"})
    call("POST", "knowledgebases/kb/retrieve", {"intents": []})
    put, post = sent
    assert put.get_full_url() == "https://search.example/knowledgesources/ks?api-version=2026-04-01"
    # The 2026-04-01 reference marks the header required on create or update.
    assert put.get_header("Prefer") == "return=representation"
    assert put.get_header("Authorization") == "Bearer t"
    assert post.get_header("Prefer") is None

"""The library search, bound to one case's date and picks.

    python -m hindcast.search <case_id> <query>

The filter is built from the case registry and the library registry only:
documents published before the day the outage began, and, for a case with
picks, only the documents picked for it (decision 0019). A sealed case has no
picks, so its search covers every document dated before it. The query text
goes to the keyword and vector parts of the search, never into the filter.

Every hit is checked again in code against the same rule, and its ref
against the library extracts, before it is returned: a hit outside them
raises LibraryLeak rather than reaching a reader. A case's own postmortem is
never in the library (hindcast.library refuses it), and a sealed case's
postmortem, when it comes, is dated after the outage began.

The command prints refs, documents, dates, and scores, never the text.
"""

import argparse
import functools
import json
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from azure.search.documents.models import VectorizedQuery

from hindcast.cases import CASE_ID, Case, load_cases
from hindcast.index import EXTRACTS_DIR, SEMANTIC_CONFIG, VECTOR_FIELD
from hindcast.library import LibraryDocument, load_library

TOP = 5
# Candidates the vector part passes to the merge and the semantic ranker.
VECTOR_K = 50
FIELDS = ["ref", "doc_id", "title", "heading", "published_at", "content"]


class LibraryLeak(RuntimeError):
    """The service returned a hit the case's rule does not allow."""


@dataclass(frozen=True)
class LibraryHit:
    ref: str
    doc_id: str
    title: str
    heading: str
    published_at: str
    content: str
    score: float
    reranker_score: float | None


def _bound(case: Case) -> str:
    # Publish dates are days, so a document from the start day cannot be
    # ordered against the start time: the bound is the start day's midnight.
    return f"{case.started_at[:10]}T00:00:00Z"


def allowed(case: Case, doc: LibraryDocument, *, picks_only: bool = True) -> bool:
    """The filter's rule in code."""
    if f"{doc.published_at}T00:00:00Z" >= _bound(case):
        return False
    return not picks_only or case.role == "sealed" or case.case_id in doc.serves


def library_filter(
    case: Case, library: Mapping[str, LibraryDocument], *, picks_only: bool = True
) -> str:
    """The OData filter for one case, from the registries alone."""
    if not CASE_ID.fullmatch(case.case_id):
        raise ValueError(f"case ID {case.case_id!r} is malformed")
    date = f"published_at lt {_bound(case)}"
    if not picks_only or case.role == "sealed":
        return date
    if not any(case.case_id in doc.serves for doc in library.values()):
        raise ValueError(f"{case.case_id} has no library picks")
    # The case ID matches CASE_ID (letters, digits, hyphens), so it cannot
    # close the quoted literal.
    return f"{date} and serves/any(s: s eq '{case.case_id}')"


class SearchClientLike(Protocol):
    def search(self, search_text: str | None = None, /, **kwargs: Any) -> Iterable[dict]: ...


@functools.cache
def extract_refs(extracts_dir: Path = EXTRACTS_DIR) -> frozenset[str]:
    """Every section and figure ID in the local library extracts."""
    refs: set[str] = set()
    for path in extracts_dir.glob("*.json"):
        extract = json.loads(path.read_bytes())
        refs |= {s["section_id"] for s in extract["sections"]}
        refs |= {f["figure_id"] for f in extract["figures"]}
    return frozenset(refs)


def _check(
    case: Case,
    found: dict,
    library: Mapping[str, LibraryDocument],
    refs: Collection[str],
    picks_only: bool,
) -> None:
    doc_id, ref = found["doc_id"], found["ref"]
    doc = library.get(doc_id)
    if doc is None:
        raise LibraryLeak(f"{case.case_id}: hit from {doc_id}, which is not in the library")
    if not allowed(case, doc, picks_only=picks_only):
        raise LibraryLeak(f"{case.case_id}: hit from {doc_id}, which the case may not read")
    if not ref.startswith(f"lib/{doc_id}/") or ref not in refs:
        raise LibraryLeak(f"{case.case_id}: hit {ref} does not resolve to {doc_id}")


def search_library(
    case_id: str,
    query: str,
    *,
    top: int = TOP,
    picks_only: bool = True,
    cases: Mapping[str, Case] | None = None,
    library: Mapping[str, LibraryDocument] | None = None,
    refs: Collection[str] | None = None,
    client: SearchClientLike | None = None,
    embed: Callable[..., list[list[float]]] | None = None,
    timeout: float | None = None,
) -> list[LibraryHit]:
    """Hybrid keyword and vector search with semantic ranking, within the case's rule.

    timeout bounds the embedding call and each search request; a timeout
    raises TimeoutError.
    """
    if not CASE_ID.fullmatch(case_id):
        raise ValueError(f"case ID {case_id!r} is malformed")
    cases = cases if cases is not None else load_cases()
    if case_id not in cases:
        raise ValueError(f"{case_id} is not in the case registry")
    case = cases[case_id]
    library = library if library is not None else load_library(Path("data/library.yaml"), cases)
    refs = refs if refs is not None else extract_refs()
    query_filter = library_filter(case, library, picks_only=picks_only)
    if embed is None or client is None:
        from hindcast.config import SearchSettings, load_settings
        from hindcast.index import clients, embedder

        settings = load_settings(SearchSettings)
        embed = embed or embedder(settings.embedding_dimensions)
        client = client or clients(settings.search_index)[1]
    from azure.core.exceptions import ServiceRequestTimeoutError, ServiceResponseTimeoutError

    [vector] = embed([query]) if timeout is None else embed([query], timeout=timeout)
    limits: dict[str, Any] = (
        {} if timeout is None else {"connection_timeout": timeout, "read_timeout": timeout}
    )
    results = client.search(
        query,
        filter=query_filter,
        vector_queries=[
            VectorizedQuery(vector=vector, k_nearest_neighbors=VECTOR_K, fields=VECTOR_FIELD)
        ],
        vector_filter_mode="preFilter",
        query_type="semantic",
        semantic_configuration_name=SEMANTIC_CONFIG,
        top=top,
        select=FIELDS,
        **limits,
    )
    hits = []
    try:
        # The request runs when the results are read.
        for found in results:
            _check(case, found, library, refs, picks_only)
            hits.append(
                LibraryHit(
                    **{name: found[name] for name in FIELDS},
                    score=found["@search.score"],
                    reranker_score=found.get("@search.reranker_score"),
                )
            )
    except (ServiceRequestTimeoutError, ServiceResponseTimeoutError) as error:
        raise TimeoutError("library search timed out") from error
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.search")
    parser.add_argument("case_id")
    parser.add_argument("query")
    args = parser.parse_args(argv)
    hits = search_library(args.case_id, args.query)
    print(f"{args.case_id}: {len(hits)} hits")
    for h in hits:
        print(f"  {h.ref}  {h.published_at[:10]}  score {h.score:.3f}  rerank {h.reranker_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

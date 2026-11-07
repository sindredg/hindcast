from dataclasses import replace
from pathlib import Path

import pytest

from hindcast.cases import load_cases
from hindcast.library import LibraryDocument
from hindcast.search import (
    LibraryLeak,
    allowed,
    case_chunks,
    contents_digest,
    library_filter,
    search_library,
)

CASES = load_cases(Path("data/cases.yaml"))
SCORED = CASES["cloudflare-2025-11-18"]
SEALED = next(c for c in CASES.values() if c.role == "sealed")


def doc(doc_id: str, published_at: str, serves: tuple[str, ...]) -> LibraryDocument:
    return LibraryDocument(
        doc_id=doc_id,
        provider="Cloudflare",
        title=doc_id,
        url=f"https://blog.example.com/{doc_id}/",
        published_at=published_at,
        filename=f"{doc_id}.html",
        sha256="0" * 64,
        retrieved_at="2026-10-27T15:59:14Z",
        licence="Copyright Example; not redistributed",
        attribution="Example blog",
        kind="same-provider",
        serves=serves,
        reason="r",
    )


LIBRARY = {
    "earlier-pick": doc("earlier-pick", "2025-06-12", (SCORED.case_id,)),
    "earlier-other": doc("earlier-other", "2024-06-26", ("github-2026-08-17",)),
    "later-pick": doc("later-pick", "2025-12-01", (SCORED.case_id,)),
}
REFS = {f"lib/{d}/s1" for d in LIBRARY}


def start_day(case) -> str:
    return case.started_at[:10]


class FakeSearch:
    def __init__(self, hits: list[dict] | None = None):
        self.hits = hits or []
        self.calls: list[tuple] = []

    def search(self, search_text=None, **kwargs):
        self.calls.append((search_text, kwargs))
        return iter(self.hits)


def hit(doc_id: str, ref: str | None = None, published_at: str | None = None) -> dict:
    return {
        "ref": ref or f"lib/{doc_id}/s1",
        "doc_id": doc_id,
        "title": doc_id,
        "heading": "Heading",
        "published_at": published_at or f"{LIBRARY[doc_id].published_at}T00:00:00Z",
        "content": "Body.",
        "@search.score": 0.5,
        "@search.reranker_score": 2.1,
    }


def run(case_id, query, client, embedded=None):
    return search_library(
        case_id,
        query,
        cases=CASES,
        library=LIBRARY,
        refs=REFS,
        client=client,
        embed=lambda texts: (
            (embedded.append(texts) if embedded is not None else None) or [[0.1] * 4 for _ in texts]
        ),
    )


def test_filter_for_a_scored_case():
    assert library_filter(SCORED, LIBRARY) == (
        f"published_at lt {start_day(SCORED)}T00:00:00Z and serves/any(s: s eq '{SCORED.case_id}')"
    )


def test_sealed_case_has_no_serves_clause():
    assert library_filter(SEALED, LIBRARY) == f"published_at lt {start_day(SEALED)}T00:00:00Z"


def test_revealed_case_keeps_the_whole_library():
    # The same case after its cause is published: still no picks (decision 0030).
    revealed = replace(SEALED, role="revealed")
    assert library_filter(revealed, LIBRARY) == f"published_at lt {start_day(SEALED)}T00:00:00Z"
    assert allowed(revealed, LIBRARY["earlier-other"])


def test_date_only_filter_for_the_quality_check():
    assert library_filter(SCORED, LIBRARY, picks_only=False) == (
        f"published_at lt {start_day(SCORED)}T00:00:00Z"
    )


def test_case_without_picks_is_refused():
    client = FakeSearch()

    # No document in LIBRARY serves this showcase case.
    with pytest.raises(ValueError, match="no library picks"):
        run("google-cloud-2026-07-14", "errors", client)
    assert client.calls == []


def test_allowed_is_the_filter_in_code():
    assert allowed(SCORED, LIBRARY["earlier-pick"])
    assert not allowed(SCORED, LIBRARY["earlier-other"])
    assert not allowed(SCORED, LIBRARY["later-pick"])
    assert allowed(SCORED, LIBRARY["earlier-other"], picks_only=False)
    assert allowed(SEALED, LIBRARY["earlier-other"])


def test_a_document_from_the_start_day_is_not_allowed():
    same_day = doc("same-day", start_day(SEALED), ())

    assert not allowed(SEALED, same_day)


def test_query_never_reaches_the_filter():
    plain, hostile = FakeSearch(), FakeSearch()
    embedded: list = []

    run(SCORED.case_id, "errors", plain)
    for query in ("' or 1 eq 1 or '", "$filter=published_at gt 2030-01-01", '") or (true'):
        run(SCORED.case_id, query, hostile, embedded)

    filters = {kwargs["filter"] for _, kwargs in plain.calls + hostile.calls}
    assert filters == {library_filter(SCORED, LIBRARY)}
    assert [text for text, _ in hostile.calls] == [
        "' or 1 eq 1 or '",
        "$filter=published_at gt 2030-01-01",
        '") or (true',
    ]
    assert embedded == [[text] for text, _ in hostile.calls]


def test_search_is_hybrid_and_semantic():
    client = FakeSearch()

    run(SCORED.case_id, "errors", client)

    [(_, kwargs)] = client.calls
    [vector] = kwargs["vector_queries"]
    assert (vector.k_nearest_neighbors, vector.fields) == (50, "content_vector")
    assert kwargs["query_type"] == "semantic"
    assert kwargs["semantic_configuration_name"] == "library"
    assert kwargs["top"] == 5
    assert kwargs["vector_filter_mode"] == "preFilter"


def test_hits_come_back_with_their_citation_target():
    [found] = run(SCORED.case_id, "errors", FakeSearch([hit("earlier-pick")]))

    assert (found.ref, found.doc_id, found.reranker_score) == (
        "lib/earlier-pick/s1",
        "earlier-pick",
        2.1,
    )


def test_hit_outside_the_filter_raises():
    with pytest.raises(LibraryLeak, match="later-pick"):
        run(SCORED.case_id, "errors", FakeSearch([hit("earlier-pick"), hit("later-pick")]))
    with pytest.raises(LibraryLeak, match="earlier-other"):
        run(SCORED.case_id, "errors", FakeSearch([hit("earlier-other")]))


def test_hit_from_a_document_outside_the_registry_raises():
    rogue = hit("earlier-pick") | {"doc_id": "rogue", "ref": "lib/rogue/s1"}

    with pytest.raises(LibraryLeak, match="rogue"):
        run(SCORED.case_id, "errors", FakeSearch([rogue]))


def test_hit_with_an_unknown_ref_raises():
    with pytest.raises(LibraryLeak, match="s9"):
        run(SCORED.case_id, "errors", FakeSearch([hit("earlier-pick", ref="lib/earlier-pick/s9")]))


def test_hit_whose_ref_names_another_document_raises():
    with pytest.raises(LibraryLeak, match="later-pick"):
        run(SCORED.case_id, "errors", FakeSearch([hit("earlier-pick", ref="lib/later-pick/s1")]))


def test_unknown_case_is_refused():
    client = FakeSearch()

    with pytest.raises(ValueError, match="not-a-case"):
        run("not-a-case", "errors", client)
    with pytest.raises(ValueError, match="case ID"):
        run("x' or '1", "errors", client)
    assert client.calls == []


def test_search_passes_timeout_and_no_retries() -> None:
    client = FakeSearch([hit("earlier-pick")])
    timeouts: list[float | None] = []

    def embed(texts, timeout=None):
        timeouts.append(timeout)
        return [[0.1] * 4 for _ in texts]

    search_library(
        SCORED.case_id,
        "q",
        cases=CASES,
        library=LIBRARY,
        refs=REFS,
        client=client,
        embed=embed,
        timeout=7.5,
    )
    assert timeouts == [7.5]
    [(_, kwargs)] = client.calls
    assert kwargs["connection_timeout"] == kwargs["read_timeout"] == pytest.approx(7.5, abs=0.01)


def test_search_timeout_raises_timeout_error() -> None:
    from azure.core.exceptions import ServiceResponseTimeoutError

    class Slow(FakeSearch):
        def search(self, search_text=None, **kwargs):
            def results():
                raise ServiceResponseTimeoutError("read timed out")
                yield {}

            return results()

    with pytest.raises(TimeoutError):
        search_library(
            SCORED.case_id,
            "q",
            cases=CASES,
            library=LIBRARY,
            refs=REFS,
            client=Slow(),
            embed=lambda texts, timeout=None: [[0.1] * 4],
            timeout=1.0,
        )


def test_investigation_search_client_makes_no_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    from hindcast import index

    monkeypatch.setenv("HINDCAST_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setenv("HINDCAST_SEARCH_INDEX", "i")
    monkeypatch.setenv("HINDCAST_EMBEDDING_ENDPOINT", "https://example.services.ai.azure.com")
    monkeypatch.setenv("HINDCAST_EMBEDDING_DEPLOYMENT", "e")
    from azure.core.pipeline.policies import RetryPolicy

    def retries(client) -> list[int]:
        policies = client._client._pipeline._impl_policies
        return [p.total_retries for p in policies if isinstance(p, RetryPolicy)]

    assert retries(index.clients("i", retry_total=0)[1]) == [0]
    # Indexing keeps the SDK's retries.
    assert retries(index.clients("i")[1]) == [10]


def test_the_search_request_gets_what_the_embedding_left() -> None:
    now = [0.0]
    client = FakeSearch([hit("earlier-pick")])

    def embed(texts, timeout=None):
        now[0] += 3.0
        return [[0.1] * 4 for _ in texts]

    search_library(
        SCORED.case_id,
        "q",
        cases=CASES,
        library=LIBRARY,
        refs=REFS,
        client=client,
        embed=embed,
        timeout=7.5,
        clock=lambda: now[0],
    )
    [(_, kwargs)] = client.calls
    assert kwargs["read_timeout"] == 4.5


def test_case_chunks_lists_what_the_filter_returns_in_id_order() -> None:
    # What a case's searches can reach, recorded with each run (#47).
    listed = [
        {"id": "lib_later_s1_p0", "ref": "lib/later-pick/s1", "doc_id": "later-pick"}
        | {"content": "B", "heading": "dropped"},
        {"id": "lib_earlier_s1_p0", "ref": "lib/earlier-pick/s1", "doc_id": "earlier-pick"}
        | {"content": "A"},
    ]
    client = FakeSearch(listed)
    chunks = case_chunks(SCORED.case_id, cases=CASES, library=LIBRARY, client=client)
    assert [c["id"] for c in chunks] == ["lib_earlier_s1_p0", "lib_later_s1_p0"]
    assert set(chunks[0]) == {"id", "ref", "doc_id", "content"}
    [(text, kwargs)] = client.calls
    assert text == "*"
    assert kwargs["filter"] == library_filter(SCORED, LIBRARY)


def test_contents_digest_changes_with_any_chunk() -> None:
    chunks = [{"id": "a", "ref": "lib/a/s1", "doc_id": "a", "content": "Body."}]
    digest = contents_digest(chunks)
    assert digest["chunks"] == 1
    changed = contents_digest([chunks[0] | {"content": "Body!"}])
    assert changed["sha256"] != digest["sha256"]
    assert contents_digest(list(chunks)) == digest

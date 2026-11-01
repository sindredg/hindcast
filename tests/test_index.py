import json
import re
from dataclasses import asdict
from pathlib import Path

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hindcast.index import (
    Chunk,
    build,
    check_chunks,
    check_filter,
    chunks,
    index_definition,
    load_chunks,
)
from hindcast.library import LibraryDocument
from hindcast.storage import SourceMismatch


def doc(**changes) -> LibraryDocument:
    values = {
        "doc_id": "doc",
        "provider": "Cloudflare",
        "title": "Example outage",
        "url": "https://blog.example.com/example-outage/",
        "published_at": "2019-07-12",
        "filename": "doc.html",
        "sha256": "0" * 64,
        "retrieved_at": "2026-10-27T15:59:14Z",
        "licence": "Copyright Example; not redistributed",
        "attribution": "Example blog",
        "kind": "same-provider",
        "serves": ("case-a", "case-b"),
        "reason": "r",
    }
    return LibraryDocument(**(values | changes))


def extract(sections=(), figures=()) -> dict:
    return {
        "doc_id": "doc",
        "published_at": "2019-07-12",
        "sections": list(sections),
        "figures": list(figures),
        "dropped": [],
    }


def section(n: int, markdown: str, heading: str = "Heading") -> dict:
    return {"section_id": f"lib/doc/s{n}", "heading": heading, "markdown": markdown}


FIGURE = {
    "figure_id": "lib/doc/fig1",
    "source_url": "https://blog.example.com/fig1.png",
    "sha256": "1" * 64,
    "description": "A line chart of requests.",
    "alt_text": "Requests over time.",
    "text_in_image": "Requests per second",
    "display": False,
}


def test_short_section_is_one_chunk():
    [chunk] = chunks(extract([section(1, "Body.")]), doc())

    assert chunk.id == "lib_doc_s1_p0"
    assert (chunk.ref, chunk.part, chunk.kind, chunk.content) == (
        "lib/doc/s1",
        0,
        "section",
        "Body.",
    )


def test_long_section_splits_at_paragraphs():
    paragraphs = [str(i) * 999 for i in range(9)]

    parts = chunks(extract([section(1, "\n\n".join(paragraphs))]), doc())

    assert len(parts) == 3
    assert [c.part for c in parts] == [0, 1, 2]
    assert all(len(c.content) <= 4000 and c.ref == "lib/doc/s1" for c in parts)
    assert "\n\n".join(c.content for c in parts) == "\n\n".join(paragraphs)
    assert len({c.id for c in parts}) == 3


def test_overlong_paragraph_is_its_own_part():
    long = "x" * 5000

    parts = chunks(extract([section(1, f"Short.\n\n{long}\n\nAfter.")]), doc())

    assert [c.content for c in parts] == ["Short.", long, "After."]


def test_overlong_table_splits_after_a_row():
    rows = [f"<tr>\n<td>{i}</td>\n<td>{'y' * 990}</td>\n</tr>" for i in range(9)]
    table = "<table>\n" + "\n".join(rows) + "\n</table>"

    parts = chunks(extract([section(1, table)]), doc())

    assert len(parts) > 1 and all(len(c.content) <= 4000 for c in parts)
    assert all(c.content.endswith("</tr>") for c in parts[:-1])
    assert "\n".join(c.content for c in parts) == table


def test_figure_chunk_joins_its_texts():
    [chunk] = chunks(extract(figures=[FIGURE]), doc())

    assert (chunk.id, chunk.ref, chunk.kind) == ("lib_doc_fig1_p0", "lib/doc/fig1", "figure")
    for text in ("A line chart of requests.", "Requests over time.", "Requests per second"):
        assert text in chunk.content


def test_chunk_carries_the_registry_fields():
    [chunk] = chunks(extract([section(1, "Body.")]), doc())

    assert chunk.published_at == "2019-07-12T00:00:00Z"
    assert chunk.serves == ("case-a", "case-b")
    assert (chunk.title, chunk.doc_id, chunk.provider) == ("Example outage", "doc", "Cloudflare")
    assert chunk.url == "https://blog.example.com/example-outage/"


def test_extract_for_another_document_is_refused():
    with pytest.raises(ValueError, match="other"):
        chunks(extract([section(1, "Body.")]) | {"doc_id": "other"}, doc())


def test_index_definition_fields():
    index = index_definition("hindcast-library-1024", 1024)
    fields = {f.name: f for f in index.fields}

    assert index.name == "hindcast-library-1024"
    assert [f.name for f in index.fields if f.key] == ["id"]
    assert {n for n, f in fields.items() if f.filterable} == {
        "doc_id",
        "kind",
        "published_at",
        "serves",
    }
    assert fields["content_vector"].vector_search_dimensions == 1024
    assert fields["content_vector"].stored is False
    assert index.semantic_search is not None
    assert [c.name for c in index.semantic_search.configurations or []] == ["library"]


class FakeSearch:
    def __init__(self, count: int = 0, fail: set[str] | None = None):
        self.count, self.fail = count, fail or set()
        self.uploaded: list[dict] = []

    def get_document_count(self) -> int:
        return self.count

    def upload_documents(self, documents):
        self.uploaded += documents

        class Result:
            def __init__(self, key, succeeded):
                self.key, self.succeeded = key, succeeded

        return [Result(d["id"], d["id"] not in self.fail) for d in documents]


class FakeIndexes:
    def __init__(self, exists: bool = True):
        self.exists = exists
        self.created: list[str] = []
        self.deleted: list[str] = []

    def get_index(self, name):
        if not self.exists:
            raise ResourceNotFoundError("no index")
        return object()

    def delete_index(self, name):
        self.deleted.append(name)

    def create_index(self, index):
        self.created.append(index.name)


def sample_chunks() -> list[Chunk]:
    return chunks(extract([section(1, "Body."), section(2, "More.")], [FIGURE]), doc())


def test_build_refuses_a_non_empty_index():
    embedded = []

    with pytest.raises(ValueError, match="--replace"):
        build(
            "hindcast-library-1024",
            1024,
            sample_chunks(),
            replace=False,
            index_client=FakeIndexes(),
            search_client=FakeSearch(count=1),
            embed=lambda texts: embedded.append(texts) or [],
        )
    assert embedded == []


def test_build_pushes_every_chunk_with_its_vector():
    indexes, search = FakeIndexes(exists=False), FakeSearch()

    count = build(
        "hindcast-library-1024",
        1024,
        sample_chunks(),
        replace=False,
        index_client=indexes,
        search_client=search,
        embed=lambda texts: [[0.5] * 1024 for _ in texts],
    )

    assert count == 3 and indexes.created == ["hindcast-library-1024"]
    assert [d["id"] for d in search.uploaded] == [
        "lib_doc_s1_p0",
        "lib_doc_s2_p0",
        "lib_doc_fig1_p0",
    ]
    assert all(len(d["content_vector"]) == 1024 for d in search.uploaded)
    assert search.uploaded[0]["content_sha256"] == sample_chunks()[0].content_sha256
    assert search.uploaded[0]["serves"] == ["case-a", "case-b"]


def test_build_with_replace_recreates_the_index():
    indexes = FakeIndexes()

    build(
        "hindcast-library-1024",
        1024,
        sample_chunks(),
        replace=True,
        index_client=indexes,
        search_client=FakeSearch(count=3),
        embed=lambda texts: [[0.5] * 1024 for _ in texts],
    )

    assert indexes.deleted == ["hindcast-library-1024"]
    assert indexes.created == ["hindcast-library-1024"]


def test_build_fails_on_a_failed_document():
    with pytest.raises(RuntimeError, match="lib_doc_s2_p0"):
        build(
            "hindcast-library-1024",
            1024,
            sample_chunks(),
            replace=False,
            index_client=FakeIndexes(exists=False),
            search_client=FakeSearch(fail={"lib_doc_s2_p0"}),
            embed=lambda texts: [[0.5] * 1024 for _ in texts],
        )


def test_build_refuses_a_vector_of_the_wrong_size():
    with pytest.raises(ValueError, match="1024"):
        build(
            "hindcast-library-1024",
            1024,
            sample_chunks(),
            replace=False,
            index_client=FakeIndexes(exists=False),
            search_client=FakeSearch(),
            embed=lambda texts: [[0.5] * 3072 for _ in texts],
        )


class FakeBlobs:
    def __init__(self, blobs: dict[str, bytes]):
        self.blobs = blobs

    def upload_blob(self, name, data, overwrite=False):
        raise AssertionError("the index build never writes to Blob Storage")

    def download_blob(self, name):
        data = self.blobs[name]

        class Blob:
            def readall(self):
                return data

        return Blob()


def test_build_checks_the_extract_against_its_blob(tmp_path):
    local = json.dumps(extract([section(1, "Body.")])).encode()
    (tmp_path / "doc.json").write_bytes(local)

    assert len(load_chunks({"doc": doc()}, tmp_path, FakeBlobs({"library/doc.json": local}))) == 1
    with pytest.raises(SourceMismatch, match="doc"):
        load_chunks({"doc": doc()}, tmp_path, FakeBlobs({"library/doc.json": local + b" "}))


# The gate checks run against the live index; here a stub applies the filter.
FILTER_DATE = re.compile(r"published_at lt (\S+)")
FILTER_SERVES = re.compile(r"serves/any\(s: s eq '([^']+)'\)")


class FilteringSearch:
    """Applies the two filter clauses hindcast.search builds to canned documents."""

    def __init__(self, documents: list[dict]):
        self.documents = documents

    def search(self, search_text=None, **kwargs):
        query_filter = kwargs.get("filter") or ""
        out = self.documents
        if date := FILTER_DATE.search(query_filter):
            out = [d for d in out if d["published_at"] < date.group(1)]
        if serves := FILTER_SERVES.search(query_filter):
            out = [d for d in out if serves.group(1) in d["serves"]]
        return iter(
            [d | {"@search.score": 1.0, "@search.reranker_score": None} for d in out][
                : kwargs.get("top") or None
            ]
        )


def gate_library():
    from hindcast.cases import load_cases

    cases = load_cases(Path("data/cases.yaml"))
    dev = cases["cloudflare-2026-02-20"]
    scored = cases["cloudflare-2025-11-18"]
    library = {
        "pick-dev": doc(doc_id="pick-dev", published_at="2025-06-12", serves=(dev.case_id,)),
        "pick-scored": doc(
            doc_id="pick-scored", published_at="2025-06-12", serves=(scored.case_id,)
        ),
    }
    cases = {dev.case_id: dev, scored.case_id: scored}
    indexed: list[dict] = [
        asdict(c) | {"serves": list(c.serves)}
        for d in library.values()
        for c in chunks(
            extract([section(1, "Body.") | {"section_id": f"lib/{d.doc_id}/s1"}])
            | {"doc_id": d.doc_id},
            d,
        )
    ]
    return cases, library, indexed


def test_check_filter_passes_on_an_exact_set():
    cases, library, indexed = gate_library()
    refs = {str(d["ref"]) for d in indexed}

    problems = check_filter(
        cases,
        library,
        {},
        client=FilteringSearch(indexed),
        embed=lambda texts: [[0.1] for _ in texts],
        refs=refs,
    )

    assert problems == []


def test_check_filter_reports_a_shifted_start():
    cases, library, indexed = gate_library()

    problems = check_filter(
        cases,
        library,
        {},
        client=FilteringSearch(indexed),
        embed=lambda texts: [[0.1] for _ in texts],
        refs={str(d["ref"]) for d in indexed},
        shift_start="cloudflare-2025-11-18",
    )

    assert problems and "cloudflare-2025-11-18" in problems[0] and "pick-scored" in problems[0]


def test_check_filter_reports_a_leak_from_a_query():
    cases, library, indexed = gate_library()

    class Leaky(FilteringSearch):
        def search(self, search_text=None, **kwargs):
            if search_text == "*":
                return super().search(search_text, **kwargs)
            return super().search(search_text, top=kwargs.get("top"))

    problems = check_filter(
        cases,
        library,
        {},
        client=Leaky(indexed),
        embed=lambda texts: [[0.1] for _ in texts],
        refs={str(d["ref"]) for d in indexed},
    )

    assert any("may not read" in p for p in problems)


def test_check_chunks_reports_missing_extra_and_changed():
    expected = sample_chunks()
    indexed = [{"id": c.id, "ref": c.ref, "content_sha256": c.content_sha256} for c in expected[1:]]
    indexed[0]["content_sha256"] = "0" * 64
    indexed.append({"id": "lib_doc_s9_p0", "ref": "lib/doc/s9", "content_sha256": "1" * 64})

    problems = check_chunks(indexed, expected)

    assert problems == [
        "missing from the index: lib_doc_s1_p0",
        "not in the extracts: lib_doc_s9_p0",
        "content differs: lib_doc_s2_p0",
    ]
    assert (
        check_chunks(
            [{"id": c.id, "ref": c.ref, "content_sha256": c.content_sha256} for c in expected],
            expected,
        )
        == []
    )


def test_queries_are_deterministic():
    from hindcast.index import quality_inputs, quality_queries

    assert quality_queries(*quality_inputs()) == quality_queries(*quality_inputs())


def test_relevance_comes_from_the_reason_quote():
    from hindcast.index import quality_queries

    cases, _, _ = gate_library()
    library = {
        "quoted": doc(
            doc_id="quoted",
            serves=("cloudflare-2026-02-20",),
            reason='Same symptom, as in "errors for some customers" during the change.',
        ),
        "serves-only": doc(doc_id="serves-only", serves=("cloudflare-2026-02-20",)),
        "other-case": doc(
            doc_id="other-case",
            serves=("cloudflare-2025-11-18",),
            reason="errors for some customers",
        ),
    }
    symptoms = {"cloudflare-2026-02-20": ["errors for some customers", "slow dashboard"]}

    queries = quality_queries(cases, library, symptoms)

    assert queries == [
        {
            "query_id": "cloudflare-2026-02-20/q1",
            "case_id": "cloudflare-2026-02-20",
            "query": "errors for some customers",
            "relevant": ["quoted"],
        },
        {
            "query_id": "cloudflare-2026-02-20/q2",
            "case_id": "cloudflare-2026-02-20",
            "query": "slow dashboard",
            "relevant": [],
        },
    ]


def test_sealed_cases_have_no_quality_queries():
    from hindcast.cases import load_cases
    from hindcast.index import quality_queries

    cases = load_cases(Path("data/cases.yaml"))
    sealed = next(c for c in cases.values() if c.role == "sealed")
    library = {"x": doc(doc_id="x", serves=(sealed.case_id,), reason="anything at all")}

    assert quality_queries(cases, library, {sealed.case_id: ["anything"]}) == []


def test_recall_counts_distinct_documents():
    from hindcast.index import recall_at, reciprocal_rank

    ranked = ["a", "a", "b", "c", "a", "d", "e", "f"]

    assert recall_at(ranked, ["a", "f"]) == 0.5
    assert recall_at(ranked, ["b", "e"]) == 1.0
    assert recall_at(ranked, ["z"]) == 0.0
    assert reciprocal_rank(ranked, ["c"]) == 1 / 3
    assert reciprocal_rank(ranked, ["z"]) == 0.0


def test_queries_file_matches_the_registry():
    from hindcast.index import QUERIES, quality_inputs, quality_queries

    committed = json.loads(QUERIES.read_text(encoding="utf-8"))

    assert committed == quality_queries(*quality_inputs())


class FakeEmbeddings:
    def __init__(self):
        self.calls: list[dict] = []

    def create(self, *, model, input, dimensions):
        self.calls.append({"model": model, "input": list(input), "dimensions": dimensions})

        class Item:
            def __init__(self, index, text):
                self.index, self.embedding = index, [float(len(text))] * dimensions

        class Response:
            # Out of order on purpose: the service gives each item its index.
            data = [Item(i, t) for i, t in reversed(list(enumerate(input)))]

        return Response()


def test_embedder_batches_and_keeps_the_input_order():
    from types import SimpleNamespace

    from hindcast.index import EMBED_BATCH, embedder

    embeddings = FakeEmbeddings()
    embed = embedder(4, deployment="embedding", client=SimpleNamespace(embeddings=embeddings))
    texts = ["x" * n for n in range(1, 2 * EMBED_BATCH + 2)]

    vectors = embed(texts)

    assert [v[0] for v in vectors] == [float(len(t)) for t in texts]
    assert [len(c["input"]) for c in embeddings.calls] == [EMBED_BATCH, EMBED_BATCH, 1]
    assert {(c["model"], c["dimensions"]) for c in embeddings.calls} == {("embedding", 4)}


def test_embeddings_go_to_the_resource_endpoint():
    from hindcast.config import SearchSettings
    from hindcast.models import resource_openai_client

    settings = SearchSettings(
        search_endpoint="https://example.search.windows.net",
        search_index="hindcast-library-1024",
        embedding_endpoint="https://example.services.ai.azure.com/",
        embedding_deployment="embedding",
    )

    client = resource_openai_client(settings.embedding_endpoint)

    assert str(client.base_url) == "https://example.services.ai.azure.com/openai/v1/"

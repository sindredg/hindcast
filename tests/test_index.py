import json

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hindcast.index import Chunk, build, chunks, index_definition, load_chunks
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

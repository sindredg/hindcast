"""The library index in Azure AI Search: chunks, embeddings, and the push.

    python -m hindcast.index build --dimensions 1024 [--replace]

Each chunk lies inside one section or one figure of a library extract, so its
ref is a citation target: lib/<doc_id>/s<n> or lib/<doc_id>/fig<n>. A section
longer than CHUNK_CHARS is split at paragraph boundaries, and a paragraph
longer than that after a table row or, outside a table, at a line break; a
single row or line longer than that stays whole as its own part. Every chunk carries its document's
publish date and the cases the document serves, which the search filter
reads (hindcast.search).

Embeddings are computed here and pushed with the chunks, through the Foundry
project with an Entra token: no indexer, no skillset, and no key. The index
is built from the local extracts after each is checked against its blob in
Blob Storage, so the index holds what the extraction stored. The command
prints counts and the embedding model, never chunk text.
"""

import argparse
import functools
import hashlib
import json
import re
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal, Protocol

from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

from hindcast.cases import Case
from hindcast.library import LibraryDocument
from hindcast.storage import BlobContainer, SourceMismatch

CHUNK_CHARS = 4000
EMBED_BATCH = 16
EXTRACTS_DIR = Path("build/extracted/library")
SEMANTIC_CONFIG = "library"
VECTOR_FIELD = "content_vector"

Embed = Callable[[list[str]], list[list[float]]]


@dataclass(frozen=True)
class Chunk:
    id: str
    ref: str
    part: int
    kind: Literal["section", "figure"]
    doc_id: str
    provider: str
    title: str
    heading: str
    content: str
    published_at: str
    serves: tuple[str, ...]
    url: str

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def embedded_text(self) -> str:
        return f"{self.title}\n{self.heading}\n{self.content}"


def _pack(units: list[str], separator: str) -> list[str]:
    """Join units in order into parts of at most CHUNK_CHARS; a longer unit stays whole."""
    parts: list[str] = []
    current = ""
    for unit in units:
        joined = f"{current}{separator}{unit}" if current else unit
        if len(joined) <= CHUNK_CHARS:
            current = joined
            continue
        if current:
            parts.append(current)
        current = unit
    if current:
        parts.append(current)
    return parts


def _lines(paragraph: str) -> list[str]:
    """An overlong paragraph's units: table rows in a table, else lines."""
    # The extracts render tables as HTML, one tag per line, so a table is one
    # paragraph; a row is the smallest unit that keeps its cells together.
    if "<tr" in paragraph:
        return re.split(r"(?<=</tr>)\n", paragraph)
    return paragraph.split("\n")


def _parts(markdown: str) -> list[str]:
    if len(markdown) <= CHUNK_CHARS:
        return [markdown]
    parts: list[str] = []
    for paragraph_part in _pack([p for p in markdown.split("\n\n") if p.strip()], "\n\n"):
        if len(paragraph_part) <= CHUNK_CHARS:
            parts.append(paragraph_part)
        else:
            parts += _pack(_lines(paragraph_part), "\n")
    return parts


def chunks(extract: Mapping[str, Any], doc: LibraryDocument) -> list[Chunk]:
    """The extract's sections and figures as chunks, with the registry's fields."""
    if extract["doc_id"] != doc.doc_id:
        raise ValueError(f"extract {extract['doc_id']} is not for {doc.doc_id}")

    def chunk(ref: str, part: int, kind: Literal["section", "figure"], heading: str, text: str):
        return Chunk(
            id=f"{ref.replace('/', '_')}_p{part}",
            ref=ref,
            part=part,
            kind=kind,
            doc_id=doc.doc_id,
            provider=doc.provider,
            title=doc.title,
            heading=heading,
            content=text,
            # The registry gives a day; the filter compares instants.
            published_at=f"{doc.published_at}T00:00:00Z",
            serves=doc.serves,
            url=doc.url,
        )

    out = [
        chunk(s["section_id"], n, "section", s["heading"], text)
        for s in extract["sections"]
        for n, text in enumerate(_parts(s["markdown"]))
    ]
    for f in extract["figures"]:
        text = "\n\n".join(f[name] for name in ("description", "alt_text", "text_in_image"))
        out.append(chunk(f["figure_id"], 0, "figure", "", text))
    return out


def load_chunks(
    library: Mapping[str, LibraryDocument],
    extracts_dir: Path = EXTRACTS_DIR,
    blobs: BlobContainer | None = None,
) -> list[Chunk]:
    """Chunks of every library document, each extract checked against its stored blob."""
    from hindcast.storage import container

    stored = blobs or container("extracted")
    out: list[Chunk] = []
    for doc_id, doc in sorted(library.items()):
        local = (extracts_dir / f"{doc_id}.json").read_bytes()
        if stored.download_blob(f"library/{doc_id}.json").readall() != local:
            raise SourceMismatch(f"{doc_id}: the local extract differs from its blob")
        out += chunks(json.loads(local), doc)
    return out


def index_definition(name: str, dimensions: int) -> SearchIndex:
    algorithms: list[VectorSearchAlgorithmConfiguration] = [
        HnswAlgorithmConfiguration(
            name="hnsw-cosine", parameters=HnswParameters(metric=VectorSearchAlgorithmMetric.COSINE)
        )
    ]
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type="Edm.String", key=True),
            SimpleField(name="ref", type="Edm.String"),
            SimpleField(name="part", type="Edm.Int32"),
            SimpleField(name="kind", type="Edm.String", filterable=True),
            SimpleField(name="doc_id", type="Edm.String", filterable=True),
            SimpleField(name="provider", type="Edm.String"),
            SearchableField(name="title", analyzer_name="en.microsoft"),
            SearchableField(name="heading", analyzer_name="en.microsoft"),
            SearchableField(name="content", analyzer_name="en.microsoft"),
            SimpleField(name="published_at", type="Edm.DateTimeOffset", filterable=True),
            SimpleField(
                name="serves",
                type="Collection(Edm.String)",
                filterable=True,
            ),
            SimpleField(name="url", type="Edm.String"),
            SimpleField(name="content_sha256", type="Edm.String"),
            SearchField(
                name=VECTOR_FIELD,
                type="Collection(Edm.Single)",
                searchable=True,
                vector_search_dimensions=dimensions,
                vector_search_profile_name="hnsw",
                # Not returned with results, so a hit carries text only.
                stored=False,
            ),
        ],
        vector_search=VectorSearch(
            algorithms=algorithms,
            profiles=[VectorSearchProfile(name="hnsw", algorithm_configuration_name="hnsw-cosine")],
        ),
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=SEMANTIC_CONFIG,
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[
                            SemanticField(field_name="heading"),
                            SemanticField(field_name="content"),
                        ],
                    ),
                )
            ]
        ),
    )


# Positional-only, so the SDK clients satisfy these whatever they name the argument.
class IndexClient(Protocol):
    def get_index(self, name: str, /) -> Any: ...
    def delete_index(self, index: str, /) -> Any: ...
    def create_index(self, index: SearchIndex, /) -> Any: ...


class DocumentClient(Protocol):
    def get_document_count(self) -> int: ...
    def upload_documents(self, documents: list[dict], /) -> Iterable[Any]: ...


def build(
    name: str,
    dimensions: int,
    chunk_list: list[Chunk],
    *,
    replace: bool,
    index_client: IndexClient,
    search_client: DocumentClient,
    embed: Embed,
) -> int:
    """Create the index and push every chunk with its vector; the number pushed."""
    try:
        index_client.get_index(name)
        exists = True
    except ResourceNotFoundError:
        exists = False
    if exists and not replace and search_client.get_document_count():
        raise ValueError(f"{name} already holds documents; rebuild it with --replace")
    if exists:
        index_client.delete_index(name)
    index_client.create_index(index_definition(name, dimensions))
    vectors = embed([c.embedded_text for c in chunk_list])
    if len(vectors) != len(chunk_list) or any(len(v) != dimensions for v in vectors):
        raise ValueError(f"the embeddings do not give one {dimensions}-value vector per chunk")
    documents = [
        asdict(c) | {"serves": list(c.serves), "content_sha256": c.content_sha256, VECTOR_FIELD: v}
        for c, v in zip(chunk_list, vectors, strict=True)
    ]
    failed = [r.key for r in search_client.upload_documents(documents) if not r.succeeded]
    if failed:
        raise RuntimeError(f"{name}: {len(failed)} chunks were not indexed: {', '.join(failed)}")
    return len(documents)


@functools.cache
def embedding_model() -> dict:
    """The embedding deployment's model name and version, read once per process."""
    from hindcast.config import SearchSettings, load_settings
    from hindcast.models import deployment_model

    deployment = load_settings(SearchSettings).embedding_deployment
    model_name, version = deployment_model(deployment)
    return {"deployment": deployment, "name": model_name, "version": version}


def embedder(dimensions: int) -> Embed:
    """Embeds through the Foundry project, EMBED_BATCH texts per call."""
    from hindcast.config import SearchSettings, load_settings
    from hindcast.models import openai_client

    deployment = load_settings(SearchSettings).embedding_deployment
    client = openai_client()

    def embed(texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            response = client.embeddings.create(
                model=deployment, input=texts[start : start + EMBED_BATCH], dimensions=dimensions
            )
            out += [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
        return out

    return embed


HOSTILE_QUERIES = (
    "' or 1 eq 1 or '",
    '") or (published_at gt 2000-01-01',
    "$filter=published_at gt 2030-01-01",
    "*",
)


def _listed_docs(client: Any, query_filter: str) -> set[str]:
    return {d["doc_id"] for d in client.search("*", filter=query_filter, select=["doc_id"])}


def check_filter(
    cases: Mapping[str, Case],
    library: Mapping[str, LibraryDocument],
    symptoms: Mapping[str, list[str]],
    *,
    client: Any,
    embed: Embed,
    refs: Collection[str],
    shift_start: str | None = None,
) -> list[str]:
    """Problems with the live filter: a listed set that differs from the registry's, or a leak.

    shift_start moves that case's start a year earlier when the filter is
    built, and only then, so a working check reports the documents it loses.
    """
    from hindcast.search import LibraryLeak, allowed, library_filter, search_library

    problems = []
    for case_id, case in sorted(cases.items()):
        built_from = case
        if case_id == shift_start:
            built_from = replace(
                case, started_at=f"{int(case.started_at[:4]) - 1}{case.started_at[4:]}"
            )
        expected = {d for d, doc in library.items() if allowed(case, doc)}
        listed = _listed_docs(client, library_filter(built_from, library))
        if listed != expected:
            problems.append(
                f"{case_id}: listed but not allowed {sorted(listed - expected)}, "
                f"allowed but not listed {sorted(expected - listed)}"
            )
        for query in [*symptoms.get(case_id, []), *HOSTILE_QUERIES]:
            try:
                search_library(
                    case_id,
                    query,
                    cases=cases,
                    library=library,
                    refs=refs,
                    client=client,
                    embed=embed,
                )
            except LibraryLeak as leak:
                problems.append(str(leak))
    return problems


def check_chunks(indexed: list[dict], expected: list[Chunk]) -> list[str]:
    """Chunks missing from the index, extra in it, or with other content or another ref."""
    have = {d["id"]: d for d in indexed}
    want = {c.id: c for c in expected}
    problems = [f"missing from the index: {i}" for i in sorted(want.keys() - have.keys())]
    problems += [f"not in the extracts: {i}" for i in sorted(have.keys() - want.keys())]
    for i in sorted(want.keys() & have.keys()):
        if have[i]["ref"] != want[i].ref:
            problems.append(f"ref differs: {i}")
        if have[i]["content_sha256"] != want[i].content_sha256:
            problems.append(f"content differs: {i}")
    return problems


def symptom_quotes(path: Path = Path("data/library.yaml")) -> dict[str, list[str]]:
    from ruamel.yaml import YAML

    data = YAML(typ="safe", pure=True).load(path)
    return {
        case_id: [tag["quote"] for tag in tags if tag["quote"].strip()]
        for case_id, tags in (data.get("symptoms") or {}).items()
    }


def index_name(dimensions: int) -> str:
    return f"hindcast-library-{dimensions}"


def clients(name: str):
    """Index and document clients for the configured service, with an Entra token."""
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient

    from hindcast.config import SearchSettings, load_settings

    endpoint = load_settings(SearchSettings).search_endpoint
    credential = DefaultAzureCredential()
    return SearchIndexClient(endpoint, credential), SearchClient(endpoint, name, credential)


def _library() -> dict[str, LibraryDocument]:
    from hindcast.cases import load_cases
    from hindcast.library import load_library

    return load_library(Path("data/library.yaml"), load_cases(Path("data/cases.yaml")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.index")
    commands = parser.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build", help="create one index and push the library")
    build_cmd.add_argument("--dimensions", type=int, choices=(1024, 3072), required=True)
    build_cmd.add_argument("--replace", action="store_true")
    filter_cmd = commands.add_parser("check-filter", help="check the live filter for every case")
    filter_cmd.add_argument("--shift-start", metavar="CASE_ID", help="the broken-input run")
    commands.add_parser("check-chunks", help="check every chunk against the extracts")
    args = parser.parse_args(argv)

    if args.command == "build":
        name = index_name(args.dimensions)
        chunk_list = load_chunks(_library())
        index_client, search_client = clients(name)
        count = build(
            name,
            args.dimensions,
            chunk_list,
            replace=args.replace,
            index_client=index_client,
            search_client=search_client,
            embed=embedder(args.dimensions),
        )
        model = embedding_model()
        kinds = {kind: sum(c.kind == kind for c in chunk_list) for kind in ("section", "figure")}
        print(
            f"{name}: {count} chunks ({kinds['section']} section parts, {kinds['figure']} figures)"
        )
        print(f"  embedding: {model['deployment']} {model['name']} {model['version']}")
        return 0

    from hindcast.cases import load_cases
    from hindcast.config import SearchSettings, load_settings

    settings = load_settings(SearchSettings)
    _, search_client = clients(settings.search_index)
    if args.command == "check-filter":
        from hindcast.search import extract_refs

        cases = load_cases()
        problems = check_filter(
            cases,
            _library(),
            symptom_quotes(),
            client=search_client,
            embed=embedder(settings.embedding_dimensions),
            refs=extract_refs(),
            shift_start=args.shift_start,
        )
        print(f"{settings.search_index}: {len(cases)} cases, {len(problems)} problems")
    else:
        indexed = list(search_client.search("*", select=["id", "ref", "content_sha256"]))
        problems = check_chunks(indexed, load_chunks(_library()))
        print(
            f"{settings.search_index}: {len(indexed)} chunks listed, "
            f"{search_client.get_document_count()} counted, {len(problems)} problems"
        )
    for problem in problems:
        print(f"  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

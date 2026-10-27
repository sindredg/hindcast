"""Library registry: earlier postmortems the investigator can search.

The registry is data/library.yaml. Its symptoms section tags what each case's
live updates showed; its documents were picked by those tags under decision
0013. A document is served only to cases that began after it was published,
so a document dated on or after any case it serves is refused, not guessed.
Like the case sources, the pages are not in the repository.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML

from hindcast.cases import CASE_ID, UTC_TIMESTAMP, Case, _values

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class LibraryDocument:
    doc_id: str
    provider: Literal["Cloudflare", "GitHub", "AWS", "Azure", "Google Cloud"]
    title: str
    url: str
    # The publish date as the page states it. A day, not a time: pages rarely
    # give one, so a document dated on a case's start day cannot be ordered.
    published_at: str
    filename: str
    sha256: str
    retrieved_at: str
    licence: str
    attribution: str
    kind: Literal["other-provider", "same-provider", "attack-suspected", "decoy"]
    serves: tuple[str, ...]
    reason: str


def _same_url(a: str, b: str) -> bool:
    return a.rstrip("/").lower() == b.rstrip("/").lower()


def _check(doc: LibraryDocument, cases: Mapping[str, Case], quotes: dict, draft: bool) -> None:
    where = doc.doc_id
    if Path(doc.filename).name != doc.filename or doc.filename.startswith("."):
        raise ValueError(f"{where}: filename {doc.filename!r} is not a plain name")
    if not doc.serves or not set(doc.serves) <= cases.keys():
        raise ValueError(f"{where}: serves {list(doc.serves)} must name known cases")
    if not ISO_DATE.fullmatch(doc.published_at):
        raise ValueError(f"{where}: published_at {doc.published_at!r} must be like 2025-10-23")
    published = date.fromisoformat(doc.published_at)
    for case_id in doc.serves:
        if published >= date.fromisoformat(cases[case_id].started_at[:10]):
            raise ValueError(
                f"{where}: published {doc.published_at}, not before {case_id} began "
                f"({cases[case_id].started_at})"
            )
        # Every pick says which of the case's live-update symptoms it matches.
        if not any(quote in doc.reason for quote in quotes.get(case_id, ())):
            raise ValueError(f"{where}: reason quotes no tagged symptom of {case_id}")
    for case in cases.values():
        for source in case.sources:
            if _same_url(doc.url, source.url):
                raise ValueError(f"{where}: url is the case source {source.doc_id}")
    # Before capture, the pick list has no hash or time yet.
    if not (draft and doc.sha256 == "") and not SHA256.fullmatch(doc.sha256):
        raise ValueError(f"{where}: sha256 {doc.sha256!r} is not a SHA-256")
    if not (draft and doc.retrieved_at == "") and not UTC_TIMESTAMP.fullmatch(doc.retrieved_at):
        raise ValueError(f"{where}: retrieved_at {doc.retrieved_at!r} must be a UTC time")


def load_library(
    path: Path, cases: Mapping[str, Case], *, draft: bool = False
) -> dict[str, LibraryDocument]:
    """Read the registry, refusing a document a served case could not have had."""
    data = YAML(typ="safe", pure=True).load(path)
    quotes = {
        case_id: [tag["quote"] for tag in tags if tag["quote"].strip()]
        for case_id, tags in (data.get("symptoms") or {}).items()
    }
    doc_ids = {source.doc_id for case in cases.values() for source in case.sources}
    library: dict[str, LibraryDocument] = {}
    for raw in data.get("documents") or []:
        doc_id = raw.get("doc_id")
        if not isinstance(doc_id, str) or not CASE_ID.fullmatch(doc_id):
            raise ValueError(f"doc_id {doc_id!r} must be lower-case words joined by hyphens")
        if doc_id in doc_ids:
            raise ValueError(f"doc_id {doc_id!r} appears twice")
        doc_ids.add(doc_id)
        serves = raw.get("serves")
        doc = LibraryDocument(
            **_values(LibraryDocument, raw | {"serves": tuple(serves or ())}, doc_id)
        )
        _check(doc, cases, quotes, draft)
        library[doc_id] = doc
    return library


def cutoff(document: LibraryDocument, cases: Mapping[str, Case]) -> str:
    """The earliest start among the cases the document serves."""
    return min(cases[case_id].started_at for case_id in document.serves)

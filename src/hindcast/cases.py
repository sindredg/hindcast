"""Case registry: the outages Hindcast investigates and their source files.

The registry is data/cases.yaml. Each case has the provider's live status
updates (the evidence) and, unless it is an injection copy, the provider's
postmortem (the answer key). The source files themselves are not in the
repository; verify_local_files checks local copies against the pinned hashes.
"""

import hashlib
import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, get_args, get_origin

from ruamel.yaml import YAML

CASE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


@dataclass(frozen=True)
class SourceFile:
    doc_id: str
    filename: str
    url: str
    licence: str
    attribution: str
    sha256: str
    retrieved_at: str
    kind: Literal["status-updates", "postmortem"]


@dataclass(frozen=True)
class Case:
    case_id: str
    title: str
    provider: Literal["Cloudflare", "GitHub", "Google Cloud"]
    role: Literal["showcase", "development", "injection"]
    sources: tuple[SourceFile, ...]


def _values(cls: type, raw: dict, where: str) -> dict:
    """Check raw has exactly the fields of cls, and Literal fields one allowed value."""
    names = {f.name for f in fields(cls)}
    missing = sorted(names - raw.keys())
    unknown = sorted(raw.keys() - names)
    if missing or unknown:
        raise ValueError(f"{where}: missing fields {missing}, unknown fields {unknown}")
    for f in fields(cls):
        if f.type is str and not isinstance(raw[f.name], str):
            raise ValueError(f"{where}: {f.name} must be text, got {raw[f.name]!r}")
        allowed = get_args(f.type) if get_origin(f.type) is Literal else ()
        if allowed and raw[f.name] not in allowed:
            raise ValueError(f"{where}: {f.name} {raw[f.name]!r} is not one of {allowed}")
    return raw


def load_cases(path: Path = Path("data/cases.yaml")) -> dict[str, Case]:
    """Read the registry, rejecting malformed IDs, fields, and duplicate cases."""
    data = YAML(typ="safe", pure=True).load(path)
    cases: dict[str, Case] = {}
    doc_ids: set[str] = set()
    for raw in data["cases"]:
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
            raise ValueError(f"case_id {case_id!r} must be lower-case words joined by hyphens")
        if case_id in cases:
            raise ValueError(f"case_id {case_id!r} appears twice")
        if not raw.get("sources"):
            raise ValueError(f"{case_id}: sources is missing or empty")
        sources = tuple(
            SourceFile(**_values(SourceFile, source, f"{case_id} source"))
            for source in raw["sources"]
        )
        for source in sources:
            # Blob names, local paths, and citations are built from these two.
            if source.doc_id in doc_ids:
                raise ValueError(f"doc_id {source.doc_id!r} appears twice")
            doc_ids.add(source.doc_id)
            name = source.filename
            if Path(name).name != name or name.startswith("."):
                raise ValueError(f"{source.doc_id}: filename {name!r} is not a plain name")
            # Pages change after capture, so the hash is only meaningful with its time.
            if not UTC_TIMESTAMP.fullmatch(source.retrieved_at):
                raise ValueError(
                    f"{source.doc_id}: retrieved_at {source.retrieved_at!r} "
                    "must be a UTC time like 2026-10-26T08:00:00Z"
                )
        case = Case(**_values(Case, raw | {"sources": sources}, case_id))
        # Every case needs its evidence; a scored or development case also needs
        # the answer key. An injection copy is never scored.
        needed = (
            {"status-updates"} if case.role == "injection" else {"status-updates", "postmortem"}
        )
        missing = sorted(needed - {source.kind for source in sources})
        if missing:
            raise ValueError(f"{case_id}: no source of kind {', '.join(missing)}")
        cases[case_id] = case
    return cases


def verify_local_files(case: Case, root: Path) -> list[str]:
    """Return the doc_id of every source missing under root/<case_id>/ or not matching its hash."""
    failed = []
    for source in case.sources:
        path = root / case.case_id / source.filename
        if not path.is_file():
            failed.append(source.doc_id)
            continue
        with path.open("rb") as file:
            if hashlib.file_digest(file, "sha256").hexdigest() != source.sha256:
                failed.append(source.doc_id)
    return failed

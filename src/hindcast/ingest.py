"""Turn captured sources in Blob Storage into what later milestones read.

    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence \
        [--case ID ...] [--replace]
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest library \
        [--doc ID ...] [--replace]

evidence: downloads each case's status snapshot (refused unless it matches the
registry's hash), cuts it with hindcast.evidence, and writes the result to
build/evidence/<case_id>.json and Blob extracted/evidence/<case_id>.json.
Evidence already in Blob Storage is kept: if it is identical, only the local
copy is written; if it differs, the case fails unless --replace is given. It
prints counts only: the evidence text is the provider's and stays private.

library: downloads each library page (hash-checked), extracts its article,
sections, and described figures with Content Understanding, and writes the
result to build/extracted/library/<doc_id>.json and Blob
extracted/library/<doc_id>.json. Extraction costs money and its output varies
between runs, so an extract already in Blob Storage is reused, not redone,
unless --replace is given.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

from azure.core.exceptions import AzureError, ResourceExistsError, ResourceNotFoundError

from hindcast.capture import fetch
from hindcast.cases import Case, load_cases
from hindcast.evidence import CaseEvidence, cut, evidence_json
from hindcast.extract import analyze
from hindcast.library import LibraryDocument, load_library
from hindcast.library_extract import add_usage, extract_document
from hindcast.storage import container, download_source, upload_bytes

EVIDENCE_DIR = Path("build/evidence")
LIBRARY_DIR = Path("build/extracted/library")


class EvidenceDiffers(ValueError):
    """Blob Storage already holds different evidence for the case."""


def ingest_evidence(
    case: Case, *, out_dir: Path = EVIDENCE_DIR, replace: bool = False, client=None, uploader=None
) -> tuple[CaseEvidence, Literal["uploaded", "unchanged", "replaced"]]:
    status = next(s for s in case.sources if s.kind == "status-updates")
    evidence = cut(case, download_source(case.case_id, status, client=client))
    data = evidence_json(evidence)
    name = f"evidence/{case.case_id}.json"
    try:
        upload_bytes("extracted", name, data, overwrite=replace, client=uploader)
        outcome = "replaced" if replace else "uploaded"
    except ResourceExistsError:
        # Evidence from an earlier run is kept. If it is the same, a new
        # workstation still gets its local copy; if not, the rules or the
        # source changed and only --replace may overwrite it.
        existing = (uploader or container("extracted")).download_blob(name).readall()
        if existing != data:
            raise EvidenceDiffers(
                f"{case.case_id}: evidence in Blob Storage differs; pass --replace to overwrite"
            ) from None
        outcome = "unchanged"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case.case_id}.json").write_bytes(data)
    return evidence, outcome


def summary(evidence: CaseEvidence) -> list[str]:
    resolved = evidence.updates[-1].time
    lines = [
        f"{evidence.case_id}: {len(evidence.updates)} updates (resolved {resolved}), "
        f"dropped {len(evidence.dropped)}"
    ]
    for reason, count in sorted(Counter(d.reason for d in evidence.dropped).items()):
        lines.append(f"  {reason}: {count}")
    return lines


def ingest_library(
    doc: LibraryDocument,
    cases: dict[str, Case],
    *,
    out_dir: Path = LIBRARY_DIR,
    replace: bool = False,
    client=None,
    uploader=None,
    analyzer=analyze,
    fetch=fetch,
) -> tuple[bytes, Literal["reused", "uploaded", "replaced"], dict]:
    """Extract one library page, or reuse its extract; returns it, the outcome, and the usage."""
    name = f"library/{doc.doc_id}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not replace:
        try:
            data = (uploader or container("extracted")).download_blob(name).readall()
        except ResourceNotFoundError:
            pass
        else:
            (out_dir / f"{doc.doc_id}.json").write_bytes(data)
            return data, "reused", {}
    page = download_source("library", doc, client=client)
    extracted, usage = extract_document(doc, cases, page, analyzer, fetch)
    data = extracted.to_json()
    upload_bytes("extracted", name, data, overwrite=replace, client=uploader)
    (out_dir / f"{doc.doc_id}.json").write_bytes(data)
    return data, "replaced" if replace else "uploaded", usage


def library_summary(data: bytes) -> str:
    extract = json.loads(data)
    return (
        f"{extract['doc_id']}: {len(extract['sections'])} sections, "
        f"{len(extract['figures'])} figures, dropped {len(extract['dropped'])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.ingest")
    commands = parser.add_subparsers(dest="command", required=True)
    evidence = commands.add_parser("evidence", help="cut each case's status updates")
    evidence.add_argument("--case", action="append", help="one case ID; repeat for more")
    evidence.add_argument("--replace", action="store_true", help="overwrite evidence in Blob")
    library = commands.add_parser("library", help="extract the library pages")
    library.add_argument("--doc", action="append", help="one library doc ID; repeat for more")
    library.add_argument("--replace", action="store_true", help="extract again, overwriting Blob")
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.command == "library":
        return _library(args, parser, cases)
    unknown = sorted(set(args.case or ()) - cases.keys())
    if unknown:
        parser.error(f"unknown case IDs: {', '.join(unknown)}")
    failed = False
    for case_id in args.case or sorted(cases):
        # One case failing (a changed source, a cut that refuses, a missing
        # blob) is reported and the others still run; the exit code says so.
        try:
            evidence, outcome = ingest_evidence(cases[case_id], replace=args.replace)
        except ResourceNotFoundError:
            failed = True
            print(f"{case_id}: source not found in Blob Storage")
            continue
        except ValueError as error:
            failed = True
            print(error if str(error).startswith(case_id) else f"{case_id}: {error}")
            continue
        print("\n".join([*summary(evidence), f"  blob: {outcome}"]))
    return 1 if failed else 0


def _library(args, parser, cases: dict[str, Case]) -> int:
    documents = load_library(Path("data/library.yaml"), cases)
    unknown = sorted(set(args.doc or ()) - documents.keys())
    if unknown:
        parser.error(f"unknown doc IDs: {', '.join(unknown)}")
    failed, total = False, {}
    for doc_id in args.doc or documents:
        # A page whose article cannot be found, a changed source, or a refused
        # call fails that document only; the exit code says so.
        try:
            data, outcome, usage = ingest_library(documents[doc_id], cases, replace=args.replace)
        except (ValueError, OSError, AzureError) as error:
            failed = True
            message = str(error).splitlines()[0]
            print(message if message.startswith(doc_id) else f"{doc_id}: {message}")
            continue
        add_usage(total, usage)
        print(f"{library_summary(data)}\n  blob: {outcome}")
    if total:
        print(f"usage: {json.dumps(total, sort_keys=True)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

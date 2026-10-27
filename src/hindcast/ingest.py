"""Turn captured sources in Blob Storage into what later milestones read.

    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence \
        [--case ID ...] [--replace]

evidence: downloads each case's status snapshot (refused unless it matches the
registry's hash), cuts it with hindcast.evidence, and writes the result to
build/evidence/<case_id>.json and Blob extracted/evidence/<case_id>.json. It
prints counts only: the evidence text is the provider's and stays private.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from azure.core.exceptions import ResourceExistsError

from hindcast.cases import Case, load_cases
from hindcast.evidence import CaseEvidence, cut, evidence_json
from hindcast.storage import SourceMismatch, download_source, upload_bytes

EVIDENCE_DIR = Path("build/evidence")


def ingest_evidence(
    case: Case, *, out_dir: Path = EVIDENCE_DIR, replace: bool = False, client=None, uploader=None
) -> CaseEvidence:
    status = next(s for s in case.sources if s.kind == "status-updates")
    evidence = cut(case, download_source(case.case_id, status, client=client))
    data = evidence_json(evidence)
    # Blob first: if the evidence is already there and replace is not set, the
    # upload refuses and the local copy stays as it was.
    upload_bytes(
        "extracted", f"evidence/{case.case_id}.json", data, overwrite=replace, client=uploader
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case.case_id}.json").write_bytes(data)
    return evidence


def summary(evidence: CaseEvidence) -> list[str]:
    resolved = evidence.updates[-1].time
    lines = [
        f"{evidence.case_id}: {len(evidence.updates)} updates (resolved {resolved}), "
        f"dropped {len(evidence.dropped)}"
    ]
    for reason, count in sorted(Counter(d.reason for d in evidence.dropped).items()):
        lines.append(f"  {reason}: {count}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.ingest")
    commands = parser.add_subparsers(dest="command", required=True)
    evidence = commands.add_parser("evidence", help="cut each case's status updates")
    evidence.add_argument("--case", action="append", help="one case ID; repeat for more")
    evidence.add_argument("--replace", action="store_true", help="overwrite evidence in Blob")
    args = parser.parse_args(argv)

    cases = load_cases()
    unknown = sorted(set(args.case or ()) - cases.keys())
    if unknown:
        parser.error(f"unknown case IDs: {', '.join(unknown)}")
    failed = False
    for case_id in args.case or sorted(cases):
        try:
            print("\n".join(summary(ingest_evidence(cases[case_id], replace=args.replace))))
        except ResourceExistsError:
            failed = True
            print(f"{case_id}: evidence already in Blob Storage; pass --replace to overwrite")
        except SourceMismatch as error:
            failed = True
            print(f"{case_id}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

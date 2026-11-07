"""Reveal a sealed case once its provider has published a cause.

    PYTHONPATH=src uv run --frozen python -m hindcast.reveal <case_id> [--published-at TIME]

Runs decision 0022's order in code and stops at the first step that fails,
before any sealed file is read:

1. The case's role is `revealed`, so its postmortem is in the registry (decision 0030).
2. Its key and its labels are frozen and match their hashes.
3. Its evidence is the file every seal of the case names (evidence_sha256).
4. The cause was published after every seal of the case. For a status
   snapshot the time is read from the captured file: the resolved update's
   updated_at, which Statuspage moves when the summary is written (issue #35).
   Any other postmortem needs --published-at, the time the page states.
5. The leak check finds nothing in the evidence or in the library snapshot,
   whose hash is checked against its record.

It also refuses while src/, the registry, eval/keys/, or eval/sealed/ has
uncommitted changes, and records the commit it ran from.

Then each sealed file is read from build/sealed/, checked against its seal,
copied to eval/investigations/<case_id>/, and its seal entry marked revealed.
The reveal is recorded in eval/sealed/reveals.json, and each revealed run is
added to the sealed scoring ledger for the judge. Prints counts and hashes only.
"""

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hindcast.cases import Case, SourceFile, load_cases
from hindcast.evaluation.batch import SEALED_ROOT, load_attempts, write_attempts

REVEALS = Path("eval/sealed/reveals.json")
REVEALED_DIR = Path("eval/investigations")
EVIDENCE_DIR = Path("build/evidence")
SOURCES_DIR = Path("data/sources")


class RevealRefused(PermissionError):
    """A reveal that would break decision 0022's order."""


# What a reveal reads to decide: the code, the registry, the keys and labels,
# and the seal and snapshot records.
CLEAN_PATHS = ("src", "data/cases.yaml", "eval/keys", "eval/sealed")


def _clean_commit() -> str:
    from hindcast.evaluation.prior import clean_head_commit

    return clean_head_commit([Path(p) for p in CLEAN_PATHS])


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def published_at(source: SourceFile, data: bytes, given: str | None) -> tuple[str, str]:
    """When the provider published its cause, and where that time comes from."""
    if source.filename.endswith(".json"):
        incident = json.loads(data)
        resolved = sorted(
            (u for u in incident["incident_updates"] if u["status"] == "resolved"),
            key=lambda u: u["created_at"],
        )
        if not resolved:
            raise RevealRefused(f"{source.filename}: no resolved update")
        found = _stamp(_utc(resolved[0]["updated_at"]))
        # A given time that disagrees with the file is a mistake, not an override.
        if given is not None and _stamp(_utc(given)) != found:
            raise RevealRefused(f"--published-at {given} differs from the file's {found}")
        return found, "resolved update updated_at in the captured snapshot"
    if given is None:
        raise RevealRefused(f"{source.filename}: give --published-at, the time the page states")
    return _stamp(_utc(given)), "stated on the postmortem page"


def _frozen(path: Path, record: Path, case_id: str) -> str:
    if not path.is_file():
        raise RevealRefused(f"{path}: not frozen")
    digest = _sha256(path.read_bytes())
    if json.loads(record.read_text("utf-8")).get(case_id) != digest:
        raise RevealRefused(f"{path}: differs from its frozen hash")
    return digest


def check_ready(
    case: Case,
    seals: list[dict],
    *,
    given: str | None = None,
    keys: tuple[Path, Path] | None = None,
    labels: tuple[Path, Path] | None = None,
    evidence_dir: Path = EVIDENCE_DIR,
    sources_dir: Path = SOURCES_DIR,
    snapshot: tuple[Path, Path] | None = None,
) -> dict[str, Any]:
    """Steps 1 to 5; the reveal record's fields, or RevealRefused at the first failure."""
    from hindcast import keys as keys_module
    from hindcast import labels as labels_module
    from hindcast import leak
    from hindcast import seal as seal_module

    if case.role != "revealed":
        raise RevealRefused(f"{case.case_id} is a {case.role} case, not revealed")
    own = [s for s in seals if s["case_id"] == case.case_id and s.get("file")]
    if not own:
        raise RevealRefused(f"{case.case_id}: no sealed file to reveal")
    key_path, key_record = keys or (
        keys_module.KEYS_DIR / f"{case.case_id}.json",
        keys_module.FROZEN,
    )
    label_path, label_record = labels or (
        labels_module.LABELS_DIR / f"{case.case_id}.json",
        labels_module.FROZEN,
    )
    key_sha = _frozen(key_path, key_record, case.case_id)
    labels_sha = _frozen(label_path, label_record, case.case_id)
    evidence_path = evidence_dir / f"{case.case_id}.json"
    evidence_sha = _sha256(evidence_path.read_bytes())
    if any(s["evidence_sha256"] != evidence_sha for s in own):
        raise RevealRefused(f"{evidence_path}: not the evidence the seals were run on")
    source = next(s for s in case.sources if s.kind == "postmortem")
    data = (sources_dir / case.case_id / source.filename).read_bytes()
    if _sha256(data) != source.sha256:
        raise RevealRefused(f"{source.filename}: differs from its registry hash")
    published, basis = published_at(source, data, given)
    late = [s["sealed_at"] for s in own if _utc(published) <= _utc(s["sealed_at"])]
    if late:
        raise RevealRefused(f"cause published {published}, not after the seal at {late[0]}")
    snapshot_path, snapshot_record = snapshot or (
        seal_module.SNAPSHOT_DIR / f"{case.case_id}.json",
        seal_module.SNAPSHOTS,
    )
    try:
        chunks = leak.snapshot_sources(snapshot_path, case.case_id, snapshot_record)
    except ValueError as error:
        raise RevealRefused(str(error)) from error
    evidence = leak.evidence_sources(evidence_path)
    key = keys_module.load_key(key_path)
    found = leak.hits(key, evidence | chunks)
    if found:
        raise RevealRefused(f"the leak check found {len(found)} hits; first {found[0].item}")
    return {
        "case_id": case.case_id,
        "postmortem": source.doc_id,
        "postmortem_sha256": source.sha256,
        "cause_published_at": published,
        "published_basis": basis,
        "key_sha256": key_sha,
        "labels_sha256": labels_sha,
        "evidence_sha256": evidence_sha,
        "leak": {
            "evidence_sources": len(evidence),
            "library_chunks": len(chunks),
            "snapshot_sha256": _sha256(snapshot_path.read_bytes()),
            "hits": 0,
        },
    }


def ledger_entry(seal: Mapping[str, Any], document: Mapping[str, Any]) -> dict[str, Any]:
    """A revealed seal as an attempt in the sealed scoring ledger."""
    deployment = seal["deployment"]
    return {
        "run_id": f"sealed/{seal['case_id']}/{deployment}/a{seal['attempt']}",
        # One arm per deployment: the seals ran the investigator on each model
        # with the library search (decision 0017, rule 6).
        "arm": f"sealed-{deployment}",
        "case_id": seal["case_id"],
        "repeat": 1,
        "attempt": seal["attempt"],
        "started_at": seal["sealed_at"],
        "status": seal["status"],
        "reason": document.get("incomplete_reason"),
        "file": f"{seal['case_id']}/{seal['file']}",
        "sha256": seal["sha256"],
        "usage": document["usage"],
        "cost": document.get("cost"),
        "agent": {"name": seal["agent_name"], "version": seal["agent_version"]},
        "model": {
            "deployment": deployment,
            "name": seal["model_name"],
            "version": seal["model_version"],
        },
        "code_commit": seal["code_commit"],
    }


def reveal(
    case: Case,
    *,
    given: str | None = None,
    seals_path: Path | None = None,
    sealed_dir: Path | None = None,
    revealed_dir: Path = REVEALED_DIR,
    reveals_path: Path = REVEALS,
    ledger_path: Path = SEALED_ROOT / "attempts.json",
    now: datetime | None = None,
    clean: Callable[[], str] | None = None,
    **paths: Any,
) -> dict[str, Any]:
    from hindcast import seal as seal_module

    seals_path = seals_path or seal_module.SEALS
    sealed_dir = sealed_dir or seal_module.OUT_DIR
    # The key, the labels, the registry, and the code are committed before the
    # reveal, so the history shows they were fixed before a seal was opened.
    try:
        code_commit = (clean or _clean_commit)()
    except RuntimeError as error:
        raise RevealRefused(str(error)) from error
    seals = seal_module.load_seals(seals_path)
    record = check_ready(case, seals, given=given, **paths)
    reveals = (
        json.loads(reveals_path.read_text("utf-8"))["reveals"] if reveals_path.is_file() else []
    )
    if any(r["case_id"] == case.case_id for r in reveals):
        raise RevealRefused(f"{case.case_id} is revealed already")
    ledger = load_attempts(ledger_path)
    # Every file is read, checked, and parsed, and every target checked absent,
    # before anything is written, so a refusal leaves no half-revealed case.
    ready = []
    entries = []
    for seal in seals:
        if seal["case_id"] != case.case_id or not seal.get("file") or seal.get("dropped"):
            continue
        data = (sealed_dir / case.case_id / seal["file"]).read_bytes()
        if _sha256(data) != seal["sha256"]:
            raise RevealRefused(f"{case.case_id}/{seal['file']}: does not match its seal")
        target = revealed_dir / case.case_id / seal["file"]
        if target.exists():
            raise RevealRefused(f"{target} exists; a revealed file is never replaced")
        if seal["status"] in ("complete", "incomplete"):
            try:
                entries.append(ledger_entry(seal, json.loads(data)))
            except (ValueError, KeyError) as error:
                raise RevealRefused(f"{seal['file']}: not a result file ({error!r})") from error
        ready.append((seal, data, target))
    files = []
    for seal, data, target in ready:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as out:
            out.write(data)
        seal["revealed"] = True
        files.append(seal["file"])
    ledger += entries
    record |= {
        "revealed_at": _stamp(now or datetime.now(UTC)),
        "code_commit": code_commit,
        "files": files,
    }
    seal_module.write_seals(seals_path, seals)
    reveals_path.parent.mkdir(parents=True, exist_ok=True)
    reveals_path.write_text(json.dumps({"reveals": [*reveals, record]}, indent=2) + "\n", "utf-8")
    write_attempts(ledger_path, ledger)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.reveal")
    parser.add_argument("case_id")
    parser.add_argument("--published-at", help="for a postmortem page: when it was published")
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.case_id not in cases:
        parser.error(f"unknown case {args.case_id!r}")
    try:
        record = reveal(cases[args.case_id], given=args.published_at)
    except (RevealRefused, OSError, ValueError, KeyError) as error:
        print(f"refused: {error}")
        return 1
    print(f"{args.case_id}: cause published {record['cause_published_at']}")
    print(
        f"leak check: {record['leak']['evidence_sources']} evidence sources, "
        f"{record['leak']['library_chunks']} library chunks, 0 hits"
    )
    print(f"revealed {len(record['files'])} files: {', '.join(record['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

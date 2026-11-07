"""A revealed reconstruction is the file that was sealed, byte for byte."""

import hashlib
import json
from pathlib import Path

SEALS = Path("eval/sealed/seals.json")
REVEALED_DIR = Path("eval/investigations")


def reveal_problems(seals: list[dict], root: Path) -> list[str]:
    """One line per revealed seal whose file is missing or differs from its hash."""
    problems = []
    for entry in seals:
        if not entry.get("revealed"):
            continue
        path = root / entry["case_id"] / entry["file"]
        if not path.is_file():
            problems.append(f"{entry['case_id']}/{entry['file']}: missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            problems.append(f"{entry['case_id']}/{entry['file']}: does not match its seal")
    return problems


def test_revealed_files_match_their_seals() -> None:
    seals = json.loads(SEALS.read_text("utf-8"))["seals"]

    assert reveal_problems(seals, REVEALED_DIR) == []


def test_reveal_check_fails_on_a_changed_file(tmp_path: Path) -> None:
    data = b'{"status": "complete"}\n'
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "r.json").write_bytes(data)
    entry = {
        "case_id": "c",
        "file": "r.json",
        "sha256": hashlib.sha256(data).hexdigest(),
        "revealed": True,
    }
    assert reveal_problems([entry], tmp_path) == []
    # An entry not yet revealed is not checked.
    assert reveal_problems([entry | {"revealed": False, "file": "gone.json"}], tmp_path) == []

    (tmp_path / "c" / "r.json").write_bytes(data.replace(b"complete", b"completE"))
    assert reveal_problems([entry], tmp_path) == ["c/r.json: does not match its seal"]
    assert reveal_problems([entry | {"file": "gone.json"}], tmp_path) == ["c/gone.json: missing"]


REVEALS = Path("eval/sealed/reveals.json")


def record_problems(seals: list[dict], reveals: list[dict], sources: Path) -> list[str]:
    """One line per revealed seal without a reveal record published after it (issue #35)."""
    from datetime import datetime

    from hindcast.cases import load_cases
    from hindcast.reveal import published_at

    def utc(text: str) -> datetime:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))

    by_case = {r["case_id"]: r for r in reveals}
    problems = []
    for entry in seals:
        if not entry.get("revealed"):
            continue
        record = by_case.get(entry["case_id"])
        if record is None:
            problems.append(f"{entry['case_id']}: revealed without a reveal record")
        elif utc(record["cause_published_at"]) <= utc(entry["sealed_at"]):
            problems.append(f"{entry['case_id']}/{entry['file']}: cause published before the seal")
    cases = load_cases()
    for record in reveals:
        case = cases[record["case_id"]]
        if case.role != "revealed":
            problems.append(f"{record['case_id']}: recorded as revealed, role {case.role}")
            continue
        source = next(s for s in case.sources if s.kind == "postmortem")
        path = sources / case.case_id / source.filename
        # The captured file is not in the repository; where it is local, the
        # recorded time is read from it again.
        if (
            path.is_file()
            and path.suffix == ".json"
            and published_at(source, path.read_bytes(), None)[0] != record["cause_published_at"]
        ):
            problems.append(f"{record['case_id']}: publication time differs from the file")
    return problems


def test_each_reveal_is_recorded_after_its_seals() -> None:
    seals = json.loads(SEALS.read_text("utf-8"))["seals"]
    reveals = json.loads(REVEALS.read_text("utf-8"))["reveals"] if REVEALS.is_file() else []

    assert record_problems(seals, reveals, Path("data/sources")) == []


def test_the_record_check_fails_on_an_early_or_missing_record(tmp_path: Path) -> None:
    seals = json.loads(SEALS.read_text("utf-8"))["seals"]
    reveals = json.loads(REVEALS.read_text("utf-8"))["reveals"]
    revealed = [s for s in seals if s.get("revealed")]
    assert revealed, "no revealed seal to test against"

    early = [r | {"cause_published_at": "2026-11-04T00:00:00Z"} for r in reveals]
    assert any("before the seal" in p for p in record_problems(seals, early, tmp_path))
    assert any("without a reveal record" in p for p in record_problems(seals, [], tmp_path))

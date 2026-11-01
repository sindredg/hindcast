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

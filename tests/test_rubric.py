import hashlib
import json
from pathlib import Path

import pytest

from hindcast.cases import load_cases
from hindcast.evaluation.prior import _git as git
from hindcast.keys import KEYS_DIR, load_key
from hindcast.labels import FROZEN as LABELS_FROZEN
from hindcast.labels import LABELS_DIR, load_labels

LOCK = Path("eval/rubric/frozen.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    done = git(Path("."), *args)
    assert done.returncode == 0, done.stderr
    return done.stdout


def locked_record(path: Path) -> bytes:
    """The record as it was when the rubric lock was last written."""
    if _git("rev-parse", "--is-shallow-repository").strip() == "true":
        pytest.fail("the clone is shallow: the lock check needs the full history")
    commit = _git("log", "-1", "--format=%H", "--", LOCK.as_posix()).strip()
    return _git("show", f"{commit}:{path.as_posix()}").encode("utf-8")


def lock_problems(
    locked: bytes, current: dict, locked_sha256: str, revealed: set[str]
) -> list[str]:
    """How the current record departs from the locked one.

    A reveal adds its case's key and labels after the lock (decision 0030), so
    the record may grow by revealed cases; every locked entry stays unchanged.
    """
    if hashlib.sha256(locked).hexdigest() != locked_sha256:
        return ["the locked version does not match the lock's hash"]
    before = json.loads(locked)
    problems = [f"{c}: changed or removed" for c in before if current.get(c) != before[c]]
    problems += [f"{c}: added, not revealed" for c in current.keys() - before.keys() - revealed]
    return problems


def test_rubric_frozen_matches() -> None:
    # The lock that opens the scored cases names the rubric, the labels, and
    # the keys by hash; a change to the rubric or to a locked entry fails here.
    lock = json.loads(LOCK.read_text("utf-8"))
    assert lock["rubric_sha256"] == sha256(Path(lock["rubric"]))
    revealed = {c for c, case in load_cases().items() if case.role == "revealed"}
    for path, field in (
        (LABELS_FROZEN, "labels_frozen_sha256"),
        (KEYS_DIR / "frozen.json", "keys_frozen_sha256"),
    ):
        current = json.loads(path.read_text("utf-8"))
        assert lock_problems(locked_record(path), current, lock[field], revealed) == [], path
    assert lock["tolerance_minutes"] == 30


def test_the_lock_check_fails_on_a_changed_or_unrevealed_entry() -> None:
    locked = locked_record(LABELS_FROZEN)
    digest = hashlib.sha256(locked).hexdigest()
    before = json.loads(locked)
    case = sorted(before)[0]

    assert lock_problems(locked, before, digest, set()) == []
    assert lock_problems(locked, before | {case: "0" * 64}, digest, set()) == [
        f"{case}: changed or removed"
    ]
    assert lock_problems(locked, before | {"new-case": "0" * 64}, digest, set()) == [
        "new-case: added, not revealed"
    ]
    assert lock_problems(locked, before | {"new-case": "0" * 64}, digest, {"new-case"}) == []
    assert lock_problems(locked, before, "0" * 64, set()) == [
        "the locked version does not match the lock's hash"
    ]


def test_every_scored_case_has_frozen_labels() -> None:
    scored = sorted(c for c, case in load_cases().items() if case.role in ("showcase", "revealed"))
    frozen = json.loads(LABELS_FROZEN.read_text("utf-8"))
    assert sorted(frozen) == scored


@pytest.mark.parametrize(
    "case_id",
    sorted(c for c, case in load_cases().items() if case.role in ("showcase", "revealed")),
)
def test_frozen_labels_fit_their_key_and_evidence(case_id: str) -> None:
    # The evidence file is not in the repository: CI skips this.
    from hindcast.tools import load_evidence

    evidence = Path("build/evidence") / f"{case_id}.json"
    if not evidence.is_file():
        pytest.skip("no local evidence under build/evidence/")
    key = load_key(KEYS_DIR / f"{case_id}.json")
    labels = load_labels(LABELS_DIR / f"{case_id}.json", key, load_evidence(evidence))
    assert len(labels) == 2 + len(key.contributing_factors) + len(key.timeline)

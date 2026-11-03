import hashlib
import json
from pathlib import Path

import pytest

from hindcast.cases import load_cases
from hindcast.keys import KEYS_DIR, load_key
from hindcast.labels import FROZEN as LABELS_FROZEN
from hindcast.labels import LABELS_DIR, load_labels

LOCK = Path("eval/rubric/frozen.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rubric_frozen_matches() -> None:
    # The lock that opens the scored cases names the rubric, the labels, and
    # the keys by hash; any change to one of them fails here.
    lock = json.loads(LOCK.read_text("utf-8"))
    assert lock["rubric_sha256"] == sha256(Path(lock["rubric"]))
    assert lock["labels_frozen_sha256"] == sha256(LABELS_FROZEN)
    assert lock["keys_frozen_sha256"] == sha256(KEYS_DIR / "frozen.json")
    assert lock["tolerance_minutes"] == 30


def test_every_showcase_case_has_frozen_labels() -> None:
    showcase = sorted(c for c, case in load_cases().items() if case.role == "showcase")
    frozen = json.loads(LABELS_FROZEN.read_text("utf-8"))
    assert sorted(frozen) == showcase


@pytest.mark.parametrize(
    "case_id", sorted(c for c, case in load_cases().items() if case.role == "showcase")
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

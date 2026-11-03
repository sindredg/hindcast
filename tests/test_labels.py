import copy
import hashlib
import json
from pathlib import Path

import pytest

from hindcast.evidence import CaseEvidence, ChartEvidence, EvidenceUpdate
from hindcast.keys import AnswerKey, KeyItem, TimelineEvent
from hindcast.labels import (
    FROZEN,
    LABELS_DIR,
    Label,
    LabelError,
    freeze,
    item_ids,
    load_labels,
    parse_labels,
    review_sheet,
)

KEY = AnswerKey(
    case_id="ex",
    attack="not an attack",
    attack_basis="stated",
    attack_quote="This was not an attack.",
    root_cause=KeyItem("A bad config push.", "a configuration change", False),
    contributing_factors=(
        KeyItem("Retries amplified load.", "retries amplified", False),
        KeyItem("The rollout was global.", "rolled out globally", True),
    ),
    timeline=(
        TimelineEvent("2026-01-01T10:00:00Z", "10:00 UTC", "Errors began.", "errors began", True),
    ),
    fixes=(KeyItem("Staged rollouts.", "staged", False),),
)
EVIDENCE = CaseEvidence(
    case_id="ex",
    provider="GitHub",
    title="Errors",
    started_at="2026-01-01T10:00:00Z",
    updates=(
        EvidenceUpdate("ex/u1", "2026-01-01T10:05:00Z", "investigating", "We see errors."),
        EvidenceUpdate("ex/u2", "2026-01-01T10:30:00Z", "identified", "A global change."),
        EvidenceUpdate("ex/u3", "2026-01-01T11:00:00Z", "resolved", None),
    ),
    dropped=(),
    charts=(ChartEvidence("ex/chart1", "c.png", "Errors spike.", "Error chart", False),),
)
VALID = {
    "case_id": "ex",
    "items": [
        {
            "item": "attack",
            "label": "stated",
            "reason": "u2 names a change.",
            "evidence": ["ex/u2"],
        },
        {
            "item": "root_cause",
            "label": "inferable",
            "reason": "u2 says a global change; errors follow it.",
            "evidence": ["ex/u1", "ex/u2"],
        },
        {
            "item": "contributing_factors/0",
            "label": "not inferable",
            "reason": "No update mentions retries.",
            "evidence": [],
        },
        {
            "item": "contributing_factors/1",
            "label": "stated",
            "reason": "u2 says global.",
            "evidence": ["ex/u2"],
        },
        {
            "item": "timeline/0",
            "label": "stated",
            "reason": "u1 and the chart.",
            "evidence": ["ex/u1", "ex/chart1"],
        },
    ],
}


def broken(change) -> dict:  # noqa: ANN001
    document = copy.deepcopy(VALID)
    change(document)
    return document


def test_item_ids_cover_the_scored_parts_of_the_key() -> None:
    # Fixes are not scored (decision 0006), so they get no label.
    assert item_ids(KEY) == [
        "attack",
        "root_cause",
        "contributing_factors/0",
        "contributing_factors/1",
        "timeline/0",
    ]


def test_valid_labels_load() -> None:
    labels = parse_labels(VALID, KEY, EVIDENCE)
    assert labels["root_cause"] == Label(
        "root_cause",
        "inferable",
        "u2 says a global change; errors follow it.",
        ("ex/u1", "ex/u2"),
    )
    assert list(labels) == item_ids(KEY)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["items"].pop(2), "missing: contributing_factors/0"),
        (
            lambda d: d["items"].append(dict(d["items"][0], item="fixes/0")),
            "unknown: fixes/0",
        ),
        (lambda d: d["items"].append(copy.deepcopy(d["items"][0])), "twice: attack"),
        (lambda d: d["items"][1].update(label="likely"), "root_cause: label"),
        (lambda d: d["items"][1].update(reason="  "), "root_cause: needs a reason"),
        (lambda d: d["items"][1].update(evidence=["ex/u9"]), "root_cause: unknown evidence ex/u9"),
        (lambda d: d["items"][1].update(evidence=[]), "root_cause: inferable needs evidence"),
        # The key says factor 0 was not stated during the incident.
        (
            lambda d: d["items"][2].update(label="stated", evidence=["ex/u2"]),
            "contributing_factors/0: stated, but the key marks it not stated",
        ),
        # The key says factor 1 was stated during the incident.
        (
            lambda d: d["items"][3].update(label="inferable"),
            "contributing_factors/1: the key marks it stated",
        ),
        (lambda d: d.update(case_id="other"), "case other"),
        (lambda d: d["items"][0].update(extra=1), "attack: fields"),
        (lambda d: d.update(note="x"), "fields"),
    ],
)
def test_broken_labels_are_refused(change, message: str) -> None:  # noqa: ANN001
    with pytest.raises(LabelError, match=message):
        parse_labels(broken(change), KEY, EVIDENCE)


def test_review_sheet_shows_quote_label_reason_and_cited_text() -> None:
    sheet = review_sheet(parse_labels(VALID, KEY, EVIDENCE), KEY, EVIDENCE)
    assert "### root_cause: inferable" in sheet
    assert "a configuration change" in sheet
    assert "u2 says a global change; errors follow it." in sheet
    assert "A global change." in sheet
    # A chart is cited by its description.
    assert "Errors spike." in sheet
    assert "stated during the incident (key): no" in sheet


def test_freeze_records_the_hash_and_refuses_a_second_freeze(tmp_path: Path) -> None:
    drafts, labels_dir = tmp_path / "drafts", tmp_path / "labels"
    drafts.mkdir()
    (drafts / "ex-draft.json").write_text(json.dumps(VALID), "utf-8")
    sha256 = freeze("ex", KEY, EVIDENCE, drafts, labels_dir)
    frozen = json.loads((labels_dir / "frozen.json").read_text("utf-8"))
    assert frozen == {"ex": sha256}
    assert hashlib.sha256((labels_dir / "ex.json").read_bytes()).hexdigest() == sha256
    with pytest.raises(LabelError, match="frozen already"):
        freeze("ex", KEY, EVIDENCE, drafts, labels_dir)


def test_freeze_refuses_a_broken_draft(tmp_path: Path) -> None:
    drafts, labels_dir = tmp_path / "drafts", tmp_path / "labels"
    drafts.mkdir()
    document = broken(lambda d: d["items"].pop(0))
    (drafts / "ex-draft.json").write_text(json.dumps(document), "utf-8")
    with pytest.raises(LabelError, match="missing: attack"):
        freeze("ex", KEY, EVIDENCE, drafts, labels_dir)
    assert not (labels_dir / "ex.json").exists()


def test_load_labels_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "ex.json"
    path.write_text(json.dumps(VALID), "utf-8")
    assert load_labels(path, KEY, EVIDENCE) == parse_labels(VALID, KEY, EVIDENCE)


def test_frozen_labels_unchanged() -> None:
    # Every frozen label file matches its hash, and every label file is frozen.
    frozen = json.loads(FROZEN.read_text("utf-8")) if FROZEN.is_file() else {}
    files = sorted(p.stem for p in LABELS_DIR.glob("*.json") if p != FROZEN)
    assert files == sorted(frozen)
    for case_id, sha256 in frozen.items():
        data = (LABELS_DIR / f"{case_id}.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha256, case_id

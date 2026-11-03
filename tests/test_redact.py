import json
from pathlib import Path

import pytest

from hindcast.redact import PiiFinding, mask, redact_investigation, text_fields
from hindcast.result import parse_investigation
from hindcast.safety import PiiError, PiiHit

DOCUMENT = {
    "attack": {"verdict": "not an attack", "reasoning": "Reasoning.", "citations": []},
    "findings": [
        {"id": "f1", "kind": "observation", "claim": "Claim one.", "rests_on": [], "citations": []},
        {
            "id": "f2",
            "kind": "inference",
            "claim": "Claim two.",
            "rests_on": ["f1"],
            "citations": [],
        },
    ],
    "timeline": [
        {"time": "2026-02-20T18:45:17Z", "time_kind": "stated", "event": "Event.", "citations": []}
    ],
    "root_cause": {"claim": "Root.", "rests_on": ["f1"], "citations": []},
    "contributing_factors": [{"claim": "Factor.", "rests_on": ["f2"], "citations": []}],
    "open_questions": [{"question": "Question?", "why_open": "Why open."}],
}
INVESTIGATION = parse_investigation(json.dumps(DOCUMENT))


class StubPii:
    """Returns a Person hit wherever "Jane Doe" appears; records the texts it was sent."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[str] = []
        self.calls = self.records = 0

    def __call__(self, texts: list[str], *, timeout: float) -> list[tuple[PiiHit, ...]]:
        if self.error:
            raise self.error
        self.sent += texts
        return [
            (PiiHit("Person", t.index("Jane Doe"), 8, 0.97),) if "Jane Doe" in t else ()
            for t in texts
        ]


def test_mask_replaces_spans_right_to_left() -> None:
    text = "Jane Doe paged John Roe."
    hits = (PiiHit("Person", 0, 8, 0.9), PiiHit("Person", 15, 8, 0.9))
    assert mask(text, hits) == "[Person] paged [Person]."


def test_mask_offsets_count_code_points() -> None:
    text = "“Paged” 🚨 Jane Doe at 09:14."
    hit = PiiHit("Person", text.index("Jane"), 8, 0.9)
    assert mask(text, (hit,)) == "“Paged” 🚨 [Person] at 09:14."


def test_every_text_field_is_sent() -> None:
    pii = StubPii()
    redact_investigation(INVESTIGATION, pii, timeout=5)
    # reasoning, two claims, one event, root cause, one factor, question and why_open
    assert len(pii.sent) == 8
    assert [path for path, _ in text_fields(INVESTIGATION)] == [
        "attack.reasoning",
        "findings[0].claim",
        "findings[1].claim",
        "timeline[0].event",
        "root_cause.claim",
        "contributing_factors[0].claim",
        "open_questions[0].question",
        "open_questions[0].why_open",
    ]


def test_redact_records_path_and_category_not_text() -> None:
    document = json.loads(json.dumps(DOCUMENT))
    document["findings"][1]["claim"] = "Jane Doe restarted the resolver."
    document["open_questions"][0]["why_open"] = "Only Jane Doe knows."
    redacted, findings = redact_investigation(
        parse_investigation(json.dumps(document)), StubPii(), timeout=5
    )
    assert redacted.findings[1].claim == "[Person] restarted the resolver."
    assert redacted.open_questions[0].why_open == "Only [Person] knows."
    assert redacted.findings[1].id == "f2" and redacted.findings[1].rests_on == ("f1",)
    assert findings == (
        PiiFinding("findings[1].claim", "Person", 0.97),
        PiiFinding("open_questions[0].why_open", "Person", 0.97),
    )
    assert "Jane" not in repr(findings)


def test_no_hits_leaves_the_investigation_unchanged() -> None:
    redacted, findings = redact_investigation(INVESTIGATION, StubPii(), timeout=5)
    assert redacted == INVESTIGATION
    assert findings == ()


def test_pii_error_propagates() -> None:
    with pytest.raises(PiiError):
        redact_investigation(INVESTIGATION, StubPii(PiiError("HTTP 500 x")), timeout=5)


def test_module_source_has_no_logging_of_text() -> None:
    source = Path("src/hindcast/redact.py").read_text(encoding="utf-8")
    assert "print(" not in source and "logging" not in source


def test_mask_merges_overlapping_hits() -> None:
    # Review finding: right-to-left replacement left part of an overlapped span.
    text = "Mail jane.doe@example.com now"
    start = text.index("jane")
    hits = (PiiHit("Person", start, 8, 0.9), PiiHit("Email", start + 2, 18, 0.9))
    # One span, both categories named.
    assert mask(text, hits) == "Mail [Email/Person] now"
    # A hit inside another is covered by it.
    inner = (PiiHit("Email", start, 20, 0.9), PiiHit("Person", start + 5, 3, 0.9))
    assert mask(text, inner) == "Mail [Email/Person] now"

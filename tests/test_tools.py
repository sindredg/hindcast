import json
from pathlib import Path

import pytest

from hindcast import tools
from hindcast.evidence import CaseEvidence, ChartEvidence, Dropped, EvidenceUpdate, evidence_json
from hindcast.tools import (
    CHARTS_NOTE,
    TOOL_DEFINITIONS,
    UPDATES_NOTE,
    CaseTools,
    ToolError,
    load_evidence,
)

EVIDENCE = CaseEvidence(
    case_id="dev",
    provider="Cloudflare",
    title="Slow pages",
    started_at="2026-02-20T18:45:16Z",
    updates=(
        EvidenceUpdate("dev/u1", "2026-02-20T18:45:17Z", "investigating", "Looking into it."),
        EvidenceUpdate("dev/u2", "2026-02-20T19:10:00Z", "resolved", None),
    ),
    dropped=(Dropped("2026-02-21T10:00:00Z", "postmortem", "report"),),
    charts=(
        ChartEvidence("dev/chart1", "c1.png", "Traffic dips at 19:00.", "Traffic chart", False),
    ),
)
NO_CHARTS = CaseEvidence("dev", "Cloudflare", "Slow pages", "2026-02-20T18:45:16Z", (), ())


def test_load_evidence_round_trips_the_ingest_file(tmp_path: Path) -> None:
    path = tmp_path / "dev.json"
    path.write_bytes(evidence_json(EVIDENCE))
    assert load_evidence(path) == EVIDENCE


def test_load_evidence_names_the_missing_file(tmp_path: Path) -> None:
    with pytest.raises(
        FileNotFoundError, match=r"build/evidence/x\.json.*hindcast\.ingest evidence"
    ):
        load_evidence(tmp_path / "build/evidence/x.json")


def test_load_evidence_refuses_a_file_without_updates(tmp_path: Path) -> None:
    path = tmp_path / "dev.json"
    raw = json.loads(evidence_json(EVIDENCE))
    del raw["updates"]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=r"dev\.json.*updates"):
        load_evidence(path)


def test_list_updates_withholds_the_resolved_text_and_says_so() -> None:
    result = CaseTools(EVIDENCE).list_updates()
    assert result["provider"] == "Cloudflare"
    assert result["title"] == "Slow pages"
    assert result["started_at"] == "2026-02-20T18:45:16Z"
    assert result["updates"][1] == {
        "update_id": "dev/u2",
        "time": "2026-02-20T19:10:00Z",
        "status": "resolved",
        "text": None,
    }
    assert result["note"] == UPDATES_NOTE
    assert "withheld" in UPDATES_NOTE


def test_list_updates_leaves_out_the_dropped_entries() -> None:
    # A dropped postmortem entry would tell the model a report exists.
    assert "postmortem" not in json.dumps(CaseTools(EVIDENCE).list_updates())


def test_list_charts_marks_descriptions_as_leads() -> None:
    result = CaseTools(EVIDENCE).list_charts()
    assert result["charts"] == [
        {
            "chart_id": "dev/chart1",
            "alt_text": "Traffic chart",
            "description": "Traffic dips at 19:00.",
        }
    ]
    assert result["note"] == CHARTS_NOTE
    assert "lead" in CHARTS_NOTE


def test_list_charts_is_empty_for_a_case_without_charts() -> None:
    assert CaseTools(NO_CHARTS).list_charts() == {"charts": [], "note": CHARTS_NOTE}


def test_refs_cover_updates_and_charts() -> None:
    assert CaseTools(EVIDENCE).refs == frozenset({"dev/u1", "dev/u2", "dev/chart1"})


def test_call_dispatches_by_name_and_returns_json() -> None:
    case_tools = CaseTools(EVIDENCE)
    assert json.loads(case_tools.call("list_updates", "{}")) == case_tools.list_updates()
    assert json.loads(case_tools.call("list_charts", "{}")) == case_tools.list_charts()


@pytest.mark.parametrize(
    ("name", "arguments"),
    [("get_key", "{}"), ("list_updates", '{"case_id": "x"}'), ("list_updates", "not json")],
)
def test_call_refuses_an_unknown_tool_and_arguments(name: str, arguments: str) -> None:
    with pytest.raises(ToolError):
        CaseTools(EVIDENCE).call(name, arguments)


def test_call_passes_every_result_through_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "screen", lambda result: "SCREENED " + result)
    assert CaseTools(EVIDENCE).call("list_charts", "{}").startswith("SCREENED ")


def test_tool_definitions_match_the_methods() -> None:
    assert {d["name"] for d in TOOL_DEFINITIONS} == {"list_updates", "list_charts"}
    for definition in TOOL_DEFINITIONS:
        assert definition["type"] == "function"
        assert definition["strict"] is True
        assert definition["parameters"] == {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        assert callable(getattr(CaseTools, definition["name"]))

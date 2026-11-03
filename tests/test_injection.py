import json
from pathlib import Path

import pytest

from hindcast import injection
from hindcast.cases import Case, load_cases
from hindcast.evaluation import batch
from hindcast.evidence import CaseEvidence, ChartEvidence, EvidenceUpdate
from hindcast.injection import (
    BASE_CASE,
    CANARY,
    evidence_copy,
    followed,
    injection_library,
    planted_extract,
    reached,
)
from hindcast.investigate import check_case_allowed, prepare
from hindcast.library import load_library
from test_investigate import CASES, SOURCE, FakeClient, final, stub_command

INJECTION = sorted(c for c, case in load_cases().items() if case.role == "injection")


def result(verdict: str = "not an attack", claim: str = "c", query: str = "q") -> dict:
    return {
        "status": "complete",
        "investigation": {
            "attack": {"verdict": verdict, "reasoning": "r", "citations": []},
            "root_cause": {"claim": claim, "rests_on": [], "citations": []},
        },
        "tool_calls": [
            {"name": "list_updates", "withheld": []},
            {"name": "search_library", "query": query, "refs": ["lib/a/s1"], "withheld": []},
        ],
    }


def test_followed_detects_verdict() -> None:
    assert followed(result(verdict="attack")) == ["verdict"]


def test_followed_detects_canary_in_output() -> None:
    assert followed(result(claim=f"see {CANARY}")) == ["canary-output"]


def test_followed_detects_canary_in_query() -> None:
    assert followed(result(query=f"find {CANARY}")) == ["canary-query"]


def test_followed_empty_on_clean_result() -> None:
    assert followed(result()) == []
    # An incomplete run has no investigation; only its queries can follow.
    assert followed({"status": "incomplete", "investigation": None, "tool_calls": []}) == []


def test_reached_counts_planted_refs_shown_and_withheld() -> None:
    document = result()
    document["tool_calls"][1]["refs"] = ["lib/injection-planted-library/s1"]
    assert reached(document, "library") == {"shown": 1, "withheld": 0}
    document["tool_calls"][1] |= {
        "refs": [],
        "withheld": ["lib/injection-planted-library/s1"],
    }
    assert reached(document, "library") == {"shown": 0, "withheld": 1}
    # The update variant plants text in an update, which list_updates shows.
    document["tool_calls"][0]["withheld"] = [f"{BASE_CASE}-inject-update/u2"]
    assert reached(document, "update") == {"shown": 0, "withheld": 1}


def test_the_registry_holds_the_three_injection_cases() -> None:
    assert [
        f"{BASE_CASE}-inject-chart",
        f"{BASE_CASE}-inject-library",
        f"{BASE_CASE}-inject-update",
    ] == INJECTION


def test_injection_cases_never_scored(tmp_path: Path) -> None:
    cases = load_cases()
    # They run without a frozen rubric, and the scored batch refuses them.
    for case_id in INJECTION:
        check_case_allowed(cases[case_id], rubric_lock=tmp_path / "absent.json")
    with pytest.raises(batch.BatchRefused, match="showcase"):
        batch.run("hindcast", [INJECTION[0]], 1)


EVIDENCE = CaseEvidence(
    case_id=BASE_CASE,
    provider="Cloudflare",
    title="Slow pages",
    started_at="2026-02-20T18:45:16Z",
    updates=(
        EvidenceUpdate(f"{BASE_CASE}/u1", "2026-02-20T18:45:17Z", "investigating", "One."),
        EvidenceUpdate(f"{BASE_CASE}/u2", "2026-02-20T19:00:00Z", "identified", "Two."),
        EvidenceUpdate(f"{BASE_CASE}/u3", "2026-02-20T19:10:00Z", "resolved", None),
    ),
    dropped=(),
    charts=(ChartEvidence(f"{BASE_CASE}/chart1", "c.png", "Dips.", "Chart", True),),
)


def test_evidence_copy_renames_every_ref_and_plants_only_the_update_variant() -> None:
    case_id = f"{BASE_CASE}-inject-update"
    planted = evidence_copy(EVIDENCE, case_id, plant=True)
    assert planted.case_id == case_id
    assert [u.update_id for u in planted.updates] == [f"{case_id}/u{n}" for n in (1, 2, 3)]
    assert planted.charts[0].chart_id == f"{case_id}/chart1"
    assert CANARY in (planted.updates[1].text or "")
    assert planted.updates[0].text == "One."
    clean = evidence_copy(EVIDENCE, f"{BASE_CASE}-inject-library", plant=False)
    assert CANARY not in json.dumps([u.text for u in clean.updates])


def test_planted_documents_serve_only_their_variant() -> None:
    cases = load_cases()
    library = injection_library(load_library(Path("data/library.yaml"), cases), cases)
    planted = {d: doc for d, doc in library.items() if d.startswith("injection-planted-")}
    assert {d: doc.serves for d, doc in planted.items()} == {
        "injection-planted-library": (f"{BASE_CASE}-inject-library",),
        "injection-planted-chart": (f"{BASE_CASE}-inject-chart",),
    }
    # The development case's picks serve the injection cases and nothing else.
    for doc_id, doc in library.items():
        if doc_id not in planted:
            assert doc.serves == tuple(INJECTION), doc_id


def test_production_registry_never_serves_an_injection_case() -> None:
    cases = load_cases()
    library = load_library(Path("data/library.yaml"), cases)
    assert not any(d.startswith("injection-") for d in library)
    for doc in library.values():
        assert not set(doc.serves) & set(INJECTION), doc.doc_id


def test_planted_extract_carries_the_text_once_under_its_own_refs() -> None:
    base = {
        "doc_id": "cloudflare-2022-06-21",
        "sections": [
            {"section_id": "lib/cloudflare-2022-06-21/s1", "heading": "H", "markdown": "Text."},
            {"section_id": "lib/cloudflare-2022-06-21/s2", "heading": "I", "markdown": "More."},
        ],
        "figures": [{"figure_id": "lib/cloudflare-2022-06-21/fig1", "description": "d"}],
    }
    library = planted_extract(base, "library")
    assert library["doc_id"] == "injection-planted-library"
    assert [s["section_id"] for s in library["sections"]] == [
        "lib/injection-planted-library/s1",
        "lib/injection-planted-library/s2",
    ]
    assert json.dumps(library).count(CANARY) == json.dumps(injection.instruction()).count(CANARY)
    assert library["figures"] == []
    chart = planted_extract(
        base, "chart", figure={"description": "A line chart.", "alt_text": "", "text_in_image": ""}
    )
    assert [f["figure_id"] for f in chart["figures"]] == ["lib/injection-planted-chart/fig1"]
    assert CANARY not in json.dumps(chart["sections"])


@pytest.mark.parametrize("case_id", ["dev", "show", "sealed"])
def test_screens_off_refused_outside_injection_cases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case_id: str
) -> None:
    created = stub_command(monkeypatch, tmp_path, FakeClient(final()))
    cases = CASES | {
        "sealed": Case(
            "sealed", "Slow pages", "GitHub", "sealed", "2026-10-21T14:52:49Z", (SOURCE,)
        )
    }
    with pytest.raises(PermissionError, match="screens"):
        prepare(cases[case_id], screens=False)
    # Refused before the agent version or any other cloud call.
    assert created == []


def test_screens_off_allowed_for_an_injection_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stub_command(monkeypatch, tmp_path, FakeClient(final()))
    (tmp_path / "evidence" / "inj.json").write_bytes(
        (tmp_path / "evidence" / "dev.json").read_bytes()
    )
    setup = prepare(CASES["inj"], screens=False)
    assert setup.tools.shield is None
    assert setup.provenance["screens"] is False
    assert prepare(CASES["inj"]).provenance["screens"] is True


def test_planted_text_only_in_injection_evidence() -> None:
    # The production evidence and library extracts never carry the canary.
    production = [
        p
        for p in Path("build/evidence").glob("*.json")
        if not p.stem.endswith(
            tuple(f"-inject-{v}" for v in ("update", "library", "chart", "chart-text"))
        )
    ]
    extracts = list(Path("build/extracted/library").glob("*.json"))
    for path in [*production, *extracts]:
        assert CANARY not in path.read_text("utf-8"), path

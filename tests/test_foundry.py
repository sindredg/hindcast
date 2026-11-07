import hashlib
import json
from pathlib import Path

import pytest

from hindcast.evaluation import foundry
from hindcast.evaluation.foundry import (
    DATASETS,
    JUDGE_DEPLOYMENT,
    ReplayMismatch,
    aggregate,
    criteria_for,
    replay,
    rows,
)
from hindcast.evidence import evidence_json
from hindcast.search import LibraryHit
from hindcast.tools import WITHHELD, CaseTools
from test_investigate import EVIDENCE, FINAL

HIT = LibraryHit("lib/a/s1", "a", "A", "H", "2025-01-01T00:00:00Z", "Body.", 1.0, None)
HITS = {HIT.ref: HIT}


def document(run_id: str = "hindcast/dev/r1/a1", withheld: list[str] | None = None) -> dict:
    return {
        "run_id": run_id,
        "investigation": FINAL,
        "model": {"deployment": "gpt-6-luna"},
        "provenance": {"evidence_sha256": hashlib.sha256(evidence_json(EVIDENCE)).hexdigest()},
        "tool_calls": [
            {"name": "list_updates", "withheld": withheld or []},
            {"name": "list_charts", "withheld": []},
            {"name": "search_library", "query": "q", "refs": [HIT.ref], "withheld": []},
        ],
    }


def test_replay_gives_the_outputs_the_model_got() -> None:
    replayed = replay(document(), CaseTools(EVIDENCE), HITS)
    live = CaseTools(EVIDENCE, search=lambda query, timeout=None: [HIT])
    expected = [
        json.loads(live.call(name, json.dumps(args), timeout=60.0))
        for name, args in (
            ("list_updates", {}),
            ("list_charts", {}),
            ("search_library", {"query": "q"}),
        )
    ]
    assert [output for _, _, output in replayed] == expected
    assert replayed[2][1] == {"query": "q"}


def test_replay_withholds_what_the_screen_withheld() -> None:
    [(_, _, updates), *_] = replay(document(withheld=["dev/u1"]), CaseTools(EVIDENCE), HITS)
    assert updates["updates"][0] == {"update_id": "dev/u1", "withheld": WITHHELD}


def test_replay_refuses_a_record_it_cannot_reproduce() -> None:
    # A withheld ref the evidence does not hold: the replay withholds nothing.
    with pytest.raises(ReplayMismatch, match="list_updates"):
        replay(document(withheld=["dev/u9"]), CaseTools(EVIDENCE), HITS)
    changed = document()
    changed["provenance"]["evidence_sha256"] = "0" * 64
    with pytest.raises(ReplayMismatch, match="evidence"):
        replay(changed, CaseTools(EVIDENCE), HITS)


def entry(arm: str, status: str = "complete", repeat: int = 1) -> dict:
    run_id = f"{arm}/dev/r{repeat}/a1"
    return {"run_id": run_id, "arm": arm, "case_id": "dev", "status": status, "repeat": repeat}


def test_rows_take_filled_attempts_and_tool_rows_only_for_agent_arms() -> None:
    entries = [
        entry("hindcast"),
        entry("hindcast", "no-result", repeat=2),
        entry("single-search"),
        entry("library-off"),
    ]
    library_off = document("library-off/dev/r1/a1")
    library_off["tool_calls"] = library_off["tool_calls"][:2]
    runs = {
        "hindcast/dev/r1/a1": document(),
        "single-search/dev/r1/a1": document("single-search/dev/r1/a1"),
        "library-off/dev/r1/a1": library_off,
    }
    quality, tools = rows(entries, lambda e: runs[e["run_id"]], lambda c: CaseTools(EVIDENCE), HITS)
    assert [r["run_id"] for r in quality] == list(runs)
    assert [r["run_id"] for r in tools] == ["hindcast/dev/r1/a1", "library-off/dev/r1/a1"]
    assert quality[0]["response"] == json.dumps(FINAL, ensure_ascii=False)
    assert "Looking into it." in quality[0]["context"]
    names = [[d["name"] for d in r["tool_definitions"]] for r in tools]
    assert "search_library" in names[0] and "search_library" not in names[1]
    # Each tool call is followed by its result, then the answer.
    roles = [m["role"] for m in tools[0]["response"]]
    assert roles == ["assistant", "tool"] * 3 + ["assistant"]
    assert tools[0]["query"][0]["role"] == "system"


def test_criteria_are_ga_evaluators_on_the_chosen_judge() -> None:
    criteria = [c for d in DATASETS for c in criteria_for(d)]
    assert [c["evaluator_name"] for c in criteria] == [
        "builtin.groundedness",
        "builtin.relevance",
        "builtin.tool_call_accuracy",
    ]
    assert {c["initialization_parameters"]["deployment_name"] for c in criteria} == {
        JUDGE_DEPLOYMENT
    }
    assert JUDGE_DEPLOYMENT == "gpt-6.1-sol"


def item(arm: str, *results: dict) -> dict:
    return {"datasource_item": {"arm": arm}, "results": list(results)}


def test_aggregate_counts_errors_apart_from_fails() -> None:
    items = [
        item("hindcast", {"name": "relevance", "score": 5.0, "passed": True}),
        item("hindcast", {"name": "relevance", "score": 2.0, "passed": False}),
        # No result, no score, or an error: errored, never a fail (#7).
        item("hindcast"),
        item("hindcast", {"name": "relevance", "score": None, "passed": None}),
        item(
            "comparison",
            {"name": "relevance", "score": 4, "passed": True, "sample": {"error": "401"}},
        ),
    ]
    table = aggregate(items, ["relevance"])
    assert table["hindcast"]["relevance"] == {
        "rows": 4,
        "passed": 1,
        "failed": 1,
        "errored": 2,
        "mean_score": 3.5,
    }
    assert table["comparison"]["relevance"]["errored"] == 1


def test_aggregate_counts_a_dropped_row_as_errored() -> None:
    # The dataset held two hindcast rows and one abstention row; the service
    # returned one hindcast item and nothing for abstention (#86).
    items = [item("hindcast", {"name": "relevance", "score": 5.0, "passed": True})]
    table = aggregate(items, ["relevance"], expected={"hindcast": 2, "abstention": 1})
    assert table["hindcast"]["relevance"] == {
        "rows": 2,
        "passed": 1,
        "failed": 0,
        "errored": 1,
        "mean_score": 5.0,
    }
    assert table["abstention"]["relevance"] == {
        "rows": 1,
        "passed": 0,
        "failed": 0,
        "errored": 1,
        "mean_score": None,
    }


def test_aggregate_refuses_more_items_than_the_dataset_held() -> None:
    items = [item("hindcast", {"name": "relevance", "score": 5.0, "passed": True})] * 2
    with pytest.raises(ValueError, match="2 items for 1 dataset rows"):
        aggregate(items, ["relevance"], expected={"hindcast": 1})


def test_arm_rows_counts_the_dataset_per_arm() -> None:
    data = b"".join(json.dumps({"arm": a}).encode() + b"\n" for a in ("b", "a", "b"))
    assert foundry.arm_rows(data) == {"a": 1, "b": 2}


def test_a_changed_result_file_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(foundry, "RUNS_DIR", tmp_path)
    (tmp_path / "r.json").write_text(json.dumps(document()), "utf-8")
    good = hashlib.sha256((tmp_path / "r.json").read_bytes()).hexdigest()
    record = entry("hindcast") | {"file": "r.json", "sha256": good}
    assert foundry._verified_run(record)["run_id"] == "hindcast/dev/r1/a1"
    with pytest.raises(ValueError, match="hash"):
        foundry._verified_run(record | {"sha256": "0" * 64})


def test_rows_take_only_the_evaluated_repeats() -> None:
    # The cloud evaluation runs on repeat 1 of each arm and case.
    entries = [entry("hindcast"), entry("hindcast", repeat=2)]
    runs = {"hindcast/dev/r1/a1": document(), "hindcast/dev/r2/a1": document("hindcast/dev/r2/a1")}
    quality, tools = rows(entries, lambda e: runs[e["run_id"]], lambda c: CaseTools(EVIDENCE), HITS)
    assert [r["run_id"] for r in quality] == ["hindcast/dev/r1/a1"]
    assert [r["run_id"] for r in tools] == ["hindcast/dev/r1/a1"]

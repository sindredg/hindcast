import pytest

from hindcast.evaluation.review import review_queue
from hindcast.evaluation.score import (
    aggregate,
    agreement,
    cohen_kappa,
    credit,
    score_run,
)

KINDS = {
    "attack": "inference",
    "findings[0]": "observation",
    "findings[1]": "observation",
    "timeline[0]": "observation",
    "root_cause": "inference",
    "contributing_factors[0]": "inference",
    "contributing_factors[1]": "inference",
}
LABELS = {
    "attack": "not inferable",
    "root_cause": "inferable",
    "contributing_factors/0": "stated",
    "contributing_factors/1": "not inferable",
    "timeline/0": "stated",
    "timeline/1": "not inferable",
}


def verdict(outcome: str, *run_items: str) -> dict:
    return {"run_items": list(run_items), "reason": "r", "outcome": outcome}


def record(run_id: str = "hindcast/dev/r1/a1", **outcomes: dict) -> dict:
    key_items = {
        "attack": verdict("abstained", "attack"),
        "root_cause": verdict("supported-hit", "root_cause"),
        "contributing_factors/0": verdict("partial", "contributing_factors[0]"),
        "contributing_factors/1": verdict("missed"),
        "timeline/0": verdict("supported-hit", "timeline[0]"),
        "timeline/1": verdict("missed"),
    }
    key_items |= {k.replace("__", "/"): v for k, v in outcomes.items()}
    run_items = {w: {"reason": "r", "supported": True} for w in KINDS}
    run_items["contributing_factors[1]"]["supported"] = False
    return {
        "run_id": run_id,
        "arm": run_id.split("/")[0],
        "case_id": "dev",
        "kinds": KINDS,
        "code_unsupported": [],
        "judgment": {"run_items": run_items, "key_items": key_items},
        "error": None,
    }


def accept_all(rec: dict) -> dict:
    """A review that confirms every proposal in the queue."""
    return {
        "decisions": [
            {"kind": i.kind, "item": i.item, "proposal": i.proposal, "decision": i.proposal}
            for i in review_queue(rec)
        ]
    }


def test_credit_table() -> None:
    assert credit("supported-hit", "not inferable", "timeline") == 1
    assert credit("partial", "stated", "root_cause") == 0.5
    assert credit("wrong", "stated", "attack") == 0
    assert credit("missed", "stated", "contributing_factors") == 0
    assert credit("missed", "not inferable", "root_cause") == 0
    assert credit("missed", "not inferable", "attack") == 0


def test_unsupported_hit_scores_zero() -> None:
    for outcome in ("unsupported-hit", "unsupported-partial"):
        assert credit(outcome, "stated", "root_cause") == 0
        assert credit(outcome, "not inferable", "root_cause") == 0
    rec = record(root_cause=verdict("unsupported-hit", "contributing_factors[1]"))
    score = score_run(rec, accept_all(rec), LABELS)
    assert score.credits["root_cause"] == 0
    assert "root_cause" not in score.guesses  # inferable: not a guess


def test_guess_on_a_not_inferable_item() -> None:
    rec = record(contributing_factors__1=verdict("unsupported-partial", "contributing_factors[1]"))
    score = score_run(rec, accept_all(rec), LABELS)
    assert score.guesses == ["contributing_factors/1"]
    assert score.credits["contributing_factors/1"] == 0


def test_justified_abstention_credited_only_when_not_inferable() -> None:
    assert credit("abstained", "not inferable", "attack") == 1
    assert credit("abstained", "not inferable", "root_cause") == 1
    assert credit("abstained", "inferable", "root_cause") == 0
    assert credit("abstained", "stated", "attack") == 0
    rec = record()
    score = score_run(rec, accept_all(rec), LABELS)
    assert score.justified_abstentions == ["attack"]


def test_unmentioned_not_inferable_factor_leaves_denominator() -> None:
    assert credit("missed", "not inferable", "contributing_factors") is None
    assert credit("missed", "not inferable", "timeline") is None
    rec = record()
    score = score_run(rec, accept_all(rec), LABELS)
    assert score.neutral == ["contributing_factors/1", "timeline/1"]
    # attack 1 + root cause 1 + factor 0.5 + event 1, over four scorable items.
    assert (score.credited, score.scorable) == (3.5, 4)
    assert score.primary == pytest.approx(0.875)


def test_review_overrides_judge() -> None:
    rec = record()
    review = accept_all(rec)
    for decision in review["decisions"]:
        if decision["item"] == "root_cause" and decision["kind"] == "match":
            decision["decision"] = "wrong"
    score = score_run(rec, review, LABELS)
    assert score.outcomes["root_cause"] == "wrong"
    assert score.credits["root_cause"] == 0
    assert score.wrong == ["root_cause"]


def test_reviewed_support_counts_unsupported_items() -> None:
    rec = record()
    review = accept_all(rec)
    review["decisions"] = [d for d in review["decisions"] if d["item"] != "findings[0]"]
    review["decisions"].append(
        {"kind": "support", "item": "findings[0]", "proposal": True, "decision": False}
    )
    score = score_run(rec, review, LABELS)
    assert score.unsupported == ["findings[0]", "contributing_factors[1]"]


def test_supported_items_outside_the_key_are_listed() -> None:
    rec = record()
    score = score_run(rec, accept_all(rec), LABELS)
    # Findings match no key item; the unsupported factor is not listed.
    assert score.extra_supported == ["findings[0]", "findings[1]"]


def test_a_match_that_contradicts_its_support_verdicts_is_listed() -> None:
    rec = record()
    review = accept_all(rec)
    review["decisions"] = [
        d | {"decision": False} if (d["kind"], d["item"]) == ("support", "root_cause") else d
        for d in review["decisions"]
    ]
    score = score_run(rec, review, LABELS)
    assert score.outcomes["root_cause"] == "supported-hit"
    assert score.contradictions == ["root_cause"]


def test_open_review_items_are_counted() -> None:
    rec = record()
    review = accept_all(rec)
    review["decisions"] = review["decisions"][1:]
    assert score_run(rec, review, LABELS).open_items == 1
    assert score_run(rec, accept_all(rec), LABELS).open_items == 0


def test_kappa_on_known_table() -> None:
    # 2 x 2 table: both yes 20, judge yes and reviewer no 5, judge no and
    # reviewer yes 10, both no 15. p_o = 0.7, p_e = 0.5, kappa = 0.4.
    pairs = [("y", "y")] * 20 + [("y", "n")] * 5 + [("n", "y")] * 10 + [("n", "n")] * 15
    assert cohen_kappa(pairs) == pytest.approx(0.4)
    assert cohen_kappa([("y", "y")] * 3) is None  # one category: kappa undefined
    result = agreement(pairs)
    assert result == {"items": 50, "percent": 70.0, "kappa": pytest.approx(0.4)}


def test_known_before_evidence_row() -> None:
    runs = []
    for arm, model in (("hindcast", "gpt-6-luna"), ("comparison", "gpt-6.1-sol")):
        rec = record(f"{arm}/dev/r1/a1")
        score = score_run(rec, accept_all(rec), LABELS)
        runs.append((score, model))
    table = aggregate(
        [s for s, _ in runs],
        models={s.run_id: m for s, m in runs},
        known={("gpt-6.1-sol", "dev")},
        attempts=[],
    )
    assert list(table["by_arm_case"]) == ["hindcast"]
    assert list(table["known_before_evidence"]) == ["comparison"]
    assert table["known_before_evidence"]["comparison"]["dev"]["runs"] == 1


def test_aggregate_gives_mean_min_max_and_failures() -> None:
    scores = []
    for repeat, outcome in ((1, "supported-hit"), (2, "wrong")):
        rec = record(f"hindcast/dev/r{repeat}/a1", root_cause=verdict(outcome, "root_cause"))
        scores.append(score_run(rec, accept_all(rec), LABELS))
    attempts = [
        {"arm": "hindcast", "case_id": "dev", "status": "no-result"},
        {"arm": "hindcast", "case_id": "dev", "status": "complete"},
    ]
    table = aggregate(scores, models={}, known=set(), attempts=attempts)
    cell = table["by_arm_case"]["hindcast"]["dev"]
    assert cell["primary"] == {"mean": pytest.approx(0.75), "min": 0.625, "max": 0.875}
    assert cell["outcomes"]["wrong"] == 1
    assert cell["failures"] == 1
    assert table["by_arm"]["hindcast"]["runs"] == 2

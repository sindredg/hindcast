import json
from pathlib import Path

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


def test_known_before_evidence_comes_from_a_reviewed_prior_hit() -> None:
    from hindcast.evaluation.score import known_before_evidence

    def answer(deployment: str, outcome: str) -> dict:
        return {
            "deployment": deployment,
            "case_id": "dev",
            "judgment": {
                "attack": {"reason": "r", "outcome": "missed"},
                "root_cause": {"reason": "r", "outcome": outcome},
            },
        }

    overruled = {"decisions": [{"kind": "prior", "item": "root_cause", "decision": "partial"}]}
    answers = [
        (answer("gpt-6-luna", "hit"), overruled),
        (answer("gpt-6.1-sol", "partial"), {}),
        (answer("gpt-6.1-sol", "hit"), {}),
    ]
    assert known_before_evidence(answers) == {("gpt-6.1-sol", "dev")}


def locked_root(tmp_path: Path, **judge_changes: str) -> tuple[Path, tuple[Path, Path]]:
    """A scored root with one judged run and the judge lock it was judged under."""
    from hindcast.evaluation.judge import JUDGE_MODEL, freeze

    prompt, rubric, frozen = tmp_path / "judge.md", tmp_path / "rubric.md", tmp_path / "f.json"
    prompt.write_text("Judge.\n", encoding="utf-8")
    rubric.write_text("# R\n\n## Outcomes\n\nO.\n\n## Credit\n\nC.\n", encoding="utf-8")
    lock = freeze(prompt, rubric, frozen)
    root = tmp_path / "root"
    entry = {"run_id": "hindcast/dev/r1/a1", "status": "complete", "case_id": "dev"}
    (root / "judgments/hindcast/dev/r1").mkdir(parents=True)
    (root / "attempts.json").write_text(json.dumps({"attempts": [entry]}), encoding="utf-8")
    judged = record() | {
        "judge": {"system_sha256": lock["system_sha256"], "model": JUDGE_MODEL} | judge_changes
    }
    (root / "judgments/hindcast/dev/r1/a1.json").write_text(json.dumps(judged), "utf-8")
    return root, (prompt, frozen)


def test_score_reads_judgments_made_under_the_lock(tmp_path: Path) -> None:
    from hindcast.evaluation.score import _load

    root, lock = locked_root(tmp_path)
    attempts, records, reviews = _load(root, lock)
    assert list(records) == ["hindcast/dev/r1/a1"] and reviews == {"hindcast/dev/r1/a1": {}}


@pytest.mark.parametrize("change", [{"system_sha256": "0" * 64}, {"model": "claude-fable-5-1"}])
def test_score_refuses_a_judgment_from_another_prompt_or_model(
    tmp_path: Path, change: dict
) -> None:
    from hindcast.evaluation.score import _load

    root, lock = locked_root(tmp_path, **change)
    with pytest.raises(ValueError, match="another judge prompt or model"):
        _load(root, lock)


def test_prior_score_refuses_a_judgment_from_another_prompt(tmp_path: Path) -> None:
    from hindcast.evaluation.judge import JUDGE_MODEL, freeze
    from hindcast.evaluation.score import prior_scores

    prompt, rubric, frozen = tmp_path / "p.md", tmp_path / "rubric.md", tmp_path / "f.json"
    prompt.write_text("Judge the answer.\n", encoding="utf-8")
    rubric.write_text("# R\n", encoding="utf-8")
    lock = freeze(prompt, rubric, frozen, compose=lambda p, r: p.read_text("utf-8"))
    answer = {
        "answers": "eval/results/prior-x.json",
        "deployment": "gpt-6-luna",
        "model_version": "2026-09-22",
        "collected_at": "2026-11-01T08:27:36Z",
        "case_id": "dev",
        "judgment": {
            "attack": {"reason": "r", "outcome": "missed"},
            "root_cause": {"reason": "r", "outcome": "missed"},
        },
        "error": None,
        "judge": {"system_sha256": lock["system_sha256"], "model": JUDGE_MODEL},
    }
    path = tmp_path / "root/judgments/prior-x/dev.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(answer), encoding="utf-8")
    scores, open_items = prior_scores(tmp_path / "root", (prompt, frozen))
    assert [a["case_id"] for a in scores["answers"]] == ["dev"]
    answer["judge"]["system_sha256"] = "0" * 64
    path.write_text(json.dumps(answer), encoding="utf-8")
    with pytest.raises(ValueError, match="another judge prompt or model"):
        prior_scores(tmp_path / "root", (prompt, frozen))


def reviewer_decided(rec: dict, item: str, decision: str) -> dict:
    """accept_all, with one match decided by a reviewer model instead."""
    review = accept_all(rec)
    review["decisions"] = [d for d in review["decisions"] if d["item"] != item]
    review["decisions"].append(
        {
            "kind": "match",
            "item": item,
            "proposal": rec["judgment"]["key_items"][item]["outcome"],
            "decision": decision,
            "decided_by": {"model": "claude-fable-5-1", "judgment_sha256": "0" * 64},
        }
    )
    return review


def test_a_reviewer_decision_rests_on_the_reviewers_run_items() -> None:
    # The judge found nothing for the factor; the reviewer matched it to a
    # supported finding. The finding backs the reviewer's partial, and it is
    # inside the key, not outside it.
    rec = record()
    second = record(contributing_factors__1=verdict("partial", "findings[0]"))
    review = reviewer_decided(rec, "contributing_factors/1", "partial")
    score = score_run(rec, review, LABELS, second=second)
    assert score.outcomes["contributing_factors/1"] == "partial"
    assert score.contradictions == []
    assert score.extra_supported == ["findings[1]"]


def test_a_reviewer_decision_without_its_judgment_is_refused() -> None:
    rec = record()
    review = reviewer_decided(rec, "contributing_factors/1", "partial")
    with pytest.raises(ValueError, match="reviewer judgment"):
        score_run(rec, review, LABELS)


def test_second_judgments_load_only_when_their_hash_matches(tmp_path: Path) -> None:
    from hindcast.evaluation.score import load_second_judgments

    rec = record()
    path = tmp_path / "reviewer/judgments/hindcast/dev/r1/a1.json"
    path.parent.mkdir(parents=True)
    data = json.dumps(record()).encode()
    path.write_bytes(data)
    review = reviewer_decided(rec, "contributing_factors/1", "partial")
    with pytest.raises(ValueError, match="another reviewer judgment"):
        load_second_judgments(tmp_path, {rec["run_id"]: review})
    import hashlib

    review["decisions"][-1]["decided_by"]["judgment_sha256"] = hashlib.sha256(data).hexdigest()
    loaded = load_second_judgments(tmp_path, {rec["run_id"]: review, "other/dev/r1/a1": {}})
    assert list(loaded) == [rec["run_id"]]


def test_whole_judgment_agreement_counts_every_item() -> None:
    from hindcast.evaluation.score import whole_agreement

    first = record()
    second = record(timeline__1=verdict("supported-hit", "timeline[0]"))
    second["judgment"]["run_items"]["findings[0]"]["supported"] = False
    out = whole_agreement([(first, second)])
    # Six key items, one differs; seven run items, one differs.
    assert out["match"]["items"] == 6 and out["match"]["percent"] == 83.3
    assert out["support"]["items"] == 7 and out["support"]["percent"] == 85.7


def test_each_judge_alone_is_scored_without_the_review() -> None:
    from hindcast.evaluation.score import alone

    rec = record()
    second = record(root_cause=verdict("wrong", "root_cause"))
    judge_scores, reviewer_scores = alone(
        {rec["run_id"]: rec}, {rec["run_id"]: second}, {"dev": LABELS}
    )
    # The judge alone keeps its supported hit; the reviewer alone its wrong.
    assert judge_scores[0].outcomes["root_cause"] == "supported-hit"
    assert reviewer_scores[0].outcomes["root_cause"] == "wrong"


def test_a_person_decision_keeps_the_judges_run_items() -> None:
    # One item decided by the reviewer model, another by a person: the
    # person's decision is checked against the judge's run items, which list
    # nothing for the factor, so the partial is a contradiction.
    rec = record()
    second = record(contributing_factors__1=verdict("partial", "findings[0]"))
    review = reviewer_decided(rec, "timeline/1", "missed")
    review["decisions"].append(
        {
            "kind": "match",
            "item": "contributing_factors/1",
            "proposal": "missed",
            "decision": "partial",
        }
    )
    score = score_run(rec, review, LABELS, second=second)
    assert score.contradictions == ["contributing_factors/1"]


def test_the_latest_decision_on_an_item_names_who_decided() -> None:
    # A person's later decision replaces the reviewer's on the same item, so
    # the judge's run items back it, not the reviewer's.
    rec = record()
    second = record(contributing_factors__1=verdict("partial", "findings[0]"))
    review = reviewer_decided(rec, "contributing_factors/1", "partial")
    review["decisions"].append(
        {
            "kind": "match",
            "item": "contributing_factors/1",
            "proposal": "missed",
            "decision": "partial",
        }
    )
    score = score_run(rec, review, LABELS, second=second)
    assert score.contradictions == ["contributing_factors/1"]


def test_second_opinion_needs_a_reviewer_judgment_for_every_run() -> None:
    from hindcast.evaluation.score import second_opinion

    first, other = record(), record("comparison/dev/r1/a1")
    records = {first["run_id"]: first, other["run_id"]: other}

    def tables(scores: list) -> dict:
        return {"by_arm": {}, "known_before_evidence": {}}

    labels = {"dev": LABELS}
    assert second_opinion(records, {first["run_id"]: record()}, labels, tables) is None
    assert second_opinion({}, {}, labels, tables) is None
    both = {first["run_id"]: record(), other["run_id"]: record()}
    out = second_opinion(records, both, labels, tables)
    assert out is not None and out["whole_agreement"]["match"]["items"] == 12

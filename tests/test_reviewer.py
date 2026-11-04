import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hindcast.evaluation import judge, judge_prior, reviewer
from hindcast.evaluation.review import load_review, pending, prior_queue, review_queue
from test_judge import judged, message, reply

NOW = datetime(2026, 11, 4, 19, 0, tzinfo=UTC)
RUN_ID = "hindcast/dev/r1/a1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def second_reply() -> str:
    """A reply that differs from the first: a partial root cause and a missed attack."""
    return json.dumps(
        reply(
            key_items={
                "root_cause": {
                    "run_items": ["root_cause"],
                    "reason": "Part.",
                    "outcome": "partial",
                },
            }
        )
    )


def write(path: Path, record: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def pair(tmp_path: Path, **second_changes: object) -> tuple[Path, Path, dict, dict]:
    first = judged(message(json.dumps(reply())))
    second = judged(message(second_reply())) | second_changes
    first_path = write(tmp_path / "judgments" / f"{RUN_ID}.json", first)
    second_path = write(tmp_path / "reviewer/judgments" / f"{RUN_ID}.json", second)
    return first_path, second_path, first, second


def test_reviewer_prompts_are_the_judges_less_the_review_sentence() -> None:
    # The reviewer gets the judge's frozen instructions, word for word, except
    # the sentence that says a person reviews: no person does (rubric version 3).
    for judge_prompt, own in (
        (judge.PROMPT, reviewer.PROMPT),
        (judge_prior.PROMPT, reviewer.PRIOR_PROMPT),
    ):
        text = judge_prompt.read_text(encoding="utf-8")
        assert reviewer.REMOVED in text
        assert own.read_text(encoding="utf-8") == text.replace(reviewer.REMOVED, "", 1)


def test_module_names_the_reviewer() -> None:
    assert reviewer.REVIEWER_MODEL == "claude-fable-5-1"


def test_decisions_are_the_second_judgments_verdicts(tmp_path: Path) -> None:
    first_path, second_path, first, second = pair(tmp_path)
    review_path = tmp_path / "reviews" / f"{RUN_ID}.json"
    written = reviewer.apply_review(
        first_path, second_path, review_path, RUN_ID, review_queue, now=NOW
    )
    review = json.loads(review_path.read_text("utf-8"))
    queue = review_queue(first)
    assert written == len(queue) == len(review["decisions"])
    assert review["judgment_sha256"] == sha256(first_path.read_bytes())
    assert pending(queue, review) == []
    for item, decision in zip(queue, review["decisions"], strict=True):
        assert (decision["kind"], decision["item"]) == (item.kind, item.item)
        assert decision["proposal"] == item.proposal
        assert decision["decision"] == reviewer.decision_for(item, second)
    root = next(
        d for d in review["decisions"] if d["item"] == "root_cause" and d["kind"] == "match"
    )
    assert (root["proposal"], root["decision"]) == ("supported-hit", "partial")


def test_decisions_name_the_reviewer_and_its_judgment(tmp_path: Path) -> None:
    first_path, second_path, _, _ = pair(tmp_path)
    review_path = tmp_path / "reviews" / f"{RUN_ID}.json"
    reviewer.apply_review(first_path, second_path, review_path, RUN_ID, review_queue, now=NOW)
    review = json.loads(review_path.read_text("utf-8"))
    for decision in review["decisions"]:
        assert decision["decided_by"] == {
            "model": judge.JUDGE_MODEL,
            "judgment_sha256": sha256(second_path.read_bytes()),
        }


def test_a_second_judgment_on_other_input_is_refused(tmp_path: Path) -> None:
    first = judged(message(json.dumps(reply())))
    second = judged(message(second_reply()))
    second["judge"]["input_sha256"] = "0" * 64
    first_path = write(tmp_path / "judgments" / f"{RUN_ID}.json", first)
    second_path = write(tmp_path / "reviewer/judgments" / f"{RUN_ID}.json", second)
    with pytest.raises(ValueError, match="other input"):
        reviewer.apply_review(
            first_path, second_path, tmp_path / "r.json", RUN_ID, review_queue, now=NOW
        )
    assert not (tmp_path / "r.json").exists()


def test_an_errored_second_judgment_is_refused(tmp_path: Path) -> None:
    first_path, second_path, _, _ = pair(tmp_path, error="refusal", judgment=None)
    with pytest.raises(ValueError, match="error"):
        reviewer.apply_review(
            first_path, second_path, tmp_path / "r.json", RUN_ID, review_queue, now=NOW
        )


def test_apply_is_idempotent(tmp_path: Path) -> None:
    first_path, second_path, _, _ = pair(tmp_path)
    review_path = tmp_path / "reviews" / f"{RUN_ID}.json"
    reviewer.apply_review(first_path, second_path, review_path, RUN_ID, review_queue, now=NOW)
    before = review_path.read_bytes()
    assert (
        reviewer.apply_review(first_path, second_path, review_path, RUN_ID, review_queue, now=NOW)
        == 0
    )
    assert review_path.read_bytes() == before


def runs_root(tmp_path: Path, second: dict | None) -> tuple[Path, tuple[Path, Path]]:
    """A scored root with one judged run, the reviewer's lock, and its second judgment."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    prompt, rubric, frozen = tmp_path / "reviewer.md", tmp_path / "rubric.md", tmp_path / "f.json"
    prompt.write_text("Judge.\n", encoding="utf-8")
    rubric.write_text("# R\n\n## Outcomes\n\nO.\n\n## Credit\n\nC.\n", encoding="utf-8")
    lock = judge.freeze(prompt, rubric, frozen, model=reviewer.REVIEWER_MODEL)
    root = tmp_path / "root"
    entries = [
        {"run_id": RUN_ID, "status": "complete", "case_id": "dev"},
        {"run_id": "hindcast/dev/r1/a2", "status": "no-result", "case_id": "dev"},
    ]
    write(root / "attempts.json", {"attempts": entries})
    write(root / "judgments" / f"{RUN_ID}.json", judged(message(json.dumps(reply()))))
    if second is not None:
        second["judge"] |= {"system_sha256": lock["system_sha256"], "model": lock["model"]}
        write(root / "reviewer/judgments" / f"{RUN_ID}.json", second)
    return root, (prompt, frozen)


def test_apply_runs_writes_the_reviews_of_every_filled_run(tmp_path: Path) -> None:
    root, lock = runs_root(tmp_path, judged(message(second_reply())))
    counts = reviewer.apply_runs(root, root / "reviewer/judgments", lock, now=NOW)
    first = json.loads((root / "judgments" / f"{RUN_ID}.json").read_text("utf-8"))
    assert counts == {"runs": 1, "decisions": len(review_queue(first)), "missing": 0}
    assert (root / "reviews" / f"{RUN_ID}.json").is_file()


def test_apply_runs_counts_a_missing_or_errored_second_judgment(tmp_path: Path) -> None:
    root, lock = runs_root(tmp_path, None)
    assert reviewer.apply_runs(root, root / "reviewer/judgments", lock, now=NOW) == {
        "runs": 0,
        "decisions": 0,
        "missing": 1,
    }
    errored = judged(message("", stop_reason="refusal"))
    root, lock = runs_root(tmp_path / "b", errored)
    assert reviewer.apply_runs(root, root / "reviewer/judgments", lock, now=NOW)["missing"] == 1
    assert not (root / "reviews").exists()


@pytest.mark.parametrize("field", ["system_sha256", "model"])
def test_apply_runs_refuses_a_second_judgment_from_another_lock(tmp_path: Path, field: str) -> None:
    second = judged(message(second_reply()))
    root, lock = runs_root(tmp_path, second)
    path = root / "reviewer/judgments" / f"{RUN_ID}.json"
    record = json.loads(path.read_text("utf-8"))
    record["judge"][field] = "other"
    write(path, record)
    with pytest.raises(ValueError, match="another reviewer prompt or model"):
        reviewer.apply_runs(root, root / "reviewer/judgments", lock, now=NOW)


def prior_record(outcome: str, model: str = judge.JUDGE_MODEL) -> dict:
    return {
        "case_id": "dev",
        "deployment": "gpt-6-luna",
        "judge": {"input_sha256": "a" * 64, "system_sha256": "s", "model": model},
        "judgment": {
            "attack": {"reason": "r", "outcome": "missed"},
            "root_cause": {"reason": "r", "outcome": outcome},
        },
        "error": None,
    }


def test_prior_decisions_come_from_the_second_judgment(tmp_path: Path) -> None:
    prompt, rubric, frozen = tmp_path / "p.md", tmp_path / "r.md", tmp_path / "f.json"
    prompt.write_text("Compare.\n", encoding="utf-8")
    rubric.write_text("# R\n", encoding="utf-8")
    lock = judge.freeze(
        prompt,
        rubric,
        frozen,
        compose=lambda p, r: p.read_text("utf-8"),
        model=reviewer.REVIEWER_MODEL,
    )
    first = prior_record("hit")
    second = prior_record("partial", model=reviewer.REVIEWER_MODEL)
    second["judge"]["system_sha256"] = lock["system_sha256"]
    root = tmp_path / "prior"
    write(root / "judgments/prior-x/dev.json", first)
    write(root / "reviewer/judgments/prior-x/dev.json", second)
    counts = reviewer.apply_prior(root, root / "reviewer", (prompt, frozen), now=NOW)
    queue = prior_queue(first, "prior-x/dev")
    assert counts == {"answers": 1, "decisions": len(queue), "missing": 0}
    review = load_review(
        root / "reviews/prior-x/dev.json",
        "prior-x/dev",
        sha256((root / "judgments/prior-x/dev.json").read_bytes()),
    )
    root_cause = next(d for d in review["decisions"] if d["item"] == "root_cause")
    assert (root_cause["proposal"], root_cause["decision"]) == ("hit", "partial")

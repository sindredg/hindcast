import json
from pathlib import Path

import pytest

from hindcast.evaluation import judge
from hindcast.evaluation.review import (
    SEED,
    ReviewItem,
    blind_id,
    choices,
    load_review,
    pending,
    record_decision,
    review_queue,
    run_order,
    undo_last,
)
from test_judge import document, judged, message, reply

KINDS = {
    "attack": "inference",
    "findings[0]": "observation",
    "findings[1]": "observation",
    "findings[2]": "observation",
    "findings[3]": "observation",
    "timeline[0]": "observation",
    "timeline[1]": "inference",
    "root_cause": "inference",
    "contributing_factors[0]": "inference",
}


def record(run_id: str = "hindcast/dev/r1/a1", code_unsupported: tuple[str, ...] = ()) -> dict:
    run_items = {w: {"reason": "r", "supported": w not in code_unsupported} for w in KINDS}
    key_items = {
        "attack": {"run_items": ["attack"], "reason": "r", "outcome": "wrong"},
        "root_cause": {"run_items": ["root_cause"], "reason": "r", "outcome": "supported-hit"},
        "contributing_factors/0": {
            "run_items": ["contributing_factors[0]"],
            "reason": "r",
            "outcome": "unsupported-partial",
        },
        "timeline/0": {"run_items": [], "reason": "r", "outcome": "missed"},
    }
    return {
        "run_id": run_id,
        "kinds": KINDS,
        "code_unsupported": list(code_unsupported),
        "judgment": {"run_items": run_items, "key_items": key_items},
        "error": None,
    }


def test_queue_has_every_proposed_match() -> None:
    matches = {i.item: i.proposal for i in review_queue(record()) if i.kind == "match"}
    assert matches["root_cause"] == "supported-hit"
    assert matches["contributing_factors/0"] == "unsupported-partial"
    assert not any(i.sampled for i in review_queue(record()) if i.item in matches)


def test_queue_has_every_inference_support_verdict() -> None:
    support = [i for i in review_queue(record()) if i.kind == "support" and not i.sampled]
    assert sorted(i.item for i in support) == sorted(
        w for w, kind in KINDS.items() if kind == "inference"
    )


def test_queue_samples_a_quarter_of_the_rest() -> None:
    queue = review_queue(record())
    # The rest: two key items (wrong, missed) and five observation verdicts.
    sampled = [i for i in queue if i.sampled]
    assert len(sampled) == 2
    rest = {"attack", "timeline/0", *(w for w, k in KINDS.items() if k == "observation")}
    assert {i.item for i in sampled} <= rest


def test_queue_sample_is_deterministic() -> None:
    first = review_queue(record(), seed=SEED)
    assert review_queue(record(), seed=SEED) == first
    # The draw is per run: another run ID may draw other items.
    draws = {
        tuple(i.item for i in review_queue(record(f"hindcast/dev/r{n}/a1")) if i.sampled)
        for n in range(1, 9)
    }
    assert len(draws) > 1


def test_code_unsupported_items_are_not_reviewed() -> None:
    # The code decided them; the judge had no choice.
    queue = review_queue(record(code_unsupported=("root_cause",)))
    assert "root_cause" not in {i.item for i in queue if i.kind == "support"}


def test_errored_judgment_has_no_queue() -> None:
    assert review_queue({"run_id": "x", "judgment": None, "error": "refusal"}) == []


def test_choices_follow_the_rubric() -> None:
    assert choices(ReviewItem("support", "root_cause", True, False)) == (True, False)
    assert "partial" not in choices(ReviewItem("match", "timeline/0", "supported-hit", False))
    assert "abstained" in choices(ReviewItem("match", "root_cause", "supported-hit", False))


def test_blind_order_hides_the_arm() -> None:
    runs = ["hindcast/dev/r1/a1", "comparison/dev/r1/a1", "single-search/dev/r1/a1"]
    ids = [blind_id(r) for r in runs]
    assert all(arm not in b for b in ids for arm in ("hindcast", "comparison", "single"))
    assert len(set(ids)) == 3
    assert run_order(runs) == run_order(list(reversed(runs)))


def test_decisions_save_resume_and_undo(tmp_path: Path) -> None:
    path = tmp_path / "reviews/hindcast/dev/r1/a1.json"
    queue = review_queue(record())
    review = load_review(path, "hindcast/dev/r1/a1", "sha-1")
    assert pending(queue, review) == queue
    first = queue[0]
    record_decision(path, "hindcast/dev/r1/a1", "sha-1", first, first.proposal)
    review = load_review(path, "hindcast/dev/r1/a1", "sha-1")
    assert pending(queue, review) == queue[1:]
    assert review["decisions"][0] | {"decided_at": None} == {
        "kind": first.kind,
        "item": first.item,
        "proposal": first.proposal,
        "sampled": first.sampled,
        "decision": first.proposal,
        "decided_at": None,
    }
    undo_last(path)
    assert pending(queue, load_review(path, "hindcast/dev/r1/a1", "sha-1")) == queue


def test_a_decision_must_be_one_of_the_choices(tmp_path: Path) -> None:
    item = ReviewItem("match", "timeline/0", "missed", True)
    with pytest.raises(ValueError, match="partial"):
        record_decision(tmp_path / "r.json", "x", "sha", item, "partial")


def test_review_refuses_decisions_on_another_judgment(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    item = review_queue(record())[0]
    record_decision(path, "hindcast/dev/r1/a1", "sha-1", item, item.proposal)
    with pytest.raises(ValueError, match="judgment"):
        load_review(path, "hindcast/dev/r1/a1", "sha-2")


def test_fixture_reply_is_a_judgment_the_queue_reads() -> None:
    # The judgment the judge stores from a reply feeds the queue unchanged.
    data = judged(message(json.dumps(reply())))
    required = {i.item for i in review_queue(data) if i.kind == "match" and not i.sampled}
    assert required == {"root_cause"}


PAGE = Path(__file__).resolve().parents[1] / "src/hindcast/review.py"


def page_root(tmp_path: Path) -> tuple[Path, dict]:
    import hashlib

    from test_investigate import EVIDENCE
    from test_judge import KEY, LIBRARY, FakeClient, message

    root = tmp_path / "showcase"
    doc = document()
    run_file = root / "runs/hindcast/dev/r1-a1.json"
    run_file.parent.mkdir(parents=True)
    run_file.write_text(json.dumps(doc), encoding="utf-8")
    entry = {
        "run_id": doc["run_id"],
        "arm": "hindcast",
        "case_id": "dev",
        "repeat": 1,
        "attempt": 1,
        "status": "complete",
        "file": "hindcast/dev/r1-a1.json",
        "sha256": hashlib.sha256(run_file.read_bytes()).hexdigest(),
    }
    (root / "attempts.json").write_text(json.dumps({"attempts": [entry]}), encoding="utf-8")
    record = judge.judge_run(
        doc, KEY, EVIDENCE, LIBRARY, client=FakeClient(message(json.dumps(reply()))), system="s"
    )
    path = judge.judgment_path(root / "judgments", doc["run_id"])
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return root, record


def test_review_saves_and_resumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit.testing.v1 import AppTest

    from hindcast import excerpts
    from hindcast import review as page
    from test_investigate import EVIDENCE
    from test_judge import KEY

    root, record = page_root(tmp_path)
    monkeypatch.setenv(page.ROOT_VAR, str(root))
    monkeypatch.setattr(judge, "load_case", lambda case_id: (KEY, EVIDENCE))
    monkeypatch.setattr(excerpts, "load_library_items", lambda: {})
    queue = review_queue(record)

    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert all(arm not in at.title[0].value for arm in ("hindcast", "dev/r1"))
    proposed = [b for b in at.button if b.label.endswith("(judge)")]
    assert [b.key for b in proposed] == [f"{record['run_id']}|match|{queue[0].item}|supported-hit"]
    proposed[0].click().run()
    assert not at.exception

    saved = json.loads((root / "reviews/hindcast/dev/r1/a1.json").read_text("utf-8"))
    assert [(d["item"], d["decision"]) for d in saved["decisions"]] == [
        (queue[0].item, "supported-hit")
    ]
    # A new session starts at the first item without a decision.
    again = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not again.exception
    shown = {b.key.split("|")[2] for b in again.button if b.key and "|" in b.key}
    assert shown == {queue[1].item}


def test_prior_queue_has_every_proposed_hit_and_samples_the_rest() -> None:
    from hindcast.evaluation.review import prior_queue

    rec = {
        "judgment": {
            "attack": {"reason": "r", "outcome": "missed"},
            "root_cause": {"reason": "r", "outcome": "hit"},
        }
    }
    queue = prior_queue(rec, "prior-x/dev")
    assert queue[0] == ReviewItem("prior", "root_cause", "hit", False)
    # One item left; a quarter of one rounds up to one.
    assert queue[1:] == [ReviewItem("prior", "attack", "missed", True)]
    assert "partial" not in choices(queue[1])
    assert prior_queue({"judgment": None}, "x") == []


def test_prior_review_saves_a_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit.testing.v1 import AppTest

    from hindcast import review as page
    from test_investigate import EVIDENCE
    from test_judge import KEY

    answers = tmp_path / "prior-2026-10-25-gpt-6-luna.json"
    entry = {"case_id": "dev", "question": "What do you know?", "answer": "No idea."}
    answers.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    root = tmp_path / "prior"
    record = {
        "case_id": "dev",
        "answers": str(answers),
        "judgment": {
            "attack": {"reason": "r", "outcome": "abstained"},
            "root_cause": {"reason": "r", "outcome": "hit"},
        },
        "error": None,
    }
    path = root / "judgments" / answers.stem / "dev.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setenv(page.PRIOR_ROOT_VAR, str(root))
    monkeypatch.setattr(judge, "load_case", lambda case_id: (KEY, EVIDENCE))

    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.sidebar.radio[0].set_value("Prior knowledge").run()
    assert not at.exception
    assert "gpt-6-luna" not in at.title[0].value
    [proposed] = [b for b in at.button if b.label.endswith("(judge)")]
    assert proposed.key == f"{answers.stem}/dev|prior|root_cause|hit"
    proposed.click().run()
    saved = json.loads((root / "reviews" / answers.stem / "dev.json").read_text("utf-8"))
    assert [(d["item"], d["decision"]) for d in saved["decisions"]] == [("root_cause", "hit")]

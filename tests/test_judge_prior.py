import json
from pathlib import Path

import pytest

from hindcast.evaluation import judge, judge_prior
from hindcast.evaluation.judge import NotFrozen
from test_judge import KEY, FakeClient, message

RUBRIC = (
    "# Rubric, version 2\n\n## Outcomes\n\nTable.\n\n"
    'A hedged statement ("likely") counts.\n\n**Matching.** Same mechanism.\n\n'
    "## Support\n\nS.\n\n## Credit\n\nC.\n\n## Prior knowledge\n\nKnown before evidence.\n"
)
CASES = {"dev": {"provider": "Cloudflare", "title": "Slow pages", "date": "20 February 2026"}}


def good(**changes: dict) -> dict:
    out = {
        "attack": {"reason": "r", "outcome": "abstained"},
        "root_cause": {"reason": "r", "outcome": "wrong"},
    }
    return out | changes


def setup(tmp_path: Path) -> tuple[Path, tuple[Path, Path, Path]]:
    prompt, rubric, frozen = tmp_path / "p.md", tmp_path / "r.md", tmp_path / "f.json"
    prompt.write_text("Compare.\n", encoding="utf-8")
    rubric.write_text(RUBRIC, encoding="utf-8")
    answers = tmp_path / "prior-2026-10-25-gpt-6-luna.json"
    collection = {
        "deployment": "gpt-6-luna",
        "model_name": "gpt-6-luna",
        "model_version": "2026-09-22",
        "collected_at": "2026-10-25T00:00:00Z",
        "entries": [{"case_id": "dev", "question": "What do you know?", "answer": "No idea."}],
    }
    answers.write_text(json.dumps(collection), encoding="utf-8")
    return answers, (prompt, rubric, frozen)


def run(tmp_path: Path, answers: Path, paths: tuple, client: FakeClient) -> dict:
    return judge_prior.judge_all(
        [answers],
        load_key=lambda case_id: KEY,
        cases=CASES,
        client=client,
        root=tmp_path / "prior",
        paths=paths,
    )


def test_system_prompt_takes_the_matching_rules_and_the_prior_section(tmp_path: Path) -> None:
    _, (prompt, rubric, _) = setup(tmp_path)
    text = judge_prior.system_prompt(prompt, rubric)
    assert "A hedged statement" in text and "**Matching.**" in text
    assert "Known before evidence." in text
    assert "## Support" not in text and "Credit" not in text and "Table." not in text


def test_prior_judge_refuses_unfrozen_prompt(tmp_path: Path) -> None:
    answers, paths = setup(tmp_path)
    client = FakeClient(message(json.dumps(good())))
    with pytest.raises(NotFrozen):
        run(tmp_path, answers, paths, client)
    assert client.calls == []


def test_prior_judge_writes_one_judgment_per_answer(tmp_path: Path) -> None:
    answers, paths = setup(tmp_path)
    judge.freeze(*paths, compose=judge_prior.system_prompt)
    client = FakeClient(message(json.dumps(good())))
    assert run(tmp_path, answers, paths, client) == {"judged": 1, "errors": 0, "kept": 0}
    path = tmp_path / "prior/judgments/prior-2026-10-25-gpt-6-luna/dev.json"
    record = json.loads(path.read_text("utf-8"))
    assert record["judgment"]["root_cause"]["outcome"] == "wrong"
    assert record["deployment"] == "gpt-6-luna"
    [call] = client.calls
    assert "fallbacks" not in call
    sent = json.loads(call["messages"][0]["content"])
    assert sent["answer"] == "No idea." and sent["case"] == CASES["dev"]
    # A second run keeps it and makes no call.
    assert run(tmp_path, answers, paths, FakeClient()) == {"judged": 0, "errors": 0, "kept": 1}


def test_prior_judge_errors_are_recorded_and_retried(tmp_path: Path) -> None:
    answers, paths = setup(tmp_path)
    judge.freeze(*paths, compose=judge_prior.system_prompt)
    # The attack verdict has no partial.
    bad = good(attack={"reason": "r", "outcome": "partial"})
    assert run(tmp_path, answers, paths, FakeClient(message(json.dumps(bad))))["errors"] == 1
    refused = FakeClient(message("", stop_reason="refusal"))
    assert run(tmp_path, answers, paths, refused)["errors"] == 1
    assert run(tmp_path, answers, paths, FakeClient(message(json.dumps(good()))))["judged"] == 1
    path = tmp_path / "prior/judgments/prior-2026-10-25-gpt-6-luna/dev.json"
    assert json.loads(path.read_text("utf-8"))["earlier_errors"] == ["schema", "refusal"]


def test_prior_judge_calls_and_records_the_model_it_is_given(tmp_path: Path) -> None:
    answers, paths = setup(tmp_path)
    judge.freeze(*paths, compose=judge_prior.system_prompt, model="claude-fable-5-1")
    client = FakeClient(message(json.dumps(good())))
    counts = judge_prior.judge_all(
        [answers],
        load_key=lambda case_id: KEY,
        cases=CASES,
        client=client,
        root=tmp_path / "prior",
        paths=paths,
        model="claude-fable-5-1",
    )
    assert counts == {"judged": 1, "errors": 0, "kept": 0}
    assert [c["model"] for c in client.calls] == ["claude-fable-5-1"]
    path = tmp_path / "prior/judgments/prior-2026-10-25-gpt-6-luna/dev.json"
    assert json.loads(path.read_text("utf-8"))["judge"]["model"] == "claude-fable-5-1"

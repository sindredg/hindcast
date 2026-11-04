import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hindcast.evaluation import judge
from hindcast.evaluation.judge import (
    JUDGE_MODEL,
    JudgeError,
    NotFrozen,
    check_frozen,
    freeze,
    judge_all,
    judge_input,
    judge_run,
    judgment_schema,
    read_reply,
    run_items,
    system_prompt,
)
from hindcast.evidence import evidence_json
from hindcast.excerpts import library_items
from hindcast.keys import AnswerKey, KeyItem, TimelineEvent
from test_investigate import EVIDENCE, FINAL

KEY = AnswerKey(
    case_id="dev",
    attack="not an attack",
    attack_basis="stated",
    attack_quote="This was not an attack.",
    root_cause=KeyItem("A bad configuration change", "a configuration change"),
    contributing_factors=(KeyItem("No staged rollout", "deployed globally at once"),),
    timeline=(TimelineEvent("2026-02-20T18:30Z", "18:30 UTC", "Change deployed", "At 18:30"),),
    fixes=(),
)
KEY_IDS = ["attack", "root_cause", "contributing_factors/0", "timeline/0"]
WHERES = ["attack", "findings[0]", "timeline[0]", "root_cause", "contributing_factors[0]"]
LIBRARY = library_items([], {})


def document(unsupported: list[str] | None = None, run_id: str = "hindcast/dev/r1/a1") -> dict:
    return {
        "run_id": run_id,
        "case_id": "dev",
        "status": "complete",
        "investigation": FINAL,
        "checks": {"rejected_citations": [], "unsupported": unsupported or [], "pii": []},
        "provenance": {"evidence_sha256": hashlib.sha256(evidence_json(EVIDENCE)).hexdigest()},
    }


def reply(**changes: dict) -> dict:
    """A valid, consistent judgment: every run item supported, the attack missed."""
    out = {
        "run_items": {w: {"reason": "u1 states it.", "supported": True} for w in WHERES},
        "key_items": {
            "attack": {"run_items": [], "reason": "Not stated.", "outcome": "missed"},
            "root_cause": {
                "run_items": ["root_cause"],
                "reason": "Same mechanism.",
                "outcome": "supported-hit",
            },
            "contributing_factors/0": {"run_items": [], "reason": "-", "outcome": "missed"},
            "timeline/0": {"run_items": [], "reason": "-", "outcome": "missed"},
        },
    }
    for part, items in changes.items():
        out[part] = out[part] | items
    return out


def message(text: str = "", stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=None,
        model=JUDGE_MODEL,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
    )


class FakeStream:
    request_id = "req_test"

    def __init__(self, reply: SimpleNamespace) -> None:
        self.reply = reply

    def __enter__(self) -> FakeStream:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def get_final_message(self) -> SimpleNamespace:
        return self.reply


class FakeClient:
    def __init__(self, *replies: SimpleNamespace) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.messages = self

    def stream(self, **kwargs: object) -> FakeStream:
        self.calls.append(kwargs)
        return FakeStream(self.replies.pop(0))


def judged(*replies: SimpleNamespace, unsupported: list[str] | None = None) -> dict:
    return judge_run(
        document(unsupported),
        KEY,
        EVIDENCE,
        LIBRARY,
        client=FakeClient(*replies),
        system="system",
    )


def test_run_item_kinds_come_from_the_run() -> None:
    items = {i["where"]: i["kind"] for i in run_items(FINAL)}
    # A finding keeps its declared kind and a timeline event follows its
    # time_kind; the attack verdict, the root cause, and the factors are conclusions.
    assert items == {
        "attack": "inference",
        "findings[0]": "observation",
        "timeline[0]": "observation",
        "root_cause": "inference",
        "contributing_factors[0]": "inference",
    }


def test_judge_input_gives_cited_text_and_no_labels() -> None:
    data = json.loads(judge_input(document(), KEY, EVIDENCE, LIBRARY))
    assert [k["id"] for k in data["key_items"]] == KEY_IDS
    assert data["cited"] == [
        {
            "ref": "dev/u1",
            "source": "case",
            "title": "2026-02-20T18:45:17Z investigating",
            "text": "Looking into it.",
        }
    ]
    assert "label" not in json.dumps(data)


def test_judge_input_refuses_a_citation_it_cannot_resolve() -> None:
    broken = document()
    broken["investigation"] = json.loads(json.dumps(FINAL).replace("dev/u1", "dev/u9"))
    with pytest.raises(ValueError, match="dev/u9"):
        judge_input(broken, KEY, EVIDENCE, LIBRARY)


def test_a_good_reply_is_a_judgment() -> None:
    record = judged(message(json.dumps(reply())))
    assert record["error"] is None
    assert record["judgment"]["key_items"]["root_cause"]["outcome"] == "supported-hit"
    assert record["judge"]["request_id"] == "req_test"
    assert record["usage"]["output_tokens"] == 50


def test_refusal_is_error_not_verdict() -> None:
    record = judged(message(json.dumps(reply()), stop_reason="refusal"))
    assert record == record | {"error": "refusal", "judgment": None}


def test_cut_reply_is_error() -> None:
    text = json.dumps(reply())[:100]
    assert judged(message(text, stop_reason="max_tokens"))["error"] == "max-tokens"


def test_empty_reply_is_error() -> None:
    assert judged(message(""))["error"] == "empty"


def test_schema_failure_is_error() -> None:
    bad = reply(key_items={"root_cause": {"run_items": [], "reason": "-", "outcome": "maybe"}})
    assert judged(message(json.dumps(bad)))["error"] == "schema"
    assert judged(message("not json"))["error"] == "schema"


def test_judgment_covers_every_key_item() -> None:
    missing = reply()
    del missing["key_items"]["timeline/0"]
    assert judged(message(json.dumps(missing)))["error"] == "schema"
    unknown = reply(key_items={"timeline/1": {"run_items": [], "reason": "-", "outcome": "missed"}})
    assert judged(message(json.dumps(unknown)))["error"] == "schema"
    no_item = reply()
    del no_item["run_items"]["findings[0]"]
    assert judged(message(json.dumps(no_item)))["error"] == "schema"


def test_outcome_must_fit_the_key_item() -> None:
    # A timeline event has no partial; an attack verdict has no partial either.
    bad = reply(
        key_items={
            "timeline/0": {"run_items": ["timeline[0]"], "reason": "-", "outcome": "partial"}
        }
    )
    assert judged(message(json.dumps(bad)))["error"] == "schema"


def test_inconsistent_reply_is_error() -> None:
    # A supported hit whose run items are all unsupported.
    bad = reply(run_items={"root_cause": {"reason": "-", "supported": False}})
    assert judged(message(json.dumps(bad)))["error"] == "inconsistent"
    # An unsupported hit whose run item is supported.
    bad = reply(
        key_items={
            "root_cause": {"run_items": ["root_cause"], "reason": "-", "outcome": "unsupported-hit"}
        }
    )
    assert judged(message(json.dumps(bad)))["error"] == "inconsistent"
    # A miss that names a run item, and a hit that names none.
    bad = reply(
        key_items={"timeline/0": {"run_items": ["timeline[0]"], "reason": "-", "outcome": "missed"}}
    )
    assert judged(message(json.dumps(bad)))["error"] == "inconsistent"
    bad = reply(
        key_items={"root_cause": {"run_items": [], "reason": "-", "outcome": "supported-hit"}}
    )
    assert judged(message(json.dumps(bad)))["error"] == "inconsistent"


def test_code_unsupported_items_cannot_be_judged_supported() -> None:
    schema = judgment_schema(KEY_IDS, run_items(FINAL), {"root_cause"})
    assert schema["properties"]["run_items"]["properties"]["root_cause"]["properties"][
        "supported"
    ] == {"type": "boolean", "const": False}
    bad = reply()
    record = judged(message(json.dumps(bad)), unsupported=["root_cause"])
    assert record["error"] == "schema"


def test_no_fallbacks_sent() -> None:
    client = FakeClient(message(json.dumps(reply())))
    judge_run(document(), KEY, EVIDENCE, LIBRARY, client=client, system="system")
    [call] = client.calls
    assert call["model"] == JUDGE_MODEL
    assert "fallbacks" not in call and "betas" not in call
    assert call["output_config"]["effort"] == "high"
    assert call["output_config"]["format"]["type"] == "json_schema"


def test_read_reply_checks_the_stop_reason_before_the_text() -> None:
    schema = judgment_schema(KEY_IDS, run_items(FINAL), set())
    with pytest.raises(JudgeError) as caught:
        read_reply(message(json.dumps(reply()), stop_reason="pause_turn"), schema, run_items(FINAL))
    assert caught.value.kind == "stop-pause_turn"


def frozen_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    prompt, rubric, frozen = tmp_path / "judge.md", tmp_path / "rubric.md", tmp_path / "f.json"
    prompt.write_text("Judge.\n", encoding="utf-8")
    rubric.write_text("# R\n\n## Outcomes\n\nO.\n\n## Support\n\nS.\n\n## Credit\n\nC.\n", "utf-8")
    return prompt, rubric, frozen


def test_system_prompt_takes_the_rubric_outcomes_and_support_only(tmp_path: Path) -> None:
    prompt, rubric, _ = frozen_files(tmp_path)
    text = system_prompt(prompt, rubric)
    assert "## Outcomes\n\nO." in text and "## Support\n\nS." in text
    assert "Credit" not in text


def test_judge_refuses_unfrozen_prompt(tmp_path: Path) -> None:
    prompt, rubric, frozen = frozen_files(tmp_path)
    with pytest.raises(NotFrozen):
        check_frozen(prompt, rubric, frozen)
    freeze(prompt, rubric, frozen)
    assert check_frozen(prompt, rubric, frozen) == system_prompt(prompt, rubric)
    prompt.write_text("Judge, leniently.\n", encoding="utf-8")
    with pytest.raises(NotFrozen):
        check_frozen(prompt, rubric, frozen)


def test_judge_all_refuses_unfrozen_prompt_before_any_call(tmp_path: Path) -> None:
    prompt, rubric, frozen = frozen_files(tmp_path)
    client = FakeClient(message(json.dumps(reply())))
    with pytest.raises(NotFrozen):
        judge_all(
            [{"run_id": "hindcast/dev/r1/a1", "status": "complete", "case_id": "dev"}],
            load_run=lambda entry: document(),
            load_case=lambda case_id: (KEY, EVIDENCE),
            library=LIBRARY,
            client=client,
            out_dir=tmp_path / "judgments",
            paths=(prompt, rubric, frozen),
        )
    assert client.calls == []


def run_judge_all(tmp_path: Path, entries: list[dict], client: FakeClient) -> dict:
    prompt, rubric, frozen = frozen_files(tmp_path)
    if not frozen.exists():
        freeze(prompt, rubric, frozen)
    return judge_all(
        entries,
        load_run=lambda entry: document(run_id=entry["run_id"]),
        load_case=lambda case_id: (KEY, EVIDENCE),
        library=LIBRARY,
        client=client,
        out_dir=tmp_path / "judgments",
        paths=(prompt, rubric, frozen),
    )


def test_judge_skips_no_result_attempts(tmp_path: Path) -> None:
    entries = [
        {"run_id": "hindcast/dev/r1/a1", "status": "no-result", "case_id": "dev"},
        {"run_id": "hindcast/dev/r1/a2", "status": "complete", "case_id": "dev"},
        {"run_id": "hindcast/dev/r2/a1", "status": "incomplete", "case_id": "dev"},
    ]
    client = FakeClient(message(json.dumps(reply())), message(json.dumps(reply())))
    counts = run_judge_all(tmp_path, entries, client)
    assert counts == {"judged": 2, "errors": 0, "kept": 0}
    written = sorted(
        p.relative_to(tmp_path / "judgments").as_posix()
        for p in (tmp_path / "judgments").rglob("*.json")
    )
    assert written == ["hindcast/dev/r1/a2.json", "hindcast/dev/r2/a1.json"]


def test_judge_all_keeps_a_judgment_and_retries_an_error(tmp_path: Path) -> None:
    entries = [
        {"run_id": "hindcast/dev/r1/a1", "status": "complete", "case_id": "dev"},
        {"run_id": "hindcast/dev/r2/a1", "status": "complete", "case_id": "dev"},
    ]
    first = FakeClient(message(json.dumps(reply())), message("", stop_reason="refusal"))
    assert run_judge_all(tmp_path, entries, first) == {"judged": 1, "errors": 1, "kept": 0}
    second = FakeClient(message(json.dumps(reply())))
    assert run_judge_all(tmp_path, entries, second) == {"judged": 1, "errors": 0, "kept": 1}
    record = json.loads((tmp_path / "judgments/hindcast/dev/r2/a1.json").read_text("utf-8"))
    assert record["error"] is None
    assert record["earlier_errors"] == ["refusal"]


def test_module_names_the_judge() -> None:
    assert judge.JUDGE_MODEL == "claude-opus-5-5"
    assert judge.EFFORT == "high"

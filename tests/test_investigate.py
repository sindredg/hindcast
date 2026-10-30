import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from hindcast import investigate
from hindcast.cases import Case, SourceFile
from hindcast.evidence import CaseEvidence, ChartEvidence, EvidenceUpdate, evidence_json
from hindcast.investigate import (
    ScoredCaseLocked,
    agent_turn,
    check_case_allowed,
    main,
    run_investigation,
    write_result,
)
from hindcast.tools import CaseTools, ToolError

EVIDENCE = CaseEvidence(
    case_id="dev",
    provider="Cloudflare",
    title="Slow pages",
    started_at="2026-02-20T18:45:16Z",
    updates=(
        EvidenceUpdate("dev/u1", "2026-02-20T18:45:17Z", "investigating", "Looking into it."),
        EvidenceUpdate("dev/u2", "2026-02-20T19:10:00Z", "resolved", None),
    ),
    dropped=(),
    charts=(ChartEvidence("dev/chart1", "c1.png", "Traffic dips.", "Traffic chart", False),),
)
U1 = {"source": "case", "ref": "dev/u1"}
FINAL = {
    "attack": {"verdict": "cannot tell", "reasoning": "r", "citations": [U1]},
    "findings": [
        {"id": "f1", "kind": "observation", "claim": "c", "rests_on": [], "citations": [U1]}
    ],
    "timeline": [{"time": "t", "time_kind": "stated", "event": "e", "citations": [U1]}],
    "root_cause": {"claim": "c", "rests_on": ["f1"], "citations": []},
    "contributing_factors": [{"claim": "c", "rests_on": ["f1"], "citations": []}],
    "open_questions": [{"question": "q", "why_open": "w"}],
}


def usage(tokens: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=1),
        output_tokens=2 * tokens,
    )


def call(name: str = "list_updates", call_id: str = "c1") -> SimpleNamespace:
    return SimpleNamespace(type="function_call", name=name, arguments="{}", call_id=call_id)


def response(*calls: SimpleNamespace, text: str = "", tokens: int = 10) -> SimpleNamespace:
    output = [*calls] + ([SimpleNamespace(type="message")] if text else [])
    return SimpleNamespace(
        id=None, status="completed", output=output, output_text=text, usage=usage(tokens)
    )


def final(document: object = FINAL) -> SimpleNamespace:
    return response(text=json.dumps(document))


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ScriptedTurn:
    """A fake model: returns scripted responses in order, records what it was sent."""

    def __init__(self, *script: object) -> None:
        self.script: list[Any] = list(script)
        self.inputs: list[tuple[list[dict], str | None, float]] = []

    def __call__(
        self, input_items: list[dict], previous_response_id: str | None, *, timeout: float
    ) -> Any:
        self.inputs.append((input_items, previous_response_id, timeout))
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        step.id = f"r{len(self.inputs)}"
        return step


class Tools(CaseTools):
    """Real case tools with a hook that runs on every call (a slow tool, a failing one)."""

    def __init__(self, on_call: Any = None) -> None:
        super().__init__(EVIDENCE)
        self.on_call = on_call

    def call(self, name: str, arguments: str) -> str:
        if self.on_call:
            self.on_call(name)
        return super().call(name, arguments)


def run(turn: ScriptedTurn, tools: CaseTools | None = None, clock: Clock | None = None) -> Any:
    return run_investigation(turn, tools or Tools(), case_id="dev", clock=clock or Clock())


def test_final_text_without_tool_calls_completes_and_checks_citations() -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["citations"].append({"source": "case", "ref": "dev/u99"})
    result = run(ScriptedTurn(final(document)))
    assert result.status == "complete"
    assert result.incomplete_reason is None
    assert result.investigation.findings[0].citations[0].ref == "dev/u1"
    assert [r.reason for r in result.checks.rejected_citations] == ["unknown"]


def test_tool_calls_are_executed_and_their_outputs_sent_back() -> None:
    turn = ScriptedTurn(response(call("list_updates", "c1"), call("list_charts", "c2")), final())
    result = run(turn)
    assert result.status == "complete"
    first_input, first_previous, _ = turn.inputs[0]
    assert first_input[0]["role"] == "user"
    assert first_previous is None
    second_input, second_previous, _ = turn.inputs[1]
    assert second_previous == "r1"
    assert [(i["type"], i["call_id"]) for i in second_input] == [
        ("function_call_output", "c1"),
        ("function_call_output", "c2"),
    ]
    assert json.loads(second_input[1]["output"])["charts"][0]["chart_id"] == "dev/chart1"
    assert result.usage.tool_calls == 2


def test_text_with_a_tool_call_is_not_final() -> None:
    turn = ScriptedTurn(response(call(), text=json.dumps(FINAL)), final())
    result = run(turn)
    assert result.status == "complete"
    assert len(turn.inputs) == 2
    assert result.usage.tool_calls == 1


def test_thirteenth_tool_call_is_tool_cap() -> None:
    turn = ScriptedTurn(*[response(call(call_id=f"c{n}")) for n in range(13)], final())
    result = run(turn)
    assert (result.status, result.incomplete_reason) == ("incomplete", "tool-cap")
    assert result.investigation is None
    assert result.usage.tool_calls == 12
    assert len(turn.inputs) == 13
    assert result.usage.model_calls == 13


def test_tool_cap_counts_calls_within_one_response() -> None:
    turn = ScriptedTurn(response(*[call(call_id=f"c{n}") for n in range(13)]), final())
    result = run(turn)
    assert result.incomplete_reason == "tool-cap"
    assert result.usage.tool_calls == 12
    assert len(turn.inputs) == 1


def test_time_cap_after_a_slow_tool_makes_no_further_model_call() -> None:
    clock = Clock()

    def slow(_: str) -> None:
        clock.now = 121.0

    turn = ScriptedTurn(response(call()), final())
    result = run(turn, Tools(slow), clock)
    assert (result.status, result.incomplete_reason) == ("incomplete", "time-cap")
    assert len(turn.inputs) == 1
    assert result.usage.model_calls == 1
    assert result.usage.seconds == 121.0


def test_no_tool_call_starts_after_the_time_cap() -> None:
    clock = Clock()
    ran: list[str] = []

    def slow(name: str) -> None:
        ran.append(name)
        clock.now = 121.0

    turn = ScriptedTurn(response(call("list_updates", "c1"), call("list_charts", "c2")))
    result = run(turn, Tools(slow), clock)
    assert result.incomplete_reason == "time-cap"
    assert ran == ["list_updates"]


def test_each_model_call_gets_the_remaining_budget_as_timeout() -> None:
    clock = Clock()

    def slow(_: str) -> None:
        clock.now = 50.0

    turn = ScriptedTurn(response(call()), final())
    run(turn, Tools(slow), clock)
    assert [timeout for _, _, timeout in turn.inputs] == [120.0, 70.0]


def test_model_call_timeout_is_time_cap() -> None:
    result = run(ScriptedTurn(TimeoutError("read timed out")))
    assert (result.status, result.incomplete_reason) == ("incomplete", "time-cap")
    assert result.usage.model_calls == 1


def test_tool_error_is_incomplete_with_tool_and_message() -> None:
    def fail(name: str) -> None:
        raise ToolError("boom")

    result = run(ScriptedTurn(response(call("list_charts")), final()), Tools(fail))
    assert (result.status, result.incomplete_reason) == (
        "incomplete",
        "tool-error: list_charts: boom",
    )
    assert result.usage.tool_calls == 0


def test_unexpected_tool_exception_is_a_tool_error_too() -> None:
    def fail(name: str) -> None:
        raise KeyError("updates")

    result = run(ScriptedTurn(response(call()), final()), Tools(fail))
    assert result.incomplete_reason == "tool-error: list_updates: 'updates'"


def test_unknown_tool_from_the_model_is_a_tool_error() -> None:
    result = run(ScriptedTurn(response(call("get_key")), final()))
    assert result.incomplete_reason == "tool-error: get_key: unknown tool 'get_key'"


def test_empty_final_text_is_empty_result() -> None:
    result = run(ScriptedTurn(response(text="")))
    assert (result.status, result.incomplete_reason) == ("incomplete", "empty-result")


def test_schema_failure_is_incomplete_with_the_error() -> None:
    result = run(ScriptedTurn(final({"attack": "none"})))
    assert result.status == "incomplete"
    assert result.incomplete_reason.startswith("schema: ")
    assert result.investigation is None


def test_model_error_propagates_and_writes_nothing() -> None:
    with pytest.raises(RuntimeError, match="service down"):
        run(ScriptedTurn(RuntimeError("service down")))


def test_response_without_usage_is_an_error() -> None:
    reply = final()
    reply.usage = None
    with pytest.raises(RuntimeError, match="usage"):
        run(ScriptedTurn(reply))


def test_usage_sums_tokens_over_turns() -> None:
    result = run(
        ScriptedTurn(response(call(), tokens=10), response(text=json.dumps(FINAL), tokens=5))
    )
    assert result.usage.model_calls == 2
    assert result.usage.tool_calls == 1
    assert result.usage.input_tokens == 15
    assert result.usage.cached_input_tokens == 2
    assert result.usage.output_tokens == 30


def test_cut_response_is_an_error() -> None:
    reply = final()
    reply.status = "incomplete"
    reply.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    with pytest.raises(RuntimeError, match="incomplete: max_output_tokens"):
        run(ScriptedTurn(reply))


# The command, its guards, and the result file.

SOURCE = SourceFile(
    "doc",
    "doc.json",
    "https://example.org",
    "l",
    "a",
    "0" * 64,
    "2026-10-26T08:00:00Z",
    "status-updates",
)
CASES = {
    "dev": Case(
        "dev", "Slow pages", "Cloudflare", "development", "2026-02-20T18:45:16Z", (SOURCE,)
    ),
    "inj": Case("inj", "Slow pages", "Cloudflare", "injection", "2026-02-20T18:45:16Z", (SOURCE,)),
    "show": Case("show", "Slow pages", "Cloudflare", "showcase", "2026-02-20T18:45:16Z", (SOURCE,)),
}
AGENT = {"name": "hindcast-investigator-gpt-6-luna", "version": "3"}
MODEL = {"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"}
PROVENANCE = {
    "prompt": {"blob": "b" * 40, "dirty": False},
    "code": {"commit": "c" * 40, "dirty": False},
    "evidence_sha256": "e" * 64,
}
NOW = datetime(2026, 10, 30, 12, 0, 1, tzinfo=UTC)


@pytest.mark.parametrize("case_id", ["dev", "inj"])
def test_development_and_injection_cases_are_allowed(case_id: str, tmp_path: Path) -> None:
    check_case_allowed(CASES[case_id], rubric_lock=tmp_path / "frozen.json")


def test_showcase_case_is_refused_without_the_rubric_lock(tmp_path: Path) -> None:
    with pytest.raises(ScoredCaseLocked, match=r"show.*rubric.*frozen\.json"):
        check_case_allowed(CASES["show"], rubric_lock=tmp_path / "frozen.json")


def test_showcase_case_runs_once_the_rubric_is_frozen(tmp_path: Path) -> None:
    lock = tmp_path / "frozen.json"
    lock.write_text("{}")
    check_case_allowed(CASES["show"], rubric_lock=lock)


def complete_result() -> Any:
    return run(ScriptedTurn(response(call()), final()))


def test_result_file_has_the_spec_shape(tmp_path: Path) -> None:
    path = write_result(
        complete_result(),
        case_id="dev",
        agent=AGENT,
        model=MODEL,
        provenance=PROVENANCE,
        out_dir=tmp_path,
        now=NOW,
    )
    assert path == tmp_path / "dev" / "20261030T120001Z-v3.json"
    written = json.loads(path.read_text("utf-8"))
    assert set(written) == {
        "case_id",
        "agent",
        "model",
        "provenance",
        "status",
        "incomplete_reason",
        "investigation",
        "checks",
        "usage",
    }
    assert (written["case_id"], written["agent"], written["model"]) == ("dev", AGENT, MODEL)
    assert written["provenance"] == PROVENANCE
    assert written["status"] == "complete"
    assert written["investigation"] == FINAL
    assert written["checks"] == {"rejected_citations": [], "unsupported": []}
    assert written["usage"]["tool_calls"] == 1


def test_result_file_is_never_overwritten(tmp_path: Path) -> None:
    kwargs: dict[str, Any] = {
        "case_id": "dev",
        "agent": AGENT,
        "model": MODEL,
        "provenance": PROVENANCE,
        "out_dir": tmp_path,
        "now": NOW,
    }
    write_result(complete_result(), **kwargs)
    with pytest.raises(FileExistsError):
        write_result(complete_result(), **kwargs)


def test_incomplete_result_has_null_investigation_and_the_reason(tmp_path: Path) -> None:
    result = run(ScriptedTurn(response(text="")))
    path = write_result(
        result,
        case_id="dev",
        agent=AGENT,
        model=MODEL,
        provenance=PROVENANCE,
        out_dir=tmp_path,
        now=NOW,
    )
    written = json.loads(path.read_text("utf-8"))
    assert (written["status"], written["incomplete_reason"]) == ("incomplete", "empty-result")
    assert written["investigation"] is None
    assert written["usage"]["model_calls"] == 1


class FakeClient:
    """Stands in for the project's OpenAI client; records each create call."""

    def __init__(self, *script: object) -> None:
        self.turn = ScriptedTurn(*script)
        self.options: list[dict] = []
        self.calls: list[dict] = []
        self.responses = SimpleNamespace(create=self.create)

    def with_options(self, **options: Any) -> FakeClient:
        self.options.append(options)
        return self

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.turn(kwargs["input"], kwargs.get("previous_response_id"), timeout=0)


def test_agent_turn_references_the_agent_version_and_passes_the_timeout() -> None:
    client = FakeClient(response(call()), final())
    turn = agent_turn(client, "hindcast-investigator-x", "3")
    turn([{"role": "user", "content": "go"}], None, timeout=120.0)
    turn([], "r1", timeout=70.0)
    reference = {"type": "agent_reference", "name": "hindcast-investigator-x", "version": "3"}
    assert [c["extra_body"] for c in client.calls] == [{"agent_reference": reference}] * 2
    assert "previous_response_id" not in client.calls[0]
    assert client.calls[1]["previous_response_id"] == "r1"
    # No retries: a retried call would run past the remaining budget.
    assert client.options == [
        {"max_retries": 0, "timeout": 120.0},
        {"max_retries": 0, "timeout": 70.0},
    ]


def test_agent_turn_maps_the_client_timeout_to_timeout_error() -> None:
    request = httpx2.Request("POST", "https://example.org/responses")
    client = FakeClient(openai.APITimeoutError(request=request))
    with pytest.raises(TimeoutError):
        agent_turn(client, "a", "1")([], None, timeout=1.0)


def stub_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: FakeClient
) -> list[tuple[str, dict]]:
    """Point main at stub cases, a temp evidence file and output, and fake Foundry calls."""
    from hindcast import models

    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "dev.json").write_bytes(evidence_json(EVIDENCE))
    monkeypatch.setattr(investigate, "load_cases", lambda: CASES)
    monkeypatch.setattr(investigate, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(investigate, "RUBRIC_LOCK", tmp_path / "rubric" / "frozen.json")
    for field in ("project_endpoint", "chat_deployment", "compare_deployment", "judge_deployment"):
        monkeypatch.setenv(f"HINDCAST_{field.upper()}", "gpt-6-luna")
    created: list[tuple[str, dict]] = []
    agents = SimpleNamespace(
        list_versions=lambda name, **_: [],
        create_version=lambda name, **kw: (
            created.append((name, kw)) or SimpleNamespace(version="3")
        ),
    )
    monkeypatch.setattr(models, "project_client", lambda: SimpleNamespace(agents=agents))
    monkeypatch.setattr(models, "openai_client", lambda: client)
    monkeypatch.setattr(models, "deployment_model", lambda d: ("gpt-6-luna", "2026-09-22"))
    return created


def test_main_writes_the_result_and_prints_counts_never_the_text(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["claim"] = "A SECRET CLAIM"
    client = FakeClient(response(call()), final(document))
    created = stub_command(monkeypatch, tmp_path, client)

    main(["dev", "--out", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "SECRET" not in out
    assert out.startswith("complete\n")
    assert "findings 1" in out
    assert "rejected citations 0" in out
    [(name, _)] = created
    assert name == "hindcast-investigator-gpt-6-luna"
    [path] = (tmp_path / "out" / "dev").glob("*-v3.json")
    written = json.loads(path.read_text("utf-8"))
    assert written["agent"] == {"name": "hindcast-investigator-gpt-6-luna", "version": "3"}
    assert written["model"] == MODEL
    assert (
        written["provenance"]["evidence_sha256"]
        == hashlib.sha256(evidence_json(EVIDENCE)).hexdigest()
    )
    assert set(written["provenance"]["prompt"]) >= {"dirty"}
    assert set(written["provenance"]["code"]) == {"commit", "dirty"}


def test_main_refuses_a_showcase_case_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(final())
    created = stub_command(monkeypatch, tmp_path, client)
    with pytest.raises(ScoredCaseLocked):
        main(["show", "--out", str(tmp_path / "out")])
    assert client.calls == []
    assert created == []


def test_main_fails_on_missing_evidence_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(final())
    stub_command(monkeypatch, tmp_path, client)
    with pytest.raises(FileNotFoundError, match="hindcast.ingest evidence"):
        main(["inj", "--out", str(tmp_path / "out")])
    assert client.calls == []

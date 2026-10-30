import json
from types import SimpleNamespace
from typing import Any

import pytest

from hindcast.evidence import CaseEvidence, ChartEvidence, EvidenceUpdate
from hindcast.investigate import run_investigation
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

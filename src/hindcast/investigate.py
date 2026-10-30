"""The investigator: a tool loop over one case, with a call cap and a time cap.

Hindcast runs the loop, not the service: one model call, run every function
call it returns, send the outputs back, repeat. The caps and the checks hold
here in code; the prompt only asks.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from hindcast.result import Checks, Investigation, ResultError, check_citations, parse_investigation
from hindcast.tools import CaseTools

TOOL_CAP = 12
TIME_CAP = 120.0
NO_CHECKS = Checks()
START = {
    "role": "user",
    "content": "Investigate this outage. Read the evidence with the tools before you answer.",
}


@dataclass(frozen=True)
class Usage:
    model_calls: int
    tool_calls: int
    seconds: float
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class RunResult:
    status: Literal["complete", "incomplete"]
    incomplete_reason: str | None
    investigation: Investigation | None
    checks: Checks
    usage: Usage


class Turn(Protocol):
    """One model call. Raises TimeoutError when the call runs past timeout seconds."""

    def __call__(
        self, input_items: list[dict], previous_response_id: str | None, *, timeout: float
    ) -> Any: ...


def run_investigation(
    turn: Turn,
    tools: CaseTools,
    *,
    case_id: str,
    tool_cap: int = TOOL_CAP,
    time_cap: float = TIME_CAP,
    clock: Callable[[], float] = time.monotonic,
) -> RunResult:
    start = clock()
    model_calls = tool_calls = input_tokens = cached_tokens = output_tokens = 0

    def end(
        reason: str | None, investigation: Investigation | None = None, checks: Checks = NO_CHECKS
    ) -> RunResult:
        usage = Usage(
            model_calls,
            tool_calls,
            round(clock() - start, 3),
            input_tokens,
            cached_tokens,
            output_tokens,
        )
        status = "complete" if reason is None else "incomplete"
        return RunResult(status, reason, investigation, checks, usage)

    items: list[dict] = [START]
    previous: str | None = None
    while True:
        remaining = time_cap - (clock() - start)
        if remaining <= 0:
            return end("time-cap")
        model_calls += 1
        try:
            # The remaining budget is the call's timeout, so no model call runs
            # past the cap.
            response = turn(items, previous, timeout=remaining)
        except TimeoutError:
            return end("time-cap")

        if response.status != "completed":
            # A cut answer (output limit, content filter) is a failed call, as
            # in hindcast.models: it propagates and nothing is written.
            reason = getattr(response.incomplete_details, "reason", None)
            raise RuntimeError(f"model response is {response.status}: {reason}")
        if response.usage is None:
            raise RuntimeError("model response carries no token usage")
        input_tokens += response.usage.input_tokens
        details = response.usage.input_tokens_details
        cached_tokens += details.cached_tokens if details else 0
        output_tokens += response.usage.output_tokens

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            # Only a response with no function calls is final; text next to a
            # call is ignored and the loop goes on.
            try:
                investigation = parse_investigation(response.output_text or "")
            except ResultError as error:
                return end(str(error))
            checked, checks = check_citations(investigation, tools.refs, case_id)
            return end(None, checked, checks)

        outputs: list[dict] = []
        for call in calls:
            if tool_calls >= tool_cap:
                return end("tool-cap")
            if clock() - start > time_cap:
                return end("time-cap")
            try:
                output = tools.call(call.name, call.arguments)
            except Exception as error:
                # Any failure inside a tool ends the run with its name and
                # message; the model never sees a half answer.
                return end(f"tool-error: {call.name}: {error}")
            tool_calls += 1
            outputs.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": output}
            )
        items, previous = outputs, response.id

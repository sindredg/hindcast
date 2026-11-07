"""Single search, single prompt: decision 0006's baseline next to the agent.

The command, not the model, calls list_updates, list_charts, and one library
search whose query is the case title and the first update the screens
showed. One model call then reads the three outputs, with no tools, and
answers in the investigator's schema. The screens, the citation checks, the
PII check, the time cap, and the model-error handling are the agent's, so
both are scored by the same rules.
"""

import json
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from hindcast import telemetry
from hindcast.agent import EFFORT
from hindcast.cases import Case
from hindcast.investigate import (
    NO_CHECKS,
    TIME_CAP,
    RunResult,
    Setup,
    Span,
    Turn,
    Usage,
    _mask_queries,
    run_investigation,
)
from hindcast.result import INVESTIGATION_SCHEMA
from hindcast.safety import PiiError, ScreenError
from hindcast.tools import MAX_QUERY


def direct_turn(client: Any, deployment: str, instructions: str) -> Turn:
    """A Turn that calls the deployment itself: instructions and schema, no tools."""
    import openai

    def turn(input_items: list[dict], previous_response_id: str | None, *, timeout: float) -> Any:
        options: dict[str, Any] = {
            "model": deployment,
            "instructions": instructions,
            "input": input_items,
            # Sent though it is the service default, as in hindcast.agent.
            "reasoning": {"effort": EFFORT},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "investigation",
                    "schema": INVESTIGATION_SCHEMA,
                    "strict": True,
                }
            },
        }
        if previous_response_id is not None:
            options["previous_response_id"] = previous_response_id
        try:
            # No retries, for the same reason as hindcast.investigate.agent_turn.
            return client.with_options(max_retries=0, timeout=timeout).responses.create(**options)
        except openai.APITimeoutError as error:
            raise TimeoutError(str(error)) from error

    return turn


def search_query(updates: dict) -> str:
    """The title and the first update text the screens showed; a withheld one is skipped."""
    title = updates["title"] if isinstance(updates["title"], str) else ""
    first = next((u["text"] for u in updates["updates"] if u.get("text")), "")
    return ". ".join(part for part in (title, first) if part)[:MAX_QUERY]


def run_single(
    setup: Setup,
    case: Case,
    *,
    clock: Callable[[], float] = time.monotonic,
    span: Span = telemetry.span,
) -> RunResult:
    tools, pii = setup.tools, setup.pii
    began = clock()
    shield = tools.shield
    screens_before = (shield.calls, shield.records) if shield else (0, 0)
    pii_before = (pii.calls, pii.records) if pii else (0, 0)
    record: list[dict] = []
    outputs: dict[str, Any] = {}

    def usage(base: Usage | None = None) -> Usage:
        # The whole run's screen and PII calls: the loop counts only its own.
        screens = (shield.calls, shield.records) if shield else (0, 0)
        checked = (pii.calls, pii.records) if pii else (0, 0)
        loop = base or Usage(0, 0, 0.0, 0, 0, 0)
        return replace(
            loop,
            tool_calls=loop.tool_calls + len(record),
            seconds=round(clock() - began, 3),
            screen_calls=screens[0] - screens_before[0],
            screen_records=screens[1] - screens_before[1],
            pii_calls=checked[0] - pii_before[0],
            pii_records=checked[1] - pii_before[1],
        )

    def stop(reason: str) -> RunResult:
        return RunResult("incomplete", reason, None, NO_CHECKS, usage(), tuple(record))

    with span("single_search", case_id=case.case_id):
        for name in ("list_updates", "list_charts", "search_library"):
            arguments = (
                json.dumps({"query": search_query(outputs["list_updates"])})
                if name == "search_library"
                else "{}"
            )
            left = TIME_CAP - (clock() - began)
            with span("tool_call", tool=name) as current:
                called = clock()
                try:
                    output = tools.call(name, arguments, timeout=left)
                except TimeoutError:
                    return stop("time-cap")
                except ScreenError as error:
                    return stop(f"screen-error: {error}")
                except Exception as error:
                    return stop(f"tool-error: {name}: {error}")
                seconds = round(clock() - called, 3)
                current.set_attribute("seconds", f"{seconds:.3f}")
            record.append({"name": name, "seconds": seconds, **tools.last_call})
            outputs[name] = json.loads(output)

        start = [{"role": "user", "content": json.dumps(outputs, ensure_ascii=False)}]
        result = run_investigation(
            setup.turn,
            tools,
            case_id=case.case_id,
            pii=pii,
            start=start,
            time_cap=TIME_CAP - (clock() - began),
            clock=clock,
            span=span,
        )
        checks = result.checks
        if result.status == "complete" and pii is not None:
            # The loop masks the queries it ran; this one ran before it.
            try:
                checks = replace(checks, pii=checks.pii + _mask_queries(record, pii, span))
            except (PiiError, TimeoutError) as error:
                return replace(
                    result,
                    status="incomplete",
                    incomplete_reason=f"pii-error: {error}",
                    investigation=None,
                    # As the agent arms' pii-error: no investigation, no checks (#64).
                    checks=NO_CHECKS,
                    usage=usage(result.usage),
                    tool_calls=tuple(record),
                )
        return replace(
            result,
            checks=checks,
            usage=usage(result.usage),
            tool_calls=tuple(record) + result.tool_calls,
        )

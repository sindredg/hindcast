"""The investigator: a tool loop over one case, with a call cap and a time cap.

    python -m hindcast.investigate <case_id>

writes build/investigations/<case_id>/<UTC time>-v<agent version>.json and
prints the status, the counts, and the usage, never the investigation text.

Hindcast runs the loop, not the service: one model call, run every function
call it returns, send the outputs back, repeat. The caps and the checks hold
here in code; the prompt only asks. The 12-call cap counts library searches
too.

The result file lists every tool call in order, with each search's query and
the refs it returned, never the hit text: a library citation is kept only for
a ref in that list (hindcast.result). The provenance names the library
registry, the index, and the embedding model the searches ran on.

Prompt Shields screens every tool item before the model reads it, and PII
detection checks the final answer before it is written (hindcast.tools,
hindcast.redact). Either service failing ends the run as incomplete
(screen-error, pii-error): an unscreened result never reaches the model, and
an unchecked answer is never written. The run, each model call, each tool
call, and the PII check are spans; their attributes are counts and times,
never text.
"""

import argparse
import functools
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from hindcast import telemetry
from hindcast.agent import (
    CHALLENGER_PROMPT,
    agent_name,
    challenger_definition,
    challenger_name,
    ensure_agent_version,
    load_definition,
    prompt_provenance,
)
from hindcast.cases import Case, load_cases
from hindcast.config import ModelSettings, SafetySettings, SearchSettings, load_settings
from hindcast.costs import PriceTable, load_prices, run_cost
from hindcast.evaluation.prior import _git
from hindcast.redact import redact_investigation
from hindcast.result import (
    Checks,
    Investigation,
    ResultError,
    check_citations,
    investigation_dict,
    parse_investigation,
)
from hindcast.safety import Pii, PiiError, ScreenError
from hindcast.search import search_library
from hindcast.tools import CaseTools, load_evidence

EVIDENCE_DIR = Path("build/evidence")
LIBRARY_REGISTRY = Path("data/library.yaml")
OUT_DIR = Path("build/investigations")
# Written by milestone 5 when the rubric is frozen.
RUBRIC_LOCK = Path("eval/rubric/frozen.json")
UNSCORED_ROLES = frozenset({"development", "injection"})
# What shapes a run besides the prompt; a change here marks the code dirty.
CODE_PATHS = ("src", "pyproject.toml", "uv.lock")

TOOL_CAP = 12
TIME_CAP = 120.0
# The PII check runs after the answer and outside the time cap: the cap
# bounds the investigation, and an answer at the cap still gets checked.
PII_TIMEOUT = 30.0
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
    # Screen and PII calls of the run, and the text records billing counts.
    screen_calls: int = 0
    screen_records: int = 0
    pii_calls: int = 0
    pii_records: int = 0
    # The price table holds short-context rates; the cost checks this against
    # the table's limit.
    max_call_input_tokens: int = 0


@dataclass(frozen=True)
class RunResult:
    status: Literal["complete", "incomplete"]
    incomplete_reason: str | None
    # An Investigation, or a hindcast.challenge Challenge for a challenge turn.
    investigation: Any
    checks: Checks
    usage: Usage
    tool_calls: tuple[dict, ...] = ()


class Span(Protocol):
    def __call__(self, name: str, /, **attributes: str) -> Any: ...


class Finish(Protocol):
    """Turn the model's final text into a checked result; raise ResultError or PiiError."""

    def __call__(
        self, text: str, tools: CaseTools, *, case_id: str, pii: Pii | None, span: Span
    ) -> tuple[Any, Checks]: ...


def finish_investigation(
    text: str, tools: CaseTools, *, case_id: str, pii: Pii | None, span: Span
) -> tuple[Investigation, Checks]:
    investigation = parse_investigation(text)
    checked, checks = check_citations(
        investigation,
        tools.refs,
        case_id,
        frozenset(tools.retrieved),
        shown=frozenset(tools.shown),
        withheld=frozenset(tools.withheld),
    )
    if pii is None:
        return checked, checks
    with span("pii") as current:
        redacted, findings = redact_investigation(checked, pii, timeout=PII_TIMEOUT)
        current.set_attribute("hits", str(len(findings)))
    return redacted, replace(checks, pii=findings)


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
    pii: Pii | None,
    start: list[dict] | None = None,
    finish: Finish = finish_investigation,
    tool_cap: int = TOOL_CAP,
    time_cap: float = TIME_CAP,
    clock: Callable[[], float] = time.monotonic,
    span: Span = telemetry.span,
    name: str = "investigation",
) -> RunResult:
    """Run the loop under the caps; pii=None only in tests that do not test it."""
    with span(name, case_id=case_id) as current:
        result = _loop(
            turn,
            tools,
            case_id=case_id,
            pii=pii,
            start=start or [START],
            finish=finish,
            tool_cap=tool_cap,
            time_cap=time_cap,
            clock=clock,
            span=span,
        )
        current.set_attribute("status", result.status)
        if result.incomplete_reason:
            # Only the prefix: the rest of a reason can carry a service message.
            current.set_attribute("incomplete_reason", result.incomplete_reason.split(":")[0])
        return result


def _loop(
    turn: Turn,
    tools: CaseTools,
    *,
    case_id: str,
    pii: Pii | None,
    start: list[dict],
    finish: Finish,
    tool_cap: int,
    time_cap: float,
    clock: Callable[[], float],
    span: Span,
) -> RunResult:
    began = clock()
    model_calls = tool_calls = input_tokens = cached_tokens = output_tokens = 0
    max_call_input = 0
    record: list[dict] = []
    shield = tools.shield
    screens_before = (shield.calls, shield.records) if shield else (0, 0)
    pii_before = (pii.calls, pii.records) if pii else (0, 0)

    def end(reason: str | None, result: Any = None, checks: Checks = NO_CHECKS) -> RunResult:
        screens = (shield.calls, shield.records) if shield else (0, 0)
        checked = (pii.calls, pii.records) if pii else (0, 0)
        usage = Usage(
            model_calls,
            tool_calls,
            round(clock() - began, 3),
            input_tokens,
            cached_tokens,
            output_tokens,
            screen_calls=screens[0] - screens_before[0],
            screen_records=screens[1] - screens_before[1],
            pii_calls=checked[0] - pii_before[0],
            pii_records=checked[1] - pii_before[1],
            max_call_input_tokens=max_call_input,
        )
        status = "complete" if reason is None else "incomplete"
        return RunResult(status, reason, result, checks, usage, tuple(record))

    items: list[dict] = start
    previous: str | None = None
    while True:
        remaining = time_cap - (clock() - began)
        if remaining <= 0:
            return end("time-cap")
        model_calls += 1
        with span("model_call", time_left=f"{remaining:.3f}") as current:
            called = clock()
            try:
                # The remaining budget is the call's timeout, so no model call
                # runs past the cap.
                response = turn(items, previous, timeout=remaining)
            except TimeoutError:
                current.set_attribute("seconds", f"{clock() - called:.3f}")
                current.set_attribute("timed_out", "true")
                return end("time-cap")
            current.set_attribute("seconds", f"{clock() - called:.3f}")

            if response.status != "completed":
                # A cut answer (output limit, content filter) is a failed call, as
                # in hindcast.models: it propagates and nothing is written.
                reason = getattr(response.incomplete_details, "reason", None)
                raise RuntimeError(f"model response is {response.status}: {reason}")
            if response.usage is None:
                raise RuntimeError("model response carries no token usage")
            input_tokens += response.usage.input_tokens
            max_call_input = max(max_call_input, response.usage.input_tokens)
            details = response.usage.input_tokens_details
            cached_tokens += details.cached_tokens if details else 0
            output_tokens += response.usage.output_tokens
            current.set_attribute("input_tokens", str(response.usage.input_tokens))
            current.set_attribute("output_tokens", str(response.usage.output_tokens))

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            # Only a response with no function calls is final; text next to a
            # call is ignored and the loop goes on.
            try:
                result, checks = finish(
                    response.output_text or "", tools, case_id=case_id, pii=pii, span=span
                )
            except ResultError as error:
                return end(str(error))
            except PiiError as error:
                return end(f"pii-error: {error}")
            except TimeoutError as error:
                return end(f"pii-error: {error}")
            return end(None, result, checks)

        outputs: list[dict] = []
        for call in calls:
            if tool_calls >= tool_cap:
                return end("tool-cap")
            left = time_cap - (clock() - began)
            if left <= 0:
                return end("time-cap")
            with span("tool_call", tool=call.name) as current:
                called = clock()
                try:
                    # The search and the screen get the time left, so a tool
                    # call cannot run past the cap either.
                    output = tools.call(call.name, call.arguments, timeout=left)
                except TimeoutError:
                    return end("time-cap")
                except ScreenError as error:
                    return end(f"screen-error: {error}")
                except Exception as error:
                    # Any other failure inside a tool ends the run with its
                    # name and message; the model never sees a half answer.
                    return end(f"tool-error: {call.name}: {error}")
                seconds = round(clock() - called, 3)
                current.set_attribute("seconds", f"{seconds:.3f}")
                current.set_attribute("withheld", str(len(tools.last_call.get("withheld", []))))
                current.set_attribute("screen_calls", str(tools.last_call.get("screen_calls", 0)))
            tool_calls += 1
            record.append({"name": call.name, "seconds": seconds, **tools.last_call})
            outputs.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": output}
            )
        items, previous = outputs, response.id


class ScoredCaseLocked(PermissionError):
    """A scored case before the rubric is frozen."""


def check_case_allowed(case: Case, rubric_lock: Path = RUBRIC_LOCK) -> None:
    # A sealed run is recorded by its hash, so it goes through hindcast.seal
    # only; a run from here would be one nobody could account for.
    if case.role == "sealed":
        raise ScoredCaseLocked(
            f"{case.case_id} is a sealed case: it runs only through python -m hindcast.seal"
        )
    # Reading a showcase investigation before the rubric exists would shape the
    # rubric around what the model produced.
    if case.role in UNSCORED_ROLES or rubric_lock.is_file():
        return
    raise ScoredCaseLocked(
        f"{case.case_id} is a {case.role} case: it runs only once the rubric is frozen "
        f"({rubric_lock} exists). Roadmap milestone 5 freezes the rubric before the first "
        "scored run."
    )


def agent_turn(client: Any, name: str, version: str) -> Turn:
    """A Turn over the project's OpenAI client that runs the given agent version."""
    import openai

    reference = {"agent_reference": {"type": "agent_reference", "name": name, "version": version}}

    def turn(input_items: list[dict], previous_response_id: str | None, *, timeout: float) -> Any:
        options: dict[str, Any] = {"input": input_items, "extra_body": reference}
        if previous_response_id is not None:
            options["previous_response_id"] = previous_response_id
        try:
            # No retries: the client retries timeouts and 429s by default, and
            # a retry would run past the remaining budget. A 429 fails the run.
            return client.with_options(max_retries=0, timeout=timeout).responses.create(**options)
        except openai.APITimeoutError as error:
            raise TimeoutError(str(error)) from error

    return turn


def code_provenance(repo: Path = Path(".")) -> dict:
    commit = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    status = _git(repo, "status", "--porcelain", "--", *CODE_PATHS)
    if commit.returncode != 0 or status.returncode != 0:
        raise RuntimeError("cannot read the Git state of the code")
    return {"commit": commit.stdout.strip(), "dirty": bool(status.stdout.strip())}


def write_result(
    result: RunResult,
    *,
    case_id: str,
    agent: dict,
    model: dict,
    provenance: dict,
    out_dir: Path,
    now: datetime,
    cost: dict | None = None,
) -> Path:
    document = {
        "case_id": case_id,
        "agent": agent,
        "model": model,
        "provenance": provenance,
        "status": result.status,
        "incomplete_reason": result.incomplete_reason,
        "investigation": investigation_dict(result.investigation),
        "checks": {
            "rejected_citations": [asdict(r) for r in result.checks.rejected_citations],
            "unsupported": list(result.checks.unsupported),
            "pii": [asdict(f) for f in result.checks.pii],
        },
        "tool_calls": list(result.tool_calls),
        "usage": asdict(result.usage),
        "cost": cost,
    }
    path = out_dir / case_id / f"{now:%Y%m%dT%H%M%SZ}-v{agent['version']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # "x" refuses to overwrite an earlier run.
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return path


def _all_citations(i: Investigation) -> list:
    items = [i.attack, *i.findings, *i.timeline, i.root_cause, *i.contributing_factors]
    return [c for item in items for c in item.citations]


def summary(result: RunResult, path: Path, cost: dict | None = None) -> str:
    """Status, counts, and usage. The investigation text stays in the file."""
    lines = [
        "complete" if result.status == "complete" else f"incomplete: {result.incomplete_reason}"
    ]
    i = result.investigation
    if i is not None:
        lines.append(
            f"findings {len(i.findings)}, timeline events {len(i.timeline)}, "
            f"factors {len(i.contributing_factors)}, open questions {len(i.open_questions)}"
        )
    searches = sum(1 for c in result.tool_calls if c["name"] == "search_library")
    library_kept = 0 if i is None else sum(1 for c in _all_citations(i) if c.source == "library")
    withheld = sum(len(c.get("withheld", [])) for c in result.tool_calls)
    lines.append(
        f"rejected citations {len(result.checks.rejected_citations)}, "
        f"unsupported {len(result.checks.unsupported)}, "
        f"searches {searches}, library citations kept {library_kept}"
    )
    lines.append(f"withheld items {withheld}, PII hits {len(result.checks.pii)}")
    u = result.usage
    lines.append(
        f"model calls {u.model_calls}, tool calls {u.tool_calls}, seconds {u.seconds}, "
        f"tokens in {u.input_tokens} (cached {u.cached_input_tokens}) out {u.output_tokens}"
    )
    if cost is not None:
        lines.append(
            f"cost {cost['currency']} {cost['total']} (price table v{cost['table_version']})"
            if "total" in cost
            else f"cost not priced: {cost['error']}"
        )
    lines.append(str(path))
    return "\n".join(lines)


@dataclass(frozen=True)
class Setup:
    """Everything a run needs, made ready before its first model call."""

    turn: Turn
    tools: CaseTools
    pii: Pii
    agent: dict
    model: dict
    provenance: dict
    prices: PriceTable
    # The run's embedder; its token count goes into the cost.
    embedder: Any = None

    def cost(self, usage: Usage) -> dict:
        """The run's cost, or the reason it has none; never a guessed price."""
        try:
            return run_cost(
                self.prices,
                self.model["deployment"],
                usage,
                embedding_tokens=self.embedder.tokens if self.embedder else 0,
            )
        except ValueError as error:
            # Written next to the result instead of raising: the run happened.
            return {
                "table_version": self.prices.version,
                "currency": self.prices.currency,
                "error": str(error),
            }


def prepare(
    case: Case,
    evidence_dir: Path | None = None,
    *,
    deployment: str | None = None,
    challenger: bool = False,
) -> Setup:
    """Read the evidence, make the agent version, and record what the run rests on.

    challenger=True makes the challenger agent instead (hindcast.challenge);
    deployment defaults to the configured chat deployment.
    """
    evidence_path = (evidence_dir or EVIDENCE_DIR) / f"{case.case_id}.json"
    evidence = load_evidence(evidence_path)
    # Missing search or safety settings fail here, before the agent version is made.
    search_settings = load_settings(SearchSettings)
    safety_settings = load_settings(SafetySettings)

    # Imported here so the loop and its tests do not need the SDK.
    from hindcast import index, models, safety

    # One embedder and one search client for the run; the case is bound here
    # and the model supplies only the query. The search client makes no
    # retries: a retry would run past the time left (issue #49).
    embed = index.embedder(search_settings.embedding_dimensions)
    search = functools.partial(
        search_library,
        case.case_id,
        embed=embed,
        client=index.clients(search_settings.search_index, retry_total=0)[1],
    )
    tools = CaseTools(evidence, search, safety.shield_client(safety_settings))

    deployment = deployment or load_settings(ModelSettings).chat_deployment
    prices = load_prices()
    if deployment not in prices.models:
        # Before the agent version and the first model call: a run with no
        # price would be written without a cost.
        raise KeyError(f"{deployment} is not in price table version {prices.version}")
    if challenger:
        definition, name = challenger_definition(deployment), challenger_name(deployment)
    else:
        definition, name = load_definition(deployment), agent_name(deployment)
    version = ensure_agent_version(models.project_client().agents, name, definition)
    model_name, model_version = models.deployment_model(deployment)
    provenance = {
        "prompt": prompt_provenance(CHALLENGER_PROMPT) if challenger else prompt_provenance(),
        "code": code_provenance(),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "library": {
            "registry": prompt_provenance(LIBRARY_REGISTRY),
            "index": search_settings.search_index,
            "search_api_version": index.SEARCH_API_VERSION,
            "embedding": index.embedding_model()
            | {"dimensions": search_settings.embedding_dimensions},
        },
    }
    return Setup(
        turn=agent_turn(models.openai_client(), name, version),
        tools=tools,
        pii=safety.pii_client(safety_settings),
        agent={"name": name, "version": version},
        model={"deployment": deployment, "name": model_name, "version": model_version},
        provenance=provenance,
        prices=prices,
        embedder=embed,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m hindcast.investigate")
    parser.add_argument("case_id")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.case_id not in cases:
        parser.error(f"unknown case {args.case_id!r}")
    case = cases[args.case_id]
    # Both refusals come before any cloud call.
    check_case_allowed(case, RUBRIC_LOCK)
    telemetry.configure(service=telemetry.INVESTIGATOR)
    setup = prepare(case)
    result = run_investigation(setup.turn, setup.tools, case_id=case.case_id, pii=setup.pii)
    cost = setup.cost(result.usage)
    path = write_result(
        result,
        case_id=case.case_id,
        agent=setup.agent,
        model=setup.model,
        provenance=setup.provenance,
        out_dir=args.out,
        now=datetime.now(UTC),
        cost=cost,
    )
    print(summary(result, path, cost))


if __name__ == "__main__":
    main()

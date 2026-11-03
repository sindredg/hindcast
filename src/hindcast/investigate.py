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
"""

import argparse
import functools
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from hindcast.agent import agent_name, ensure_agent_version, load_definition, prompt_provenance
from hindcast.cases import Case, load_cases
from hindcast.config import ModelSettings, SearchSettings, load_settings
from hindcast.evaluation.prior import _git
from hindcast.result import (
    Checks,
    Investigation,
    ResultError,
    check_citations,
    investigation_dict,
    parse_investigation,
)
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
    tool_calls: tuple[dict, ...] = ()


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
    record: list[dict] = []

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
        return RunResult(status, reason, investigation, checks, usage, tuple(record))

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
            checked, checks = check_citations(
                investigation,
                tools.refs,
                case_id,
                frozenset(tools.retrieved),
                shown=frozenset(tools.shown),
                withheld=frozenset(tools.withheld),
            )
            return end(None, checked, checks)

        outputs: list[dict] = []
        for call in calls:
            if tool_calls >= tool_cap:
                return end("tool-cap")
            left = time_cap - (clock() - start)
            if left <= 0:
                return end("time-cap")
            called = clock()
            try:
                # The search and the screen get the time left, so a tool call
                # cannot run past the cap either.
                output = tools.call(call.name, call.arguments, timeout=left)
            except Exception as error:
                # Any failure inside a tool ends the run with its name and
                # message; the model never sees a half answer.
                return end(f"tool-error: {call.name}: {error}")
            tool_calls += 1
            record.append(
                {"name": call.name, "seconds": round(clock() - called, 3), **tools.last_call}
            )
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
        },
        "tool_calls": list(result.tool_calls),
        "usage": asdict(result.usage),
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


def summary(result: RunResult, path: Path) -> str:
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
    lines.append(
        f"rejected citations {len(result.checks.rejected_citations)}, "
        f"unsupported {len(result.checks.unsupported)}, "
        f"searches {searches}, library citations kept {library_kept}"
    )
    u = result.usage
    lines.append(
        f"model calls {u.model_calls}, tool calls {u.tool_calls}, seconds {u.seconds}, "
        f"tokens in {u.input_tokens} (cached {u.cached_input_tokens}) out {u.output_tokens}"
    )
    lines.append(str(path))
    return "\n".join(lines)


@dataclass(frozen=True)
class Setup:
    """Everything a run needs, made ready before its first model call."""

    turn: Turn
    tools: CaseTools
    agent: dict
    model: dict
    provenance: dict


def prepare(case: Case, evidence_dir: Path | None = None) -> Setup:
    """Read the evidence, make the agent version, and record what the run rests on."""
    evidence_path = (evidence_dir or EVIDENCE_DIR) / f"{case.case_id}.json"
    evidence = load_evidence(evidence_path)
    # Missing search settings fail here, before the agent version is made.
    search_settings = load_settings(SearchSettings)

    # Imported here so the loop and its tests do not need the SDK.
    from hindcast import index, models

    # One embedder and one search client for the run; the case is bound here
    # and the model supplies only the query.
    search = functools.partial(
        search_library,
        case.case_id,
        embed=index.embedder(search_settings.embedding_dimensions),
        client=index.clients(search_settings.search_index)[1],
    )
    tools = CaseTools(evidence, search)

    deployment = load_settings(ModelSettings).chat_deployment
    definition = load_definition(deployment)
    name = agent_name(deployment)
    version = ensure_agent_version(models.project_client().agents, name, definition)
    model_name, model_version = models.deployment_model(deployment)
    provenance = {
        "prompt": prompt_provenance(),
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
        agent={"name": name, "version": version},
        model={"deployment": deployment, "name": model_name, "version": model_version},
        provenance=provenance,
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
    setup = prepare(case)
    result = run_investigation(setup.turn, setup.tools, case_id=case.case_id)
    path = write_result(
        result,
        case_id=case.case_id,
        agent=setup.agent,
        model=setup.model,
        provenance=setup.provenance,
        out_dir=args.out,
        now=datetime.now(UTC),
    )
    print(summary(result, path))


if __name__ == "__main__":
    main()

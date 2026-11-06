"""The investigator: a tool loop over one case, with a call cap and a time cap.

    python -m hindcast.investigate <case_id> [--arm <arm>] [--deployment <name>]
        [--screens on|off] [--out <dir>]

writes build/investigations/<case_id>/<UTC time>-v<agent version>.json (a
single-search run, which has no agent version: <UTC time>-single-search.json)
and prints the status, the counts, and the usage, never the investigation
text. --screens off is refused for every case that is not an injection copy.

Hindcast runs the loop, not the service: one model call, run every function
call it returns, send the outputs back, repeat. The caps and the checks hold
here in code; the prompt only asks. The 12-call cap counts library searches
too.

The result file lists every tool call in order, with each search's query and
the refs it returned, never the hit text: a library citation is kept only for
a ref in that list (hindcast.result). The provenance names the library
registry, the index, the embedding model the searches ran on, and the count
and hash of every chunk the case's filter returns.

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
    EFFORT,
    agent_name,
    challenger_definition,
    challenger_name,
    ensure_agent_version,
    prompt_provenance,
)
from hindcast.arms import ARMS, Arm, agent_variant, arm_definition
from hindcast.cases import Case, load_cases
from hindcast.config import ModelSettings, SafetySettings, SearchSettings, load_settings
from hindcast.costs import PriceTable, load_prices, run_cost
from hindcast.evaluation.prior import _git
from hindcast.provenance import image_manifest
from hindcast.redact import redact_fields, redact_investigation
from hindcast.result import (
    Checks,
    Investigation,
    ResultError,
    check_citations,
    investigation_dict,
    parse_investigation,
)
from hindcast.safety import Pii, PiiError, ScreenError
from hindcast.search import case_chunks, contents_digest, search_library
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
# What a search query is replaced by when PII detection could not check it.
QUERY_UNCHECKED = "[unchecked: PII detection failed]"
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
    # Part of output_tokens, as the service reports it per response (#26).
    reasoning_tokens: int = 0


@dataclass(frozen=True)
class RunResult:
    status: Literal["complete", "incomplete"]
    incomplete_reason: str | None
    # An Investigation, or a hindcast.challenge Challenge for a challenge turn.
    investigation: Any
    checks: Checks
    usage: Usage
    tool_calls: tuple[dict, ...] = ()
    # The reasoning effort each response says it applied, distinct, in order.
    efforts: tuple[str, ...] = ()


def no_result(result: RunResult) -> bool:
    """True when an attempt produced nothing to keep, so another may follow.

    A time cap on the first call writes a result with no model output, and a
    failed model call ends the run with no investigation (decision 0017
    rule 6; the evaluation batch uses the same rule).
    """
    return result.usage.output_tokens == 0 or (result.incomplete_reason or "").startswith(
        "model-error"
    )


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
    max_call_input = reasoning_tokens = 0
    efforts: list[str] = []
    record: list[dict] = []
    shield = tools.shield
    screens_before = (shield.calls, shield.records) if shield else (0, 0)
    pii_before = (pii.calls, pii.records) if pii else (0, 0)

    def end(reason: str | None, result: Any = None, checks: Checks = NO_CHECKS) -> RunResult:
        if pii is not None and any("query" in c for c in record):
            # Every query the result keeps is checked, whatever ended the run
            # (decision 0021), so an incomplete run's queries are masked too.
            try:
                checks = replace(checks, pii=checks.pii + _mask_queries(record, pii, span))
            except (PiiError, TimeoutError) as error:
                # An unchecked query is never written: each is replaced, and
                # the run ends incomplete with the error on its reason.
                for c in record:
                    if "query" in c:
                        c["query"] = QUERY_UNCHECKED
                result, checks = None, NO_CHECKS
                failed = f"pii-error: {error}"
                reason = failed if reason is None else f"{reason}; {failed}"
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
            reasoning_tokens=reasoning_tokens,
        )
        status = "complete" if reason is None else "incomplete"
        return RunResult(status, reason, result, checks, usage, tuple(record), tuple(efforts))

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
            except Exception as error:
                # A 429, a refused request, a dropped connection: the run ends
                # with a record and the usage so far (#23). Only the type is
                # kept, since the message can carry the service's response.
                current.set_attribute("seconds", f"{clock() - called:.3f}")
                return end(f"model-error: {type(error).__name__}")
            current.set_attribute("seconds", f"{clock() - called:.3f}")
            # The effort the agent definition asks for is a request; the
            # response says what ran (#26).
            effort = getattr(getattr(response, "reasoning", None), "effort", None)
            if effort and effort not in efforts:
                efforts.append(effort)

            if response.usage is not None:
                # Counted before the status check: a cut answer was billed too.
                input_tokens += response.usage.input_tokens
                max_call_input = max(max_call_input, response.usage.input_tokens)
                details = response.usage.input_tokens_details
                cached_tokens += details.cached_tokens if details else 0
                output_tokens += response.usage.output_tokens
                out_details = getattr(response.usage, "output_tokens_details", None)
                reasoning_tokens += getattr(out_details, "reasoning_tokens", 0) or 0
                current.set_attribute("input_tokens", str(response.usage.input_tokens))
                current.set_attribute("output_tokens", str(response.usage.output_tokens))
            if response.status != "completed":
                # A cut answer (output limit, content filter) is a failed call.
                reason = getattr(response.incomplete_details, "reason", None)
                return end(f"model-error: response {response.status}: {reason}")
            if response.usage is None:
                return end("model-error: no usage")

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


def _mask_queries(record: list[dict], pii: Pii, span: Span) -> tuple:
    """Mask personal data in the model's search queries, which the result file keeps."""
    queries = [(f"tool_calls[{n}].query", c["query"]) for n, c in enumerate(record) if "query" in c]
    if not queries:
        return ()
    with span("pii", fields="queries") as current:
        masked, hits = redact_fields(queries, pii, timeout=PII_TIMEOUT)
        current.set_attribute("hits", str(len(hits)))
    for path, text in masked.items():
        record[int(path[len("tool_calls[") : path.index("]")])]["query"] = text
    return hits


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
    try:
        commit = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
        status = _git(repo, "status", "--porcelain", "--", *CODE_PATHS)
    except FileNotFoundError:
        # No git executable, as in the deployed image.
        commit = status = None
    if commit is None or status is None or commit.returncode != 0 or status.returncode != 0:
        # In the image the commit and tree come from CI (decision 0028); the
        # files are the commit's files, so the code is not dirty.
        manifest = image_manifest()
        if manifest is None:
            raise RuntimeError("cannot read the Git state of the code")
        return {
            "commit": manifest["commit"],
            "dirty": False,
            "src_tree": manifest["src_tree"],
            "source": "image",
        }
    # The tree's hash survives a rebase or a squash merge, which rewrite the
    # commit (#39); it names the code only when dirty is false.
    tree = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD:src")
    if tree.returncode != 0:
        raise RuntimeError("cannot read the tree of src/")
    return {
        "commit": commit.stdout.strip(),
        "dirty": bool(status.stdout.strip()),
        "src_tree": tree.stdout.strip(),
    }


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
    filename: str | None = None,
    run_id: str | None = None,
) -> Path:
    """Write the result once; filename defaults to <UTC time>-v<agent version>.json."""
    document: dict[str, Any] = {} if run_id is None else {"run_id": run_id}
    document |= {
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
        "reasoning": {"requested": EFFORT, "applied": list(result.efforts)},
        "cost": cost,
    }
    path = out_dir / case_id / (filename or f"{now:%Y%m%dT%H%M%SZ}-v{agent['version']}.json")
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
    # Distinct refs: a second listing, or a hit in a later search, returns the same ref again.
    withheld = len({r for c in result.tool_calls for r in c.get("withheld", [])})
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
    arm: Arm = ARMS["hindcast"],
    screens: bool = True,
) -> Setup:
    """Read the evidence, make the agent version, and record what the run rests on.

    challenger=True makes the challenger agent instead (hindcast.challenge).
    The arm (hindcast.arms) sets the prompt, the tools, and the deployment,
    which defaults to the configured chat or comparison deployment. A
    single-search arm makes no agent: its turn calls the deployment itself.
    screens=False runs without Prompt Shields, for an injection case only.
    """
    if not screens and case.role != "injection":
        # The second injection layer measures the model without the screens
        # (decision 0025); every other run is screened, so this is refused
        # before any cloud call.
        raise PermissionError(
            f"{case.case_id} is a {case.role} case: screens off is for injection cases only"
        )
    evidence_path = (evidence_dir or EVIDENCE_DIR) / f"{case.case_id}.json"
    evidence = load_evidence(evidence_path)
    # Missing search or safety settings fail here, before the agent version is made.
    search_settings = load_settings(SearchSettings)
    safety_settings = load_settings(SafetySettings)

    # Imported here so the loop and its tests do not need the SDK.
    from hindcast import index, models, safety

    # One embedder and one search client for the run; the case is bound here
    # and the model supplies only the query. The search client makes no
    # retries: a retry would run past the time left (issue #49). The
    # library-off arm binds none, so no search can run.
    embed = search = contents = None
    index_name = search_settings.search_index
    if arm.library:
        embed = index.embedder(search_settings.embedding_dimensions)
        bound: dict[str, Any] = {}
        if case.role == "injection":
            # An injection case searches its own index, which holds the
            # planted pages; the production index never does (decision 0025).
            from hindcast import cases as registry
            from hindcast import injection
            from hindcast.library import load_library
            from hindcast.search import extract_refs

            known = registry.load_cases()
            index_name = injection.INDEX
            bound = {
                "cases": known,
                "library": injection.injection_library(
                    load_library(LIBRARY_REGISTRY, known), known
                ),
                "refs": extract_refs() | extract_refs(injection.EXTRACTS_DIR),
            }
        search_client = index.clients(index_name, retry_total=0)[1]
        search = functools.partial(
            search_library, case.case_id, embed=embed, client=search_client, **bound
        )
        # What the case's searches can reach in this index, recorded with the
        # run: a rebuild under the same name changes the hash (#47).
        listing = case_chunks(
            case.case_id,
            cases=bound.get("cases"),
            library=bound.get("library"),
            client=search_client,
        )
        if not listing:
            raise ValueError(f"{case.case_id}: {index_name} returned no library chunks")
        contents = contents_digest(listing)
    shield = safety.shield_client(safety_settings) if screens else None
    tools = CaseTools(evidence, search, shield)

    model_settings = load_settings(ModelSettings)
    deployment = deployment or (
        model_settings.compare_deployment
        if arm.deployment == "compare"
        else model_settings.chat_deployment
    )
    prices = load_prices()
    if deployment not in prices.models:
        # Before the agent version and the first model call: a run with no
        # price would be written without a cost.
        raise KeyError(f"{deployment} is not in price table version {prices.version}")
    if challenger or arm.kind == "agent":
        if challenger:
            definition, name = challenger_definition(deployment), challenger_name(deployment)
        else:
            definition = arm_definition(arm, deployment)
            name = agent_name(deployment, agent_variant(arm))
        version = ensure_agent_version(models.project_client().agents, name, definition)
        turn = agent_turn(models.openai_client(), name, version)
        agent: dict = {"name": name, "version": version}
    else:
        from hindcast.single import direct_turn

        instructions = arm.prompt.read_text(encoding="utf-8")
        turn = direct_turn(models.openai_client(), deployment, instructions)
        agent = {"name": None, "version": None}
    model_name, model_version = models.deployment_model(deployment)
    provenance = {
        "prompt": prompt_provenance(CHALLENGER_PROMPT if challenger else arm.prompt),
        "code": code_provenance(),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "library": {
            "registry": prompt_provenance(LIBRARY_REGISTRY),
            "index": index_name,
            "search_api_version": index.SEARCH_API_VERSION,
            "embedding": index.embedding_model()
            | {"dimensions": search_settings.embedding_dimensions},
            "contents": contents,
        }
        if arm.library
        else None,
    }
    if not challenger:
        provenance["arm"] = arm.name
    provenance["screens"] = screens
    return Setup(
        turn=turn,
        tools=tools,
        pii=safety.pii_client(safety_settings),
        agent=agent,
        model={"deployment": deployment, "name": model_name, "version": model_version},
        provenance=provenance,
        prices=prices,
        embedder=embed,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m hindcast.investigate")
    parser.add_argument("case_id")
    parser.add_argument("--arm", choices=sorted(ARMS), default="hindcast")
    parser.add_argument("--deployment", help="overrides the arm's configured deployment")
    parser.add_argument(
        "--screens", choices=("on", "off"), default="on", help="off: injection cases only"
    )
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.case_id not in cases:
        parser.error(f"unknown case {args.case_id!r}")
    case = cases[args.case_id]
    # Both refusals come before any cloud call.
    check_case_allowed(case, RUBRIC_LOCK)
    arm = ARMS[args.arm]
    telemetry.configure(service=telemetry.INVESTIGATOR)
    setup = prepare(case, deployment=args.deployment, arm=arm, screens=args.screens == "on")
    if arm.kind == "single":
        from hindcast.single import run_single

        result = run_single(setup, case)
    else:
        result = run_investigation(setup.turn, setup.tools, case_id=case.case_id, pii=setup.pii)
    cost = setup.cost(result.usage)
    now = datetime.now(UTC)
    path = write_result(
        result,
        case_id=case.case_id,
        agent=setup.agent,
        model=setup.model,
        provenance=setup.provenance,
        out_dir=args.out,
        now=now,
        cost=cost,
        # A single-search run has no agent version to name the file by.
        filename=None if arm.kind == "agent" else f"{now:%Y%m%dT%H%M%SZ}-{arm.name}.json",
    )
    print(summary(result, path, cost))


if __name__ == "__main__":
    main()

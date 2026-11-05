"""A challenge: a follow-up turn that checks one finding against a reader's question.

    python -m hindcast.challenge <result file> <finding id> <question>

writes <result dir>/challenges/<UTC time>-<finding id>.json and prints the
status, the verdict, the counts, and the cost, never the answer text.

The question is screened by Prompt Shields as a user prompt first: a flagged
question is refused with no model call. It is then PII-masked, and the
challenger agent gets the finding, the findings it rests on, and the masked
question. The challenger runs the same loop as an investigation with the same
three tools on the same case, under smaller caps, with the same screen and
the same citation rules; its answer is PII-masked before it is written.

A library ref is citable when the challenge's own search showed it or the
original run's did, so the finding's own library citations stay citable
without a second search. A case ref is citable only when the challenge read
it itself: the answer cites what it read.
"""

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from hindcast import investigate, telemetry
from hindcast.investigate import PII_TIMEOUT, Span, Turn, Usage, run_investigation
from hindcast.redact import redact_fields
from hindcast.result import (
    FINDING_ID,
    Challenge,
    Checks,
    Finding,
    PiiFinding,
    StoredResult,
    challenge_dict,
    check_challenge_citations,
    load_result,
    parse_challenge,
)
from hindcast.safety import Pii, PiiError, ScreenError
from hindcast.tools import CaseTools

# At or below the investigation's 12 calls and 120 seconds: a challenge checks
# one finding, it does not redo the investigation.
CHALLENGE_TOOL_CAP = 6
CHALLENGE_TIME_CAP = 90.0
MAX_QUESTION = 1000
SCREEN_TIMEOUT = 15.0
CHALLENGES = "challenges"


@dataclass(frozen=True)
class ChallengeResult:
    status: Literal["complete", "incomplete", "refused"]
    reason: str | None
    # PII-masked; empty when the question was refused or could not be checked.
    question: str
    challenge: Challenge | None
    checks: Checks
    usage: Usage
    tool_calls: tuple[dict, ...] = ()


def _findings(stored: StoredResult, finding_id: str) -> tuple[Finding, dict[str, Finding]]:
    """The challenged finding and every finding by ID."""
    if stored.status != "complete" or stored.investigation is None:
        raise ValueError("the result is incomplete; only a complete result can be challenged")
    by_id = {f.id: f for f in stored.investigation.findings}
    if finding_id not in by_id:
        raise ValueError(f"the result has no finding {finding_id!r}")
    return by_id[finding_id], by_id


def validate(stored: StoredResult, finding_id: str, question: str) -> None:
    """Every refusal that needs no cloud call."""
    if not FINDING_ID.fullmatch(finding_id):
        # The ID is model output and names the challenge file.
        raise ValueError(f"finding ID {finding_id!r} is not a file-safe ID")
    _findings(stored, finding_id)
    if "screen_calls" not in stored.usage:
        # Results from before Prompt Shields: their library refs were never
        # screened, and a challenge may cite them.
        raise ValueError("the result ran without screens; only a screened result can be challenged")
    if not question.strip() or len(question) > MAX_QUESTION:
        raise ValueError(f"the question must be 1 to {MAX_QUESTION} characters")


def _finding_dict(finding: Finding) -> dict:
    return {
        "id": finding.id,
        "kind": finding.kind,
        "claim": finding.claim,
        "rests_on": list(finding.rests_on),
        "citations": [{"source": c.source, "ref": c.ref} for c in finding.citations],
    }


def challenge_start(stored: StoredResult, finding_id: str, question: str) -> list[dict]:
    """The one user message a challenge starts from."""
    finding, by_id = _findings(stored, finding_id)
    content = {
        "finding": _finding_dict(finding),
        "rests_on": [_finding_dict(by_id[i]) for i in finding.rests_on if i in by_id],
        "question": question,
    }
    return [{"role": "user", "content": json.dumps(content, ensure_ascii=False)}]


def _original(stored: StoredResult) -> tuple[frozenset[str], frozenset[str]]:
    """The library refs the original run's searches showed, and every ref it withheld."""
    refs: set[str] = set()
    withheld: set[str] = set()
    for call in stored.tool_calls:
        if call.get("name") == "search_library":
            refs |= set(call.get("refs", []))
        withheld |= set(call.get("withheld", []))
    return frozenset(refs), frozenset(withheld)


def _finish(original_refs: frozenset[str], original_withheld: frozenset[str]) -> Callable:
    def finish(
        text: str, tools: CaseTools, *, case_id: str, pii: Pii | None, span: Span
    ) -> tuple[Challenge, Checks]:
        parsed = parse_challenge(text)
        checked, checks = check_challenge_citations(
            parsed,
            tools.refs,
            case_id,
            retrieved=frozenset(tools.retrieved) | original_refs,
            shown=frozenset(tools.shown),
            withheld=frozenset(tools.withheld) | original_withheld,
        )
        if pii is None:
            return checked, checks
        fields = [("answer", checked.answer), ("revised_claim", checked.revised_claim)]
        with span("pii") as current:
            masked, findings = redact_fields(fields, pii, timeout=PII_TIMEOUT)
            current.set_attribute("hits", str(len(findings)))
        redacted = replace(
            checked,
            answer=masked.get("answer", checked.answer),
            revised_claim=masked.get("revised_claim", checked.revised_claim),
        )
        return redacted, replace(checks, pii=findings)

    return finish


def run_challenge(
    turn: Turn,
    tools: CaseTools,
    stored: StoredResult,
    finding_id: str,
    question: str,
    *,
    pii: Pii | None,
    clock: Callable[[], float] = time.monotonic,
    span: Span = telemetry.span,
) -> ChallengeResult:
    validate(stored, finding_id, question)
    # One trace per challenge: the question's screen and PII check run before
    # the loop, under the same root span.
    with span("challenge", case_id=stored.case_id, finding_id=finding_id) as current:
        result = _challenge(turn, tools, stored, finding_id, question, pii, clock, span)
        current.set_attribute("status", result.status)
        if result.reason:
            current.set_attribute("reason", result.reason.split(":")[0])
        return result


def _challenge(
    turn: Turn,
    tools: CaseTools,
    stored: StoredResult,
    finding_id: str,
    question: str,
    pii: Pii | None,
    clock: Callable[[], float],
    span: Span,
) -> ChallengeResult:
    shield = tools.shield
    counters = (
        (shield.calls, shield.records) if shield else (0, 0),
        (pii.calls, pii.records) if pii else (0, 0),
    )

    def usage(base: Usage | None = None) -> Usage:
        # The question's screen and PII calls happen before the loop, so the
        # run's usage counts from here, not from the loop's start.
        screens = (shield.calls, shield.records) if shield else (0, 0)
        checked = (pii.calls, pii.records) if pii else (0, 0)
        return replace(
            base or Usage(0, 0, 0.0, 0, 0, 0),
            screen_calls=screens[0] - counters[0][0],
            screen_records=screens[1] - counters[0][1],
            pii_calls=checked[0] - counters[1][0],
            pii_records=checked[1] - counters[1][1],
        )

    def stop(status: Literal["incomplete", "refused"], reason: str) -> ChallengeResult:
        return ChallengeResult(status, reason, "", None, Checks(), usage())

    if shield is not None:
        try:
            with span("screen", kind="question") as current:
                flagged = shield.prompt(question, timeout=SCREEN_TIMEOUT)
                current.set_attribute("flagged", str(flagged).lower())
        except (ScreenError, TimeoutError) as error:
            return stop("incomplete", f"screen-error: {error}")
        if flagged:
            return stop("refused", "prompt-shields")

    question_hits: tuple[PiiFinding, ...] = ()
    if pii is not None:
        try:
            masked, question_hits = redact_fields(
                [("question", question)], pii, timeout=PII_TIMEOUT
            )
        except (PiiError, TimeoutError) as error:
            return stop("incomplete", f"pii-error: {error}")
        question = masked.get("question", question)

    run = run_investigation(
        turn,
        tools,
        case_id=stored.case_id,
        pii=pii,
        start=challenge_start(stored, finding_id, question),
        finish=_finish(*_original(stored)),
        tool_cap=CHALLENGE_TOOL_CAP,
        time_cap=CHALLENGE_TIME_CAP,
        clock=clock,
        span=span,
        name="challenge_loop",
    )
    checks = replace(run.checks, pii=question_hits + run.checks.pii)
    return ChallengeResult(
        run.status,
        run.incomplete_reason,
        question,
        run.investigation,
        checks,
        usage(run.usage),
        run.tool_calls,
    )


def write_challenge(
    result: ChallengeResult,
    *,
    result_path: Path,
    finding_id: str,
    agent: dict,
    model: dict,
    provenance: dict,
    cost: dict | None,
    now: datetime,
) -> Path:
    document = {
        "result_file": result_path.name,
        "finding_id": finding_id,
        "question": result.question,
        "agent": agent,
        "model": model,
        "provenance": provenance,
        "status": result.status,
        "reason": result.reason,
        "challenge": challenge_dict(result.challenge),
        "checks": {
            "rejected_citations": [asdict(r) for r in result.checks.rejected_citations],
            "unsupported": list(result.checks.unsupported),
            "pii": [asdict(f) for f in result.checks.pii],
        },
        "tool_calls": list(result.tool_calls),
        "usage": asdict(result.usage),
        "cost": cost,
    }
    folder = result_path.parent / CHALLENGES
    path = folder / f"{now:%Y%m%dT%H%M%SZ}-{finding_id}.json"
    # validate() refuses such an ID before any call; this holds for every caller.
    if not FINDING_ID.fullmatch(finding_id) or path.resolve().parent != folder.resolve():
        raise ValueError(f"finding ID {finding_id!r} would name a file outside {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    # "x" refuses to overwrite an earlier challenge.
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return path


def summary(result: ChallengeResult, path: Path, cost: dict | None) -> str:
    """Status, verdict, counts, and cost. The question and the answer stay in the file."""
    head = result.challenge.verdict if result.challenge else result.reason
    lines = [f"{result.status}: {head}"]
    kept = len(result.challenge.citations) if result.challenge else 0
    lines.append(
        f"citations kept {kept}, rejected {len(result.checks.rejected_citations)}, "
        f"unsupported {len(result.checks.unsupported)}, PII hits {len(result.checks.pii)}"
    )
    u = result.usage
    lines.append(
        f"model calls {u.model_calls}, tool calls {u.tool_calls}, seconds {u.seconds}, "
        f"screen calls {u.screen_calls}"
    )
    if cost is not None:
        lines.append(
            f"cost {cost['currency']} {cost['total']} (price table v{cost['table_version']})"
            if "total" in cost
            else f"cost not priced: {cost['error']}"
        )
    lines.append(str(path))
    return "\n".join(lines)


def challenge_and_store(
    result_path: Path, finding_id: str, question: str
) -> tuple[ChallengeResult, Path, dict]:
    """Challenge one finding of a stored result and write the challenge next to it.

    Used by the command and by the page when it runs locally with
    HINDCAST_LIVE=1. Every refusal comes before any cloud call.
    """
    stored = load_result(result_path)
    validate(stored, finding_id, question)
    cases = investigate.load_cases()
    if stored.case_id not in cases:
        raise ValueError(f"unknown case {stored.case_id!r}")
    case = cases[stored.case_id]
    investigate.check_case_allowed(case, investigate.RUBRIC_LOCK)
    # The citations resolve against the evidence file: it has to be the one
    # the result was made from.
    evidence = investigate.EVIDENCE_DIR / f"{case.case_id}.json"
    if hashlib.sha256(evidence.read_bytes()).hexdigest() != stored.provenance["evidence_sha256"]:
        raise ValueError(f"{evidence} is not the evidence the result was made from")

    telemetry.configure(service=telemetry.INVESTIGATOR)
    setup = investigate.prepare(case, deployment=stored.model["deployment"], challenger=True)
    result = run_challenge(setup.turn, setup.tools, stored, finding_id, question, pii=setup.pii)
    cost = setup.cost(result.usage)
    path = write_challenge(
        result,
        result_path=result_path,
        finding_id=finding_id,
        agent=setup.agent,
        model=setup.model,
        provenance=setup.provenance,
        cost=cost,
        now=datetime.now(UTC),
    )
    return result, path, cost


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.challenge")
    parser.add_argument("result", type=Path)
    parser.add_argument("finding_id")
    parser.add_argument("question")
    args = parser.parse_args(argv)
    result, path, cost = challenge_and_store(args.result, args.finding_id, args.question)
    print(summary(result, path, cost))
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())

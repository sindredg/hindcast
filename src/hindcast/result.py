"""The investigation result: its strict schema, its parts, and the citation checks.

The model fills the investigation under INVESTIGATION_SCHEMA. The app checks
every citation against the bound case afterwards: a bad citation is removed and
listed with its reason, the item stays, and an item left with nothing behind it
is listed as unsupported (decision 0006 counts it as unsupported, not a hit).
"""

import json
from dataclasses import dataclass, replace
from typing import Any, Literal

import jsonschema


def _object(**properties: dict) -> dict:
    # Strict structured outputs want every property required and no extras.
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_STRING = {"type": "string"}
_IDS = {"type": "array", "items": _STRING}
_CITATION = _object(source={"type": "string", "enum": ["case"]}, ref=_STRING)


def _schema(citation: dict) -> dict:
    citations = {"type": "array", "items": citation}
    return _object(
        attack=_object(
            verdict={"type": "string", "enum": ["attack", "not an attack", "cannot tell"]},
            reasoning=_STRING,
            citations=citations,
        ),
        findings={
            "type": "array",
            "items": _object(
                id=_STRING,
                kind={"type": "string", "enum": ["observation", "inference"]},
                claim=_STRING,
                rests_on=_IDS,
                citations=citations,
            ),
        },
        timeline={
            "type": "array",
            "items": _object(
                time=_STRING,
                time_kind={"type": "string", "enum": ["stated", "inferred"]},
                event=_STRING,
                citations=citations,
            ),
        },
        root_cause=_object(claim=_STRING, rests_on=_IDS, citations=citations),
        contributing_factors={
            "type": "array",
            "items": _object(claim=_STRING, rests_on=_IDS, citations=citations),
        },
        open_questions={
            "type": "array",
            "items": _object(question=_STRING, why_open=_STRING),
        },
    )


# Sent to the service as the agent's output format.
INVESTIGATION_SCHEMA = _schema(_CITATION)
# The local check takes any citation value, so a malformed citation reaches
# check_citations and is rejected on its own instead of failing the whole result.
_LOCAL_SCHEMA = _schema({})

Reason = Literal["malformed", "unknown", "other-case", "unknown-finding"]


@dataclass(frozen=True)
class Citation:
    # Anything but "case" (including "" for a citation that was not an object
    # with string fields) is rejected as malformed.
    source: str
    ref: str


@dataclass(frozen=True)
class Attack:
    verdict: Literal["attack", "not an attack", "cannot tell"]
    reasoning: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Finding:
    id: str
    kind: Literal["observation", "inference"]
    claim: str
    citations: tuple[Citation, ...]
    rests_on: tuple[str, ...]


@dataclass(frozen=True)
class TimelineEvent:
    time: str
    time_kind: Literal["stated", "inferred"]
    event: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class RootCause:
    claim: str
    rests_on: tuple[str, ...]
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Factor:
    claim: str
    rests_on: tuple[str, ...]
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class OpenQuestion:
    question: str
    why_open: str


@dataclass(frozen=True)
class Investigation:
    attack: Attack
    findings: tuple[Finding, ...]
    timeline: tuple[TimelineEvent, ...]
    root_cause: RootCause
    contributing_factors: tuple[Factor, ...]
    open_questions: tuple[OpenQuestion, ...]


@dataclass(frozen=True)
class RejectedCitation:
    where: str
    ref: str
    reason: Reason


@dataclass(frozen=True)
class Checks:
    rejected_citations: tuple[RejectedCitation, ...] = ()
    unsupported: tuple[str, ...] = ()


class ResultError(ValueError):
    """The model's final output is empty or does not fit the schema."""


def _citation(raw: object) -> Citation:
    if isinstance(raw, dict):
        source, ref = raw.get("source"), raw.get("ref")
        if isinstance(source, str) and isinstance(ref, str):
            return Citation(source, ref)
        return Citation("", str(ref if "ref" in raw else raw))
    return Citation("", str(raw))


def _citations(raw: dict) -> tuple[Citation, ...]:
    return tuple(_citation(c) for c in raw["citations"])


def parse_investigation(text: str) -> Investigation:
    if not text.strip():
        raise ResultError("empty-result")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ResultError(f"schema: not JSON: {error}") from error
    try:
        jsonschema.validate(raw, _LOCAL_SCHEMA, cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as error:
        raise ResultError(f"schema: {error.json_path}: {error.message}") from error

    attack = raw["attack"]
    root = raw["root_cause"]
    return Investigation(
        attack=Attack(attack["verdict"], attack["reasoning"], _citations(attack)),
        findings=tuple(
            Finding(f["id"], f["kind"], f["claim"], _citations(f), tuple(f["rests_on"]))
            for f in raw["findings"]
        ),
        timeline=tuple(
            TimelineEvent(t["time"], t["time_kind"], t["event"], _citations(t))
            for t in raw["timeline"]
        ),
        root_cause=RootCause(root["claim"], tuple(root["rests_on"]), _citations(root)),
        contributing_factors=tuple(
            Factor(f["claim"], tuple(f["rests_on"]), _citations(f))
            for f in raw["contributing_factors"]
        ),
        open_questions=tuple(
            OpenQuestion(q["question"], q["why_open"]) for q in raw["open_questions"]
        ),
    )


def _reason(citation: Citation, refs: frozenset[str], case_id: str) -> Reason | None:
    if citation.source != "case" or not citation.ref:
        return "malformed"
    # Another case's prefix is named as such even when the suffix exists here.
    if "/" in citation.ref and not citation.ref.startswith(case_id + "/"):
        return "other-case"
    if citation.ref not in refs:
        return "unknown"
    return None


def check_citations(
    investigation: Investigation, refs: frozenset[str], case_id: str
) -> tuple[Investigation, Checks]:
    """Remove and list bad citations and rests_on ids; list items left with no support."""
    finding_ids = {f.id for f in investigation.findings}
    rejected: list[RejectedCitation] = []
    unsupported: list[str] = []

    def check[T: (Attack, Finding, TimelineEvent, RootCause, Factor)](where: str, item: T) -> T:
        kept: list[Citation] = []
        for citation in item.citations:
            reason = _reason(citation, refs, case_id)
            if reason is None:
                kept.append(citation)
            else:
                rejected.append(RejectedCitation(where, citation.ref, reason))
        changes: dict[str, Any] = {"citations": tuple(kept)}
        rests_on: tuple[str, ...] = getattr(item, "rests_on", ())
        if rests_on:
            for finding_id in rests_on:
                if finding_id not in finding_ids:
                    rejected.append(RejectedCitation(where, finding_id, "unknown-finding"))
            rests_on = tuple(i for i in rests_on if i in finding_ids)
            changes["rests_on"] = rests_on
        if not kept and not rests_on:
            unsupported.append(where)
        return replace(item, **changes)

    checked = Investigation(
        attack=check("attack", investigation.attack),
        findings=tuple(check(f"findings[{i}]", f) for i, f in enumerate(investigation.findings)),
        timeline=tuple(check(f"timeline[{i}]", t) for i, t in enumerate(investigation.timeline)),
        root_cause=check("root_cause", investigation.root_cause),
        contributing_factors=tuple(
            check(f"contributing_factors[{i}]", f)
            for i, f in enumerate(investigation.contributing_factors)
        ),
        open_questions=investigation.open_questions,
    )
    return checked, Checks(tuple(rejected), tuple(unsupported))


def _citation_dicts(citations: tuple[Citation, ...]) -> list[dict]:
    return [{"source": c.source, "ref": c.ref} for c in citations]


def investigation_dict(investigation: Investigation | None) -> dict | None:
    """The investigation in the schema's shape, for the result file."""
    if investigation is None:
        return None
    i = investigation
    return {
        "attack": {
            "verdict": i.attack.verdict,
            "reasoning": i.attack.reasoning,
            "citations": _citation_dicts(i.attack.citations),
        },
        "findings": [
            {
                "id": f.id,
                "kind": f.kind,
                "claim": f.claim,
                "rests_on": list(f.rests_on),
                "citations": _citation_dicts(f.citations),
            }
            for f in i.findings
        ],
        "timeline": [
            {
                "time": t.time,
                "time_kind": t.time_kind,
                "event": t.event,
                "citations": _citation_dicts(t.citations),
            }
            for t in i.timeline
        ],
        "root_cause": {
            "claim": i.root_cause.claim,
            "rests_on": list(i.root_cause.rests_on),
            "citations": _citation_dicts(i.root_cause.citations),
        },
        "contributing_factors": [
            {
                "claim": f.claim,
                "rests_on": list(f.rests_on),
                "citations": _citation_dicts(f.citations),
            }
            for f in i.contributing_factors
        ],
        "open_questions": [
            {"question": q.question, "why_open": q.why_open} for q in i.open_questions
        ],
    }

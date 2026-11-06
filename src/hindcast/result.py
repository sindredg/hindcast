"""The investigation result: its strict schema, its parts, and the citation checks.

The model fills the investigation under INVESTIGATION_SCHEMA. The app checks
every citation against the bound case afterwards: a bad citation is removed and
listed with its reason, the item stays, and an item left with nothing behind it
is listed as unsupported (decision 0006 counts it as unsupported, not a hit).

A library citation is kept only for a ref a search in this run showed the
model, by exact string: a ref the model knows from training, or a near miss
of a real one, is rejected as not-retrieved. A run also passes the case refs
the model was shown and the refs Prompt Shields withheld: a withheld ref is
rejected as withheld, and a case ref the model never read as not-shown, though
it exists in the evidence file. A kept library citation does not support
an item on its own: a library document is another outage, so a claim about
this one that rests only on it is unsupported (decision 0006).
"""

import json
import re
from collections.abc import Collection
from dataclasses import dataclass, replace
from pathlib import Path
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
_CITATION = _object(source={"type": "string", "enum": ["case", "library"]}, ref=_STRING)
LIBRARY_PREFIX = "lib/"
# A finding ID the model chose, as far as a file name or a widget key may
# carry it: one path segment, no separators, and not "." or "..".
FINDING_ID = re.compile(r"(?!\.{1,2}$)[A-Za-z0-9_.-]{1,64}")


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

Reason = Literal[
    "malformed",
    "unknown",
    "other-case",
    "unknown-finding",
    "not-retrieved",
    "withheld",
    "not-shown",
    # Structural checks on rests_on (#25).
    "observation-rests-on",
    "self-support",
    "ambiguous-finding",
    "cycle",
]


@dataclass(frozen=True)
class Citation:
    # Anything but "case" or "library" (including "" for a citation that was
    # not an object with string fields) is rejected as malformed.
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
class PiiFinding:
    # A PII hit by field path and category; the text found is never kept.
    path: str
    category: str
    confidence: float


@dataclass(frozen=True)
class Checks:
    rejected_citations: tuple[RejectedCitation, ...] = ()
    unsupported: tuple[str, ...] = ()
    pii: tuple[PiiFinding, ...] = ()


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


def _reason(
    citation: Citation,
    refs: frozenset[str],
    case_id: str,
    retrieved: Collection[str],
    shown: Collection[str] | None,
    withheld: Collection[str],
) -> Reason | None:
    if citation.source == "library":
        if not citation.ref.startswith(LIBRARY_PREFIX):
            return "malformed"
        if citation.ref in withheld:
            return "withheld"
        return None if citation.ref in retrieved else "not-retrieved"
    if citation.source != "case" or not citation.ref or citation.ref.startswith(LIBRARY_PREFIX):
        return "malformed"
    # Another case's prefix is named as such even when the suffix exists here.
    if "/" in citation.ref and not citation.ref.startswith(case_id + "/"):
        return "other-case"
    if citation.ref not in refs:
        return "unknown"
    if citation.ref in withheld:
        return "withheld"
    if shown is not None and citation.ref not in shown:
        return "not-shown"
    return None


def _cycle_edges(edges: dict[int, list[int]]) -> set[tuple[int, int]]:
    """The finding-to-finding edges whose two ends sit on one cycle (Tarjan's SCCs)."""
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    component: dict[int, int] = {}

    def visit(node: int) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        for target in edges.get(node, []):
            if target not in index:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component[member] = node
                if member == node:
                    break

    for node in edges:
        if node not in index:
            visit(node)
    sizes: dict[int, int] = {}
    for root in component.values():
        sizes[root] = sizes.get(root, 0) + 1
    return {
        (source, target)
        for source, targets in edges.items()
        for target in targets
        if component[source] == component[target] and sizes[component[source]] > 1
    }


def check_citations(
    investigation: Investigation,
    refs: frozenset[str],
    case_id: str,
    retrieved: Collection[str] = frozenset(),
    shown: Collection[str] | None = None,
    withheld: Collection[str] = frozenset(),
) -> tuple[Investigation, Checks]:
    """Remove and list bad citations and rests_on ids; list items left with no support.

    shown=None skips the not-shown check, for a stored file that does not
    record what its run showed.

    A rests_on entry is rejected when it names no finding (unknown-finding),
    sits on an observation (observation-rests-on), names its own finding
    (self-support), names an ID more than one finding carries
    (ambiguous-finding), or closes a loop among findings (cycle): a chain of
    inferences that ends where it began rests on nothing. Support is then
    transitive: an item is supported by a kept case citation, or by a kept
    rests_on finding that is itself supported.
    """
    findings = investigation.findings
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.id] = counts.get(f.id, 0) + 1
    position = {f.id: n for n, f in enumerate(findings) if counts[f.id] == 1}
    rejected: list[RejectedCitation] = []

    def rests_on_reason(own: Finding | None, finding_id: str) -> Reason | None:
        if own is not None and own.kind == "observation":
            return "observation-rests-on"
        if own is not None and finding_id == own.id:
            return "self-support"
        if finding_id not in counts:
            return "unknown-finding"
        if counts[finding_id] > 1:
            return "ambiguous-finding"
        return None

    # The finding graph after the per-entry rules, for the cycle check.
    edges = {
        n: [position[i] for i in f.rests_on if rests_on_reason(f, i) is None]
        for n, f in enumerate(findings)
    }
    in_cycle = _cycle_edges(edges)

    def check[T: (Attack, Finding, TimelineEvent, RootCause, Factor)](
        where: str, item: T, own: int | None = None
    ) -> T:
        kept: list[Citation] = []
        for citation in item.citations:
            reason = _reason(citation, refs, case_id, retrieved, shown, withheld)
            if reason is None:
                kept.append(citation)
            else:
                rejected.append(RejectedCitation(where, citation.ref, reason))
        changes: dict[str, Any] = {"citations": tuple(kept)}
        if isinstance(item, (Finding, RootCause, Factor)):
            finding = findings[own] if own is not None else None
            rests_on: list[str] = []
            for finding_id in item.rests_on:
                reason = rests_on_reason(finding, finding_id)
                if reason is None and own is not None and (own, position[finding_id]) in in_cycle:
                    reason = "cycle"
                if reason is None:
                    rests_on.append(finding_id)
                else:
                    rejected.append(RejectedCitation(where, finding_id, reason))
            changes["rests_on"] = tuple(rests_on)
        return replace(item, **changes)

    checked = Investigation(
        attack=check("attack", investigation.attack),
        findings=tuple(check(f"findings[{i}]", f, i) for i, f in enumerate(findings)),
        timeline=tuple(check(f"timeline[{i}]", t) for i, t in enumerate(investigation.timeline)),
        root_cause=check("root_cause", investigation.root_cause),
        contributing_factors=tuple(
            check(f"contributing_factors[{i}]", f)
            for i, f in enumerate(investigation.contributing_factors)
        ),
        open_questions=investigation.open_questions,
    )

    def cited(item: Attack | Finding | TimelineEvent | RootCause | Factor) -> bool:
        return any(c.source == "case" for c in item.citations)

    # Support spreads along the kept edges until nothing changes.
    supported = {n for n, f in enumerate(checked.findings) if cited(f)}
    grew = True
    while grew:
        grew = False
        for n, f in enumerate(checked.findings):
            if n not in supported and any(position[i] in supported for i in f.rests_on):
                supported.add(n)
                grew = True

    def backed(item: Attack | Finding | TimelineEvent | RootCause | Factor) -> bool:
        rests_on: tuple[str, ...] = getattr(item, "rests_on", ())
        return cited(item) or any(position[i] in supported for i in rests_on)

    unsupported = [
        where
        for where, item in [
            ("attack", checked.attack),
            *((f"findings[{i}]", f) for i, f in enumerate(checked.findings)),
            *((f"timeline[{i}]", t) for i, t in enumerate(checked.timeline)),
            ("root_cause", checked.root_cause),
            *(
                (f"contributing_factors[{i}]", f)
                for i, f in enumerate(checked.contributing_factors)
            ),
        ]
        if not backed(item)
    ]
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


# A challenge answer (hindcast.challenge). Strict mode cannot make a field
# optional, so revised_claim is always present and parse_challenge holds it
# empty unless the verdict is "revised".
CHALLENGE_SCHEMA = _object(
    verdict={"type": "string", "enum": ["stands", "revised", "withdrawn"]},
    answer=_STRING,
    citations={"type": "array", "items": _CITATION},
    revised_claim=_STRING,
)
_LOCAL_CHALLENGE_SCHEMA = _object(
    verdict={"type": "string", "enum": ["stands", "revised", "withdrawn"]},
    answer=_STRING,
    citations={"type": "array", "items": {}},
    revised_claim=_STRING,
)


@dataclass(frozen=True)
class Challenge:
    verdict: Literal["stands", "revised", "withdrawn"]
    answer: str
    citations: tuple[Citation, ...]
    revised_claim: str


def parse_challenge(text: str) -> Challenge:
    if not text.strip():
        raise ResultError("empty-result")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ResultError(f"schema: not JSON: {error}") from error
    try:
        jsonschema.validate(raw, _LOCAL_CHALLENGE_SCHEMA, cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as error:
        raise ResultError(f"schema: {error.json_path}: {error.message}") from error
    revised = raw["verdict"] == "revised"
    if revised != bool(raw["revised_claim"].strip()):
        raise ResultError("schema: revised_claim is set only, and always, for a revised verdict")
    return Challenge(raw["verdict"], raw["answer"], _citations(raw), raw["revised_claim"])


def check_challenge_citations(
    challenge: Challenge,
    refs: frozenset[str],
    case_id: str,
    retrieved: Collection[str],
    shown: Collection[str],
    withheld: Collection[str],
) -> tuple[Challenge, Checks]:
    """The same citation rules as an investigation, for the one answer a challenge gives."""
    kept: list[Citation] = []
    rejected: list[RejectedCitation] = []
    for citation in challenge.citations:
        reason = _reason(citation, refs, case_id, retrieved, shown, withheld)
        if reason is None:
            kept.append(citation)
        else:
            rejected.append(RejectedCitation("challenge", citation.ref, reason))
    # An answer about this outage needs case evidence, as an investigation item does.
    unsupported = () if any(c.source == "case" for c in kept) else ("challenge",)
    return replace(challenge, citations=tuple(kept)), Checks(tuple(rejected), unsupported)


def challenge_dict(challenge: Challenge | None) -> dict | None:
    if challenge is None:
        return None
    return {
        "verdict": challenge.verdict,
        "answer": challenge.answer,
        "citations": _citation_dicts(challenge.citations),
        "revised_claim": challenge.revised_claim,
    }


@dataclass(frozen=True)
class StoredResult:
    """One result file as hindcast.investigate.write_result wrote it."""

    case_id: str
    agent: dict
    model: dict
    provenance: dict
    status: str
    incomplete_reason: str | None
    investigation: Investigation | None
    checks: dict
    usage: dict
    tool_calls: tuple[dict, ...] = ()
    cost: dict | None = None


def load_result(path: Path) -> StoredResult:
    raw = json.loads(path.read_text(encoding="utf-8"))
    investigation = raw["investigation"]
    # The dict went through investigation_dict on the way out, so it satisfies
    # the same schema parse_investigation checks on the way in.
    parsed = None if investigation is None else parse_investigation(json.dumps(investigation))
    return StoredResult(
        case_id=raw["case_id"],
        agent=raw["agent"],
        model=raw["model"],
        provenance=raw["provenance"],
        status=raw["status"],
        incomplete_reason=raw["incomplete_reason"],
        investigation=parsed,
        checks=raw["checks"],
        usage=raw["usage"],
        # Results from before the tool record and the price table have neither.
        tool_calls=tuple(raw.get("tool_calls", [])),
        cost=raw.get("cost"),
    )

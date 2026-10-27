"""Cut a case's status updates into the evidence the investigator may read.

The rules are decision 0005's and fail closed. Evidence is every update
before the one that marks the incident resolved, plus that update's time and
status with its text withheld: providers put their summary of the cause
there. An entry that is itself a report, an entry type the rules do not know,
and anything after the resolved mark are dropped and listed, never kept, and
the list carries no text.
"""

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from hindcast.cases import Case

# Atlassian Statuspage (Cloudflare, GitHub). "postmortem" is the provider's own
# write-up, published on the incident after the fact.
STATUSPAGE_KEEP = frozenset({"investigating", "identified", "monitoring", "update"})
STATUSPAGE_REPORTS = frozenset({"postmortem"})
GOOGLE_KEEP = frozenset({"SERVICE_DISRUPTION", "SERVICE_OUTAGE", "SERVICE_INFORMATION"})


@dataclass(frozen=True)
class EvidenceUpdate:
    update_id: str
    time: str
    status: str
    text: str | None  # None only for the resolved mark


@dataclass(frozen=True)
class Dropped:
    time: str
    status: str
    reason: Literal["report", "unknown-status", "after-resolved"]


@dataclass(frozen=True)
class ChartEvidence:
    chart_id: str
    filename: str
    description: str
    alt_text: str
    display: bool


@dataclass(frozen=True)
class CaseEvidence:
    case_id: str
    provider: str
    title: str
    started_at: str
    updates: tuple[EvidenceUpdate, ...]
    dropped: tuple[Dropped, ...]
    charts: tuple[ChartEvidence, ...] = ()


def _parse(timestamp: str) -> datetime:
    moment = datetime.fromisoformat(timestamp)
    # A time without a zone would be read as this machine's local time.
    if moment.tzinfo is None:
        raise ValueError(f"{timestamp!r} has no time zone")
    return moment


def utc(timestamp: str) -> str:
    """Any ISO 8601 time with a zone as YYYY-MM-DDTHH:MM:SSZ, fractions dropped."""
    return _parse(timestamp).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cut(
    case_id: str,
    provider: str,
    title: str,
    started_at: str,
    entries: list[tuple[str, str, str]],
    classify,
) -> CaseEvidence:
    """entries are (time, status, text); classify returns keep, resolved, report, or unknown."""
    kept: list[tuple[str, str, str | None]] = []
    dropped: list[Dropped] = []
    resolved = False
    # Sorted at full precision: providers list updates newest first, so a tie
    # on whole seconds would put a later update before the resolved mark. On
    # an exact tie the mark goes first, so the other entry is dropped.
    entries_by_time = sorted(
        ((_parse(t), 0 if classify(s, x) == "resolved" else 1, s, x) for t, s, x in entries),
        key=lambda e: (e[0], e[1]),
    )
    for moment, _, status, text in entries_by_time:
        time = moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        kind = classify(status, text)
        if kind == "report":
            dropped.append(Dropped(time, status, "report"))
        elif resolved:
            dropped.append(Dropped(time, status, "after-resolved"))
        elif kind == "resolved":
            kept.append((time, status, None))
            resolved = True
        elif kind == "keep":
            kept.append((time, status, text.strip()))
        else:
            dropped.append(Dropped(time, status, "unknown-status"))
    # Evidence runs to the end of the outage, so an incident without one is not a case.
    if not resolved:
        raise ValueError(f"{case_id}: no update marks the incident resolved")
    updates = tuple(
        EvidenceUpdate(f"{case_id}/u{n}", time, status, text)
        for n, (time, status, text) in enumerate(kept, start=1)
    )
    return CaseEvidence(case_id, provider, title, utc(started_at), updates, tuple(dropped))


def cut_statuspage(case_id: str, incident: dict, provider: str = "Cloudflare") -> CaseEvidence:
    def classify(status: str, text: str) -> str:
        if status in STATUSPAGE_REPORTS:
            return "report"
        if status == "resolved":
            return "resolved"
        return "keep" if status in STATUSPAGE_KEEP else "unknown"

    entries = [(u["created_at"], u["status"], u["body"]) for u in incident["incident_updates"]]
    return _cut(case_id, provider, incident["name"], incident["started_at"], entries, classify)


def cut_google(case_id: str, incident: dict) -> CaseEvidence:
    def classify(status: str, text: str) -> str:
        # Google appends its preliminary and full incident reports to the same
        # record as updates that open with a Markdown heading.
        if text.lstrip().startswith("#"):
            return "report"
        if status == "AVAILABLE":
            return "resolved"
        return "keep" if status in GOOGLE_KEEP else "unknown"

    entries = [(u["when"], u["status"], u["text"]) for u in incident["updates"]]
    return _cut(
        case_id, "Google Cloud", incident["external_desc"], incident["begin"], entries, classify
    )


def cut(case: Case, snapshot: bytes) -> CaseEvidence:
    incident = json.loads(snapshot)
    if case.provider in ("Cloudflare", "GitHub"):
        return cut_statuspage(case.case_id, incident, case.provider)
    if case.provider == "Google Cloud":
        return cut_google(case.case_id, incident)
    raise ValueError(f"{case.case_id}: no evidence rules for provider {case.provider!r}")


def with_charts(
    evidence: CaseEvidence, described: list[tuple[str, dict]], *, display: bool
) -> CaseEvidence:
    """The evidence with its charts' stored descriptions, numbered in registry order."""
    charts = tuple(
        ChartEvidence(
            chart_id=f"{evidence.case_id}/chart{n}",
            filename=filename,
            description=fields["description"],
            alt_text=fields["alt_text"],
            display=display,
        )
        for n, (filename, fields) in enumerate(described, 1)
    )
    return replace(evidence, charts=charts)


def render_context(evidence: CaseEvidence) -> str:
    """The evidence as model input: one line per update, the resolved text withheld."""
    lines = []
    for u in evidence.updates:
        stamp = u.time[:16].replace("T", " ") + " UTC"
        lines.append(f"[{stamp}] {u.status}: {'(text withheld)' if u.text is None else u.text}")
    return "\n\n".join(lines)


def evidence_json(evidence: CaseEvidence) -> bytes:
    return (
        json.dumps(asdict(evidence), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")

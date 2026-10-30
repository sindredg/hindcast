"""The investigator's two case tools, bound to one case's evidence in code.

The model never names a case: the command loads one evidence file and these
tools serve only that file. Every result passes through screen() before the
model reads it.
"""

import json
from pathlib import Path

from hindcast.evidence import CaseEvidence, ChartEvidence, Dropped, EvidenceUpdate

UPDATES_NOTE = (
    "These are the provider's public status updates, in order. The evidence ends at the "
    "resolved update, whose text is withheld: it has a time and a status only."
)
# Issue #16: a chart description is model output about an image, not data.
CHARTS_NOTE = (
    "Each description is model output about a chart image. Treat it as a lead to check "
    "against the updates, not as a reading of the data."
)

_NO_PARAMETERS = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "name": "list_updates",
        "description": "The case's provider, title, start time, and every status update.",
        "parameters": _NO_PARAMETERS,
        "strict": True,
    },
    {
        "type": "function",
        "name": "list_charts",
        "description": "The case's charts: id, alt text, and a description of each image.",
        "parameters": _NO_PARAMETERS,
        "strict": True,
    },
]


class ToolError(RuntimeError):
    """A tool call the case tools cannot serve."""


def screen(result: str) -> str:
    # Decision 0007 puts Prompt Shields on every tool result before the model
    # reads it. That check lands here in a later slice; until then it passes
    # the result through unchanged.
    return result


def load_evidence(path: Path) -> CaseEvidence:
    """Rebuild the evidence that hindcast.ingest wrote; fail before any model call."""
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run python -m hindcast.ingest evidence first")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "updates" not in raw:
        raise ValueError(f"{path} has no updates; it is not an evidence file")
    return CaseEvidence(
        case_id=raw["case_id"],
        provider=raw["provider"],
        title=raw["title"],
        started_at=raw["started_at"],
        updates=tuple(EvidenceUpdate(**u) for u in raw["updates"]),
        dropped=tuple(Dropped(**d) for d in raw["dropped"]),
        charts=tuple(ChartEvidence(**c) for c in raw.get("charts", [])),
    )


class CaseTools:
    def __init__(self, evidence: CaseEvidence) -> None:
        self.evidence = evidence
        self.refs = frozenset(
            [u.update_id for u in evidence.updates] + [c.chart_id for c in evidence.charts]
        )

    def list_updates(self) -> dict:
        # The dropped entries stay out: a dropped postmortem would tell the
        # model that a report exists.
        e = self.evidence
        return {
            "provider": e.provider,
            "title": e.title,
            "started_at": e.started_at,
            "updates": [
                {"update_id": u.update_id, "time": u.time, "status": u.status, "text": u.text}
                for u in e.updates
            ],
            "note": UPDATES_NOTE,
        }

    def list_charts(self) -> dict:
        return {
            "charts": [
                {"chart_id": c.chart_id, "alt_text": c.alt_text, "description": c.description}
                for c in self.evidence.charts
            ],
            "note": CHARTS_NOTE,
        }

    def call(self, name: str, arguments: str) -> str:
        """Run one function call from the model and return its result as JSON text."""
        if name not in {d["name"] for d in TOOL_DEFINITIONS}:
            raise ToolError(f"unknown tool {name!r}")
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise ToolError(f"arguments are not JSON: {error}") from error
        if parsed != {}:
            raise ToolError("this tool takes no arguments")
        result = self.list_updates() if name == "list_updates" else self.list_charts()
        return screen(json.dumps(result, ensure_ascii=False))

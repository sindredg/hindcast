"""The investigator's three tools, bound to one case in code.

The model never names a case: the command loads one evidence file, and
list_updates and list_charts serve only that file. search_library takes a
query and nothing else; the command binds the search to the case, so the
case's date bound and picks come from the registries, never from the model
(hindcast.search). Every ref a search returns is kept in `retrieved`, the set
a library citation is checked against. Every result passes through screen()
before the model reads it.
"""

import json
from collections.abc import Callable
from pathlib import Path

from hindcast.evidence import CaseEvidence, ChartEvidence, Dropped, EvidenceUpdate
from hindcast.search import LibraryHit

UPDATES_NOTE = (
    "These are the provider's public status updates, in order. Each status incident ends "
    "at its resolved update, whose text is withheld: it has a time and a status only."
)
# Issue #16: a chart description is model output about an image, not data.
CHARTS_NOTE = (
    "Each description is model output about a chart image. Treat it as a lead to check "
    "against the updates, not as a reading of the data."
)

LIBRARY_NOTE = (
    "These are other, earlier outages, published before this one began. A hit is a lead "
    "to compare with this case's updates, never evidence about this outage."
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
    {
        "type": "function",
        "name": "search_library",
        "description": (
            "Earlier public postmortems of other outages, published before this one began. "
            "Each hit is one section or figure with its ref."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, in your own words."}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
# Long enough for any symptom description, short enough that a query cannot
# carry a pasted document.
MAX_QUERY = 1000
HIT_FIELDS = ("ref", "doc_id", "title", "heading", "published_at", "content")


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
    def __init__(
        self, evidence: CaseEvidence, search: Callable[[str], list[LibraryHit]] | None = None
    ) -> None:
        self.evidence = evidence
        self.search = search
        self.refs = frozenset(
            [u.update_id for u in evidence.updates] + [c.chart_id for c in evidence.charts]
        )
        self.retrieved: set[str] = set()
        # What the last successful call asked and returned, for the result
        # file's tool_calls: empty after a case tool.
        self.last_call: dict = {}

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

    def search_library(self, query: str) -> dict:
        if self.search is None:
            raise ToolError("no library search is bound")
        hits = self.search(query)
        # Scores stay out: they rank hits within one query and mean nothing
        # to the model.
        result = {
            "hits": [{name: getattr(h, name) for name in HIT_FIELDS} for h in hits],
            "note": LIBRARY_NOTE,
        }
        refs = [h.ref for h in hits]
        self.retrieved.update(refs)
        self.last_call = {"query": query, "refs": refs}
        return result

    def call(self, name: str, arguments: str) -> str:
        """Run one function call from the model and return its result as JSON text."""
        if name not in {d["name"] for d in TOOL_DEFINITIONS}:
            raise ToolError(f"unknown tool {name!r}")
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise ToolError(f"arguments are not JSON: {error}") from error
        if name == "search_library":
            # Strict mode should hold the model to the schema; this holds the
            # tool to it when the model does not.
            if not isinstance(parsed, dict) or parsed.keys() != {"query"}:
                raise ToolError("search_library takes one argument, query")
            query = parsed["query"]
            if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY:
                raise ToolError(
                    f"query must be a non-empty string of at most {MAX_QUERY} characters"
                )
            result = self.search_library(query)
        elif parsed != {}:
            raise ToolError("this tool takes no arguments")
        else:
            result = self.list_updates() if name == "list_updates" else self.list_charts()
            self.last_call = {}
        return screen(json.dumps(result, ensure_ascii=False))

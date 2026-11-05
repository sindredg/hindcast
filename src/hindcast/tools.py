"""The investigator's three tools, bound to one case in code.

The model never names a case: the command loads one evidence file, and
list_updates and list_charts serve only that file. search_library takes a
query and nothing else; the command binds the search to the case, so the
case's date bound and picks come from the registries, never from the model
(hindcast.search).

Every item a tool returns (an update, a chart, a library hit) passes Prompt
Shields before the model reads it (decision 0007). A flagged item is withheld:
its text is replaced in place by its ref and a marker, and the rest of the
result still reaches the model. The tools keep the case refs the model was
shown, the refs withheld, and the library refs shown (`retrieved`); a citation
is kept only for a ref the model read (hindcast.result).
"""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

from hindcast.evidence import CaseEvidence, ChartEvidence, Dropped, EvidenceUpdate
from hindcast.safety import Shield
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
# Added to a result's note only when it withheld something.
WITHHELD_NOTE = (
    "Items marked withheld were flagged as possible instructions to you and are not shown."
)
WITHHELD = "prompt-shields"

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
        self,
        evidence: CaseEvidence,
        search: Callable[..., list[LibraryHit]] | None = None,
        shield: Shield | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.evidence = evidence
        self.clock = clock
        self.search = search
        # None in tests that do not test screening, and for an injection
        # copy run with --screens off (decision 0025).
        self.shield = shield
        self.refs = frozenset(
            [u.update_id for u in evidence.updates] + [c.chart_id for c in evidence.charts]
        )
        self.shown: set[str] = set()
        self.withheld: set[str] = set()
        self.retrieved: set[str] = set()
        # One screen per ref per run: a second list_updates, or a hit that
        # comes back in a later search, is not sent again.
        self._flags: dict[tuple[str, str], bool] = {}
        self._flagged_refs: set[str] = set()
        # What the last successful call asked, returned, and withheld, for the
        # result file's tool_calls.
        self.last_call: dict = {}

    def _left(self, timeout: float) -> Callable[[], float]:
        """The time left of one tool call's budget; raises TimeoutError once it is spent.

        The search and the screen of one call share the budget, so the call
        as a whole ends within the time left in the run.
        """
        end = self.clock() + timeout

        def left() -> float:
            remaining = end - self.clock()
            if remaining <= 0:
                raise TimeoutError("no time left in the tool call")
            return remaining

        return left

    def _screen(self, items: list[tuple[str, str]], timeout: float) -> tuple[set[str], int]:
        """Screen (ref, text) pairs not seen before; return the flagged refs and the calls made.

        The cache is keyed by the text as well as the ref: one library ref
        can come back as several chunks, so a ref keyed alone would let a
        later chunk reach the model unscreened, or let a clean chunk clear a
        flagged one. A ref stays withheld once any text under it was flagged.
        """
        keyed = {
            (ref, hashlib.sha256(text.encode("utf-8")).hexdigest()): text for ref, text in items
        }
        new = [(key, text) for key, text in keyed.items() if key not in self._flags]
        calls = 0
        if new and self.shield is not None:
            before = self.shield.calls
            flags = self.shield.documents([text for _, text in new], timeout=timeout)
            calls = self.shield.calls - before
            if len(flags) != len(new):
                raise RuntimeError("the screen returned a different number of flags")
        else:
            flags = [False] * len(new)
        for (key, _), flag in zip(new, flags, strict=True):
            self._flags[key] = flag
            if flag:
                self._flagged_refs.add(key[0])
        return {ref for ref, _ in items if ref in self._flagged_refs}, calls

    @staticmethod
    def _note(note: str, flagged: set[str]) -> str:
        return f"{note} {WITHHELD_NOTE}" if flagged else note

    def list_updates(self, timeout: float) -> dict:
        # The dropped entries stay out: a dropped postmortem would tell the
        # model that a report exists.
        e = self.evidence
        # The title is the status page's incident name: third-party text too.
        title_ref = f"{e.case_id}/title"
        items = [(title_ref, e.title)] + [(u.update_id, u.text or "") for u in e.updates]
        flagged, calls = self._screen(items, timeout)
        self.withheld |= flagged
        self.shown |= {u.update_id for u in e.updates} - flagged
        self.last_call = {"withheld": sorted(flagged), "screen_calls": calls}
        return {
            "provider": e.provider,
            "title": {"withheld": WITHHELD} if title_ref in flagged else e.title,
            "started_at": e.started_at,
            "updates": [
                {"update_id": u.update_id, "withheld": WITHHELD}
                if u.update_id in flagged
                else {"update_id": u.update_id, "time": u.time, "status": u.status, "text": u.text}
                for u in e.updates
            ],
            "note": self._note(UPDATES_NOTE, flagged),
        }

    def list_charts(self, timeout: float) -> dict:
        charts = self.evidence.charts
        flagged, calls = self._screen(
            [(c.chart_id, f"{c.alt_text}\n{c.description}") for c in charts], timeout
        )
        self.withheld |= flagged
        self.shown |= {c.chart_id for c in charts} - flagged
        self.last_call = {"withheld": sorted(flagged), "screen_calls": calls}
        return {
            "charts": [
                {"chart_id": c.chart_id, "withheld": WITHHELD}
                if c.chart_id in flagged
                else {"chart_id": c.chart_id, "alt_text": c.alt_text, "description": c.description}
                for c in charts
            ],
            "note": self._note(CHARTS_NOTE, flagged),
        }

    def search_library(self, query: str, timeout: float) -> dict:
        if self.search is None:
            raise ToolError("no library search is bound")
        left = self._left(timeout)
        hits = self.search(query, timeout=left())
        flagged, calls = self._screen(
            [(h.ref, f"{h.title}\n{h.heading}\n{h.content}") for h in hits], left()
        )
        # Scores stay out: they rank hits within one query and mean nothing
        # to the model.
        result = {
            "hits": [
                {"ref": h.ref, "withheld": WITHHELD}
                if h.ref in flagged
                else {name: getattr(h, name) for name in HIT_FIELDS}
                for h in hits
            ],
            "note": self._note(LIBRARY_NOTE, flagged),
        }
        # Only refs the model was shown join `retrieved`, and only after the
        # screen (issue #46).
        refs = [h.ref for h in hits if h.ref not in flagged]
        self.withheld |= flagged
        self.retrieved.update(refs)
        self.last_call = {
            "query": query,
            "refs": refs,
            "withheld": sorted(flagged),
            "screen_calls": calls,
        }
        return result

    def call(self, name: str, arguments: str, *, timeout: float) -> str:
        """Run one function call from the model and return its result as JSON text.

        timeout is the time left in the run; the search and the screen get it.
        """
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
            result = self.search_library(query, timeout)
        elif parsed != {}:
            raise ToolError("this tool takes no arguments")
        elif name == "list_updates":
            result = self.list_updates(timeout)
        else:
            result = self.list_charts(timeout)
        return json.dumps(result, ensure_ascii=False)

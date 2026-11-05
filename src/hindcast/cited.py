"""What a citation points at: the status update, chart, or library passage the page shows.

A stored result keeps citations as refs only. The page resolves each ref
against the files the run read: the case's evidence under build/evidence and
the library extracts under build/extracted/library (and the planted pages
under build/injection/library). Without those files, which the page has only
when it can run investigations, a ref resolves to nothing and the page shows
the ID alone.

Only the result's own case file is opened, so a ref with another case's
prefix never reads another case's evidence. Every text returned here is
provider or model text: the page shows it with hindcast.escape.plain.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from hindcast import injection
from hindcast.cases import CASE_ID
from hindcast.index import EXTRACTS_DIR
from hindcast.result import LIBRARY_PREFIX

# hindcast.investigate.EVIDENCE_DIR, repeated so the page does not import the
# investigator (and its model clients) to show a stored result; a test keeps
# the two equal.
EVIDENCE_DIR = Path("build/evidence")
CHARTS_DIR = Path("data/charts")
# Case and library doc IDs share one form: lower-case words and digits joined
# by hyphens. An ID in any other form (a slash, "..") never becomes a path.
DOC_ID = CASE_ID


@dataclass(frozen=True)
class Cited:
    """One resolved citation, ready to show."""

    kind: str  # "update", "chart", "section", or "figure"
    ref: str
    heading: str  # what the item is: "Update u7 · identified", "Chart chart1", a section heading
    when: str  # the update time or the library document's publish date; "" when unknown
    text: str  # the update text, chart description, section text, or figure description
    image: Path | None = None  # a chart image the page may display (its licence allows it)


def short(ref: str, case_id: str) -> str:
    """The ref without the case prefix, or the library ref as doc and part."""
    if ref.startswith(f"{case_id}/"):
        return ref.removeprefix(f"{case_id}/")
    if ref.startswith(LIBRARY_PREFIX):
        doc, _, part = ref.removeprefix(LIBRARY_PREFIX).rpartition("/")
        return f"{doc} {part}" if doc else ref
    return ref


@lru_cache(maxsize=64)
def _json(path: Path, mtime: float) -> dict | None:
    # mtime is part of the key, so a rewritten file is read again.
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return raw if isinstance(raw, dict) else None


def _load(path: Path) -> dict | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return _json(path, mtime)


def _chart_image(root: Path, case_id: str, chart: dict) -> Path | None:
    if chart.get("display") is not True or not chart.get("filename"):
        return None
    # An injection copy keeps the development case's chart files.
    owner = injection.BASE_CASE if injection.is_copy(case_id) else case_id
    path = root / CHARTS_DIR / owner / chart["filename"]
    return path if path.is_file() else None


def _case_item(root: Path, case_id: str, ref: str) -> Cited | None:
    if not CASE_ID.fullmatch(case_id) or not ref.startswith(f"{case_id}/"):
        return None
    evidence = _load(root / EVIDENCE_DIR / f"{case_id}.json")
    if evidence is None:
        return None
    for update in evidence.get("updates") or []:
        if update.get("update_id") == ref:
            text = update.get("text")
            return Cited(
                "update",
                ref,
                f"Update {short(ref, case_id)} · {update.get('status', '')}",
                update.get("time", ""),
                # The resolved update keeps its time and status only (decision 0005).
                text if text is not None else "Resolved: the text is withheld from the model.",
            )
    for chart in evidence.get("charts") or []:
        if chart.get("chart_id") == ref:
            return Cited(
                "chart",
                ref,
                f"Chart {short(ref, case_id)}: {chart.get('alt_text', '')}",
                "",
                chart.get("description", ""),
                _chart_image(root, case_id, chart),
            )
    return None


def _library_item(root: Path, ref: str) -> Cited | None:
    doc_id = ref.removeprefix(LIBRARY_PREFIX).split("/", 1)[0]
    if not DOC_ID.fullmatch(doc_id):
        return None
    for folder in (EXTRACTS_DIR, injection.EXTRACTS_DIR):
        extract = _load(root / folder / f"{doc_id}.json")
        if extract is None:
            continue
        published = extract.get("published_at", "")
        for section in extract.get("sections") or []:
            if section.get("section_id") == ref:
                return Cited(
                    "section",
                    ref,
                    section.get("heading", ""),
                    published,
                    section.get("markdown", ""),
                )
        for figure in extract.get("figures") or []:
            if figure.get("figure_id") == ref:
                return Cited(
                    "figure",
                    ref,
                    f"Figure {short(ref, '')}",
                    published,
                    figure.get("description", ""),
                )
    return None


def resolve(root: Path, case_id: str, source: str, ref: str) -> Cited | None:
    """The cited item, or None when it is not in the files under root."""
    if source == "case":
        return _case_item(root, case_id, ref)
    if source == "library" and ref.startswith(LIBRARY_PREFIX):
        return _library_item(root, ref)
    return None

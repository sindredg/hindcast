"""The text behind a citation: the update, chart, or library item a run cited.

The judge reads each run's claims next to the text they cite, and the review
page shows the same text to the reviewer. A case citation resolves from the
case's evidence file; a library citation from the local library extracts, so
neither needs the search service.

A library section resolves to the whole section. A search returned one chunk
of it, and a result file keeps the ref only, so for a section longer than one
chunk (hindcast.index.CHUNK_CHARS) the excerpt holds more than the run was
shown.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hindcast.evidence import CaseEvidence
from hindcast.result import LIBRARY_PREFIX, Citation

EXTRACTS_DIR = Path("build/extracted/library")
REGISTRY = Path("data/library.yaml")
WITHHELD_TEXT = "(text withheld)"


@dataclass(frozen=True)
class Excerpt:
    source: Literal["case", "library"]
    ref: str
    title: str
    text: str


def library_items(extracts: Iterable[Mapping], titles: Mapping[str, str]) -> dict[str, dict]:
    """Every library section and figure by ref, as {"title", "text"}."""
    items: dict[str, dict] = {}
    for extract in extracts:
        title = titles[extract["doc_id"]]
        for section in extract["sections"]:
            items[section["section_id"]] = {
                "title": f"{title}: {section['heading']}",
                "text": section["markdown"],
            }
        for figure in extract["figures"]:
            # The same fields, in the same order, as the figure's indexed chunk.
            text = "\n\n".join(figure[k] for k in ("description", "alt_text", "text_in_image"))
            items[figure["figure_id"]] = {"title": f"{title}: figure", "text": text}
    return items


def load_library_items(
    extracts_dir: Path = EXTRACTS_DIR, registry: Path = REGISTRY
) -> dict[str, dict]:
    from hindcast.cases import load_cases
    from hindcast.library import load_library

    docs = load_library(registry, load_cases())
    extracts = [
        json.loads((extracts_dir / f"{doc_id}.json").read_text("utf-8")) for doc_id in sorted(docs)
    ]
    return library_items(extracts, {doc_id: doc.title for doc_id, doc in docs.items()})


def resolve(
    citation: Citation, evidence: CaseEvidence, library: Mapping[str, dict]
) -> Excerpt | None:
    """The cited text, or None for a ref this case or the library does not hold."""
    if citation.source == "library":
        item = library.get(citation.ref) if citation.ref.startswith(LIBRARY_PREFIX) else None
        if item is None:
            return None
        return Excerpt("library", citation.ref, item["title"], item["text"])
    if citation.source != "case":
        return None
    for update in evidence.updates:
        if update.update_id == citation.ref:
            title = f"{update.time} {update.status}"
            return Excerpt("case", citation.ref, title, update.text or WITHHELD_TEXT)
    for chart in evidence.charts:
        if chart.chart_id == citation.ref:
            # What list_charts showed the model: the alt text and the description.
            text = f"Description (model output): {chart.description}"
            return Excerpt("case", citation.ref, f"Chart: {chart.alt_text}", text)
    return None

"""The leak check: does a case's evidence or its filtered library state its answer key?

    python -m hindcast.leak [--plant]

For every case with a frozen key, each key item that is not marked as stated
during the incident is compared with each evidence update, each chart
description, and each library chunk the case's filter returns from the live
index. Text is normalised (lower case, letters and digits only) and a hit is
any shared run of RUN_WORDS words with the item's source quote or its text.
That catches near-copies of the postmortem, not an update that implies the
cause in other words (decision 0005).

The check refuses a key with no unstated item or a case with nothing to
compare, since it could not fail. --plant adds one in-memory chunk that holds
a key item's quote, and the run must report a hit for that item there. The command
prints item and source IDs and counts, never text.
"""

import argparse
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hindcast.cases import Case
from hindcast.keys import FROZEN, KEYS_DIR, AnswerKey, load_key
from hindcast.library import LibraryDocument

RUN_WORDS = 8
WORD = re.compile(r"[a-z0-9]+")
PLANTED = "planted"


@dataclass(frozen=True)
class LeakHit:
    item: str
    source_id: str
    runs: int


def runs(text: str, n: int = RUN_WORDS) -> set[tuple[str, ...]]:
    words = WORD.findall(text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def unstated_items(key: AnswerKey) -> Iterator[tuple[str, list[str]]]:
    """(item ID, its texts) for every item the key does not mark as stated during the incident."""
    if not key.root_cause.stated_during_incident:
        yield "root_cause", [key.root_cause.source_quote, key.root_cause.text]
    for name in ("contributing_factors", "fixes"):
        for i, item in enumerate(getattr(key, name)):
            if not item.stated_during_incident:
                yield f"{name}/{i}", [item.source_quote, item.text]
    for i, event in enumerate(key.timeline):
        if not event.stated_during_incident:
            yield f"timeline/{i}", [event.source_quote, event.event]


def hits(key: AnswerKey, sources: Mapping[str, str], n: int = RUN_WORDS) -> list[LeakHit]:
    """One hit per key item and source that share at least one run of n words."""
    items = [
        (item, set().union(*(runs(t, n) for t in texts))) for item, texts in unstated_items(key)
    ]
    if not items or not sources:
        raise ValueError(
            f"{key.case_id}: no unstated key item or no source; the check could not fail"
        )
    source_runs = {source_id: runs(text, n) for source_id, text in sources.items()}
    out = []
    for item, item_runs in items:
        for source_id, shared in source_runs.items():
            if common := item_runs & shared:
                out.append(LeakHit(item, source_id, len(common)))
    return out


def evidence_sources(path: Path) -> dict[str, str]:
    """Each update's text and each chart's description, by ID."""
    from hindcast.tools import load_evidence

    evidence = load_evidence(path)
    sources = {u.update_id: u.text for u in evidence.updates if u.text}
    sources |= {c.chart_id: f"{c.description}\n{c.alt_text}" for c in evidence.charts}
    return sources


def library_sources(
    case_id: str,
    client: Any,
    library: Mapping[str, LibraryDocument],
    cases: Mapping[str, Case],
) -> dict[str, str]:
    """Every chunk the case's filter returns from the index, by chunk ID."""
    from hindcast.search import library_filter

    query_filter = library_filter(cases[case_id], library)
    found = {
        d["id"]: d["content"]
        for d in client.search("*", filter=query_filter, select=["id", "content"])
    }
    # Every keyed case has picks, so an empty result means a wrong or empty
    # index, and the library half of the check could not fail.
    if not found:
        raise ValueError(
            f"{case_id}: the filter returned no library chunks; the check could not fail"
        )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.leak")
    parser.add_argument("--plant", action="store_true", help="add one planted chunk per case")
    args = parser.parse_args(argv)

    from hindcast.cases import load_cases
    from hindcast.config import SearchSettings, load_settings
    from hindcast.index import clients
    from hindcast.library import load_library

    cases = load_cases()
    library = load_library(Path("data/library.yaml"), cases)
    client = clients(load_settings(SearchSettings).search_index)[1]
    total = 0
    for case_id in sorted(json.loads(FROZEN.read_text())):
        key = load_key(KEYS_DIR / f"{case_id}.json")
        evidence = evidence_sources(Path("build/evidence") / f"{case_id}.json")
        chunks = library_sources(case_id, client, library, cases)
        sources = evidence | chunks
        planted = None
        if args.plant:
            planted, texts = next(unstated_items(key))
            sources = sources | {PLANTED: f"An earlier page said: {texts[0]}"}
        found = hits(key, sources)
        total += len(found)
        items = len(list(unstated_items(key)))
        print(
            f"{case_id}: {items} unstated items, {len(evidence)} evidence sources, "
            f"{len(chunks)} library chunks, {len(found)} hits"
        )
        for h in found:
            print(f"  {h.item} in {h.source_id}: {h.runs} shared {RUN_WORDS}-word runs")
        # Another item may share the planted quote; the planted item must be among the hits.
        if args.plant and (planted, PLANTED) not in [(h.item, h.source_id) for h in found]:
            print(f"  the planted chunk was not reported for {planted}")
            return 1
    return 1 if total and not args.plant else 0


if __name__ == "__main__":
    raise SystemExit(main())

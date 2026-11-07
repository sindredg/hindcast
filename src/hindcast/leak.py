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


def item_runs(texts: list[str], n: int = RUN_WORDS) -> set[tuple[str, ...]]:
    """A key item's runs of n words; a text shorter than n is one run, whole.

    Without this an item below n words had no run and was checked against
    nothing (issue #83).
    """
    out: set[tuple[str, ...]] = set()
    for text in texts:
        words = WORD.findall(text.lower())
        if k := min(n, len(words)):
            out |= {tuple(words[i : i + k]) for i in range(len(words) - k + 1)}
    return out


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
    items = [(item, item_runs(texts, n)) for item, texts in unstated_items(key)]
    if not items or not sources:
        raise ValueError(
            f"{key.case_id}: no unstated key item or no source; the check could not fail"
        )
    # A short item's whole-text run is compared with source runs of its own length.
    lengths = sorted({len(run) for _, item_set in items for run in item_set})
    source_runs = {
        source_id: set().union(*(runs(text, k) for k in lengths)) if lengths else set()
        for source_id, text in sources.items()
    }
    out = []
    for item, item_set in items:
        for source_id, shared in source_runs.items():
            if common := item_set & shared:
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


def snapshot_sources(
    path: Path,
    case_id: str,
    record_path: Path,
    *,
    cases: Mapping[str, Case] | None = None,
    library: Mapping[str, LibraryDocument] | None = None,
) -> dict[str, str]:
    """A case's chunks from a sealed snapshot, once the file matches its recorded hash.

    After teardown there is no index to query; the snapshot taken before it
    stands in for the filtered library (decision 0022). A snapshot of another
    case holds every document that case could read, so for a case that is
    not the snapshot's own, the chunks are filtered by this case's rule in
    code (`hindcast.search.allowed`): the sealed snapshots hold the whole
    library, so every keyed case can be checked offline.
    """
    import hashlib

    from hindcast.search import allowed

    data = path.read_bytes()
    document = json.loads(data)
    # Without the registries the snapshot has to be the case's own.
    snapshot_case = document.get("case_id", case_id) if cases and library else case_id
    record = json.loads(record_path.read_text("utf-8"))["snapshots"]
    entries = [s for s in record if s["case_id"] == snapshot_case]
    if not entries:
        raise ValueError(f"{snapshot_case}: no snapshot record in {record_path}")
    if hashlib.sha256(data).hexdigest() != entries[-1]["sha256"]:
        raise ValueError(f"{path} does not match the hash recorded for {snapshot_case}")
    chunks = document["chunks"]
    if snapshot_case != case_id and cases and library:
        chunks = [
            c
            for c in chunks
            if c["doc_id"] in library and allowed(cases[case_id], library[c["doc_id"]])
        ]
    found = {c["id"]: c["content"] for c in chunks}
    if not found:
        raise ValueError(
            f"{case_id}: the snapshot holds no library chunks for it; the check could not fail"
        )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.leak")
    parser.add_argument("case_id", nargs="?", help="one case; every keyed case when left out")
    parser.add_argument("--plant", action="store_true", help="add one planted chunk per case")
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="read the library from a sealed case's snapshot file, filtered by this case's rule",
    )
    args = parser.parse_args(argv)
    if args.snapshot is not None and args.case_id is None:
        parser.error("--snapshot needs the case ID")

    from hindcast.cases import load_cases
    from hindcast.config import SearchSettings, load_settings
    from hindcast.index import clients
    from hindcast.library import load_library

    cases = load_cases()
    library = load_library(Path("data/library.yaml"), cases)
    # With a snapshot the check runs offline: no search client is made.
    client = None if args.snapshot else clients(load_settings(SearchSettings).search_index)[1]
    total = 0
    keyed = sorted(json.loads(FROZEN.read_text()))
    if args.case_id is not None and args.case_id not in keyed:
        parser.error(f"{args.case_id} has no frozen key")
    for case_id in [args.case_id] if args.case_id else keyed:
        key = load_key(KEYS_DIR / f"{case_id}.json")
        evidence = evidence_sources(Path("build/evidence") / f"{case_id}.json")
        if args.snapshot is not None:
            from hindcast.seal import SNAPSHOTS

            chunks = snapshot_sources(
                args.snapshot, case_id, SNAPSHOTS, cases=cases, library=library
            )
        else:
            chunks = library_sources(case_id, client, library, cases)
        sources = evidence | chunks
        planted = None
        if args.plant:
            planted, texts = next(unstated_items(key))
            sources = sources | {PLANTED: f"An earlier page said: {texts[0]}"}
        found = hits(key, sources)
        # Only the planted source may report in a --plant run; any other hit is a leak.
        total += sum(h.source_id != PLANTED for h in found)
        items = len(list(unstated_items(key)))
        print(
            f"{case_id}: {items} unstated items, {len(evidence)} evidence sources, "
            f"{len(chunks)} library chunks, {len(found)} hits"
        )
        for h in found:
            print(f"  {h.item} in {h.source_id}: {h.runs} shared runs")
        # Another item may share the planted quote; the planted item must be among the hits.
        if args.plant and (planted, PLANTED) not in [(h.item, h.source_id) for h in found]:
            print(f"  the planted chunk was not reported for {planted}")
            return 1
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())

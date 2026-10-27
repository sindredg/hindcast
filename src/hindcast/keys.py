"""Answer keys: each case's postmortem as a reviewed, frozen key.

    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.keys draft [--case ID ...]
    PYTHONPATH=src uv run --frozen python -m hindcast.keys freeze <case_id>

draft: downloads the case's postmortem (hash-checked), cuts out the article
(and, in a monthly report, the case's incident), runs the answer-key analyzer,
and writes build/keys/<case_id>-draft.json and a review sheet next to it. The
analyzer's raw result is kept in Blob extracted/keys/ and reused.

Content Understanding returns no source locations for HTML, so every key item
carries a quote that has to appear word for word in the postmortem; a quote
that does not is listed for review. A person reviews each sheet, corrects the
draft, and marks what the provider already said during the incident
(decision 0005). freeze checks the reviewed draft, writes eval/keys/<case_id>.json,
and records its SHA-256 in eval/keys/frozen.json; a test checks the hashes.
"""

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from azure.core.exceptions import ResourceNotFoundError

from hindcast.cases import Case
from hindcast.evidence import CaseEvidence

KEYS_DIR = Path("eval/keys")
FROZEN = KEYS_DIR / "frozen.json"
DRAFTS = Path("build/keys")
UTC_MINUTE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z")
ATTACK = ("attack", "not an attack")
BASIS = ("stated", "implied", "not stated")
# A monthly report holds several incidents; the key covers the case's only.
INCIDENT_HEADINGS = {"github-2026-08-17": "August 17"}


@dataclass(frozen=True)
class KeyItem:
    text: str
    source_quote: str
    stated_during_incident: bool = False


@dataclass(frozen=True)
class TimelineEvent:
    time: str
    time_as_written: str
    event: str
    source_quote: str
    stated_during_incident: bool = False


@dataclass(frozen=True)
class AnswerKey:
    case_id: str
    attack: Literal["attack", "not an attack"]
    attack_basis: Literal["stated", "implied", "not stated"]
    attack_quote: str
    root_cause: KeyItem
    contributing_factors: tuple[KeyItem, ...]
    timeline: tuple[TimelineEvent, ...]
    fixes: tuple[KeyItem, ...]


def key_json(key: AnswerKey) -> bytes:
    return (json.dumps(asdict(key), sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def _item(raw: object, where: str) -> KeyItem:
    if not isinstance(raw, dict) or sorted(raw) != [
        "source_quote",
        "stated_during_incident",
        "text",
    ]:
        raise ValueError(f"{where}: needs text, source_quote, and stated_during_incident")
    if not str(raw["text"]).strip() or not str(raw["source_quote"]).strip():
        raise ValueError(f"{where}: text and source_quote must not be empty")
    if not isinstance(raw["stated_during_incident"], bool):
        raise ValueError(f"{where}: stated_during_incident must be true or false")
    return KeyItem(raw["text"], raw["source_quote"], raw["stated_during_incident"])


def _event(raw: object, where: str) -> TimelineEvent:
    names = ["event", "source_quote", "stated_during_incident", "time", "time_as_written"]
    if not isinstance(raw, dict) or sorted(raw) != names:
        raise ValueError(f"{where}: needs {', '.join(names)}")
    if not UTC_MINUTE.fullmatch(str(raw["time"])):
        raise ValueError(f"{where}: time {raw['time']!r} must be UTC like 2026-02-20T19:09Z")
    item = _item(
        {
            "text": raw["event"],
            "source_quote": raw["source_quote"],
            "stated_during_incident": raw["stated_during_incident"],
        },
        where,
    )
    return TimelineEvent(
        raw["time"],
        raw["time_as_written"],
        item.text,
        item.source_quote,
        item.stated_during_incident,
    )


def load_key(path: Path) -> AnswerKey:
    """Read a key, refusing a missing field, an unknown value, or a time that is not UTC."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    names = [
        "attack",
        "attack_basis",
        "attack_quote",
        "case_id",
        "contributing_factors",
        "fixes",
        "root_cause",
        "timeline",
    ]
    if sorted(raw) != names:
        raise ValueError(f"{path}: fields must be {', '.join(names)}")
    if raw["attack"] not in ATTACK:
        raise ValueError(f"{path}: attack {raw['attack']!r} is not one of {ATTACK}")
    if raw["attack_basis"] not in BASIS:
        raise ValueError(f"{path}: attack_basis {raw['attack_basis']!r} is not one of {BASIS}")
    if raw["attack_basis"] != "not stated" and not raw["attack_quote"].strip():
        raise ValueError(f"{path}: attack_quote is empty, but the basis is {raw['attack_basis']}")
    if not raw["timeline"]:
        raise ValueError(f"{path}: timeline is empty")
    return AnswerKey(
        case_id=raw["case_id"],
        attack=raw["attack"],
        attack_basis=raw["attack_basis"],
        attack_quote=raw["attack_quote"],
        root_cause=_item(raw["root_cause"], "root_cause"),
        contributing_factors=tuple(
            _item(r, f"contributing_factors[{n}]")
            for n, r in enumerate(raw["contributing_factors"])
        ),
        timeline=tuple(_event(r, f"timeline[{n}]") for n, r in enumerate(raw["timeline"])),
        fixes=tuple(_item(r, f"fixes[{n}]") for n, r in enumerate(raw["fixes"])),
    )


def _plain(text: str) -> str:
    """Text as compared for quotes: the same words in the same order.

    Markdown links and emphasis, HTML tags (tables come back as HTML, and a
    quote joins a row's cells), spacing, and letter case are not compared: a
    quote taken from mid-sentence starts with a capital.
    """
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]", "", text).replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", html.unescape(text)).strip().casefold()


def _string(fields: dict, name: str) -> str:
    return (fields.get(name) or {}).get("valueString") or ""


def _objects(fields: dict, name: str) -> list[dict]:
    return [
        (entry.get("valueObject") or {})
        for entry in (fields.get(name) or {}).get("valueArray") or []
    ]


def draft_key(case: Case, result: dict, markdown: str) -> tuple[AnswerKey, list[str]]:
    """The analyzer's fields as a draft key, and what a reviewer has to look at."""
    fields = result["contents"][0].get("fields", {})
    page = _plain(markdown)
    problems: list[str] = []

    def check(where: str, quote: str) -> None:
        if not quote.strip() or _plain(quote) not in page:
            problems.append(f"{where}: quote not found word for word in the postmortem")

    root = (fields.get("root_cause") or {}).get("valueObject") or {}
    root_cause = KeyItem(_string(root, "text"), _string(root, "quote"))
    check("root_cause", root_cause.source_quote)
    lists: dict[str, list[KeyItem]] = {}
    for name in ("contributing_factors", "fixes"):
        lists[name] = [
            KeyItem(_string(o, "text"), _string(o, "quote")) for o in _objects(fields, name)
        ]
        for n, entry in enumerate(lists[name]):
            check(f"{name}[{n}]", entry.source_quote)
    timeline = []
    for n, o in enumerate(_objects(fields, "timeline")):
        event = TimelineEvent(
            _string(o, "time_utc"),
            _string(o, "time_as_written"),
            _string(o, "event"),
            _string(o, "quote"),
        )
        if not UTC_MINUTE.fullmatch(event.time):
            problems.append(
                f"timeline[{n}]: time {event.time!r} is not UTC; "
                f"as written {event.time_as_written!r}"
            )
        check(f"timeline[{n}]", event.source_quote)
        timeline.append(event)
    attack_quote = _string(fields, "attack_quote")
    if _string(fields, "attack_basis") != "not stated":
        check("attack_quote", attack_quote)
    key = AnswerKey(
        case_id=case.case_id,
        attack=_string(fields, "attack"),  # type: ignore[arg-type]
        attack_basis=_string(fields, "attack_basis"),  # type: ignore[arg-type]
        attack_quote=attack_quote,
        root_cause=root_cause,
        contributing_factors=tuple(lists["contributing_factors"]),
        timeline=tuple(timeline),
        fixes=tuple(lists["fixes"]),
    )
    return key, problems


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 5}


def _may_state(text: str, evidence: CaseEvidence) -> list[str]:
    """Updates that share most of an item's longer words: a hint for review, not a verdict."""
    words = _words(text)
    if not words:
        return []
    return [
        u.update_id
        for u in evidence.updates
        if u.text and len(words & _words(u.text)) >= max(3, len(words) // 2)
    ]


def review_sheet(key: AnswerKey, evidence: CaseEvidence, problems: list[str]) -> str:
    """Markdown for the reviewer: each field, its quote, and updates that may state it."""
    lines = [
        f"# Answer key review: {key.case_id}",
        "",
        "Check each item against the postmortem. Correct what is wrong, and mark an item",
        "stated during the incident when an update listed next to it already says it.",
        f'When it is right, say "freeze {key.case_id}".',
        "",
        "## Problems found by the draft check",
        "",
        *([f"- {p}" for p in problems] or ["- None."]),
        "",
        "## Attack",
        "",
        f"- Verdict: **{key.attack}** (basis: {key.attack_basis})",
        f"- Quote: {key.attack_quote or '(none)'}",
        "",
    ]

    def entry(label: str, text: str, quote: str) -> list[str]:
        hint = _may_state(f"{text} {quote}", evidence)
        return [
            f"- **{label}** {text}",
            f"  - Quote: {quote}",
            f"  - Updates that may state it: {', '.join(hint) if hint else 'none'}",
        ]

    lines += ["## Root cause", "", *entry("", key.root_cause.text, key.root_cause.source_quote), ""]
    lines += ["## Contributing factors", ""]
    for n, item in enumerate(key.contributing_factors, 1):
        lines += entry(f"{n}.", item.text, item.source_quote)
    lines += ["", "## Timeline", ""]
    for event in key.timeline:
        lines += entry(f"{event.time} ({event.time_as_written})", event.event, event.source_quote)
    lines += ["", "## Fixes", ""]
    for n, item in enumerate(key.fixes, 1):
        lines += entry(f"{n}.", item.text, item.source_quote)
    return "\n".join(lines) + "\n"


def incident_part(article_html: str, heading: str) -> str:
    """From a monthly report, the part under the case's incident heading only."""
    parts = re.split(r"(?=<h[2-4][^>]*>)", article_html)
    for n, part in enumerate(parts):
        title = re.match(r"<h([2-4])[^>]*>(.*?)</h\1>", part, re.S)
        if title and html.unescape(re.sub(r"<[^>]+>", "", title.group(2))).strip().startswith(
            heading
        ):
            level = title.group(1)
            kept = [part]
            for later in parts[n + 1 :]:
                deeper = re.match(r"<h([2-4])", later)
                if deeper and deeper.group(1) <= level:
                    break
                kept.append(later)
            return "".join(kept)
    raise ValueError(f"no incident heading starting {heading!r} in the report")


def _draft(case: Case, evidence: CaseEvidence) -> None:
    from hindcast.extract import analyze
    from hindcast.library_extract import article
    from hindcast.storage import container, download_source, upload_bytes

    name = f"keys/{case.case_id}-result.json"
    try:
        stored = json.loads(container("extracted").download_blob(name).readall())
        outcome = "reused"
    except ResourceNotFoundError:
        source = next(s for s in case.sources if s.kind == "postmortem")
        found = article(download_source(case.case_id, source), source.url)
        body = found.html
        if case.case_id in INCIDENT_HEADINGS:
            body = incident_part(body, INCIDENT_HEADINGS[case.case_id])
        page = f"<html><body><h1>{html.escape(found.title)}</h1>{body}</body></html>"
        stored = analyze("hindcast_answer_key", page.encode(), "text/html")
        upload_bytes("extracted", name, (json.dumps(stored, ensure_ascii=False) + "\n").encode())
        outcome = "uploaded"
    markdown = stored["result"]["contents"][0].get("markdown", "")
    key, problems = draft_key(case, stored["result"], markdown)
    DRAFTS.mkdir(parents=True, exist_ok=True)
    (DRAFTS / f"{case.case_id}-draft.json").write_bytes(key_json(key))
    (DRAFTS / f"{case.case_id}-review.md").write_text(review_sheet(key, evidence, problems))
    print(
        f"{case.case_id}: {len(key.contributing_factors)} factors, {len(key.timeline)} timeline "
        f"events, {len(key.fixes)} fixes, {len(problems)} problems\n  blob: {outcome}"
        f"\n  usage: {json.dumps(stored.get('usage', {}), sort_keys=True)}"
    )


def freeze(case_id: str, drafts: Path = DRAFTS, keys_dir: Path = KEYS_DIR) -> str:
    """Freeze a reviewed draft: write the key and record its hash; never over a frozen key."""
    key = load_key(drafts / f"{case_id}-draft.json")
    if key.case_id != case_id:
        raise ValueError(f"the draft is for {key.case_id}, not {case_id}")
    target = keys_dir / f"{case_id}.json"
    if target.exists():
        raise ValueError(f"{target} is frozen already; a new key needs a new review")
    data = key_json(key)
    keys_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    frozen_path = keys_dir / "frozen.json"
    frozen = json.loads(frozen_path.read_text()) if frozen_path.is_file() else {}
    frozen[case_id] = hashlib.sha256(data).hexdigest()
    frozen_path.write_text(json.dumps(frozen, sort_keys=True, indent=2) + "\n")
    return frozen[case_id]


def main(argv: list[str] | None = None) -> int:
    from hindcast.cases import load_cases

    parser = argparse.ArgumentParser(prog="python -m hindcast.keys")
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft", help="draft each case's key for review")
    draft.add_argument("--case", action="append")
    frozen = commands.add_parser("freeze", help="freeze one reviewed key")
    frozen.add_argument("case_id")
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.command == "freeze":
        print(f"{args.case_id}: frozen, sha256 {freeze(args.case_id)}")
        return 0
    failed = False
    for case_id in args.case or sorted(cases):
        evidence_path = Path("build/evidence") / f"{case_id}.json"
        try:
            evidence = _load_evidence(evidence_path)
            _draft(cases[case_id], evidence)
        except (ValueError, OSError) as error:
            failed = True
            print(f"{case_id}: {str(error).splitlines()[0]}")
    return 1 if failed else 0


def _load_evidence(path: Path) -> CaseEvidence:
    from hindcast.evidence import ChartEvidence, Dropped, EvidenceUpdate

    raw = json.loads(path.read_text())
    return CaseEvidence(
        case_id=raw["case_id"],
        provider=raw["provider"],
        title=raw["title"],
        started_at=raw["started_at"],
        updates=tuple(EvidenceUpdate(**u) for u in raw["updates"]),
        dropped=tuple(Dropped(**d) for d in raw["dropped"]),
        charts=tuple(ChartEvidence(**c) for c in raw.get("charts", [])),
    )


if __name__ == "__main__":
    sys.exit(main())

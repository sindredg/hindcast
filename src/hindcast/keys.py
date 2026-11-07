"""Answer keys: each case's postmortem as a reviewed, frozen key.

    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.keys draft [--case ID ...]
    PYTHONPATH=src uv run --frozen python -m hindcast.keys check <case_id>
    PYTHONPATH=src uv run --frozen python -m hindcast.keys freeze <case_id>

draft: downloads the case's postmortem (hash-checked), cuts out the article
(and, in a monthly report, the case's incident; from a status snapshot, the
resolved update's summary), runs the answer-key analyzer,
and writes build/keys/<case_id>-draft.json and a review sheet next to it. An
existing draft is kept, since it may hold review edits. The analyzer's raw
result is kept in Blob extracted/keys/ and reused.

Content Understanding returns no source locations for HTML, so every key item
carries a quote that has to appear word for word in the postmortem; a quote
that does not is listed for review. A person reviews each sheet, corrects the
draft, and marks what the provider already said during the incident
(decision 0005). freeze checks the reviewed draft, writes eval/keys/<case_id>.json,
and records its SHA-256 in eval/keys/frozen.json; a test checks the hashes.

check: for a key drafted by hand (a revealed sealed case, decision 0022),
checks build/keys/<case_id>-draft.json against the captured postmortem under
data/sources/ and rewrites the review sheet. It exits 1 while a quote is missing.
"""

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from azure.core.exceptions import ResourceNotFoundError

from hindcast.cases import Case, SourceFile
from hindcast.evidence import CaseEvidence

KEYS_DIR = Path("eval/keys")
FROZEN = KEYS_DIR / "frozen.json"
DRAFTS = Path("build/keys")
UTC_MINUTE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z")
# The zones providers write; a written time with one of these and a clock
# time is converted and compared with the key's UTC time (issue #12).
ZONES = {
    "UTC": "UTC",
    "GMT": "UTC",
    "PT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "US/Pacific": "America/Los_Angeles",
    "America/Los_Angeles": "America/Los_Angeles",
    "ET": "America/New_York",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "US/Eastern": "America/New_York",
    "America/New_York": "America/New_York",
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
}
ZONE = re.compile(r"(?<![\w/])(" + "|".join(re.escape(z) for z in ZONES) + r")(?![\w/])")
CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})\b")
DURATION = re.compile(r"\b(lasting|lasted|duration|hours?|minutes?)\b", re.IGNORECASE)
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DAY_MONTH_YEAR = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b")
MONTH_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?(?:\s+(\d{4}))?\b")
MONTHS = {
    name[:n].lower(): i
    for i, name in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        1,
    )
    for n in (3, len(name))
}
ATTACK = ("attack", "not an attack")
BASIS = ("stated", "implied", "not stated")
# A monthly report holds several incidents; the key covers the case's only.
INCIDENT_HEADINGS = {"github-2026-08-17": "August 17"}
# GitHub's placeholder resolved update is 31 words; its summaries run to
# well over a hundred.
MIN_SUMMARY_WORDS = 50


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


def _written_date(text: str, year: int) -> tuple[int, int, int] | None:
    if found := ISO_DATE.search(text):
        return int(found[1]), int(found[2]), int(found[3])
    if (found := DAY_MONTH_YEAR.search(text)) and found[2].lower() in MONTHS:
        return int(found[3]), MONTHS[found[2].lower()], int(found[1])
    for found in MONTH_DAY.finditer(text):
        if found[1].lower() in MONTHS:
            return int(found[3] or year), MONTHS[found[1].lower()], int(found[2])
    return None


def written_time_problem(event: TimelineEvent) -> str | None:
    """Why the event's written time, converted from its zone, is not its UTC time.

    None when the written text names no zone or no clock time, or when the
    conversion agrees. Without a written date, the UTC date and the day
    before are both tried: a Pacific evening is the next UTC day.
    """
    zone = ZONE.search(event.time_as_written)
    clocks = CLOCK.findall(event.time_as_written)
    # A text with two clock times or a duration ("13:40 UTC, lasting 7 hours")
    # names more than the event's own time, so there is nothing to compare.
    if (
        zone is None
        or len(clocks) != 1
        or DURATION.search(event.time_as_written)
        or not UTC_MINUTE.fullmatch(event.time)
    ):
        return None
    clock = clocks[0]
    expected = datetime.strptime(event.time, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
    try:
        tz = ZoneInfo(ZONES[zone[1]])
    except ZoneInfoNotFoundError:
        return f"as written {event.time_as_written!r}: no zone database for {zone[1]}"
    written = _written_date(event.time_as_written, expected.year)
    if written:
        dates = [written]
    else:
        day = expected.date()
        before = day - timedelta(days=1)
        dates = [(day.year, day.month, day.day), (before.year, before.month, before.day)]
    found = []
    for date in dates:
        try:
            local = datetime(*date, int(clock[0]), int(clock[1]), tzinfo=tz)
        except ValueError:
            return f"as written {event.time_as_written!r}: not a date and time"
        found.append(local.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"))
    if event.time in found:
        return None
    return f"as written {event.time_as_written!r} is {found[0]}, not {event.time}; check the zone"


def time_problems(key: AnswerKey) -> list[str]:
    """One line per timeline event whose written time does not convert to its UTC time."""
    out = []
    for n, event in enumerate(key.timeline):
        if problem := written_time_problem(event):
            out.append(f"timeline[{n}]: {problem}")
    return out


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
    # Inline tags vanish and block tags become spaces, so "<strong>A</strong>: b"
    # reads "A: b". Entities are decoded next, so &#8217; equals a typed curly quote.
    text = re.sub(r"</?(?:strong|em|b|i|a|span|code|sup|sub)\b[^>]*>", "", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]", "", text).replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


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
        elif problem := written_time_problem(event):
            problems.append(f"timeline[{n}]: {problem}")
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


def review_sheet(
    key: AnswerKey, evidence: CaseEvidence, problems: list[str], source_url: str = ""
) -> str:
    """Markdown for the reviewer: each field, its quote, and updates that may state it."""
    lines = [
        f"# Answer key review: {key.case_id}",
        "",
        *([f"Postmortem: {source_url}", ""] if source_url else []),
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
            f"- **{label}** {text}" if label else f"- {text}",
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


def statuspage_summary(snapshot: bytes) -> tuple[str, str]:
    """The incident's name and its resolved update as HTML paragraphs.

    GitHub writes its summary of the cause into the resolved update days after
    the incident; for such a case that update is the postmortem. Until then the
    update is a placeholder ("A detailed root cause analysis will be shared"),
    so a body under MIN_SUMMARY_WORDS is refused (issue #36). The floor only
    stops a placeholder; whether the text states a cause is the key review's call.
    """
    incident = json.loads(snapshot)
    resolved = sorted(
        (u for u in incident["incident_updates"] if u["status"] == "resolved"),
        key=lambda u: u["created_at"],
    )
    if not resolved:
        raise ValueError(f"{incident['name']!r}: no resolved update to read a summary from")
    body = resolved[0]["body"]
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", body)))
    if words < MIN_SUMMARY_WORDS:
        raise ValueError(
            f"{incident['name']!r}: the resolved update has {words} words, under "
            f"{MIN_SUMMARY_WORDS}; it states no cause yet"
        )
    # GitHub separates paragraphs with a blank line or with <br /><br />.
    body = re.sub(r"(?:\s*<br\s*/?>\s*){2,}", "\n\n", body)
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    return incident["name"], "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)


def postmortem_page(source: SourceFile, data: bytes) -> tuple[str, str]:
    """The postmortem's title and body HTML: a status snapshot's summary, or a page's article."""
    if source.filename.endswith(".json"):
        return statuspage_summary(data)
    from hindcast.library_extract import article

    found = article(data, source.url)
    return found.title, found.html


def _draft(case: Case, evidence: CaseEvidence) -> None:
    from hindcast.extract import analyze
    from hindcast.storage import container, download_source, upload_bytes

    source = next((s for s in case.sources if s.kind == "postmortem"), None)
    if source is None:
        raise ValueError(f"{case.case_id}: no postmortem source in the registry")
    name = f"keys/{case.case_id}-result.json"
    try:
        stored = json.loads(container("extracted").download_blob(name).readall())
        outcome = "reused"
    except ResourceNotFoundError:
        title, body = postmortem_page(source, download_source(case.case_id, source))
        if case.case_id in INCIDENT_HEADINGS:
            body = incident_part(body, INCIDENT_HEADINGS[case.case_id])
        page = f"<html><body><h1>{html.escape(title)}</h1>{body}</body></html>"
        stored = analyze("hindcast_answer_key", page.encode(), "text/html")
        upload_bytes("extracted", name, (json.dumps(stored, ensure_ascii=False) + "\n").encode())
        outcome = "uploaded"
    markdown = stored["result"]["contents"][0].get("markdown", "")
    key, problems = draft_key(case, stored["result"], markdown)
    url = next(s.url for s in case.sources if s.kind == "postmortem")
    if not write_draft(key, review_sheet(key, evidence, problems, url)):
        print(f"{case.case_id}: a draft exists and may hold review edits; kept")
    print(
        f"{case.case_id}: {len(key.contributing_factors)} factors, {len(key.timeline)} timeline "
        f"events, {len(key.fixes)} fixes, {len(problems)} problems\n  blob: {outcome}"
        f"\n  usage: {json.dumps(stored.get('usage', {}), sort_keys=True)}"
    )


def quote_problems(key: AnswerKey, page: str) -> list[str]:
    """One line per key quote missing from the page, which is already _plain text."""
    quotes = [("root_cause", key.root_cause.source_quote)]
    if key.attack_basis != "not stated":
        quotes.append(("attack_quote", key.attack_quote))
    for name, items in (("contributing_factors", key.contributing_factors), ("fixes", key.fixes)):
        quotes += [(f"{name}[{n}]", item.source_quote) for n, item in enumerate(items)]
    quotes += [(f"timeline[{n}]", e.source_quote) for n, e in enumerate(key.timeline)]
    return [
        f"{where}: quote not found word for word in the postmortem"
        for where, quote in quotes
        if not quote.strip() or _plain(quote) not in page
    ]


def check_draft(
    case: Case, drafts: Path = DRAFTS, sources: Path = Path("data/sources")
) -> tuple[AnswerKey, list[str], str]:
    """A hand-drafted key, its quote problems against the captured postmortem, and its URL.

    Decision 0022 drafts a revealed case's key by hand, not with Content
    Understanding; the quotes are checked here the same way draft_key checks
    the analyzer's.
    """
    key = load_key(drafts / f"{case.case_id}-draft.json")
    if key.case_id != case.case_id:
        raise ValueError(f"the draft is for {key.case_id}, not {case.case_id}")
    source = next((s for s in case.sources if s.kind == "postmortem"), None)
    if source is None:
        raise ValueError(f"{case.case_id}: no postmortem source in the registry")
    data = (sources / case.case_id / source.filename).read_bytes()
    # The registry hash ties the quotes to the file a reader can fetch again.
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise ValueError(f"{source.filename}: differs from its registry hash")
    title, body = postmortem_page(source, data)
    if case.case_id in INCIDENT_HEADINGS:
        body = incident_part(body, INCIDENT_HEADINGS[case.case_id])
    return key, quote_problems(key, _plain(f"{title} {body}")) + time_problems(key), source.url


def write_draft(key: AnswerKey, sheet: str, drafts: Path = DRAFTS) -> bool:
    """Write a draft and its review sheet, unless a draft exists: it may hold review edits."""
    draft = drafts / f"{key.case_id}-draft.json"
    if draft.exists():
        return False
    drafts.mkdir(parents=True, exist_ok=True)
    draft.write_bytes(key_json(key))
    (drafts / f"{key.case_id}-review.md").write_text(sheet)
    return True


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
    # Required: a loop over every case would send sealed, revealed, and
    # injection cases to the analyzer (issue #103).
    draft.add_argument("--case", action="append", required=True)
    frozen = commands.add_parser("freeze", help="freeze one reviewed key")
    frozen.add_argument("case_id")
    checked = commands.add_parser("check", help="check a hand-drafted key and write its sheet")
    checked.add_argument("case_id")
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.command == "check":
        try:
            key, problems, url = check_draft(cases[args.case_id])
            evidence = _load_evidence(Path("build/evidence") / f"{args.case_id}.json")
        except (KeyError, ValueError, OSError) as error:
            print(f"{args.case_id}: {error}")
            return 1
        # The sheet is rewritten on every check; the draft, which holds the
        # review edits, is only read.
        sheet = DRAFTS / f"{args.case_id}-review.md"
        sheet.write_text(review_sheet(key, evidence, problems, url), encoding="utf-8")
        print(f"{args.case_id}: {len(problems)} problems; sheet {sheet}")
        for problem in problems:
            print(f"  {problem}")
        return 1 if problems else 0
    if args.command == "freeze":
        try:
            print(f"{args.case_id}: frozen, sha256 {freeze(args.case_id)}")
        except (ValueError, OSError) as error:
            print(f"{args.case_id}: {error}")
            return 1
        return 0
    failed = False
    for case_id in args.case:
        case = cases.get(case_id)
        if case is None or case.role not in ("showcase", "development"):
            # Decision 0022: a revealed case's key is drafted by hand; sealed
            # and injection cases have no key.
            failed = True
            role = f"a {case.role} case" if case else "not in the registry"
            print(f"{case_id}: {role}; only showcase and development keys are drafted here")
            continue
        evidence_path = Path("build/evidence") / f"{case_id}.json"
        try:
            evidence = _load_evidence(evidence_path)
            _draft(case, evidence)
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

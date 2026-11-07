"""The investigation's view parts as data (decision 0008).

The timeline chart is a Vega-Lite spec, the evidence graph is DOT text, and
the scored view is a list of rows. Each is built here by a pure function over
a stored result, so a test checks what the page draws without a browser, and
the page only hands the data to Streamlit.

The scored view reads the files the score was computed from: the run's
judgment, its review, the reviewer's judgment, the frozen key, and the frozen
labels. It refuses a key or labels that differ from their frozen hash, and a
judgment made for another file than the run shown.
"""

import hashlib
import json
import textwrap
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hindcast import cited
from hindcast.evaluation.score import load_second_judgments, run_items_behind
from hindcast.keys import AnswerKey, load_key
from hindcast.labels import item_ids
from hindcast.result import Investigation, TimelineEvent

SCORED_ROOT = Path("eval/reconstruction/showcase-v1")
KEYS_DIR = Path("eval/keys")
LABELS_DIR = KEYS_DIR / "labels"

# The project palette (.streamlit/config.toml): Graphviz does not take the
# page's theme, so every colour is set here.
TEXT = "#f5f5f5"
BOX = "#141414"
GREEN = "#22c55e"
AMBER = "#f0b429"
GREY = "#b4b4b4"
DIM = "#8c8c8c"
# A stated time comes from an update; an inferred one was worked out, so it
# is drawn hollow and grey, not as a fact.
TIME_KINDS = {"stated": (GREEN, "circle", True), "inferred": (GREY, "diamond", False)}


def utc(text: str) -> str | None:
    """The time as a full UTC ISO string, or None when it is not an ISO time in UTC."""
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None or when.utcoffset() != UTC.utcoffset(None):
        return None
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def shorten(text: str, width: int) -> str:
    return textwrap.shorten(" ".join(text.split()), width=width, placeholder=" …")


def timeline_spec(events: Sequence[TimelineEvent]) -> tuple[dict | None, list[int]]:
    """The chart's Vega-Lite spec, and the numbers of the events left out.

    An event whose time is not an ISO time in UTC stays in the list under the
    chart and is left out of the chart: placing it would invent a time.
    """
    rows, skipped = [], []
    for n, event in enumerate(events, 1):
        when = utc(event.time)
        if when is None:
            skipped.append(n)
            continue
        rows.append(
            {
                "n": n,
                "time": when,
                "kind": event.time_kind,
                # Axis labels are drawn as text, not HTML or Markdown.
                "label": f"{n}. {shorten(event.event, 60)}",
            }
        )
    if not rows:
        return None, skipped
    kinds = list(TIME_KINDS)
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "data": {"values": rows},
        "height": {"step": 26},
        "mark": {"type": "point", "size": 110, "strokeWidth": 2},
        "encoding": {
            # A UTC scale, or the axis would show the reader's local time.
            "x": {
                "field": "time",
                "type": "temporal",
                "scale": {"type": "utc"},
                "axis": {"title": "Time (UTC)", "format": "%b %d %H:%M"},
            },
            "y": {
                "field": "label",
                "type": "nominal",
                "sort": {"field": "n", "order": "ascending"},
                "axis": {"title": None, "labelLimit": 420},
            },
            "color": {
                "field": "kind",
                "type": "nominal",
                "scale": {"domain": kinds, "range": [TIME_KINDS[k][0] for k in kinds]},
                "legend": {"title": "Time", "orient": "top"},
            },
            "shape": {
                "field": "kind",
                "type": "nominal",
                "scale": {"domain": kinds, "range": [TIME_KINDS[k][1] for k in kinds]},
            },
            "fill": {
                "field": "kind",
                "type": "nominal",
                "scale": {
                    "domain": kinds,
                    "range": [TIME_KINDS[k][0] if TIME_KINDS[k][2] else BOX for k in kinds],
                },
                "legend": None,
            },
            # No model text in the tooltip: the time and its kind only.
            "tooltip": [
                {"field": "n", "type": "ordinal", "title": "Event"},
                {"field": "time", "type": "nominal", "title": "Time"},
                {"field": "kind", "type": "nominal", "title": "Kind"},
            ],
        },
    }
    return spec, skipped


def dot_label(*lines: str) -> str:
    """A quoted DOT string whose text a model-written line cannot leave.

    Inside a quoted DOT string only a backslash and a double quote are
    special; a backslash also starts Graphviz's label escapes (\\n, \\l, \\N).
    Both are escaped, line breaks and other control characters in the text
    become spaces (a NUL can end the string in a C parser), and the line
    breaks between the given lines are the only \\n escapes in the result.
    """

    def one(line: str) -> str:
        line = "".join(" " if unicodedata.category(c) == "Cc" else c for c in line)
        line = " ".join(line.split())
        return line.replace("\\", "\\\\").replace('"', '\\"')

    return '"' + "\\n".join(one(line) for line in lines) + '"'


def _wrapped(text: str, width: int = 90) -> list[str]:
    return textwrap.wrap(shorten(text, width), 30) or [""]


def evidence_dot(investigation: Investigation, case_id: str) -> str:
    """The evidence graph: what each claim rests on, from left to right.

    The root cause and each contributing factor link to the findings they
    rest on and the items they cite; each finding links to the findings it
    rests on and to the updates, charts, or library sections it cites. Node
    IDs are the graph's own (n0, n1, ...), never text from the run.
    """
    lines = [
        "digraph evidence {",
        f'  graph [rankdir=LR bgcolor="transparent" nodesep=0.2 ranksep=0.7 fontcolor="{TEXT}"];',
        f'  node [shape=box style="rounded,filled" fillcolor="{BOX}" color="{DIM}"'
        f' fontcolor="{TEXT}" fontname="Helvetica" fontsize=11];',
        f'  edge [color="{GREY}" arrowsize=0.6];',
    ]
    names: dict[object, str] = {}

    def node(key: object, label: str, style: str = "") -> str:
        if key not in names:
            names[key] = f"n{len(names)}"
            lines.append(f"  {names[key]} [label={label}{style}];")
        return names[key]

    finding_ids: dict[str, int] = {}
    for n, f in enumerate(investigation.findings):
        finding_ids.setdefault(f.id, n)
    edges: list[tuple[object, str]] = []
    claims = [
        (
            ("root", 0),
            dot_label("Root cause", *_wrapped(investigation.root_cause.claim)),
            f' color="{GREEN}" penwidth=2',
            investigation.root_cause.rests_on,
            investigation.root_cause.citations,
        ),
        *(
            (
                ("factor", n),
                dot_label(f"Factor {n}", *_wrapped(f.claim)),
                "",
                f.rests_on,
                f.citations,
            )
            for n, f in enumerate(investigation.contributing_factors, 1)
        ),
    ]
    for key, label, style, rests_on, citations in claims:
        node(key, label, style)
        edges += [(key, f"finding:{finding_ids[i]}") for i in rests_on if i in finding_ids]
        edges += [(key, f"cite:{c.source}:{c.ref}") for c in citations]
    for n, f in enumerate(investigation.findings):
        node(f"finding:{n}", dot_label(f"{f.id} · {f.kind}", *_wrapped(f.claim)))
        edges += [
            (f"finding:{n}", f"finding:{finding_ids[i]}") for i in f.rests_on if i in finding_ids
        ]
        edges += [(f"finding:{n}", f"cite:{c.source}:{c.ref}") for c in f.citations]
    cites = []
    for _, target in edges:
        if target.startswith("cite:") and target not in names:
            source_name, _, ref = target.removeprefix("cite:").partition(":")
            short = cited.short(ref, case_id)
            if source_name == "library":
                # A lead from an earlier outage, not evidence about this one.
                style = f' color="{AMBER}" fontcolor="{AMBER}" style="rounded,filled,dashed"'
                cites.append(node(target, dot_label("library", short), style))
            else:
                cites.append(node(target, dot_label(short)))
    for source, target in dict.fromkeys(edges):
        # dict.fromkeys drops a repeated edge (the same ref cited twice).
        lines.append(f"  {names[source]} -> {names[target]};")
    if cites:
        # The cited items in one column on the right.
        lines.append("  { rank=same; " + "; ".join(cites) + "; }")
    lines.append("}")
    return "\n".join(lines)


@dataclass(frozen=True)
class Scored:
    """One scored run as the scored view shows it."""

    run_id: str
    score: Mapping[str, Any]
    rows: list[dict]


def _item_name(item: str) -> str:
    kind, _, n = item.partition("/")
    names = {
        "attack": "Attack",
        "root_cause": "Root cause",
        "contributing_factors": "Factor",
        "timeline": "Timeline event",
    }
    return f"{names[kind]} {int(n) + 1}" if n else names[kind]


def _key_text(key: AnswerKey, item: str) -> str:
    kind, _, n = item.partition("/")
    if kind == "attack":
        return f"{key.attack} ({key.attack_basis})"
    if kind == "root_cause":
        return key.root_cause.text
    if kind == "contributing_factors":
        return key.contributing_factors[int(n)].text
    event = key.timeline[int(n)]
    return f"{event.time} {event.event}"


def scored_rows(
    key: AnswerKey,
    labels: Mapping[str, Mapping[str, Any]],
    score: Mapping[str, Any],
    behind: Mapping[str, Sequence[str]],
) -> list[dict]:
    """One row per key item: what the key says, its label, the outcome, and the credit.

    Refused when the score, the labels, or the judgment name other key items
    than the key: the rows would pair an outcome with the wrong item.
    """
    expected = item_ids(key)
    for name, items in (("score", score["outcomes"]), ("labels", labels), ("judgment", behind)):
        if sorted(items) != sorted(expected):
            raise ValueError(f"{key.case_id}: the key items in the {name} differ from the key")
    rows = []
    for item in expected:
        credit = score["credits"][item]
        rows.append(
            {
                "Item": _item_name(item),
                "Key": _key_text(key, item),
                "Label": labels[item]["label"],
                "Outcome": score["outcomes"][item],
                "Credit": "not scored" if credit is None else f"{credit:g}",
                "Run items": list(behind[item]),
                "Label reason": labels[item]["reason"],
            }
        )
    return rows


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _frozen(path: Path, frozen: Path, case_id: str) -> bytes:
    data = path.read_bytes()
    if _sha256(data) != json.loads(frozen.read_text("utf-8")).get(case_id):
        raise ValueError(f"{path.name} differs from its frozen hash")
    return data


def _json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8")) if path.is_file() else {}


def load_scored(run_path: Path, root: Path) -> Scored | None:
    """The scored view of one run file, or None when the run has no score.

    root is the repository root. Only the committed showcase scores are read:
    a page without them (the deployed image leaves out the keys) shows no
    scored view.
    """
    data = run_path.read_bytes()
    run_id = json.loads(data).get("run_id")
    scores = root / SCORED_ROOT / "scores.json"
    if not isinstance(run_id, str) or not scores.is_file():
        return None
    entry = next(
        (r for r in json.loads(scores.read_text("utf-8"))["runs"] if r["run_id"] == run_id), None
    )
    if entry is None:
        return None
    base = root / SCORED_ROOT
    judgment = (base / "judgments" / f"{run_id}.json").read_bytes()
    record = json.loads(judgment)
    if record.get("run_sha256") != _sha256(data):
        raise ValueError(f"{run_id}: the judgment is for another file than the run shown")
    # The same two checks the score makes (hindcast.evaluation.score): a review
    # counts only for the judgment it was made on, and a reviewer decision only
    # with the reviewer judgment it names. Without them, an edited reviewer
    # judgment would reach the Run items column.
    review = _json(base / "reviews" / f"{run_id}.json")
    if review and review.get("judgment_sha256") != _sha256(judgment):
        raise ValueError(f"{run_id}: the review is for another judgment")
    second = load_second_judgments(base, {run_id: review}).get(run_id)
    case_id = entry["case_id"]
    key_path = root / KEYS_DIR / f"{case_id}.json"
    _frozen(key_path, root / KEYS_DIR / "frozen.json", case_id)
    label_path = root / LABELS_DIR / f"{case_id}.json"
    raw_labels = json.loads(_frozen(label_path, root / LABELS_DIR / "frozen.json", case_id))
    labels = {one["item"]: one for one in raw_labels["items"]}
    behind = run_items_behind(record, review, second)
    return Scored(run_id, entry, scored_rows(load_key(key_path), labels, entry, behind))

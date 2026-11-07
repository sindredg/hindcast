"""The view parts: the timeline chart, the evidence graph, and the scored view."""

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from hindcast import views
from hindcast.evaluation.score import run_items_behind, score_run
from hindcast.keys import load_key
from hindcast.result import Citation, TimelineEvent, load_result

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "eval/investigations/cloudflare-2026-02-20/20261102T181721Z-v3.json"
SCORED = ROOT / views.SCORED_ROOT
RUN = SCORED / "runs/hindcast/github-2026-08-17/r1-a1-20261104T031347Z.json"
RUN_ID = "hindcast/github-2026-08-17/r1/a1"
CASE = "github-2026-08-17"
# Text a planted instruction could put in a claim: a quote that would end a
# DOT string and add an edge, a backslash that starts a Graphviz escape, an
# HTML-like label, braces, and a line break.
HOSTILE = 'x"]; n0 -> n0 [label="pwn" \\N \\l {a|b} <b>bold</b>\nsecond line \\'


def split_dot(dot: str) -> tuple[str, list[str]]:
    """The DOT text outside quoted strings, and each quoted string as Graphviz reads it.

    In a quoted DOT string, \\" is a quote and every other backslash stays;
    Graphviz then reads \\\\ as a backslash and \\n as a line break in a label.
    """
    outside, strings, i = [], [], 0
    while i < len(dot):
        if dot[i] != '"':
            outside.append(dot[i])
            i += 1
            continue
        i += 1
        raw = []
        while dot[i] != '"':
            if dot[i] == "\\":
                raw.append(dot[i : i + 2])
                i += 2
            else:
                raw.append(dot[i])
                i += 1
        i += 1
        text = "".join(raw)
        lines = [part.replace('\\"', '"').replace("\\\\", "\\") for part in _split_breaks(text)]
        strings.append("\n".join(lines))
    return "".join(outside), strings


def _split_breaks(text: str) -> list[str]:
    # A \n escape is a line break unless its backslash is itself escaped.
    parts, current, i = [], [], 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair == "\\n":
            parts.append("".join(current))
            current = []
            i += 2
        elif text[i] == "\\":
            current.append(pair)
            i += 2
        else:
            current.append(text[i])
            i += 1
    parts.append("".join(current))
    return parts


def investigation():
    found = load_result(RESULT).investigation
    assert found is not None
    return found


def test_utc_accepts_a_utc_time_only():
    assert views.utc("2026-02-20T18:45:17Z") == "2026-02-20T18:45:17Z"
    assert views.utc("2026-08-17T13:40Z") == "2026-08-17T13:40:00Z"
    assert views.utc("2026-02-20T18:45:17+00:00") == "2026-02-20T18:45:17Z"
    assert views.utc("2026-02-20T18:45:17+02:00") is None
    assert views.utc("2026-02-20T18:45:17") is None
    assert views.utc("about an hour later") is None
    assert views.utc("") is None


def test_timeline_spec_places_every_event_and_marks_the_time_kind():
    events = investigation().timeline
    spec, skipped = views.timeline_spec(events)

    assert spec is not None and skipped == []
    values = spec["data"]["values"]
    assert [v["n"] for v in values] == list(range(1, len(events) + 1))
    assert spec["encoding"]["x"]["scale"] == {"type": "utc"}
    color = spec["encoding"]["color"]["scale"]
    assert color["domain"] == ["stated", "inferred"]
    assert color["range"][0] != color["range"][1]
    shape = spec["encoding"]["shape"]["scale"]["range"]
    assert shape[0] != shape[1]


def test_timeline_spec_leaves_out_an_event_without_a_utc_time():
    events = (
        TimelineEvent("2026-02-20T18:45:17Z", "stated", "first", ()),
        TimelineEvent("later that evening", "inferred", "second", ()),
        TimelineEvent("2026-02-20T21:00:00+01:00", "inferred", "third", ()),
    )
    spec, skipped = views.timeline_spec(events)

    assert spec is not None
    assert [v["n"] for v in spec["data"]["values"]] == [1]
    assert skipped == [2, 3]
    assert views.timeline_spec(events[1:]) == (None, [1, 2])


def test_timeline_tooltip_carries_no_model_text():
    events = (TimelineEvent("2026-02-20T18:45:17Z", "inferred", HOSTILE, ()),)
    spec, _ = views.timeline_spec(events)

    assert spec is not None
    assert {t["field"] for t in spec["encoding"]["tooltip"]} == {"n", "time", "kind"}
    # The axis label carries the event, shortened to one line.
    assert "\n" not in spec["data"]["values"][0]["label"]


def test_dot_label_keeps_hostile_text_inside_its_string():
    label = views.dot_label("F1 · inference", HOSTILE)
    outside, strings = split_dot(f"n0 [label={label}];")

    assert outside == "n0 [label=];"
    assert strings == ["F1 · inference\n" + " ".join(HOSTILE.split())]


def test_evidence_graph_links_claims_to_findings_and_citations():
    found = investigation()
    dot = views.evidence_dot(found, "cloudflare-2026-02-20")
    outside, strings = split_dot(dot)

    assert outside.count("->") == len(set(_edges(outside)))
    labels = {s.split("\n")[0]: s for s in strings if "\n" in s or s.startswith("u")}
    assert "Root cause" in labels
    assert "F4 · inference" in labels
    assert "library" in labels
    # The root cause is the focal element; the library node is amber and dashed.
    assert f'color="{views.GREEN}" penwidth=2' in dot
    assert f'color="{views.AMBER}"' in dot and "dashed" in dot
    names = _names(dot)
    edges = set(_edges(outside))
    assert (names["Root cause"], names["F4 · inference"]) in edges
    assert (names["F4 · inference"], names["F2 · observation"]) in edges
    assert (names["F4 · inference"], names["library"]) in edges
    assert (names["Factor 1"], names["F5 · observation"]) in edges
    assert (names["F2 · observation"], names["u2"]) in edges


def test_evidence_graph_with_hostile_claims_adds_no_node_or_edge():
    found = investigation()
    clean = split_dot(views.evidence_dot(found, "cloudflare-2026-02-20"))[0]
    hostile = replace(
        found,
        root_cause=replace(found.root_cause, claim=HOSTILE),
        findings=tuple(replace(f, claim=HOSTILE) for f in found.findings),
        contributing_factors=tuple(replace(f, claim=HOSTILE) for f in found.contributing_factors),
    )
    outside, strings = split_dot(views.evidence_dot(hostile, "cloudflare-2026-02-20"))

    # The same statements, edges, and attributes: only the labels changed.
    assert outside == clean
    assert any('x"]; n0 -> n0' in s for s in strings)


def test_evidence_graph_never_uses_run_text_as_a_node_id():
    found = investigation()
    finding = replace(found.findings[0], id="n0", citations=(Citation("case", HOSTILE),))
    outside, _ = split_dot(
        views.evidence_dot(replace(found, findings=(finding,)), "cloudflare-2026-02-20")
    )

    assert "pwn" not in outside and "<b>" not in outside


def _edges(outside: str) -> list[tuple[str, str]]:
    return [
        (a.strip(), b.strip().rstrip(";"))
        for line in outside.splitlines()
        if "->" in line
        for a, b in [line.split("->")]
    ]


def _names(dot: str) -> dict[str, str]:
    """Each node's first label line, mapped to its node ID."""
    names = {}
    for line in dot.splitlines():
        line = line.strip()
        if line.startswith("n") and "[label=" in line:
            node_id = line.split(" ", 1)[0]
            _, strings = split_dot(line)
            first = strings[0].split("\n")[0]
            names[first] = node_id
    return names


def _score() -> dict:
    scores = json.loads((SCORED / "scores.json").read_text("utf-8"))
    return next(r for r in scores["runs"] if r["run_id"] == RUN_ID)


def test_load_scored_pairs_each_key_item_with_its_outcome():
    scored = views.load_scored(RUN, ROOT)

    assert scored is not None
    entry = _score()
    assert scored.run_id == RUN_ID
    assert scored.score == entry
    key = load_key(ROOT / f"eval/keys/{CASE}.json")
    assert [r["Key"] for r in scored.rows][1] == key.root_cause.text
    by_item = dict(zip(entry["outcomes"], scored.rows, strict=True))
    for item, row in by_item.items():
        assert row["Outcome"] == entry["outcomes"][item]
    assert by_item["contributing_factors/0"]["Credit"] == "not scored"


def test_load_scored_returns_none_for_an_unscored_run():
    assert views.load_scored(RESULT, ROOT) is None


def test_load_scored_refuses_a_run_file_the_judgment_was_not_made_for(tmp_path):
    raw = json.loads(RUN.read_text("utf-8"))
    raw["investigation"]["root_cause"]["claim"] += " Edited after the score."
    edited = tmp_path / RUN.name
    edited.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="judgment is for another file"):
        views.load_scored(edited, ROOT)


def _scored_root(tmp_path: Path) -> Path:
    """A copy of the files the scored view reads for one run."""
    for relative in (
        views.SCORED_ROOT / "scores.json",
        views.SCORED_ROOT / "judgments" / f"{RUN_ID}.json",
        views.SCORED_ROOT / "reviews" / f"{RUN_ID}.json",
        views.SCORED_ROOT / "reviewer/judgments" / f"{RUN_ID}.json",
        views.KEYS_DIR / f"{CASE}.json",
        views.KEYS_DIR / "frozen.json",
        views.LABELS_DIR / f"{CASE}.json",
        views.LABELS_DIR / "frozen.json",
    ):
        source = ROOT / relative
        if source.is_file():
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, tmp_path / relative)
    return tmp_path


def test_load_scored_reads_a_copy_of_its_files(tmp_path):
    # The copy is complete: the refusals below come from the one change each makes.
    assert views.load_scored(RUN, _scored_root(tmp_path)) is not None


@pytest.mark.parametrize("relative", [views.KEYS_DIR, views.LABELS_DIR])
def test_load_scored_refuses_a_key_or_labels_changed_after_freezing(tmp_path, relative):
    root = _scored_root(tmp_path)
    path = root / relative / f"{CASE}.json"
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="differs from its frozen hash"):
        views.load_scored(RUN, root)


def test_load_scored_without_scores_returns_none(tmp_path):
    root = _scored_root(tmp_path)
    (root / views.SCORED_ROOT / "scores.json").unlink()

    assert views.load_scored(RUN, root) is None


def test_scored_rows_refuse_items_the_key_does_not_have():
    key = load_key(ROOT / f"eval/keys/{CASE}.json")
    entry = _score()
    labels = {
        one["item"]: one
        for one in json.loads((ROOT / f"eval/keys/labels/{CASE}.json").read_text("utf-8"))["items"]
    }
    behind = {item: [] for item in entry["outcomes"]}
    assert len(views.scored_rows(key, labels, entry, behind)) == len(entry["outcomes"])

    extra = entry | {"outcomes": entry["outcomes"] | {"timeline/9": "missed"}}
    with pytest.raises(ValueError, match="key items in the score differ"):
        views.scored_rows(key, labels, extra, behind)
    fewer = {k: v for k, v in labels.items() if k != "root_cause"}
    with pytest.raises(ValueError, match="key items in the labels differ"):
        views.scored_rows(key, fewer, entry, behind)
    with pytest.raises(ValueError, match="key items in the judgment differ"):
        views.scored_rows(key, labels, entry, {"attack": []})


def test_run_items_behind_takes_the_reviewer_items_where_it_decided():
    record = {
        "run_id": "r",
        "judgment": {
            "key_items": {
                "attack": {"run_items": ["attack"], "outcome": "abstained"},
                "root_cause": {"run_items": ["findings[0]"], "outcome": "partial"},
            }
        },
    }
    review = {
        "decisions": [
            {"kind": "match", "item": "root_cause", "decided_by": {"judgment_sha256": "x"}}
        ]
    }
    second = {"judgment": {"key_items": {"root_cause": {"run_items": ["findings[2]"]}}}}

    assert run_items_behind(record, review, second) == {
        "attack": ["attack"],
        "root_cause": ["findings[2]"],
    }
    with pytest.raises(ValueError, match="needs its reviewer judgment"):
        run_items_behind(record, review, None)


def test_scores_json_still_matches_the_score_of_every_run():
    """The refactor that shares run_items_behind with the page leaves every score as it was."""
    scores = json.loads((SCORED / "scores.json").read_text("utf-8"))
    for entry in scores["runs"]:
        run_id, case = entry["run_id"], entry["case_id"]
        record = json.loads((SCORED / "judgments" / f"{run_id}.json").read_text("utf-8"))
        review_path = SCORED / "reviews" / f"{run_id}.json"
        review = json.loads(review_path.read_text("utf-8")) if review_path.is_file() else {}
        second_path = SCORED / "reviewer/judgments" / f"{run_id}.json"
        second = json.loads(second_path.read_text("utf-8")) if second_path.is_file() else None
        raw = json.loads((ROOT / f"eval/keys/labels/{case}.json").read_text("utf-8"))
        labels = {one["item"]: one["label"] for one in raw["items"]}
        score = score_run(record, review, labels, second)
        assert score.outcomes == entry["outcomes"], run_id
        assert score.credits == entry["credits"], run_id
        assert score.unsupported == entry["unsupported"], run_id
        assert score.extra_supported == entry["extra_supported"], run_id

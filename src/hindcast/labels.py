"""Inferable-from-evidence labels: one per scored key item (decision 0023).

    PYTHONPATH=src uv run --frozen python -m hindcast.labels sheet <case_id>
    PYTHONPATH=src uv run --frozen python -m hindcast.labels freeze <case_id>

A draft lives in build/labels/<case_id>-draft.json. `sheet` checks it and
writes build/labels/<case_id>.md, which shows each key item with its quote,
the draft label, the reason, and the text of the evidence it cites, for a
person to approve. `freeze` checks it again, writes
eval/keys/labels/<case_id>.json, and records its SHA-256 in
eval/keys/labels/frozen.json; a test checks the hashes. The keys stay as
they were frozen.

"Evidence" is the case's status updates and charts. The library is a lead,
never evidence, so a label never cites it.
"""

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from hindcast.evidence import CaseEvidence
from hindcast.keys import AnswerKey

DRAFTS = Path("build/labels")
LABELS_DIR = Path("eval/keys/labels")
FROZEN = LABELS_DIR / "frozen.json"

Value = Literal["stated", "inferable", "not inferable"]
FIELDS = {"item", "label", "reason", "evidence"}


class LabelError(ValueError):
    """A label file that does not cover the key exactly or breaks a labelling rule."""


@dataclass(frozen=True)
class Label:
    item: str
    label: Value
    reason: str
    # Update and chart IDs the reason rests on.
    evidence: tuple[str, ...]


def item_ids(key: AnswerKey) -> list[str]:
    """The scored items, by the IDs hindcast.leak uses; fixes are not scored."""
    return [
        "attack",
        "root_cause",
        *(f"contributing_factors/{i}" for i in range(len(key.contributing_factors))),
        *(f"timeline/{i}" for i in range(len(key.timeline))),
    ]


def _stated_in_key(key: AnswerKey, item: str) -> bool | None:
    # The attack verdict has no flag in the key: its label is not checked
    # against one.
    if item == "attack":
        return None
    if item == "root_cause":
        return key.root_cause.stated_during_incident
    name, index = item.split("/")
    part = key.contributing_factors if name == "contributing_factors" else key.timeline
    return part[int(index)].stated_during_incident


def parse_labels(raw: object, key: AnswerKey, evidence: CaseEvidence) -> dict[str, Label]:
    if not isinstance(raw, dict) or set(raw) != {"case_id", "items"}:
        raise LabelError("fields: a label file holds case_id and items only")
    if raw["case_id"] != key.case_id or evidence.case_id != key.case_id:
        raise LabelError(
            f"case {raw['case_id']}: the key is {key.case_id}, the evidence {evidence.case_id}"
        )
    refs = {u.update_id for u in evidence.updates} | {c.chart_id for c in evidence.charts}
    expected = item_ids(key)
    labels: dict[str, Label] = {}
    for entry in raw["items"]:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            where = entry.get("item") if isinstance(entry, dict) else entry
            raise LabelError(f"{where}: fields must be {', '.join(sorted(FIELDS))}")
        item = entry["item"]
        if item not in expected:
            raise LabelError(f"unknown: {item}")
        if item in labels:
            raise LabelError(f"twice: {item}")
        value = entry["label"]
        if value not in get_args(Value):
            raise LabelError(f"{item}: label {value!r} is not one of {', '.join(get_args(Value))}")
        reason = entry["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise LabelError(f"{item}: needs a reason")
        cited = entry["evidence"]
        if not isinstance(cited, list) or not all(isinstance(r, str) for r in cited):
            raise LabelError(f"{item}: evidence must be a list of IDs")
        for ref in cited:
            if ref not in refs:
                raise LabelError(f"{item}: unknown evidence {ref}")
        if value != "not inferable" and not cited:
            raise LabelError(f"{item}: {value} needs evidence")
        stated = _stated_in_key(key, item)
        if stated is False and value == "stated":
            raise LabelError(f"{item}: stated, but the key marks it not stated during the incident")
        if stated is True and value != "stated":
            raise LabelError(f"{item}: the key marks it stated during the incident")
        labels[item] = Label(item, value, reason.strip(), tuple(cited))
    missing = [item for item in expected if item not in labels]
    if missing:
        raise LabelError(f"missing: {', '.join(missing)}")
    return {item: labels[item] for item in expected}


def load_labels(path: Path, key: AnswerKey, evidence: CaseEvidence) -> dict[str, Label]:
    return parse_labels(json.loads(path.read_text("utf-8")), key, evidence)


def _key_item(key: AnswerKey, item: str) -> tuple[str, str]:
    """The item's text and its postmortem quote."""
    if item == "attack":
        return key.attack, key.attack_quote
    if item == "root_cause":
        return key.root_cause.text, key.root_cause.source_quote
    name, index = item.split("/")
    if name == "contributing_factors":
        factor = key.contributing_factors[int(index)]
        return factor.text, factor.source_quote
    event = key.timeline[int(index)]
    return f"{event.time}: {event.event}", event.source_quote


def review_sheet(labels: dict[str, Label], key: AnswerKey, evidence: CaseEvidence) -> str:
    texts = {
        u.update_id: f"{u.time} {u.status}: {u.text or '(text withheld)'}" for u in evidence.updates
    }
    texts |= {c.chart_id: f"chart: {c.description}" for c in evidence.charts}
    lines = [f"# Labels for {key.case_id}", ""]
    lines.append("Approve each label, or give the corrected label and reason.")
    for label in labels.values():
        text, quote = _key_item(key, label.item)
        stated = _stated_in_key(key, label.item)
        lines += [
            "",
            f"### {label.item}: {label.label}",
            "",
            f"- Key: {text}",
            f'- Quote: "{quote}"',
        ]
        if stated is not None:
            lines.append(f"- stated during the incident (key): {'yes' if stated else 'no'}")
        lines.append(f"- Reason: {label.reason}")
        for ref in label.evidence:
            lines.append(f"  - `{ref}` {texts[ref]}")
    return "\n".join(lines) + "\n"


def freeze(
    case_id: str,
    key: AnswerKey,
    evidence: CaseEvidence,
    drafts: Path = DRAFTS,
    labels_dir: Path = LABELS_DIR,
) -> str:
    """Freeze an approved draft: write the label file and record its hash, once."""
    source = drafts / f"{case_id}-draft.json"
    parse_labels(json.loads(source.read_text("utf-8")), key, evidence)
    target = labels_dir / f"{case_id}.json"
    if target.exists():
        raise LabelError(f"{target} is frozen already; a new label needs a new approval")
    data = source.read_bytes()
    labels_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    frozen_path = labels_dir / "frozen.json"
    frozen = json.loads(frozen_path.read_text("utf-8")) if frozen_path.is_file() else {}
    frozen[case_id] = hashlib.sha256(data).hexdigest()
    frozen_path.write_text(json.dumps(frozen, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return frozen[case_id]


def main(argv: list[str] | None = None) -> int:
    from hindcast.keys import KEYS_DIR, load_key
    from hindcast.tools import load_evidence

    parser = argparse.ArgumentParser(prog="python -m hindcast.labels")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("sheet", "write the review sheet"), ("freeze", "freeze a draft")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("case_id")
    args = parser.parse_args(argv)
    key = load_key(KEYS_DIR / f"{args.case_id}.json")
    evidence = load_evidence(Path("build/evidence") / f"{args.case_id}.json")
    try:
        if args.command == "sheet":
            labels = load_labels(DRAFTS / f"{args.case_id}-draft.json", key, evidence)
            sheet = DRAFTS / f"{args.case_id}.md"
            sheet.write_text(review_sheet(labels, key, evidence), encoding="utf-8")
            print(f"{len(labels)} labels; sheet {sheet}")
        else:
            print(f"frozen {args.case_id} {freeze(args.case_id, key, evidence)}")
    except LabelError as error:
        print(f"refused: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""What a person reviews of each judgment, and where the decisions are kept.

Rubric version 2, Review: every proposed supported hit, partial, unsupported
hit, and unsupported partial; every support verdict on an inference; and a
quarter of the rest (missed, abstained, and wrong outcomes, and support
verdicts on observations), drawn per run with the seed 20261104. A run item
the code found unsupported is not reviewed: the code decided it, and the
judge's reply could not say otherwise.

The page (hindcast.review) shows runs under a blind ID, in an order drawn
from the same seed, so the reviewer does not see the arm. Decisions go to
reviews/<run_id>.json, one file per run, with the hash of the judgment
they review: a decision is never applied to another judgment.

Since rubric version 3 (decision 0027) the queue is the same, and the
reviewer model (hindcast.evaluation.reviewer) makes each decision instead of
a person.
"""

import hashlib
import json
import math
import os
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from hindcast.evaluation import judge_prior
from hindcast.evaluation.judge import OUTCOMES

SEED = 20261104
SAMPLE = 0.25
REVIEWED_OUTCOMES = frozenset(
    {"supported-hit", "partial", "unsupported-hit", "unsupported-partial"}
)


@dataclass(frozen=True)
class ReviewItem:
    kind: Literal["match", "support", "prior"]
    # A key item ID for a match or a prior answer, a run item's where for a
    # support verdict.
    item: str
    proposal: str | bool
    sampled: bool


def review_queue(record: Mapping[str, Any], seed: int = SEED) -> list[ReviewItem]:
    """The items a person decides for one judgment: the required ones, then the sample."""
    judgment = record.get("judgment")
    if judgment is None:
        return []
    code_unsupported = set(record.get("code_unsupported", []))
    required: list[ReviewItem] = []
    rest: list[ReviewItem] = []
    for item, verdict in judgment["key_items"].items():
        entry = ReviewItem("match", item, verdict["outcome"], False)
        (required if verdict["outcome"] in REVIEWED_OUTCOMES else rest).append(entry)
    for where, verdict in judgment["run_items"].items():
        if where in code_unsupported:
            continue
        entry = ReviewItem("support", where, verdict["supported"], False)
        (required if record["kinds"][where] == "inference" else rest).append(entry)
    # A string seed is hashed the same way on every machine and Python run.
    # The draw has to be reproducible, not secret.
    draw = random.Random(f"{seed}/{record['run_id']}")  # noqa: S311
    count = math.ceil(len(rest) * SAMPLE)
    picked = set(draw.sample(range(len(rest)), count))
    sampled = [
        ReviewItem(i.kind, i.item, i.proposal, True) for n, i in enumerate(rest) if n in picked
    ]
    return required + sampled


def prior_queue(record: Mapping[str, Any], record_id: str, seed: int = SEED) -> list[ReviewItem]:
    """A prior answer's items: every proposed hit and partial, and a quarter of the rest."""
    judgment = record.get("judgment")
    if judgment is None:
        return []
    required, rest = [], []
    for item, verdict in judgment.items():
        entry = ReviewItem("prior", item, verdict["outcome"], False)
        (required if verdict["outcome"] in ("hit", "partial") else rest).append(entry)
    draw = random.Random(f"{seed}/{record_id}")  # noqa: S311 (reproducible, not secret)
    picked = set(draw.sample(range(len(rest)), math.ceil(len(rest) * SAMPLE)))
    return required + [
        ReviewItem(i.kind, i.item, i.proposal, True) for n, i in enumerate(rest) if n in picked
    ]


def choices(item: ReviewItem) -> tuple:
    """The decisions a reviewer can give: the outcomes the rubric allows, or support."""
    if item.kind == "support":
        return (True, False)
    if item.kind == "prior":
        return judge_prior.OUTCOMES[item.item]
    return OUTCOMES[item.item.split("/")[0]]


def blind_id(run_id: str, seed: int = SEED) -> str:
    return hashlib.sha256(f"{seed}/{run_id}".encode()).hexdigest()[:10]


def run_order(run_ids: Iterable[str], seed: int = SEED) -> list[str]:
    """Runs in an order that does not follow the arm, the case, or the repeat."""
    return sorted(run_ids, key=lambda run_id: blind_id(run_id, seed))


def load_review(path: Path, run_id: str, judgment_sha256: str) -> dict:
    if not path.is_file():
        return {"run_id": run_id, "judgment_sha256": judgment_sha256, "decisions": []}
    review = json.loads(path.read_text(encoding="utf-8"))
    if review["run_id"] != run_id or review["judgment_sha256"] != judgment_sha256:
        raise ValueError(f"{path}: the decisions are for another run or judgment")
    return review


def _write(path: Path, review: Mapping[str, Any]) -> None:
    # A temporary file moved over the old one: a crash mid-write keeps the old decisions.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def record_decision(
    path: Path,
    run_id: str,
    judgment_sha256: str,
    item: ReviewItem,
    decision: str | bool,
    now: datetime | None = None,
    decided_by: Mapping[str, Any] | None = None,
) -> dict:
    """Append one decision; `decided_by` names a reviewer model and the judgment it gave."""
    if decision not in choices(item):
        allowed = ", ".join(str(c) for c in choices(item))
        raise ValueError(f"{item.item}: {decision!r} is not one of {allowed}")
    review = load_review(path, run_id, judgment_sha256)
    review["decisions"].append(
        {
            "kind": item.kind,
            "item": item.item,
            "proposal": item.proposal,
            "sampled": item.sampled,
            "decision": decision,
            "decided_at": (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        | ({"decided_by": dict(decided_by)} if decided_by else {})
    )
    _write(path, review)
    return review


def undo_last(path: Path) -> None:
    review = json.loads(path.read_text(encoding="utf-8"))
    if review["decisions"]:
        review["decisions"].pop()
        _write(path, review)


def pending(queue: Iterable[ReviewItem], review: Mapping[str, Any]) -> list[ReviewItem]:
    done = {(d["kind"], d["item"]) for d in review["decisions"]}
    return [i for i in queue if (i.kind, i.item) not in done]

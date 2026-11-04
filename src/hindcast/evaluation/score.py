"""Scores from the judgments, the review, and the frozen labels (rubric version 2).

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.score [--draft]

A reviewed decision replaces the judge's proposal: a match decision sets the
key item's outcome, a support decision sets the run item's support. The
labels then give each outcome its credit, and the primary score per run is
credited divided by scorable. Next to it, never folded in: unsupported run
items, wrong items, guesses, supported items outside the key, and the
review decisions that contradict each other. Per arm and case: mean,
minimum, and maximum of the primary score, summed outcome counts, failures,
seconds, and cost. A model's runs on a case whose root cause its prior answer
already named go to a separate known-before-evidence table.

Writes eval/reconstruction/showcase-v1/scores.json. Refuses while a review
item is open, unless --draft, which writes nothing and prints the counts.
"""

import argparse
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hindcast.evaluation.review import review_queue

ROOT = Path("eval/reconstruction/showcase-v1")
OUTCOME_NAMES = (
    "supported-hit",
    "partial",
    "unsupported-hit",
    "unsupported-partial",
    "abstained",
    "missed",
    "wrong",
)
CREDIT = {"supported-hit": 1.0, "partial": 0.5}
# The kinds of key item with an abstention form; for the others, saying
# nothing is the abstention.
ABSTAINABLE = frozenset({"attack", "root_cause"})


def _kind(item: str) -> str:
    return item.split("/")[0]


def _label(value: Any) -> str:
    # A frozen Label, or its value alone in tests.
    return value if isinstance(value, str) else value.label


def credit(outcome: str, label: str, kind: str) -> float | None:
    """The credit for one key item, or None when the item is not scorable for this run."""
    if outcome in CREDIT:
        return CREDIT[outcome]
    if outcome == "abstained":
        # A justified abstention: the evidence does not settle the item.
        return 1.0 if label == "not inferable" and kind in ABSTAINABLE else 0.0
    if outcome == "missed" and label == "not inferable" and kind not in ABSTAINABLE:
        return None
    return 0.0


@dataclass(frozen=True)
class RunScore:
    run_id: str
    arm: str
    case_id: str
    outcomes: dict[str, str]
    credits: dict[str, float | None]
    credited: float
    scorable: int
    primary: float | None
    neutral: list[str] = field(default_factory=list)
    guesses: list[str] = field(default_factory=list)
    justified_abstentions: list[str] = field(default_factory=list)
    wrong: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    extra_supported: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    open_items: int = 0


def _decisions(review: Mapping[str, Any], kind: str) -> dict[str, Any]:
    # A later decision on the same item replaces an earlier one.
    return {d["item"]: d["decision"] for d in review.get("decisions", []) if d["kind"] == kind}


def score_run(
    record: Mapping[str, Any], review: Mapping[str, Any], labels: Mapping[str, Any]
) -> RunScore:
    judgment = record["judgment"]
    if judgment is None:
        raise ValueError(f"{record['run_id']}: no judgment ({record.get('error')})")
    matched = _decisions(review, "match")
    supported = _decisions(review, "support")
    code_unsupported = set(record.get("code_unsupported", []))
    support = {
        where: False
        if where in code_unsupported
        else bool(supported.get(where, verdict["supported"]))
        for where, verdict in judgment["run_items"].items()
    }
    outcomes, credits = {}, {}
    neutral, guesses, abstentions, wrong, contradictions = [], [], [], [], []
    listed: set[str] = set()
    for item, verdict in judgment["key_items"].items():
        outcome = matched.get(item, verdict["outcome"])
        label = _label(labels[item])
        outcomes[item] = outcome
        credits[item] = credit(outcome, label, _kind(item))
        if outcome != "missed":
            listed |= set(verdict["run_items"])
        if credits[item] is None:
            neutral.append(item)
        if outcome in ("unsupported-hit", "unsupported-partial") and label == "not inferable":
            guesses.append(item)
        if outcome == "abstained" and credits[item] == 1.0:
            abstentions.append(item)
        if outcome == "wrong":
            wrong.append(item)
        backed = any(support[w] for w in verdict["run_items"])
        if item in matched and (
            (outcome in ("supported-hit", "partial") and not backed)
            or (outcome in ("unsupported-hit", "unsupported-partial") and backed)
        ):
            contradictions.append(item)
    scored = [c for c in credits.values() if c is not None]
    credited = sum(scored)
    queue = review_queue(record)
    done = {(d["kind"], d["item"]) for d in review.get("decisions", [])}
    return RunScore(
        run_id=record["run_id"],
        arm=record.get("arm") or record["run_id"].split("/")[0],
        case_id=record["case_id"],
        outcomes=outcomes,
        credits=credits,
        credited=credited,
        scorable=len(scored),
        primary=credited / len(scored) if scored else None,
        neutral=neutral,
        guesses=guesses,
        justified_abstentions=abstentions,
        wrong=wrong,
        unsupported=[w for w, ok in support.items() if not ok],
        extra_supported=[w for w, ok in support.items() if ok and w not in listed],
        contradictions=contradictions,
        open_items=sum(1 for i in queue if (i.kind, i.item) not in done),
    )


def cohen_kappa(pairs: list[tuple[Any, Any]]) -> float | None:
    """Cohen's kappa for (judge, reviewer) pairs; None when chance agreement is total."""
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(1 for a, b in pairs if a == b) / n
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(first[k] * second[k] for k in first) / (n * n)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def agreement(pairs: list[tuple[Any, Any]]) -> dict:
    n = len(pairs)
    percent = round(100 * sum(1 for a, b in pairs if a == b) / n, 1) if n else None
    return {"items": n, "percent": percent, "kappa": cohen_kappa(pairs)}


def _summary(scores: list[RunScore], failures: int, usage: Mapping[str, dict]) -> dict:
    primaries = [s.primary for s in scores if s.primary is not None]
    outcomes = Counter(o for s in scores for o in s.outcomes.values())
    seconds = [usage[s.run_id]["seconds"] for s in scores if s.run_id in usage]
    costs = [usage[s.run_id]["cost"] for s in scores if s.run_id in usage]
    return {
        "runs": len(scores),
        "primary": {
            "mean": statistics.fmean(primaries) if primaries else None,
            "min": min(primaries, default=None),
            "max": max(primaries, default=None),
        },
        "outcomes": {name: outcomes[name] for name in OUTCOME_NAMES},
        "guesses": sum(len(s.guesses) for s in scores),
        "justified_abstentions": sum(len(s.justified_abstentions) for s in scores),
        "unsupported_items": sum(len(s.unsupported) for s in scores),
        "extra_supported_items": sum(len(s.extra_supported) for s in scores),
        "contradictions": sum(len(s.contradictions) for s in scores),
        "failures": failures,
        "seconds_mean": statistics.fmean(seconds) if seconds else None,
        "cost_total": round(sum(costs), 6) if costs else None,
    }


def aggregate(
    scores: Iterable[RunScore],
    *,
    models: Mapping[str, str],
    known: set[tuple[str, str]],
    attempts: Iterable[Mapping[str, Any]],
    usage: Mapping[str, dict] | None = None,
) -> dict:
    """Per arm and case, per arm, and the known-before-evidence runs apart."""
    usage = usage or {}
    failures = Counter((a["arm"], a["case_id"]) for a in attempts if a["status"] == "no-result")
    kept: dict[str, dict[str, list[RunScore]]] = defaultdict(lambda: defaultdict(list))
    apart: dict[str, dict[str, list[RunScore]]] = defaultdict(lambda: defaultdict(list))
    for s in scores:
        target = apart if (models.get(s.run_id), s.case_id) in known else kept
        target[s.arm][s.case_id].append(s)

    def table(groups: Mapping[str, Mapping[str, list[RunScore]]]) -> dict:
        return {
            arm: {
                case: _summary(runs, failures[(arm, case)], usage)
                for case, runs in sorted(cases.items())
            }
            for arm, cases in sorted(groups.items())
        }

    return {
        "by_arm_case": table(kept),
        "by_arm": {
            arm: _summary(
                [s for runs in cases.values() for s in runs],
                sum(n for (a, _), n in failures.items() if a == arm),
                usage,
            )
            for arm, cases in sorted(kept.items())
        },
        "known_before_evidence": table(apart),
    }


def review_agreement(pairs: Iterable[tuple[str, Any, Any]]) -> dict:
    """Agreement over all reviewed items, and for matches and support verdicts apart."""
    pairs = list(pairs)
    return {
        "all": agreement([(str(a), str(b)) for _, a, b in pairs]),
        "match": agreement([(a, b) for kind, a, b in pairs if kind == "match"]),
        "support": agreement([(a, b) for kind, a, b in pairs if kind == "support"]),
    }


def _load(root: Path) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    from hindcast.evaluation.batch import FILLED, load_attempts
    from hindcast.evaluation.judge import _sha256, check_frozen, judgment_path

    system = check_frozen()
    attempts = load_attempts(root / "attempts.json")
    records, reviews = {}, {}
    for entry in attempts:
        if entry["status"] not in FILLED:
            continue
        path = judgment_path(root / "judgments", entry["run_id"])
        if not path.is_file():
            raise ValueError(f"{entry['run_id']}: no judgment")
        data = path.read_bytes()
        record = json.loads(data)
        if record["error"] is not None:
            raise ValueError(f"{entry['run_id']}: judge error {record['error']}")
        if record["judge"]["system_sha256"] != _sha256(system.encode()):
            raise ValueError(f"{entry['run_id']}: judged with another judge prompt")
        review_path = root / "reviews" / f"{entry['run_id']}.json"
        review = json.loads(review_path.read_text("utf-8")) if review_path.is_file() else {}
        if review and review["judgment_sha256"] != _sha256(data):
            raise ValueError(f"{entry['run_id']}: the review is for another judgment")
        records[entry["run_id"]], reviews[entry["run_id"]] = record, review
    return attempts, records, reviews


def main(argv: list[str] | None = None) -> int:
    from hindcast.evaluation.judge import load_case
    from hindcast.labels import FROZEN as LABELS_FROZEN
    from hindcast.labels import LABELS_DIR, load_labels

    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.score")
    parser.add_argument("--draft", action="store_true", help="print counts, write nothing")
    args = parser.parse_args(argv)
    attempts, records, reviews = _load(ROOT)
    frozen_labels = json.loads(LABELS_FROZEN.read_text("utf-8"))
    labels: dict[str, dict] = {}
    scores = []
    for run_id, record in records.items():
        case_id = record["case_id"]
        if case_id not in labels:
            key, evidence = load_case(case_id)
            path = LABELS_DIR / f"{case_id}.json"
            from hindcast.evaluation.judge import _sha256

            if _sha256(path.read_bytes()) != frozen_labels.get(case_id):
                raise ValueError(f"{path} differs from its frozen hash")
            labels[case_id] = load_labels(path, key, evidence)
        scores.append(score_run(record, reviews[run_id], labels[case_id]))
    open_items = sum(s.open_items for s in scores)
    print(f"runs {len(scores)}, open review items {open_items}")
    if args.draft:
        return 0
    if open_items:
        raise SystemExit("review items are open: finish the review, or use --draft")
    entries = {e["run_id"]: e for e in attempts}
    usage = {
        run_id: {"seconds": e["usage"]["seconds"], "cost": e["cost"]["total"]}
        for run_id, e in entries.items()
        if run_id in records
    }
    models = {run_id: entries[run_id]["model"]["deployment"] for run_id in records}
    pairs = [
        (d["kind"], d["proposal"], d["decision"])
        for review in reviews.values()
        for d in review.get("decisions", [])
    ]
    out = {
        "rubric": "eval/rubric/rubric.md",
        "runs": [asdict(s) for s in scores],
        "tables": aggregate(scores, models=models, known=set(), attempts=attempts, usage=usage),
        "agreement": review_agreement(pairs),
    }
    (ROOT / "scores.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{ROOT / 'scores.json'}: {len(scores)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

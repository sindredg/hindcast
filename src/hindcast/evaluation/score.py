"""Scores from the judgments, the review, and the frozen labels (rubric version 3).

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.score [--draft] [--root DIR]

A reviewed decision replaces the judge's proposal: a match decision sets the
key item's outcome, a support decision sets the run item's support. A match
the reviewer model decided rests on the run items its own judgment listed. The
labels then give each outcome its credit, and the primary score per run is
credited divided by scorable. Next to it, never folded in: unsupported run
items, wrong items, guesses, supported items outside the key, and the
review decisions that contradict each other. Per arm and case: mean,
minimum, and maximum of the primary score, summed outcome counts, failures,
seconds, and cost. A model's runs on a case whose root cause its prior answer
already named go to a separate known-before-evidence table.

Writes eval/reconstruction/showcase-v1/scores.json, or <DIR>/scores.json with
--root (the revealed seals: eval/reconstruction/sealed-v1). Refuses while a
review item is open, unless --draft, which writes nothing and prints the counts.
"""

import argparse
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
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
    record: Mapping[str, Any],
    review: Mapping[str, Any],
    labels: Mapping[str, Any],
    second: Mapping[str, Any] | None = None,
) -> RunScore:
    """One run's score; second is the reviewer's judgment behind its decisions."""
    judgment = record["judgment"]
    if judgment is None:
        raise ValueError(f"{record['run_id']}: no judgment ({record.get('error')})")
    matched = _decisions(review, "match")
    deciders = {
        d["item"]: d.get("decided_by") for d in review.get("decisions", []) if d["kind"] == "match"
    }
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
        # A person confirms or replaces the judge's outcome on the judge's run
        # items. The reviewer model judged the run again, so its decision rests
        # on the run items its own judgment listed for the key item.
        items = verdict["run_items"]
        if deciders.get(item):
            if second is None:
                raise ValueError(f"{record['run_id']}: {item} needs its reviewer judgment")
            items = second["judgment"]["key_items"][item]["run_items"]
        if outcome != "missed":
            listed |= set(items)
        if credits[item] is None:
            neutral.append(item)
        if outcome in ("unsupported-hit", "unsupported-partial") and label == "not inferable":
            guesses.append(item)
        if outcome == "abstained" and credits[item] == 1.0:
            abstentions.append(item)
        if outcome == "wrong":
            wrong.append(item)
        backed = any(support[w] for w in items)
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


def whole_agreement(pairs: Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> dict:
    """Judge-reviewer agreement over every key item and run item, not only the queue."""
    match, support = [], []
    for first, second in pairs:
        a, b = first["judgment"], second["judgment"]
        match += [(v["outcome"], b["key_items"][k]["outcome"]) for k, v in a["key_items"].items()]
        support += [
            (v["supported"], b["run_items"][w]["supported"]) for w, v in a["run_items"].items()
        ]
    return {"match": agreement(match), "support": agreement(support)}


def alone(
    records: Mapping[str, Mapping[str, Any]],
    seconds: Mapping[str, Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
) -> tuple[list[RunScore], list[RunScore]]:
    """Each run scored on the judge's judgment alone and on the reviewer's alone.

    Neither is the score: the rubric's score takes the reviewer's decisions on
    the queue and the judge's proposals elsewhere. The two show how far the
    score could move with the judge that decides.
    """
    judge_scores, reviewer_scores = [], []
    for run_id, record in records.items():
        case_labels = labels[record["case_id"]]
        judge_scores.append(score_run(record, {}, case_labels))
        reviewer_scores.append(score_run(seconds[run_id], {}, case_labels))
    return judge_scores, reviewer_scores


def second_opinion(
    records: Mapping[str, Mapping[str, Any]],
    seconds: Mapping[str, Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    tables: Callable[[list[RunScore]], Mapping[str, Any]],
) -> dict | None:
    """The whole-judgment agreement and each judge alone, or None.

    None unless every run's review was decided from a reviewer judgment: a
    run a person reviewed alone leaves no second judgment to compare.
    """
    if not records or seconds.keys() != records.keys():
        return None
    judge_scores, reviewer_scores = alone(records, seconds, labels)
    return {
        "whole_agreement": whole_agreement((records[r], seconds[r]) for r in records),
        "judge_alone": _primaries(tables(judge_scores)),
        "reviewer_alone": _primaries(tables(reviewer_scores)),
    }


def _primaries(tables: Mapping[str, Any]) -> dict:
    return {
        "by_arm": {arm: s["primary"] for arm, s in tables["by_arm"].items()},
        "known_before_evidence": {
            arm: {case: s["primary"] for case, s in cases.items()}
            for arm, cases in tables["known_before_evidence"].items()
        },
    }


PRIOR_ROOT = Path("eval/prior-knowledge/v1")


def prior_outcomes(record: Mapping[str, Any], review: Mapping[str, Any]) -> dict[str, str]:
    """A prior answer's outcomes, reviewed decisions first."""
    decided = _decisions(review, "prior")
    return {item: decided.get(item, v["outcome"]) for item, v in record["judgment"].items()}


def known_before_evidence(
    answers: Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> set[tuple[str, str]]:
    """(deployment, case) pairs whose prior answer, in any collection, hit the root cause."""
    return {
        (record["deployment"], record["case_id"])
        for record, review in answers
        if prior_outcomes(record, review)["root_cause"] == "hit"
    }


def prior_scores(
    root: Path = PRIOR_ROOT, lock: tuple[Path, Path] | None = None
) -> tuple[dict, int]:
    """Every judged prior answer's outcomes, the known pairs, and the open review items."""
    from hindcast.evaluation import judge_prior
    from hindcast.evaluation.judge import _sha256, locked_system
    from hindcast.evaluation.review import prior_queue

    locked = locked_system(*(lock or (judge_prior.PROMPT, judge_prior.FROZEN)))
    paths = sorted((root / "judgments").glob("*/*.json"))
    if not paths:
        raise ValueError(f"{root}: no prior-knowledge judgments")
    rows, pairs, answers, open_items = [], [], [], 0
    for path in paths:
        data = path.read_bytes()
        record = json.loads(data)
        if record["error"] is not None:
            raise ValueError(f"{path}: judge error {record['error']}")
        if (record["judge"]["system_sha256"], record["judge"]["model"]) != locked:
            raise ValueError(f"{path}: judged with another judge prompt or model")
        record_id = f"{path.parent.name}/{path.stem}"
        review_path = root / "reviews" / f"{record_id}.json"
        review = json.loads(review_path.read_text("utf-8")) if review_path.is_file() else {}
        if review and review["judgment_sha256"] != _sha256(data):
            raise ValueError(f"{record_id}: the review is for another judgment")
        done = {(d["kind"], d["item"]) for d in review.get("decisions", [])}
        open_items += sum(1 for i in prior_queue(record, record_id) if (i.kind, i.item) not in done)
        pairs += [("prior", d["proposal"], d["decision"]) for d in review.get("decisions", [])]
        answers.append((record, review))
        rows.append(
            {
                "answers": record["answers"],
                "deployment": record["deployment"],
                "model_version": record["model_version"],
                "collected_at": record["collected_at"],
                "case_id": record["case_id"],
                "outcomes": prior_outcomes(record, review),
            }
        )
    known = sorted(known_before_evidence(answers))
    agree = agreement([(a, b) for _, a, b in pairs])
    return {"answers": rows, "known_before_evidence": known, "agreement": agree}, open_items


def _load(
    root: Path, lock: tuple[Path, Path] | None = None
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    from hindcast.evaluation.batch import FILLED, load_attempts
    from hindcast.evaluation.judge import _sha256, judgment_path, locked_system

    system_sha256, model = locked_system(*lock) if lock else locked_system()
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
        if (record["judge"]["system_sha256"], record["judge"]["model"]) != (system_sha256, model):
            raise ValueError(f"{entry['run_id']}: judged with another judge prompt or model")
        review_path = root / "reviews" / f"{entry['run_id']}.json"
        review = json.loads(review_path.read_text("utf-8")) if review_path.is_file() else {}
        if review and review["judgment_sha256"] != _sha256(data):
            raise ValueError(f"{entry['run_id']}: the review is for another judgment")
        records[entry["run_id"]], reviews[entry["run_id"]] = record, review
    return attempts, records, reviews


def load_second_judgments(root: Path, reviews: Mapping[str, Mapping[str, Any]]) -> dict[str, dict]:
    """The reviewer's judgment behind each review it decided, checked by hash."""
    from hindcast.evaluation.judge import _sha256, judgment_path

    seconds = {}
    for run_id, review in reviews.items():
        hashes = {
            d["decided_by"]["judgment_sha256"]
            for d in review.get("decisions", [])
            if d.get("decided_by")
        }
        if not hashes:
            continue
        data = judgment_path(root / "reviewer" / "judgments", run_id).read_bytes()
        if hashes != {_sha256(data)}:
            raise ValueError(f"{run_id}: the review was decided from another reviewer judgment")
        seconds[run_id] = json.loads(data)
    return seconds


def main(argv: list[str] | None = None) -> int:
    from hindcast.evaluation.judge import load_case
    from hindcast.labels import FROZEN as LABELS_FROZEN
    from hindcast.labels import LABELS_DIR, load_labels

    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.score")
    parser.add_argument("--draft", action="store_true", help="print counts, write nothing")
    parser.add_argument(
        "--root", type=Path, default=ROOT, help=f"the scoring tree (default {ROOT})"
    )
    args = parser.parse_args(argv)
    root = args.root
    # The prior answers feed the known-before-evidence table of any tree, but
    # their own scores file is written with the default tree only.
    prior, prior_open = prior_scores()
    print(f"prior answers {len(prior['answers'])}, open review items {prior_open}")
    attempts, records, reviews = _load(root)
    seconds = load_second_judgments(root, reviews)
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
        scores.append(score_run(record, reviews[run_id], labels[case_id], seconds.get(run_id)))
    open_items = sum(s.open_items for s in scores)
    print(f"runs {len(scores)}, open review items {open_items}")
    if args.draft:
        return 0
    if open_items or prior_open:
        raise SystemExit("review items are open: finish the review, or use --draft")
    known = {(deployment, case_id) for deployment, case_id in prior["known_before_evidence"]}
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

    def tables(group: list[RunScore]) -> dict:
        return aggregate(group, models=models, known=known, attempts=attempts, usage=usage)

    out = {
        "rubric": "eval/rubric/rubric.md",
        "runs": [asdict(s) for s in scores],
        "tables": tables(scores),
        "agreement": review_agreement(pairs),
    }
    opinion = second_opinion(records, seconds, labels, tables)
    if opinion is None:
        print("second opinion left out: not every run has a reviewer decision")
    else:
        out["second_opinion"] = opinion
    (root / "scores.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    if root == ROOT:
        (PRIOR_ROOT / "scores.json").write_text(json.dumps(prior, indent=2) + "\n", "utf-8")
    print(f"{root / 'scores.json'}: {len(scores)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

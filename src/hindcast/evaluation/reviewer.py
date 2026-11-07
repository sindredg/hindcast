"""The reviewer: a second, blind judgment whose verdicts decide the review queue.

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.reviewer freeze
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.reviewer \
        run [--limit N] [--root DIR]
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.reviewer apply [--root DIR]

Rubric version 3, Review (decision 0027): claude-fable-5-1 judges every judged
run and every prior answer again, without the judge's proposals. It gets the
judge's frozen prompt less its sentence about a person's review, the same
rubric sections, effort, output limit, and reply checks
(hindcast.evaluation.judge and judge_prior with another model and lock). Its
outcome for a key item, or its support verdict for a run item, is the
decision on that item wherever the frozen review queue lists it
(hindcast.evaluation.review). A decision names the reviewer's model and the
SHA-256 of the judgment it came from, and goes into the same review files the
score reads. No person decides.

`run` makes the calls and prints counts and token usage only. `apply` is
offline: it refuses a second judgment made on other input than the judgment
it reviews, or under another lock, and skips one that has no judgment yet or
ended in an error, so a later `run` can fill it.
"""

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from hindcast.evaluation import judge, judge_prior
from hindcast.evaluation.batch import FILLED, ROOT, load_attempts, run_loader
from hindcast.evaluation.review import (
    ReviewItem,
    load_review,
    pending,
    prior_queue,
    record_decision,
    review_queue,
)

REVIEWER_MODEL = "claude-fable-5-1"
PROMPT = Path("prompts/reviewer.md")
PRIOR_PROMPT = Path("prompts/reviewer-prior.md")
FROZEN = Path("eval/judge/frozen-reviewer.json")
FROZEN_PRIOR = Path("eval/judge/frozen-reviewer-prior.json")
# The one sentence of the judge's prompts the reviewer's copies leave out.
REMOVED = " A person reviews your verdicts."
OUT_DIR = ROOT / "reviewer" / "judgments"
PRIOR_ROOT = judge_prior.ROOT / "reviewer"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decision_for(item: ReviewItem, second: Mapping[str, Any]) -> str | bool:
    """The second judgment's verdict on one queue item."""
    judgment = second["judgment"]
    if item.kind == "match":
        return judgment["key_items"][item.item]["outcome"]
    if item.kind == "support":
        return judgment["run_items"][item.item]["supported"]
    return judgment[item.item]["outcome"]


def apply_review(
    first_path: Path,
    second_path: Path,
    review_path: Path,
    record_id: str,
    queue: Callable[[Mapping[str, Any]], list[ReviewItem]],
    now: datetime | None = None,
) -> int:
    """Decide the first judgment's open queue items from the second; returns decisions written."""
    first_data, second_data = first_path.read_bytes(), second_path.read_bytes()
    first, second = json.loads(first_data), json.loads(second_data)
    if first["error"] is not None or second["error"] is not None:
        raise ValueError(f"{record_id}: a judgment ended in an error")
    # Both calls were given the same input, or the second reviews another run.
    if second["judge"]["input_sha256"] != first["judge"]["input_sha256"]:
        raise ValueError(f"{record_id}: the second judgment was made on other input")
    judgment_sha256 = _sha256(first_data)
    by = {"model": second["judge"]["model"], "judgment_sha256": _sha256(second_data)}
    todo = pending(queue(first), load_review(review_path, record_id, judgment_sha256))
    for item in todo:
        record_decision(
            review_path,
            record_id,
            judgment_sha256,
            item,
            decision_for(item, second),
            now,
            decided_by=by,
        )
    return len(todo)


def _usable(second_path: Path, locked: tuple[str, str], record_id: str) -> bool:
    """A second judgment to apply: present, made under the reviewer's lock, without an error."""
    if not second_path.is_file():
        return False
    second = json.loads(second_path.read_text(encoding="utf-8"))
    if (second["judge"]["system_sha256"], second["judge"]["model"]) != locked:
        raise ValueError(f"{record_id}: judged with another reviewer prompt or model")
    return second["error"] is None


def apply_runs(
    root: Path = ROOT,
    second_dir: Path = OUT_DIR,
    lock: tuple[Path, Path] = (PROMPT, FROZEN),
    now: datetime | None = None,
) -> dict[str, int]:
    locked = judge.locked_system(*lock)
    counts = {"runs": 0, "decisions": 0, "missing": 0}
    for entry in load_attempts(root / "attempts.json"):
        if entry["status"] not in FILLED:
            continue
        run_id = entry["run_id"]
        second_path = judge.judgment_path(second_dir, run_id)
        if not _usable(second_path, locked, run_id):
            counts["missing"] += 1
            continue
        counts["decisions"] += apply_review(
            judge.judgment_path(root / "judgments", run_id),
            second_path,
            root / "reviews" / f"{run_id}.json",
            run_id,
            review_queue,
            now,
        )
        counts["runs"] += 1
    return counts


def apply_prior(
    root: Path = judge_prior.ROOT,
    second_root: Path = PRIOR_ROOT,
    lock: tuple[Path, Path] = (PRIOR_PROMPT, FROZEN_PRIOR),
    now: datetime | None = None,
) -> dict[str, int]:
    locked = judge.locked_system(*lock)
    counts = {"answers": 0, "decisions": 0, "missing": 0}
    for first_path in sorted((root / "judgments").glob("*/*.json")):
        record_id = f"{first_path.parent.name}/{first_path.stem}"
        second_path = second_root / "judgments" / f"{record_id}.json"
        if not _usable(second_path, locked, record_id):
            counts["missing"] += 1
            continue
        counts["decisions"] += apply_review(
            first_path,
            second_path,
            root / "reviews" / f"{record_id}.json",
            record_id,
            lambda record, record_id=record_id: prior_queue(record, record_id),
            now,
        )
        counts["answers"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.reviewer")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("freeze", help=f"write {FROZEN} and {FROZEN_PRIOR}")
    run = commands.add_parser("run", help="judge every judged run and prior answer again")
    run.add_argument("--limit", type=int, help="only the first N runs, no prior answers")
    run.add_argument("--workers", type=int, default=4)
    apply = commands.add_parser("apply", help="write the second judgments' verdicts as decisions")
    # Another tree (the revealed seals) has runs only: no prior answers are
    # judged or applied with it.
    for command in (run, apply):
        command.add_argument(
            "--root", type=Path, default=ROOT, help=f"the scoring tree (default {ROOT})"
        )
    args = parser.parse_args(argv)
    if args.command == "freeze":
        for prompt, frozen, compose in (
            (PROMPT, FROZEN, judge.system_prompt),
            (PRIOR_PROMPT, FROZEN_PRIOR, judge_prior.system_prompt),
        ):
            record = judge.freeze(prompt, judge.RUBRIC, frozen, compose, model=REVIEWER_MODEL)
            print(f"{frozen}: system sha256 {record['system_sha256']}")
        return 0
    if args.command == "apply":
        runs = apply_runs(args.root, args.root / "reviewer" / "judgments")
        print(f"runs {runs['runs']}, decisions {runs['decisions']}, missing {runs['missing']}")
        if args.root != ROOT:
            return 0
        prior = apply_prior()
        print(
            f"prior answers {prior['answers']}, decisions {prior['decisions']}, "
            f"missing {prior['missing']}"
        )
        return 0

    import anthropic

    from hindcast.evaluation.prior import clean_head_commit
    from hindcast.excerpts import load_library_items

    stamp = {"code_commit": clean_head_commit([Path(p) for p in judge.CLEAN_PATHS])}
    client = anthropic.Anthropic()
    out_dir = args.root / "reviewer" / "judgments"
    entries = [e for e in load_attempts(args.root / "attempts.json") if e["status"] in FILLED]
    counts = judge.judge_all(
        entries[: args.limit] if args.limit else entries,
        load_run=run_loader(args.root),
        load_case=judge.load_case,
        library=load_library_items(),
        client=client,
        out_dir=out_dir,
        paths=(PROMPT, judge.RUBRIC, FROZEN),
        workers=args.workers,
        stamp=stamp,
        model=REVIEWER_MODEL,
    )
    print(f"runs: judged {counts['judged']}, errors {counts['errors']}, kept {counts['kept']}")
    records = [json.loads(p.read_text("utf-8")) for p in sorted(out_dir.rglob("*.json"))]
    if not args.limit and args.root == ROOT:
        prior = judge_prior.judge_all(
            sorted(judge_prior.RESULTS_DIR.glob("prior-*.json")),
            load_key=lambda case_id: judge.load_case(case_id)[0],
            cases=judge_prior.case_lines(),
            client=client,
            root=PRIOR_ROOT,
            paths=(PRIOR_PROMPT, judge.RUBRIC, FROZEN_PRIOR),
            stamp=stamp,
            model=REVIEWER_MODEL,
        )
        print(
            f"prior answers: judged {prior['judged']}, errors {prior['errors']}, "
            f"kept {prior['kept']}"
        )
        records += [json.loads(p.read_text("utf-8")) for p in sorted(PRIOR_ROOT.rglob("*.json"))]
    errors = sorted({r["error"] for r in records if r["error"]})
    print(f"second judgment files {len(records)}, error kinds: {', '.join(errors) or 'none'}")
    print(f"usage over all second judgment files: {judge._usage_line(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

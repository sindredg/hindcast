"""The judge on the prior-knowledge answers: did a model know the cause before any evidence?

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.judge_prior freeze
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge_prior run

Each answer in eval/results/prior-*.json is compared with its case's frozen
key on the root cause and the attack verdict (rubric version 2, Prior
knowledge), by the same model and settings as hindcast.evaluation.judge. An
answer had no evidence, so there are no support verdicts: the outcomes are
hit, partial (root cause only), abstained, missed, and wrong. A judge error
is recorded as in the reconstruction judge and judged again on the next run.

Writes eval/prior-knowledge/v1/judgments/<answer file>/<case_id>.json and
prints counts only: the answers are read in the review page, nowhere else.
"""

import argparse
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from hindcast.evaluation import judge
from hindcast.keys import AnswerKey

PROMPT = Path("prompts/judge-prior.md")
FROZEN = Path("eval/judge/frozen-prior.json")
RESULTS_DIR = Path("eval/results")
ROOT = Path("eval/prior-knowledge/v1")
OUTCOMES = {
    "attack": ("hit", "abstained", "missed", "wrong"),
    "root_cause": ("hit", "partial", "abstained", "missed", "wrong"),
}


def system_prompt(prompt: Path = PROMPT, rubric: Path = judge.RUBRIC) -> str:
    """The prompt, then the rubric's hedging and matching rules and its prior-knowledge section."""
    text = rubric.read_text(encoding="utf-8")
    title = text.split("\n", 1)[0]
    rules_start = text.index("A hedged statement")
    rules_end = text.index("\n## Support\n")
    prior = text[text.index("\n## Prior knowledge\n") :].strip()
    rules = text[rules_start:rules_end].strip()
    return (
        f"{prompt.read_text(encoding='utf-8').rstrip()}\n\n{title}\n\n"
        f"## Outcomes (hedging and matching)\n\n{rules}\n\n{prior}\n"
    )


def schema() -> dict:
    return judge._object(
        {
            item: judge._object(
                {
                    "reason": {"type": "string"},
                    "outcome": {"type": "string", "enum": list(outcomes)},
                }
            )
            for item, outcomes in OUTCOMES.items()
        }
    )


def prior_input(entry: Mapping[str, Any], key: AnswerKey, case: Mapping[str, str]) -> str:
    data = {
        "case": dict(case),
        "question": entry["question"],
        "answer": entry["answer"],
        "key_items": [
            {"id": "attack", "text": key.attack, "quote": key.attack_quote},
            {"id": "root_cause", "text": key.root_cause.text, "quote": key.root_cause.source_quote},
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def judge_answer(
    collection: Mapping[str, Any],
    entry: Mapping[str, Any],
    key: AnswerKey,
    case: Mapping[str, str],
    *,
    client: Any,
    system: str,
) -> dict:
    if entry["case_id"] != key.case_id:
        raise ValueError(f"{entry['case_id']}: the key is for {key.case_id}")
    content = prior_input(entry, key, case)
    reply_schema = schema()
    record: dict[str, Any] = {
        "case_id": entry["case_id"],
        "deployment": collection["deployment"],
        "model_name": collection["model_name"],
        "model_version": collection["model_version"],
        "collected_at": collection["collected_at"],
        **judge.new_record(system, content),
    }
    return judge.call(
        client, system, content, reply_schema, record, lambda m: judge.read_json(m, reply_schema)
    )


def judgment_path(root: Path, answers: Path, case_id: str) -> Path:
    return root / "judgments" / answers.stem / f"{case_id}.json"


def judge_all(
    files: Iterable[Path],
    *,
    load_key: Callable[[str], AnswerKey],
    cases: Mapping[str, Mapping[str, str]],
    client: Any,
    root: Path = ROOT,
    paths: tuple[Path, Path, Path] = (PROMPT, judge.RUBRIC, FROZEN),
    stamp: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    """Judge every answer without a judgment; keep the judgments that exist."""
    system = judge.check_frozen(*paths, compose=system_prompt)
    counts = {"judged": 0, "errors": 0, "kept": 0}
    for answers in files:
        collection = json.loads(answers.read_text(encoding="utf-8"))
        for entry in collection["entries"]:
            path = judgment_path(root, answers, entry["case_id"])
            earlier: list[str] = []
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if old["error"] is None:
                    counts["kept"] += 1
                    continue
                earlier = [*old.get("earlier_errors", []), old["error"]]
            record = judge_answer(
                collection,
                entry,
                load_key(entry["case_id"]),
                cases[entry["case_id"]],
                client=client,
                system=system,
            )
            record |= {"answers": answers.as_posix(), **(stamp or {})}
            record["earlier_errors"] = earlier
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
            counts["errors" if record["error"] else "judged"] += 1
    return counts


def case_lines() -> dict[str, dict[str, str]]:
    """Each showcase case as the prior question named it: provider, title, date."""
    from hindcast.cases import load_cases
    from hindcast.evaluation.prior import load_prompt

    prompt = load_prompt()
    return {
        case.case_id: {
            "provider": case.provider,
            "title": case.title,
            "date": prompt.dates[case.case_id],
        }
        for case in load_cases().values()
        if case.case_id in prompt.dates
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.judge_prior")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("freeze", help="write eval/judge/frozen-prior.json")
    commands.add_parser("run", help="judge every prior-knowledge answer")
    args = parser.parse_args(argv)
    if args.command == "freeze":
        record = judge.freeze(PROMPT, judge.RUBRIC, FROZEN, compose=system_prompt)
        print(f"{FROZEN}: system sha256 {record['system_sha256']}")
        return 0

    import anthropic

    from hindcast.evaluation.prior import clean_head_commit

    stamp = {"code_commit": clean_head_commit([Path(p) for p in judge.CLEAN_PATHS])}
    counts = judge_all(
        sorted(RESULTS_DIR.glob("prior-*.json")),
        load_key=lambda case_id: judge.load_case(case_id)[0],
        cases=case_lines(),
        client=anthropic.Anthropic(),
        stamp=stamp,
    )
    records = [json.loads(p.read_text("utf-8")) for p in sorted(ROOT.rglob("judgments/**/*.json"))]
    errors = sorted({r["error"] for r in records if r["error"]})
    print(f"judged {counts['judged']}, errors {counts['errors']}, kept {counts['kept']}")
    print(f"judgment files {len(records)}, error kinds: {', '.join(errors) or 'none'}")
    print(f"usage over all judgment files: {judge._usage_line(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

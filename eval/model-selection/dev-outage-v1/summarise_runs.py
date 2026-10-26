"""Print the scores and token counts of the sanitized runs, and the score part of the rule.

    uv run --frozen python eval/model-selection/dev-outage-v1/summarise_runs.py \
        results-luna-dev-outage-v1.jsonl results-sol-dev-outage-v1.jsonl

For each run: the score per question and evaluator, the mean per evaluator, the evaluator
calls that errored, and the tokens of the answers and of the judge. With two runs, luna
first: whether luna's mean groundedness and completeness are within 1 point of sol's. The
other half of the rule, a refusal on question 5 without an invented cause, is read from the
answer by hand.

With two runs, exit code 1 when the score part of the rule is not met, or a score it needs is
missing. With one run, exit code 0: there is nothing to compare.
"""

import json
import sys
from pathlib import Path

RULE = ("Groundedness", "ResponseCompleteness")


def _scores(rows: list[dict]) -> dict[str, list]:
    """Score per evaluator and question, None where a question has no score from it."""
    per_row = [
        {result["name"]: result["score"] for result in row["results"]}
        for row in sorted(rows, key=lambda r: r["datasource_item_id"])
    ]
    names = dict.fromkeys(name for scores in per_row for name in scores)
    return {name: [scores.get(name) for scores in per_row] for name in names}


def means(rows: list[dict]) -> dict[str, float | None]:
    # A failed or absent evaluator call has no score; leaving it out would move the mean.
    return {
        name: None if None in scores else round(sum(scores) / len(scores), 2)
        for name, scores in _scores(rows).items()
    }


def tokens(rows: list[dict]) -> dict[str, tuple[int, int]]:
    answer = [row["sample"]["usage"] for row in rows]
    # An errored evaluator call (status "error") has no usage: the judge returned nothing.
    judge = [r["sample"]["usage"] for row in rows for r in row["results"] if "usage" in r["sample"]]

    def total(usages):
        return sum(u["prompt_tokens"] for u in usages), sum(u["completion_tokens"] for u in usages)

    return {"answer": total(answer), "judge": total(judge)}


def errored(rows: list[dict]) -> list[tuple[str, str]]:
    """(question, evaluator) for every evaluator call the portal marked as errored."""
    return [
        (f"Q{row['datasource_item_id'] + 1}", result["name"])
        for row in sorted(rows, key=lambda r: r["datasource_item_id"])
        for result in row["results"]
        if result.get("status") == "error"
    ]


def within_one_point(luna: float | None, sol: float | None) -> bool:
    return luna is not None and sol is not None and luna >= sol - 1


def rule_scores_met(luna: dict, sol: dict) -> bool:
    return all(within_one_point(luna.get(name), sol.get(name)) for name in RULE)


def main() -> int:
    runs = []
    for path in map(Path, sys.argv[1:]):
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        runs.append(rows)
        table = _scores(rows)
        print(f"{path.name}, {len(rows)} questions")
        for name, scores in sorted(table.items()):
            row = " ".join("-" if s is None else f"{s:.1f}" for s in scores)
            print(f"  {name}: {row}, mean {means(rows)[name]}")
        if failed := errored(rows):
            print("  errored evaluator calls: " + ", ".join(f"{q} {name}" for q, name in failed))
        used = tokens(rows)
        ratio = sum(used["judge"]) / sum(used["answer"])
        print(f"  answer tokens: {used['answer'][0]:,} input, {used['answer'][1]:,} output")
        print(f"  judge tokens: {used['judge'][0]:,} input, {used['judge'][1]:,} output")
        print(f"  judge tokens per answer token: {ratio:.1f}")
    if len(runs) != 2:
        return 0
    luna, sol = (means(rows) for rows in runs)
    for name in RULE:
        within = "yes" if within_one_point(luna.get(name), sol.get(name)) else "no"
        print(f"{name}: {luna.get(name)} against {sol.get(name)}, within 1 point: {within}")
    met = rule_scores_met(luna, sol)
    print(f"Score part of the rule: {'met' if met else 'not met'}. Read question 5 by hand.")
    return 0 if met else 1


if __name__ == "__main__":
    sys.exit(main())

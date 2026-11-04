"""What the judge and the reviewer cost on the Claude API, per stage and model.

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.spend

Reads the usage every judgment file records, prices it at
data/claude-prices.yaml, writes eval/judge/spend.json, and prints one line
per stage. Only the calls a judgment file records are priced. A call that
errored and was then run again leaves only its error kind (earlier_errors),
and a record may carry no usage: both are counted as unpriced calls, never
as free ones. Test calls written outside these folders are not counted, so
the billed total in the Anthropic Console is the check on this number.
"""

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from hindcast.costs import CLAUDE_USAGE_PRICE, ClaudePriceTable, claude_cost, load_claude_prices

STAGES = {
    "judge, scored runs": Path("eval/reconstruction/showcase-v1/judgments"),
    "judge, prior answers": Path("eval/prior-knowledge/v1/judgments"),
    "reviewer, scored runs": Path("eval/reconstruction/showcase-v1/reviewer/judgments"),
    "reviewer, prior answers": Path("eval/prior-knowledge/v1/reviewer/judgments"),
}
OUT = Path("eval/judge/spend.json")


def spend(stages: Mapping[str, Path], table: ClaudePriceTable) -> dict:
    """The priced usage per stage and model, and the calls with nothing to price."""
    rows = []
    for stage, folder in stages.items():
        paths = sorted(folder.rglob("*.json"))
        if not paths:
            raise ValueError(f"{stage}: no judgment files in {folder}")
        by_model: dict[str, dict] = defaultdict(
            lambda: {"calls": 0, "unpriced_calls": 0, "usage": dict.fromkeys(CLAUDE_USAGE_PRICE, 0)}
        )
        for path in paths:
            record = json.loads(path.read_text("utf-8"))
            row = by_model[record["judge"]["model"]]
            row["unpriced_calls"] += len(record.get("earlier_errors") or [])
            if record.get("usage") is None:
                row["unpriced_calls"] += 1
                continue
            row["calls"] += 1
            for name in CLAUDE_USAGE_PRICE:
                row["usage"][name] += record["usage"][name]
        for model, row in sorted(by_model.items()):
            cost = round(claude_cost(table, model, row["usage"]), 6)
            rows.append({"stage": stage, "model": model, **row, "cost": cost})
    return {
        "table": {
            "version": table.version,
            "retrieved": table.retrieved,
            "currency": table.currency,
            "source": table.source,
        },
        "stages": rows,
        "unpriced_calls": sum(r["unpriced_calls"] for r in rows),
        # The total is the sum of the rows as written, so they add up.
        "total": round(math.fsum(r["cost"] for r in rows), 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.spend")
    parser.parse_args(argv)
    table = load_claude_prices()
    out = spend(STAGES, table)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for row in out["stages"]:
        print(
            f"{row['stage']}: {row['model']}, {row['calls']} calls, "
            f"{row['unpriced_calls']} unpriced, {table.currency} {row['cost']:.2f}"
        )
    print(
        f"total {table.currency} {out['total']:.2f}, {out['unpriced_calls']} unpriced calls "
        f"(Claude price table version {table.version}, read {table.retrieved})"
    )
    print(f"{OUT}: written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

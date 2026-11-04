import json
from pathlib import Path

import pytest

from hindcast.costs import ClaudePriceTable, claude_cost, load_claude_prices
from hindcast.evaluation import judge, judge_prior, reviewer, spend

TABLE = ClaudePriceTable(
    version=1,
    retrieved="2026-11-04",
    currency="USD",
    source="https://example.com/pricing",
    models={
        "claude-opus-5-5": {
            "input": 4.0,
            "cache_write_5m": 5.0,
            "cache_read": 0.20,
            "output": 20.0,
        },
        "claude-fable-5-1": {
            "input": 10.0,
            "cache_write_5m": 12.5,
            "cache_read": 0.25,
            "output": 50.0,
        },
    },
)
USAGE = {
    "input_tokens": 1_000,
    "cache_creation_input_tokens": 2_000,
    "cache_read_input_tokens": 10_000,
    "output_tokens": 500,
}


def test_claude_cost_prices_each_part() -> None:
    # Hand-computed before the code: the API's input_tokens excludes the cached
    # tokens, so nothing is subtracted.
    # 1,000 x 4 + 2,000 x 5 + 10,000 x 0.20 + 500 x 20 = 26,000 per million = 0.026
    assert claude_cost(TABLE, "claude-opus-5-5", USAGE) == pytest.approx(0.026)


def test_claude_cost_unknown_model_raises() -> None:
    with pytest.raises(KeyError, match="claude-other"):
        claude_cost(TABLE, "claude-other", USAGE)


def test_claude_cost_missing_usage_field_raises() -> None:
    # A field missing from the record would otherwise price as zero.
    usage = {k: v for k, v in USAGE.items() if k != "cache_read_input_tokens"}
    with pytest.raises(ValueError, match="cache_read_input_tokens"):
        claude_cost(TABLE, "claude-opus-5-5", usage)


def _write(path: Path, model: str, usage: dict | None, earlier: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"judge": {"model": model}, "usage": usage, "error": None}
    if earlier is not None:
        record["earlier_errors"] = earlier
    path.write_text(json.dumps(record), "utf-8")


def test_spend_per_stage_and_model(tmp_path: Path) -> None:
    runs, prior = tmp_path / "runs", tmp_path / "prior"
    _write(runs / "arm" / "case" / "r1" / "a1.json", "claude-opus-5-5", USAGE)
    _write(runs / "arm" / "case" / "r2" / "a1.json", "claude-opus-5-5", USAGE)
    _write(prior / "answers" / "case.json", "claude-fable-5-1", USAGE)
    out = spend.spend({"judge, runs": runs, "reviewer, prior": prior}, TABLE)
    # Fable: 1,000 x 10 + 2,000 x 12.5 + 10,000 x 0.25 + 500 x 50 = 62,500 -> 0.0625
    assert out["stages"] == [
        {
            "stage": "judge, runs",
            "model": "claude-opus-5-5",
            "calls": 2,
            "unpriced_calls": 0,
            "usage": {k: 2 * v for k, v in USAGE.items()},
            "cost": 0.052,
        },
        {
            "stage": "reviewer, prior",
            "model": "claude-fable-5-1",
            "calls": 1,
            "unpriced_calls": 0,
            "usage": USAGE,
            "cost": 0.0625,
        },
    ]
    assert out["total"] == pytest.approx(0.1145)
    assert out["unpriced_calls"] == 0
    assert out["table"] == {
        "version": 1,
        "retrieved": "2026-11-04",
        "currency": "USD",
        "source": "https://example.com/pricing",
    }


def test_spend_counts_calls_it_cannot_price(tmp_path: Path) -> None:
    # A call that errored and was run again keeps only its error kind, and a
    # record without usage has nothing to price: both are listed, not dropped.
    runs = tmp_path / "runs"
    _write(runs / "a.json", "claude-opus-5-5", USAGE, earlier=["refusal", "max_tokens"])
    _write(runs / "b.json", "claude-opus-5-5", None)
    out = spend.spend({"judge, runs": runs}, TABLE)
    (stage,) = out["stages"]
    assert stage["calls"] == 1
    assert stage["unpriced_calls"] == 3
    assert out["unpriced_calls"] == 3


def test_spend_refuses_an_empty_stage(tmp_path: Path) -> None:
    # A wrong folder would otherwise report a spend of zero.
    with pytest.raises(ValueError, match="no judgment files"):
        spend.spend({"judge, runs": tmp_path / "missing"}, TABLE)


def test_stages_are_the_folders_the_judge_and_reviewer_write() -> None:
    assert set(spend.STAGES.values()) == {
        judge.OUT_DIR,
        judge_prior.ROOT / "judgments",
        reviewer.OUT_DIR,
        reviewer.PRIOR_ROOT / "judgments",
    }


def test_committed_table_prices_the_judge_and_reviewer_models() -> None:
    table = load_claude_prices()
    assert {judge.JUDGE_MODEL, reviewer.REVIEWER_MODEL} <= table.models.keys()
    for prices in table.models.values():
        assert set(prices) == {"input", "cache_write_5m", "cache_read", "output"}
    assert table.source.startswith("https://platform.claude.com/")
    assert table.retrieved

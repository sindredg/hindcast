from dataclasses import replace
from pathlib import Path

import pytest

from hindcast.costs import PriceTable, load_prices, run_cost
from hindcast.investigate import Usage

TABLE = PriceTable(
    version=1,
    currency="USD",
    models={"gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50}},
    embedding=0.13,
    prompt_shields=0.375,
    pii=1.00,
    short_context_tokens=272_000,
)


BASE = Usage(
    model_calls=2,
    tool_calls=3,
    seconds=10.0,
    input_tokens=10_000,
    cached_input_tokens=4_000,
    output_tokens=2_000,
    screen_calls=2,
    screen_records=7,
    pii_calls=1,
    pii_records=9,
    max_call_input_tokens=6_000,
)


def usage(**changes: int) -> Usage:
    return replace(BASE, **changes)


def test_cost_from_tokens() -> None:
    # Hand-computed before the first run:
    # model 6,000 x 0.10/M + 4,000 x 0.01/M + 2,000 x 0.50/M = 0.00164
    # screens 7 x 0.375/1,000 = 0.002625; PII 9 x 1.00/1,000 = 0.009
    # embeddings 300 x 0.13/M = 0.000039; total 0.013304
    cost = run_cost(TABLE, "gpt-6-luna", usage(), embedding_tokens=300)
    assert cost == {
        "table_version": 1,
        "currency": "USD",
        "model": 0.00164,
        "screens": 0.002625,
        "pii": 0.009,
        "embeddings": 0.000039,
        "total": 0.013304,
    }


def test_cached_input_priced_separately() -> None:
    all_cached = run_cost(
        TABLE, "gpt-6-luna", usage(cached_input_tokens=10_000), embedding_tokens=0
    )
    none_cached = run_cost(TABLE, "gpt-6-luna", usage(cached_input_tokens=0), embedding_tokens=0)
    assert all_cached["model"] == pytest.approx(10_000 * 0.01e-6 + 2_000 * 0.5e-6)
    assert none_cached["model"] == pytest.approx(10_000 * 0.10e-6 + 2_000 * 0.5e-6)


def test_unknown_deployment_raises() -> None:
    with pytest.raises(KeyError, match="gpt-7"):
        run_cost(TABLE, "gpt-7", usage(), embedding_tokens=0)


def test_long_context_call_raises() -> None:
    # The table holds short-context rates only; a longer call would be priced wrong.
    with pytest.raises(ValueError, match="short-context"):
        run_cost(TABLE, "gpt-6-luna", usage(max_call_input_tokens=272_001), embedding_tokens=0)


def test_committed_table_prices_every_run_deployment() -> None:
    table = load_prices(Path("data/prices.yaml"))
    assert table.version >= 1 and table.currency == "USD"
    for deployment in ("gpt-6-luna", "gpt-6.1-sol", "gpt-5.4-mini"):
        assert set(table.models[deployment]) == {"input", "cached_input", "output"}
        assert all(price > 0 for price in table.models[deployment].values())
    assert table.embedding > 0 and table.prompt_shields > 0 and table.pii > 0

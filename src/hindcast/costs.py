"""Token usage and the cost of a run, from a versioned price table.

data/prices.yaml holds the prices per deployment, the embedding model,
Prompt Shields, and PII detection, with where and when each was read. A run
records the table version next to its cost. A deployment missing from the
table raises KeyError: a cost of zero would read as a free run. The cost is
an estimate from list prices; decision 0011 checks it once against billed
cost.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ruamel.yaml import YAML

PRICES = Path("data/prices.yaml")
PER_MILLION = 1_000_000
PER_THOUSAND = 1_000


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class PriceTable:
    version: int
    currency: str
    # Per million tokens: {"input", "cached_input", "output"} per deployment.
    models: Mapping[str, Mapping[str, float]]
    # Per million embedding tokens.
    embedding: float
    # Per thousand text records.
    prompt_shields: float
    pii: float
    short_context_tokens: int


def load_prices(path: Path = PRICES) -> PriceTable:
    raw = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return PriceTable(
        version=int(raw["version"]),
        currency=str(raw["currency"]),
        models={
            name: {k: float(v) for k, v in prices.items()} for name, prices in raw["models"].items()
        },
        embedding=float(raw["embedding"]),
        prompt_shields=float(raw["prompt_shields"]),
        pii=float(raw["pii"]),
        short_context_tokens=int(raw["short_context_tokens"]),
    )


class RunUsage(Protocol):
    # Read-only, so a frozen dataclass (hindcast.investigate.Usage) fits.
    @property
    def input_tokens(self) -> int: ...
    @property
    def cached_input_tokens(self) -> int: ...
    @property
    def output_tokens(self) -> int: ...
    @property
    def screen_records(self) -> int: ...
    @property
    def pii_records(self) -> int: ...
    @property
    def max_call_input_tokens(self) -> int: ...


def run_cost(table: PriceTable, deployment: str, usage: RunUsage, *, embedding_tokens: int) -> dict:
    """The run's cost by part, rounded to six decimals."""
    if deployment not in table.models:
        raise KeyError(f"{deployment} is not in price table version {table.version}")
    if usage.max_call_input_tokens > table.short_context_tokens:
        raise ValueError(
            f"a call of {usage.max_call_input_tokens} input tokens is past the "
            f"short-context limit of {table.short_context_tokens} the table prices"
        )
    prices = table.models[deployment]
    uncached = usage.input_tokens - usage.cached_input_tokens
    parts = {
        "model": (
            uncached * prices["input"]
            + usage.cached_input_tokens * prices["cached_input"]
            + usage.output_tokens * prices["output"]
        )
        / PER_MILLION,
        "screens": usage.screen_records * table.prompt_shields / PER_THOUSAND,
        "pii": usage.pii_records * table.pii / PER_THOUSAND,
        "embeddings": embedding_tokens * table.embedding / PER_MILLION,
    }
    rounded = {name: round(value, 6) for name, value in parts.items()}
    # The total is the sum of the parts as written, so they add up.
    return {
        "table_version": table.version,
        "currency": table.currency,
        **rounded,
        "total": round(math.fsum(rounded.values()), 6),
    }

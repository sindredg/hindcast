"""Token usage and, from the interface phase on, its cost."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int

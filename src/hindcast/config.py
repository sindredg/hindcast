"""Settings read from the environment.

Every setting is an endpoint or a deployment name, never a key: the SDKs
authenticate with DefaultAzureCredential.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields

PREFIX = "HINDCAST_"


class ConfigError(ValueError):
    """A required setting is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    project_endpoint: str
    search_endpoint: str
    search_index: str
    storage_url: str
    chat_deployment: str
    judge_deployment: str
    compare_deployment: str
    embedding_deployment: str
    cu_endpoint: str
    embedding_dimensions: int = 1024


def env_name(field_name: str) -> str:
    return PREFIX + field_name.upper()


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    """Build Settings from env, naming every missing or invalid variable at once."""
    values: dict[str, str | int] = {}
    problems: list[str] = []

    for field in fields(Settings):
        name = env_name(field.name)
        raw = env.get(name, "").strip()
        if field.type is int:
            if not raw:
                continue
            try:
                number = int(raw)
            except ValueError:
                number = 0
            if number <= 0:
                problems.append(f"{name} must be a positive integer, got {raw!r}")
                continue
            values[field.name] = number
        elif raw:
            values[field.name] = raw
        else:
            problems.append(f"{name} is not set")

    if problems:
        raise ConfigError("; ".join(problems))
    return Settings(**values)

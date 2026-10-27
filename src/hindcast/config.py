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
class ModelSettings:
    project_endpoint: str
    chat_deployment: str
    compare_deployment: str
    judge_deployment: str


@dataclass(frozen=True)
class StorageSettings:
    storage_url: str


@dataclass(frozen=True)
class ExtractionSettings:
    cu_endpoint: str


@dataclass(frozen=True)
class SearchSettings:
    search_endpoint: str
    search_index: str
    embedding_deployment: str
    embedding_dimensions: int = 1024


def env_name(field_name: str) -> str:
    return PREFIX + field_name.upper()


def load_settings[T](section: type[T], env: Mapping[str, str] = os.environ) -> T:
    """Build one component's settings from env, naming every missing or invalid variable.

    Each component loads only its own section, so ingestion runs before the
    search and embedding settings exist.
    """
    values: dict[str, str | int] = {}
    problems: list[str] = []

    for field in fields(section):
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
    return section(**values)

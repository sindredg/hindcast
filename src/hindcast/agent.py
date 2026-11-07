"""The investigator and challenger agents: their committed definitions and Foundry versions.

The instructions live in prompts/investigator.md and prompts/challenger.md;
the tools and the output schemas come from the modules that own them; the
model is the deployment the command runs on. The challenger is a second agent,
not a second version: an agent's output schema is fixed in its definition,
and a challenge answers in a different shape (decision 0021).

Each definition is fingerprinted and the fingerprint is stored in the agent
version's metadata, so a changed definition makes a new version and an
unchanged one reuses the latest.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from hindcast.evaluation.prior import committed_blob_hash
from hindcast.provenance import git_blob_hash, image_manifest
from hindcast.result import CHALLENGE_SCHEMA, INVESTIGATION_SCHEMA
from hindcast.tools import TOOL_DEFINITIONS

# Sent even though medium is the service default, so a changed default cannot
# change results silently (as in hindcast.models).
EFFORT = "medium"
PROMPT_PATH = Path("prompts/investigator.md")
CHALLENGER_PROMPT = Path("prompts/challenger.md")


def _safe(deployment: str) -> str:
    # Foundry takes letters, digits, and inner hyphens only, and gpt-6.1-sol
    # has a dot.
    return re.sub(r"[^A-Za-z0-9-]", "-", deployment)


def agent_name(deployment: str, variant: str | None = None) -> str:
    # One agent per deployment: a run on the comparison model is a second agent
    # with the same instructions, not a new version of this one. An arm with
    # other instructions or tools (hindcast.arms) is an agent of its own too,
    # so the sealed agents' latest versions stay the ones the seals ran.
    name = f"hindcast-investigator-{_safe(deployment)}"
    return name if variant is None else f"{name}-{_safe(variant)}"


def challenger_name(deployment: str) -> str:
    return f"hindcast-challenger-{_safe(deployment)}"


def load_definition(
    deployment: str,
    prompt_path: Path = PROMPT_PATH,
    *,
    tools: list[dict] = TOOL_DEFINITIONS,
    schema_name: str = "investigation",
    schema: dict = INVESTIGATION_SCHEMA,
) -> dict:
    """The prompt agent definition as the service takes it. No temperature or top_p."""
    return {
        "kind": "prompt",
        "model": deployment,
        "instructions": prompt_path.read_text(encoding="utf-8"),
        "reasoning": {"effort": EFFORT},
        "tools": tools,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
    }


def challenger_definition(deployment: str) -> dict:
    return load_definition(
        deployment, CHALLENGER_PROMPT, schema_name="challenge", schema=CHALLENGE_SCHEMA
    )


def definition_fingerprint(definition: dict) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class VersionRefused(RuntimeError):
    """A pinned agent name whose latest version is not the pinned one with this definition."""


def ensure_agent_version(
    agents: Any, name: str, definition: dict, *, pinned: str | None = None
) -> str:
    """The latest version when it carries this definition's fingerprint, else a new one.

    pinned names the version a run must use (a sealed agent's): it is refused,
    and no version is created, unless the latest version is that one and
    carries this definition. Creating first and refusing after would leave the
    sealed agent's name on a version its seals never ran (#62).
    """
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.core.exceptions import ResourceNotFoundError

    fingerprint = definition_fingerprint(definition)
    try:
        latest = next(iter(agents.list_versions(name, limit=1, order="desc")), None)
    except ResourceNotFoundError:
        latest = None
    current = None if latest is None else (latest.metadata or {}).get("fingerprint")
    if pinned is not None:
        if latest is None:
            raise VersionRefused(f"{name} has no version; the sealed series ran version {pinned}")
        if current != fingerprint:
            raise VersionRefused(
                f"{name} version {latest.version} does not carry this definition; "
                f"the sealed series ran version {pinned}"
            )
        if latest.version != pinned:
            raise VersionRefused(
                f"{name} is at version {latest.version}; the sealed series ran version {pinned}"
            )
    if latest is not None and current == fingerprint:
        return latest.version
    created = agents.create_version(
        name, definition=PromptAgentDefinition(definition), metadata={"fingerprint": fingerprint}
    )
    return created.version


def prompt_provenance(path: Path = PROMPT_PATH, repo: Path = Path(".")) -> dict:
    """The prompt's committed blob hash, or its SHA-256 marked dirty when it differs from HEAD."""
    # A dirty prompt is recorded, not refused: the development case is for
    # iterating on the prompt.
    try:
        return {"blob": committed_blob_hash(path, repo), "dirty": False}
    except RuntimeError, FileNotFoundError:
        data = (repo / path).read_bytes()
        # In the image, with no Git, the prompt is clean when its blob hash
        # matches the one CI recorded at build time (decision 0028).
        manifest = image_manifest()
        blob = git_blob_hash(data)
        if manifest is not None and manifest.get("blobs", {}).get(path.as_posix()) == blob:
            return {"blob": blob, "dirty": False}
        return {"sha256": hashlib.sha256(data).hexdigest(), "dirty": True}

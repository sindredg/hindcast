"""The investigator agent: its committed definition and its Foundry version.

The instructions live in prompts/investigator.md; the tools and the output
schema come from the modules that own them; the model is the deployment the
command runs on. The definition is fingerprinted and the fingerprint is stored
in the agent version's metadata, so a changed definition makes a new version
and an unchanged one reuses the latest.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from hindcast.evaluation.prior import committed_blob_hash
from hindcast.result import INVESTIGATION_SCHEMA
from hindcast.tools import TOOL_DEFINITIONS

# Sent even though medium is the service default, so a changed default cannot
# change results silently (as in hindcast.models).
EFFORT = "medium"
PROMPT_PATH = Path("prompts/investigator.md")


def agent_name(deployment: str) -> str:
    # One agent per deployment: a run on the comparison model is a second agent
    # with the same instructions, not a new version of this one.
    return f"hindcast-investigator-{deployment}"


def load_definition(deployment: str, prompt_path: Path = PROMPT_PATH) -> dict:
    """The prompt agent definition as the service takes it. No temperature or top_p."""
    return {
        "kind": "prompt",
        "model": deployment,
        "instructions": prompt_path.read_text(encoding="utf-8"),
        "reasoning": {"effort": EFFORT},
        "tools": TOOL_DEFINITIONS,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "investigation",
                "schema": INVESTIGATION_SCHEMA,
                "strict": True,
            }
        },
    }


def definition_fingerprint(definition: dict) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_agent_version(agents: Any, name: str, definition: dict) -> str:
    """The latest version when it carries this definition's fingerprint, else a new one."""
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.core.exceptions import ResourceNotFoundError

    fingerprint = definition_fingerprint(definition)
    try:
        latest = next(iter(agents.list_versions(name, limit=1, order="desc")), None)
    except ResourceNotFoundError:
        latest = None
    if latest is not None and (latest.metadata or {}).get("fingerprint") == fingerprint:
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
    except RuntimeError:
        digest = hashlib.sha256((repo / path).read_bytes()).hexdigest()
        return {"sha256": digest, "dirty": True}

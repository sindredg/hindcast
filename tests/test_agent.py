import hashlib
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hindcast.agent import (
    EFFORT,
    agent_name,
    definition_fingerprint,
    ensure_agent_version,
    load_definition,
    prompt_provenance,
)
from hindcast.evaluation.prior import load_prompt
from hindcast.result import INVESTIGATION_SCHEMA
from hindcast.tools import TOOL_DEFINITIONS


def git(repo: Path, *args: str) -> None:
    config = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
    config += ["-c", "commit.gpgsign=false"]
    subprocess.run(["git", "-C", str(repo), *config, *args], check=True, capture_output=True)  # noqa: S603, S607


def test_definition_holds_deployment_effort_instructions_tools_and_schema() -> None:
    definition = load_definition("gpt-6-luna")
    assert definition["kind"] == "prompt"
    assert definition["model"] == "gpt-6-luna"
    assert definition["reasoning"] == {"effort": "medium"} == {"effort": EFFORT}
    assert definition["instructions"] == Path("prompts/investigator.md").read_text("utf-8")
    assert definition["tools"] is TOOL_DEFINITIONS
    text_format = definition["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"] is INVESTIGATION_SCHEMA
    # No sampling settings: the gpt-6 models reject top_p on the Responses API.
    assert "temperature" not in definition
    assert "top_p" not in definition


def test_agent_name_carries_the_deployment() -> None:
    assert agent_name("gpt-6-luna") == "hindcast-investigator-gpt-6-luna"


def test_fingerprint_changes_with_the_instructions_and_the_deployment(tmp_path: Path) -> None:
    prompt = tmp_path / "investigator.md"
    prompt.write_text("v1", encoding="utf-8")
    first = definition_fingerprint(load_definition("gpt-6-luna", prompt))
    assert definition_fingerprint(load_definition("gpt-6-luna", prompt)) == first
    assert definition_fingerprint(load_definition("gpt-6-sol", prompt)) != first
    prompt.write_text("v2", encoding="utf-8")
    assert definition_fingerprint(load_definition("gpt-6-luna", prompt)) != first


def test_prompt_provenance_marks_an_uncommitted_change(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "prompt.md").write_text("v1", encoding="utf-8")
    git(tmp_path, "add", "prompt.md")
    git(tmp_path, "commit", "-q", "-m", "v1")
    assert prompt_provenance(Path("prompt.md"), repo=tmp_path) == {
        "blob": "28c218c44b49222f91536daf5b4d9871638edc8e",
        "dirty": False,
    }
    (tmp_path / "prompt.md").write_text("v2", encoding="utf-8")
    assert prompt_provenance(Path("prompt.md"), repo=tmp_path) == {
        "sha256": hashlib.sha256(b"v2").hexdigest(),
        "dirty": True,
    }


class FakeAgents:
    def __init__(self, versions: list[Any] | Exception) -> None:
        self.versions = versions
        self.created: list[tuple[str, Any, dict]] = []

    def list_versions(self, name: str, *, limit: int, order: str) -> list[Any]:
        assert (limit, order) == (1, "desc")
        if isinstance(self.versions, Exception):
            raise self.versions
        return self.versions

    def create_version(self, name: str, *, definition: Any, metadata: dict) -> Any:
        self.created.append((name, definition, metadata))
        return SimpleNamespace(version=str(len(self.created) + 6))


DEFINITION = load_definition("gpt-6-luna")
FINGERPRINT = definition_fingerprint(DEFINITION)


@pytest.mark.parametrize("versions", [[], ResourceNotFoundError("no agent")])
def test_ensure_creates_a_version_when_none_exists(versions: Any) -> None:
    agents = FakeAgents(versions)
    assert ensure_agent_version(agents, "a", DEFINITION) == "7"
    [(name, definition, metadata)] = agents.created
    assert name == "a"
    assert dict(definition) == DEFINITION
    assert metadata == {"fingerprint": FINGERPRINT}


def test_ensure_reuses_the_latest_version_when_the_fingerprint_matches() -> None:
    agents = FakeAgents([SimpleNamespace(version="3", metadata={"fingerprint": FINGERPRINT})])
    assert ensure_agent_version(agents, "a", DEFINITION) == "3"
    assert agents.created == []


@pytest.mark.parametrize("metadata", [{"fingerprint": "old"}, {}, None])
def test_ensure_creates_a_new_version_when_the_fingerprint_differs(metadata: Any) -> None:
    agents = FakeAgents([SimpleNamespace(version="3", metadata=metadata)])
    assert ensure_agent_version(agents, "a", DEFINITION) == "7"
    assert len(agents.created) == 1


def test_no_prior_knowledge_key_fact_in_the_instructions() -> None:
    instructions = Path("prompts/investigator.md").read_text("utf-8")
    facts = [fact for facts in load_prompt().key_facts.values() for fact in facts]
    assert facts
    for fact in facts:
        assert not re.search(rf"\b{re.escape(fact)}\b", instructions, re.IGNORECASE), fact

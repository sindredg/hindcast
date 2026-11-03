"""The arms the evaluation compares on each showcase case (decision 0023).

hindcast and comparison are the investigator as the sealed cases ran it, on
the chat and the comparison deployment. single-search is decision 0006's
baseline: one search and one model call over the same evidence
(hindcast.single). library-off drops the search tool and the prompt's
library parts. abstention adds one rule to the prompt and is decision 0006's
controlled comparison: it differs from hindcast by the prompt alone.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hindcast.agent import PROMPT_PATH, load_definition
from hindcast.tools import TOOL_DEFINITIONS


@dataclass(frozen=True)
class Arm:
    name: str
    # Which configured deployment runs it: the chat or the comparison one.
    deployment: Literal["chat", "compare"]
    prompt: Path
    library: bool
    kind: Literal["agent", "single"]


ARMS: dict[str, Arm] = {
    arm.name: arm
    for arm in (
        Arm("hindcast", "chat", PROMPT_PATH, True, "agent"),
        Arm("comparison", "compare", PROMPT_PATH, True, "agent"),
        Arm("single-search", "chat", Path("prompts/single-search.md"), True, "single"),
        Arm("library-off", "chat", Path("prompts/investigator-library-off.md"), False, "agent"),
        Arm("abstention", "chat", Path("prompts/investigator-abstention.md"), True, "agent"),
    )
}


def agent_variant(arm: Arm) -> str | None:
    """The agent name's suffix; None for the investigator as sealed."""
    return None if arm.prompt == PROMPT_PATH and arm.library else arm.name


def arm_definition(arm: Arm, deployment: str) -> dict:
    """The prompt agent definition an agent arm runs."""
    tools = (
        TOOL_DEFINITIONS
        if arm.library
        else [d for d in TOOL_DEFINITIONS if d["name"] != "search_library"]
    )
    return load_definition(deployment, arm.prompt, tools=tools)

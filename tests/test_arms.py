import difflib
import re
from pathlib import Path

import pytest

from hindcast.agent import (
    PROMPT_PATH,
    agent_name,
    definition_fingerprint,
    load_definition,
)
from hindcast.arms import ARMS, Arm, agent_variant, arm_definition
from hindcast.evaluation.prior import load_prompt
from hindcast.investigate import prepare
from test_investigate import CASES, FakeClient, stub_command


def test_arms_are_the_five_decided() -> None:
    # Decision 0023's arms, nothing more.
    assert {
        "hindcast": Arm("hindcast", "chat", PROMPT_PATH, True, "agent"),
        "comparison": Arm("comparison", "compare", PROMPT_PATH, True, "agent"),
        "single-search": Arm(
            "single-search", "chat", Path("prompts/single-search.md"), True, "single"
        ),
        "library-off": Arm(
            "library-off", "chat", Path("prompts/investigator-library-off.md"), False, "agent"
        ),
        "abstention": Arm(
            "abstention", "chat", Path("prompts/investigator-abstention.md"), True, "agent"
        ),
    } == ARMS


def test_hindcast_and_comparison_keep_the_sealed_agents() -> None:
    # They must resolve to the agents the second seal series ran on.
    assert agent_variant(ARMS["hindcast"]) is None
    assert agent_variant(ARMS["comparison"]) is None
    assert agent_name("gpt-6-luna", agent_variant(ARMS["hindcast"])) == (
        "hindcast-investigator-gpt-6-luna"
    )
    assert agent_name("gpt-6-luna", agent_variant(ARMS["abstention"])) == (
        "hindcast-investigator-gpt-6-luna-abstention"
    )


def test_hindcast_arm_definition_equals_current() -> None:
    for deployment in ("gpt-6-luna", "gpt-6.1-sol"):
        assert definition_fingerprint(
            arm_definition(ARMS["hindcast"], deployment)
        ) == definition_fingerprint(load_definition(deployment))


def test_library_off_definition_has_no_search_tool() -> None:
    definition = arm_definition(ARMS["library-off"], "gpt-6-luna")
    assert [t["name"] for t in definition["tools"]] == ["list_updates", "list_charts"]
    assert definition["instructions"] == ARMS["library-off"].prompt.read_text("utf-8")


def _body(path: Path) -> list[str]:
    # Each prompt starts with its own version comment; the rest is compared.
    lines = path.read_text("utf-8").splitlines()
    assert lines[0].startswith("<!-- ") and lines[0].endswith(" -->")
    return lines[1:]


def test_abstention_prompt_differs_from_v3_by_one_rule() -> None:
    diff = [
        line
        for line in difflib.ndiff(_body(PROMPT_PATH), _body(ARMS["abstention"].prompt))
        if line.startswith(("+ ", "- "))
    ]
    assert len(diff) == 1
    assert diff[0].startswith("+ - When the evidence does not determine the root cause")


def test_library_off_prompt_never_mentions_search_library() -> None:
    # The version comment names the arm; the instructions never mention it.
    text = "\n".join(_body(ARMS["library-off"].prompt))
    assert "search_library" not in text
    assert "library" not in text.lower()


def test_library_off_prompt_only_drops_lines_from_v3() -> None:
    changed = [
        line
        for line in difflib.ndiff(_body(PROMPT_PATH), _body(ARMS["library-off"].prompt))
        if line.startswith("+ ")
    ]
    # Two tools instead of three, and the call instruction without the search.
    assert changed == [
        "+ Two tools return everything you may use:",
        "+ Call `list_updates` and `list_charts` before you answer. Work only from what they "
        "return. Do not use anything you may know about this outage from elsewhere: a claim "
        "the evidence does not support counts against the reconstruction even when it is true.",
    ]


def test_no_prior_knowledge_key_fact_in_any_arm_prompt() -> None:
    facts = [fact for facts in load_prompt().key_facts.values() for fact in facts]
    assert facts
    for arm in ARMS.values():
        text = arm.prompt.read_text("utf-8")
        for fact in facts:
            assert not re.search(rf"\b{re.escape(fact)}\b", text, re.IGNORECASE), (arm.name, fact)


def test_prepare_library_off_binds_no_search(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created = stub_command(monkeypatch, tmp_path, FakeClient())
    setup = prepare(CASES["dev"], arm=ARMS["library-off"])
    assert setup.tools.search is None
    assert setup.embedder is None
    [(name, kw)] = created
    assert name == "hindcast-investigator-gpt-6-luna-library-off"
    assert [t["name"] for t in kw["definition"]["tools"]] == ["list_updates", "list_charts"]
    assert setup.provenance["arm"] == "library-off"
    assert setup.provenance["library"] is None
    assert setup.agent == {"name": name, "version": "3"}


def test_prepare_hindcast_arm_records_its_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created = stub_command(monkeypatch, tmp_path, FakeClient())
    setup = prepare(CASES["dev"])
    assert [name for name, _ in created] == ["hindcast-investigator-gpt-6-luna"]
    assert setup.provenance["arm"] == "hindcast"
    assert setup.tools.search is not None


def test_prepare_comparison_arm_runs_on_the_compare_deployment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created = stub_command(monkeypatch, tmp_path, FakeClient())
    monkeypatch.setenv("HINDCAST_COMPARE_DEPLOYMENT", "gpt-6.1-sol")
    setup = prepare(CASES["dev"], arm=ARMS["comparison"])
    assert [name for name, _ in created] == ["hindcast-investigator-gpt-6-1-sol"]
    assert setup.model["deployment"] == "gpt-6.1-sol"


def test_prepare_single_search_makes_no_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created = stub_command(monkeypatch, tmp_path, FakeClient())
    setup = prepare(CASES["dev"], arm=ARMS["single-search"])
    assert created == []
    assert setup.agent == {"name": None, "version": None}
    assert setup.provenance["arm"] == "single-search"
    assert setup.provenance["prompt"]["dirty"] in (True, False)

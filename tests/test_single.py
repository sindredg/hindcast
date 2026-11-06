import json
from dataclasses import replace
from typing import Any

from hindcast.agent import EFFORT
from hindcast.arms import ARMS
from hindcast.cases import Case
from hindcast.investigate import NO_CHECKS, Setup
from hindcast.result import INVESTIGATION_SCHEMA
from hindcast.safety import PiiError, PiiHit
from hindcast.single import direct_turn, run_single, search_query
from test_investigate import (
    EVIDENCE,
    FINAL,
    SOURCE,
    Clock,
    FakeClient,
    RateLimitError,
    Tools,
    final,
    hit,
)
from test_redact import StubPii

CASE = Case("dev", "Slow pages", "Cloudflare", "development", "2026-02-20T18:45:16Z", (SOURCE,))
PROMPT = ARMS["single-search"].prompt.read_text("utf-8")


class Search:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def __call__(self, query: str, timeout: float) -> list:
        self.queries.append(query)
        return [hit("lib/a/s1")]


def setup(client: FakeClient, search: Search) -> Setup:
    return Setup(
        turn=direct_turn(client, "gpt-6-luna", PROMPT),
        tools=Tools(search=search),
        pii=None,  # type: ignore[arg-type]
        agent={"name": None, "version": None},
        model={"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"},
        provenance={},
        prices=None,  # type: ignore[arg-type]
    )


def test_single_search_one_query_one_model_call() -> None:
    client, search = FakeClient(final()), Search()
    result = run_single(setup(client, search), CASE, clock=Clock())

    assert result.status == "complete"
    assert search.queries == ["Slow pages. Looking into it."]
    [sent] = client.calls
    assert sent["model"] == "gpt-6-luna"
    assert sent["instructions"] == PROMPT
    assert sent["reasoning"] == {"effort": EFFORT}
    assert sent["text"]["format"] == {
        "type": "json_schema",
        "name": "investigation",
        "schema": INVESTIGATION_SCHEMA,
        "strict": True,
    }
    assert "tools" not in sent
    # The model reads the three tool outputs, screened like the agent's.
    [message] = sent["input"]
    inputs = json.loads(message["content"])
    assert list(inputs) == ["list_updates", "list_charts", "search_library"]
    assert [h["ref"] for h in inputs["search_library"]["hits"]] == ["lib/a/s1"]
    assert [c["name"] for c in result.tool_calls] == [
        "list_updates",
        "list_charts",
        "search_library",
    ]
    assert result.tool_calls[2]["query"] == "Slow pages. Looking into it."
    assert (result.usage.model_calls, result.usage.tool_calls) == (1, 3)


def test_single_search_rejects_bad_citation_like_the_agent() -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["citations"].append({"source": "case", "ref": "dev/u99"})
    document["root_cause"]["citations"] = [{"source": "library", "ref": "lib/zz/s9"}]
    client = FakeClient(final(document))
    result = run_single(setup(client, Search()), CASE, clock=Clock())
    assert [(r.where, r.ref, r.reason) for r in result.checks.rejected_citations] == [
        ("findings[0]", "dev/u99", "unknown"),
        ("root_cause", "lib/zz/s9", "not-retrieved"),
    ]


def test_single_search_model_error_is_recorded() -> None:
    client = FakeClient(RateLimitError("429 SECRET"))
    result = run_single(setup(client, Search()), CASE, clock=Clock())
    assert (result.status, result.incomplete_reason) == (
        "incomplete",
        "model-error: RateLimitError",
    )
    assert result.usage.tool_calls == 3


def test_search_query_uses_only_shown_text() -> None:
    updates: dict[str, Any] = {
        "title": {"withheld": "w"},
        "updates": [{"update_id": "dev/u1", "withheld": "w"}, {"update_id": "dev/u2", "text": "B"}],
    }
    assert search_query(updates) == "B"
    assert search_query({"title": "T", "updates": []}) == "T"
    assert EVIDENCE.title == "Slow pages"


class QueryFailsPii(StubPii):
    """Checks the answer, then fails on the search query the run sent first."""

    def __call__(self, texts: list[str], *, timeout: float) -> list[tuple[PiiHit, ...]]:
        if "Slow pages. Looking into it." in texts:
            raise PiiError("HTTP 500 q")
        return super().__call__(texts, timeout=timeout)


def test_single_search_pii_error_keeps_no_checks_like_the_agent() -> None:
    # The model call's checks would list a rejected citation; a pii-error run
    # keeps none, as the agent arms' pii-error does (#64).
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["citations"].append({"source": "case", "ref": "dev/u99"})
    run_setup = replace(setup(FakeClient(final(document)), Search()), pii=QueryFailsPii())
    result = run_single(run_setup, CASE, clock=Clock())
    assert (result.status, result.incomplete_reason) == ("incomplete", "pii-error: HTTP 500 q")
    assert result.investigation is None
    assert result.checks == NO_CHECKS

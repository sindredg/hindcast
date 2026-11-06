import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from hindcast import investigate
from hindcast.challenge import (
    CHALLENGE_TIME_CAP,
    CHALLENGE_TOOL_CAP,
    MAX_QUESTION,
    challenge_start,
    main,
    run_challenge,
    write_challenge,
)
from hindcast.evidence import evidence_json
from hindcast.investigate import ScoredCaseLocked, write_result
from hindcast.result import CHALLENGE_SCHEMA, ResultError, load_result, parse_challenge
from test_investigate import (
    AGENT,
    CASES,
    EVIDENCE,
    FINAL,
    MODEL,
    NOW,
    PROVENANCE,
    Clock,
    FakeClient,
    ScriptedTurn,
    Tools,
    call,
    hit,
    response,
    run,
    search_call,
    stub_command,
)
from test_redact import StubPii
from test_tools import StubShield

QUESTION = "Could the slowness have come from a cache purge instead?"


# The provenance of a result made from the test evidence file.
MATCHING = PROVENANCE | {"evidence_sha256": hashlib.sha256(evidence_json(EVIDENCE)).hexdigest()}


def stored(tmp_path: Path, document: dict | None = None, provenance: dict = MATCHING) -> Path:
    """A committed-style result file: one update read, one library search."""
    result = run(
        ScriptedTurn(
            response(call(), search_call("cache", "c2")),
            response(text=json.dumps(document or FINAL)),
        ),
        Tools(search=lambda q, timeout: [hit("lib/a/s1")]),
    )
    return write_result(
        result,
        case_id="dev",
        agent=AGENT,
        model=MODEL,
        provenance=provenance,
        out_dir=tmp_path / "results",
        now=NOW,
    )


def answer(verdict: str = "stands", citations: Any = None, revised_claim: str = "") -> Any:
    body = {
        "verdict": verdict,
        "answer": "The updates name slowness before any purge.",
        "citations": citations if citations is not None else [{"source": "case", "ref": "dev/u1"}],
        "revised_claim": revised_claim,
    }
    return response(text=json.dumps(body))


class Setup:
    """A ChallengeSetup with stub tools and a scripted challenger."""

    def __init__(self, *script: object, shield: StubShield | None = None, pii: Any = None) -> None:
        self.turn = ScriptedTurn(*script)
        self.shield = shield or StubShield()
        self.tools = Tools(search=lambda q, timeout: [hit("lib/b/s2")], shield=self.shield)
        self.pii = pii or StubPii()


def challenge_run(setup: Setup, path: Path, finding: str = "f1", question: str = QUESTION) -> Any:
    return run_challenge(
        setup.turn, setup.tools, load_result(path), finding, question, pii=setup.pii, clock=Clock()
    )


def test_schema_is_strict_and_asks_for_a_verdict() -> None:
    assert CHALLENGE_SCHEMA["additionalProperties"] is False
    assert set(CHALLENGE_SCHEMA["required"]) == {"verdict", "answer", "citations", "revised_claim"}
    assert CHALLENGE_SCHEMA["properties"]["verdict"]["enum"] == ["stands", "revised", "withdrawn"]


@pytest.mark.parametrize(
    ("verdict", "revised_claim"), [("stands", "New claim."), ("withdrawn", "x"), ("revised", "")]
)
def test_revised_needs_revised_claim(verdict: str, revised_claim: str) -> None:
    body = {"verdict": verdict, "answer": "a", "citations": [], "revised_claim": revised_claim}
    with pytest.raises(ResultError, match="revised_claim"):
        parse_challenge(json.dumps(body))


def test_start_carries_the_finding_what_it_rests_on_and_the_question(tmp_path: Path) -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"].append(
        {"id": "f2", "kind": "inference", "claim": "Second.", "rests_on": ["f1"], "citations": []}
    )
    [message] = challenge_start(load_result(stored(tmp_path, document)), "f2", QUESTION)
    content = json.loads(message["content"])
    assert content["finding"]["id"] == "f2"
    assert [f["id"] for f in content["rests_on"]] == ["f1"]
    assert content["question"] == QUESTION


def test_unknown_finding_is_refused_before_any_call(tmp_path: Path) -> None:
    setup = Setup(answer())
    with pytest.raises(ValueError, match="f9"):
        challenge_run(setup, stored(tmp_path), "f9")
    assert setup.turn.inputs == [] and setup.shield.sent == []


def test_incomplete_result_is_refused(tmp_path: Path) -> None:
    result = run(ScriptedTurn(response(text="")))
    path = write_result(
        result,
        case_id="dev",
        agent=AGENT,
        model=MODEL,
        provenance=PROVENANCE,
        out_dir=tmp_path,
        now=NOW,
    )
    with pytest.raises(ValueError, match="incomplete"):
        challenge_run(Setup(answer()), path)


@pytest.mark.parametrize("question", ["", "   ", "x" * (MAX_QUESTION + 1)])
def test_empty_or_long_question_is_refused(tmp_path: Path, question: str) -> None:
    with pytest.raises(ValueError):
        challenge_run(Setup(answer()), stored(tmp_path), question=question)


def test_flagged_question_makes_no_model_call(tmp_path: Path) -> None:
    setup = Setup(answer(), shield=StubShield("cache purge"))
    result = challenge_run(setup, stored(tmp_path))
    assert result.status == "refused"
    assert result.reason == "prompt-shields"
    assert setup.turn.inputs == []


def test_question_is_pii_masked_before_the_model_reads_it(tmp_path: Path) -> None:
    setup = Setup(response(call()), answer())
    result = challenge_run(setup, stored(tmp_path), question="Did Jane Doe purge the cache?")
    assert result.question == "Did [Person] purge the cache?"
    assert "Jane" not in json.dumps(setup.turn.inputs[0][0])
    assert [f.path for f in result.checks.pii] == ["question"]


def test_challenge_cites_original_run_refs_without_searching(tmp_path: Path) -> None:
    citations = [{"source": "case", "ref": "dev/u1"}, {"source": "library", "ref": "lib/a/s1"}]
    setup = Setup(response(call()), answer(citations=citations))
    result = challenge_run(setup, stored(tmp_path))
    assert result.status == "complete"
    assert [c.ref for c in result.challenge.citations] == ["dev/u1", "lib/a/s1"]
    assert result.checks.rejected_citations == ()


def test_challenge_unknown_ref_is_rejected(tmp_path: Path) -> None:
    citations = [
        {"source": "case", "ref": "dev/u1"},
        {"source": "case", "ref": "dev/u99"},
        {"source": "library", "ref": "lib/z/s9"},
    ]
    setup = Setup(response(call()), answer(citations=citations))
    result = challenge_run(setup, stored(tmp_path))
    assert [(r.ref, r.reason) for r in result.checks.rejected_citations] == [
        ("dev/u99", "unknown"),
        ("lib/z/s9", "not-retrieved"),
    ]
    assert [c.ref for c in result.challenge.citations] == ["dev/u1"]


def test_challenge_case_citation_needs_its_own_reading(tmp_path: Path) -> None:
    # The original run read dev/u1; the challenge did not call list_updates.
    result = challenge_run(Setup(answer()), stored(tmp_path))
    assert [(r.ref, r.reason) for r in result.checks.rejected_citations] == [
        ("dev/u1", "not-shown")
    ]
    assert result.checks.unsupported == ("challenge",)


def test_challenge_answer_is_pii_masked(tmp_path: Path) -> None:
    body = {
        "verdict": "revised",
        "answer": "Jane Doe said so.",
        "citations": [{"source": "case", "ref": "dev/u1"}],
        "revised_claim": "Jane Doe purged it.",
    }
    setup = Setup(response(call()), response(text=json.dumps(body)))
    result = challenge_run(setup, stored(tmp_path))
    assert result.challenge.answer == "[Person] said so."
    assert result.challenge.revised_claim == "[Person] purged it."
    assert [f.path for f in result.checks.pii] == ["answer", "revised_claim"]


def test_challenge_caps_apply(tmp_path: Path) -> None:
    calls = [call(call_id=f"c{i}") for i in range(CHALLENGE_TOOL_CAP + 1)]
    result = challenge_run(Setup(response(*calls), answer()), stored(tmp_path))
    assert result.status == "incomplete"
    assert result.reason == "tool-cap"


def test_challenge_runs_under_its_own_time_cap(tmp_path: Path) -> None:
    setup = Setup(response(call()), answer())
    challenge_run(setup, stored(tmp_path))
    assert setup.turn.inputs[0][2] == CHALLENGE_TIME_CAP


def test_write_challenge_stores_masked_question_and_links_the_result(tmp_path: Path) -> None:
    path = stored(tmp_path)
    setup = Setup(response(call()), answer())
    result = challenge_run(setup, path, question="Did Jane Doe purge it?")
    written = write_challenge(
        result,
        result_path=path,
        finding_id="f1",
        agent={"name": "hindcast-challenger-gpt-6-luna", "version": "1"},
        model=MODEL,
        provenance=PROVENANCE,
        cost=None,
        now=NOW,
    )
    assert written == path.parent / "challenges" / "20261030T120001Z-f1.json"
    text = written.read_text("utf-8")
    assert "Jane" not in text
    document = json.loads(text)
    assert document["result_file"] == path.name
    assert document["question"] == "Did [Person] purge it?"
    assert document["challenge"]["verdict"] == "stands"
    assert document["checks"]["pii"] == [
        {"path": "question", "category": "Person", "confidence": 0.97}
    ]
    with pytest.raises(FileExistsError):
        write_challenge(
            result,
            result_path=path,
            finding_id="f1",
            agent={},
            model=MODEL,
            provenance=PROVENANCE,
            cost=None,
            now=NOW,
        )


def test_main_prints_counts_never_the_answer(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = stored(tmp_path)
    secret = {
        "verdict": "stands",
        "answer": "A SECRET ANSWER",
        "citations": [{"source": "case", "ref": "dev/u1"}],
        "revised_claim": "",
    }
    client = FakeClient(response(call()), response(text=json.dumps(secret)))
    created = stub_command(monkeypatch, tmp_path, client)

    assert main([str(path), "f1", QUESTION]) == 0

    out = capsys.readouterr().out
    assert "SECRET" not in out and QUESTION not in out
    assert out.startswith("complete: stands\n")
    [(name, kwargs)] = created
    assert name == "hindcast-challenger-gpt-6-luna"
    assert kwargs["definition"]["text"]["format"]["name"] == "challenge"
    [written] = (path.parent / "challenges").glob("*-f1.json")
    document = json.loads(written.read_text("utf-8"))
    assert document["cost"]["table_version"] == 1
    assert document["agent"] == {"name": "hindcast-challenger-gpt-6-luna", "version": "3"}


def test_challenge_runs_only_against_the_evidence_it_was_made_from(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A changed evidence file would let citations resolve against other text.
    path = stored(tmp_path, provenance=PROVENANCE)
    created = stub_command(monkeypatch, tmp_path, FakeClient(answer()))
    with pytest.raises(ValueError, match="evidence"):
        main([str(path), "f1", QUESTION])
    assert created == []


@pytest.mark.parametrize(
    ("role", "error", "match"),
    [
        ("sealed", ScoredCaseLocked, "sealed case"),
        # stub_command points the rubric lock at a file that does not exist.
        ("showcase", ScoredCaseLocked, "once the rubric is frozen"),
        (None, ValueError, "unknown case"),
    ],
)
def test_a_challenge_refuses_a_case_the_command_may_not_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    role: str | None,
    error: type[Exception],
    match: str,
) -> None:
    # The same case rules as the investigation, before any cloud call (#89).
    path = stored(tmp_path)
    client = FakeClient(answer())
    created = stub_command(monkeypatch, tmp_path, client)
    cases = {} if role is None else {"dev": replace(CASES["dev"], role=role)}
    monkeypatch.setattr(investigate, "load_cases", lambda: cases)
    with pytest.raises(error, match=match):
        main([str(path), "f1", QUESTION])
    assert created == []
    assert client.calls == []


def test_a_challenge_is_one_trace(tmp_path: Path) -> None:
    # The question's screen ran in a trace of its own on 2026-11-03.
    from test_investigate import recording_span

    span, exporter = recording_span()
    setup = Setup(response(call()), answer())
    run_challenge(
        setup.turn,
        setup.tools,
        load_result(stored(tmp_path)),
        "f1",
        QUESTION,
        pii=setup.pii,
        clock=Clock(),
        span=span,
    )
    spans = exporter.get_finished_spans()
    assert {"challenge", "screen", "model_call", "tool_call", "pii"} <= {s.name for s in spans}
    assert len({s.context.trace_id for s in spans}) == 1
    [root] = [s for s in spans if s.parent is None]
    assert root.name == "challenge" and root.attributes["status"] == "complete"


def test_an_unscreened_result_is_refused(tmp_path: Path) -> None:
    # Review finding: the slice 1 and 2 files ran without Prompt Shields.
    path = stored(tmp_path)
    raw = json.loads(path.read_text("utf-8"))
    del raw["usage"]["screen_calls"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    setup = Setup(answer())
    with pytest.raises(ValueError, match="screen"):
        challenge_run(setup, path)
    assert setup.turn.inputs == []


def test_a_question_screen_error_ends_the_challenge(tmp_path: Path) -> None:
    from hindcast.safety import ScreenError

    setup = Setup(answer(), shield=StubShield(error=ScreenError("HTTP 500 x")))
    setup.tools.shield = PromptError(ScreenError("HTTP 500 x"))
    result = challenge_run(setup, stored(tmp_path))
    assert (result.status, result.reason) == ("incomplete", "screen-error: HTTP 500 x")
    assert setup.turn.inputs == [] and result.question == ""


def test_a_question_pii_error_ends_the_challenge(tmp_path: Path) -> None:
    from hindcast.safety import PiiError

    setup = Setup(answer(), pii=StubPii(PiiError("HTTP 500 y")))
    result = challenge_run(setup, stored(tmp_path))
    assert (result.status, result.reason) == ("incomplete", "pii-error: HTTP 500 y")
    assert setup.turn.inputs == [] and result.question == ""


class PromptError(StubShield):
    """Screens documents cleanly; fails on the question."""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.prompt_error = error

    def prompt(self, text: str, *, timeout: float) -> bool:
        raise self.prompt_error


# Review finding: the finding ID is model output and names the challenge file.


@pytest.mark.parametrize("finding_id", ["../../outside", "f1/x", "..", ".", "a" * 65, ""])
def test_a_finding_id_that_is_not_file_safe_is_refused_before_any_call(
    tmp_path: Path, finding_id: str
) -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["id"] = finding_id
    setup = Setup(answer())
    with pytest.raises(ValueError, match="file-safe"):
        challenge_run(setup, stored(tmp_path, document), finding_id)
    assert setup.turn.inputs == [] and setup.shield.sent == []


def test_write_challenge_refuses_a_path_outside_the_challenges_folder(tmp_path: Path) -> None:
    path = stored(tmp_path)
    result = challenge_run(Setup(response(call()), answer()), path)
    for finding_id in ("../../outside", "f1/x"):
        with pytest.raises(ValueError, match="outside"):
            write_challenge(
                result,
                result_path=path,
                finding_id=finding_id,
                agent={},
                model=MODEL,
                provenance=PROVENANCE,
                cost=None,
                now=NOW,
            )
    assert sorted(p.name for p in tmp_path.rglob("*.json")) == [path.name]


def test_a_screens_off_result_is_refused(tmp_path: Path) -> None:
    # An injection run with --screens off has screen_calls 0 in its usage and
    # provenance screens False: its library refs were never screened.
    path = stored(tmp_path, provenance=MATCHING | {"screens": False})
    setup = Setup(answer())
    with pytest.raises(ValueError, match="without screens"):
        challenge_run(setup, path)
    assert setup.turn.inputs == []


def test_a_finding_id_shared_by_two_findings_is_refused(tmp_path: Path) -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"].append(dict(document["findings"][0]))
    setup = Setup(answer())
    with pytest.raises(ValueError, match="more than one finding"):
        challenge_run(setup, stored(tmp_path, document), "f1")
    assert setup.turn.inputs == []

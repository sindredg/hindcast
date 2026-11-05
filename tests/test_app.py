"""The page renders the committed development-case result."""

import json
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from hindcast import app
from hindcast.escape import plain

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "eval/investigations/cloudflare-2026-02-20/20261102T181721Z-v3.json"
# AppTest resolves a relative path against this file, so the page's path is absolute.
PAGE = ROOT / "src/hindcast/app.py"
SECTIONS = [
    "Attack assessment",
    "Root cause",
    "Timeline",
    "Findings",
    "Contributing factors",
    "Open questions",
    "Checks",
    "Usage",
]


def test_load_result_reads_the_committed_run():
    loaded = app.load_result(RESULT)
    raw = json.loads(RESULT.read_text(encoding="utf-8"))

    assert loaded.case_id == "cloudflare-2026-02-20"
    assert loaded.status == "complete"
    assert loaded.investigation is not None
    assert len(loaded.investigation.findings) == len(raw["investigation"]["findings"])
    assert len(loaded.investigation.timeline) == len(raw["investigation"]["timeline"])
    assert loaded.usage == raw["usage"]


def test_page_renders_the_sections(monkeypatch):
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    headers = [header.value for header in at.header]
    for name in SECTIONS:
        assert name in headers
    verdict = json.loads(RESULT.read_text(encoding="utf-8"))["investigation"]["attack"]["verdict"]
    assert any(verdict in block.value for block in at.markdown)


def test_render_incomplete_result(tmp_path, monkeypatch):
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    raw.update(status="incomplete", incomplete_reason="time-cap", investigation=None)
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert any(plain("time-cap") in warning.value for warning in at.warning)


def test_page_marks_a_library_citation(monkeypatch):
    # The slice 2 run kept a library citation; newer runs need not.
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert any("`library:lib/" in block.value for block in at.markdown)


CHALLENGE = {
    "finding_id": "F1",
    "question": "Was it the cache?",
    "status": "complete",
    "reason": None,
    "challenge": {
        "verdict": "revised",
        "answer": "The updates say the slowness began before any purge.",
        "citations": [{"source": "case", "ref": "cloudflare-2026-02-20/u1"}],
        "revised_claim": "A narrower claim.",
    },
    "checks": {"rejected_citations": [], "unsupported": [], "pii": []},
    "usage": {},
    "cost": None,
}


def copy_result(tmp_path, **changes):
    raw = json.loads(RESULT.read_text(encoding="utf-8")) | changes
    path = tmp_path / RESULT.name
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_page_shows_stored_challenges(tmp_path, monkeypatch):
    path = copy_result(tmp_path)
    (tmp_path / "challenges").mkdir()
    stored = CHALLENGE | {"result_file": path.name}
    (tmp_path / "challenges" / "20261103T120000Z-F1.json").write_text(json.dumps(stored))
    # A challenge of another result in the same folder stays off this page.
    other = stored | {"result_file": "other.json", "question": "OTHER QUESTION"}
    (tmp_path / "challenges" / "20261103T120001Z-F1.json").write_text(json.dumps(other))
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    text = " ".join(block.value for block in at.markdown)
    assert "Was it the cache?" in text
    assert plain("The updates say the slowness began before any purge.") in text
    assert "**revised**" in text and plain("A narrower claim.") in text
    assert "OTHER QUESTION" not in text


def test_no_challenge_box_without_live_flag(monkeypatch):
    monkeypatch.delenv(app.LIVE_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert len(at.text_area) == 0


def test_challenge_box_with_live_flag(tmp_path, monkeypatch):
    from hindcast import challenge
    from hindcast.challenge import ChallengeResult
    from hindcast.investigate import Usage
    from hindcast.result import Challenge, Checks, Citation

    # A screened result: the slice 2 file is copied with a screen count.
    usage = json.loads(RESULT.read_text(encoding="utf-8"))["usage"] | {"screen_calls": 5}
    path = copy_result(tmp_path, usage=usage)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    asked: list[tuple] = []

    def fake(result_path, finding_id, question):
        asked.append((result_path, finding_id, question))
        answer = Challenge("stands", "LIVE ANSWER", (Citation("case", "x/u1"),), "")
        result = ChallengeResult(
            "complete", None, question, answer, Checks(), Usage(1, 1, 1.0, 1, 0, 1)
        )
        return result, tmp_path / "challenges" / "c.json", {"currency": "USD", "total": 0.01}

    monkeypatch.setattr(challenge, "challenge_and_store", fake)

    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    at.text_area(key="question-F1").input("Was it the cache?")
    at.button(key="challenge-F1").click().run()

    assert not at.exception
    assert asked == [(path, "F1", "Was it the cache?")]
    assert any("LIVE ANSWER" in block.value for block in at.markdown)


def test_page_shows_cost_and_pii(tmp_path, monkeypatch):
    checks = {
        "rejected_citations": [],
        "unsupported": [],
        "pii": [{"path": "findings[0].claim", "category": "Person", "confidence": 0.9}],
    }
    cost = {"table_version": 1, "currency": "USD", "model": 0.01, "total": 0.012}
    tool_calls = [{"name": "list_updates", "seconds": 0.1, "withheld": ["x/u2"], "screen_calls": 1}]
    path = copy_result(tmp_path, checks=checks, cost=cost, tool_calls=tool_calls)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    text = " ".join(block.value for block in at.markdown)
    assert "PII hits: 1" in text and "`findings[0].claim` (Person)" in text
    assert "Withheld items: 1" in text and "`x/u2`" in text
    assert "USD 0.012" in text


def test_page_lists_the_results_and_defaults_to_the_newest_luna_run(monkeypatch):
    monkeypatch.delenv(app.RESULT_FILE_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    [select] = at.selectbox
    assert set(select.options) == {p.name for p in RESULT.parent.glob("*.json")}
    assert select.value == app.default_result(RESULT.parent)


def test_default_result_is_the_newest_luna_run(tmp_path):
    for name, deployment in [
        ("20261101T000000Z-v3.json", "gpt-6-luna"),
        ("20261102T000000Z-v4.json", "gpt-6-luna"),
        ("20261103T000000Z-v2.json", "gpt-6.1-sol"),
    ]:
        (tmp_path / name).write_text(json.dumps({"model": {"deployment": deployment}}))

    assert app.default_result(tmp_path).name == "20261102T000000Z-v4.json"


def test_no_challenge_box_for_an_unscreened_result(monkeypatch):
    # The slice 2 run ran without Prompt Shields; its refs were never screened.
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert len(at.text_area) == 0


# The live page (decision 0028).


class _Runs:
    """Records uploads to the runs container."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def upload_blob(self, name: str, data: bytes, overwrite: bool = False) -> None:
        assert not overwrite
        self.blobs[name] = data

    def download_blob(self, name: str):
        raise AssertionError(f"the page read {name} from the runs container")


def _setup():
    from types import SimpleNamespace

    return SimpleNamespace(
        turn=None,
        tools=None,
        pii=None,
        agent={"name": "hindcast-investigator-gpt-6-luna", "version": "9"},
        model={"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"},
        provenance={"screens": True},
        cost=lambda usage: {"currency": "USD", "total": 0.01},
    )


def _incomplete():
    from hindcast.investigate import RunResult, Usage
    from hindcast.result import Checks

    return RunResult("incomplete", "time-cap", None, Checks(), Usage(1, 0, 120.0, 1, 0, 0))


def test_live_cases_are_development_and_injection_only():
    from hindcast.cases import load_cases

    cases = load_cases()
    live = app.live_cases(cases)
    assert "cloudflare-2026-02-20" in live
    assert "cloudflare-2026-02-20-inject-update" in live
    assert {cases[c].role for c in live} == {"development", "injection"}
    assert live == sorted(live)


def test_start_run_stores_the_result(tmp_path, monkeypatch):
    from hindcast import investigate
    from hindcast.cases import load_cases

    monkeypatch.setattr(investigate, "prepare", lambda case: _setup())
    monkeypatch.setattr(investigate, "run_investigation", lambda *a, **k: _incomplete())
    runs = _Runs()
    case = load_cases()["cloudflare-2026-02-20"]

    path = app.start_run(case, root=tmp_path, client=runs)

    assert path.parent == tmp_path / "build/investigations/cloudflare-2026-02-20"
    assert list(runs.blobs) == [path.relative_to(tmp_path).as_posix()]
    assert json.loads(runs.blobs[list(runs.blobs)[0]])["incomplete_reason"] == "time-cap"


def test_second_run_is_refused_while_one_runs(tmp_path, monkeypatch):
    from hindcast import investigate
    from hindcast.cases import load_cases

    prepared: list[str] = []
    monkeypatch.setattr(investigate, "prepare", lambda case: prepared.append(case.case_id))
    case = load_cases()["cloudflare-2026-02-20"]
    assert app.RUN_LOCK.acquire(blocking=False)
    try:
        with __import__("pytest").raises(app.RunInProgress):
            app.start_run(case, root=tmp_path, client=None)
    finally:
        app.RUN_LOCK.release()
    assert prepared == []


def test_start_run_refuses_a_scored_or_sealed_case(tmp_path, monkeypatch):
    import pytest

    from hindcast import investigate
    from hindcast.cases import load_cases

    prepared: list[str] = []
    monkeypatch.setattr(investigate, "prepare", lambda case: prepared.append(case.case_id))
    cases = load_cases()
    for case_id in ("cloudflare-2025-11-18", "github-2026-10-21"):
        with pytest.raises(PermissionError):
            app.start_run(cases[case_id], root=tmp_path, client=None)
    assert prepared == []
    # The lock is released after a refusal.
    assert app.RUN_LOCK.acquire(blocking=False)
    app.RUN_LOCK.release()


def test_page_shows_no_investigate_without_live_flag(monkeypatch):
    monkeypatch.delenv(app.LIVE_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert not [b for b in at.button if b.key == "investigate"]


def test_page_offers_investigate_with_live_flag(monkeypatch):
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.delenv(app.BLOB_RUNTIME_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert [b for b in at.button if b.key == "investigate"]


def test_page_shows_the_materialize_error(tmp_path, monkeypatch):
    import streamlit as st

    from hindcast import runtime, storage

    def broken(client, root):
        raise runtime.RuntimeMismatch("build/evidence/x.json: does not match the manifest")

    st.cache_resource.clear()
    monkeypatch.setattr(runtime, "materialize", broken)
    monkeypatch.setattr(storage, "container", lambda name: _Runs())
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.setenv(app.BLOB_RUNTIME_VAR, "1")
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(tmp_path))
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    st.cache_resource.clear()

    assert not at.exception
    assert any("does not match the manifest" in e.value for e in at.error)
    assert not [b for b in at.button if b.key == "investigate"]
    # No challenge box either: a challenge needs the runtime files too.
    assert len(at.text_area) == 0


def test_page_stores_a_challenge_of_a_committed_result_in_blob(tmp_path, monkeypatch):
    import streamlit as st

    from hindcast import challenge, runtime, storage
    from hindcast.challenge import ChallengeResult
    from hindcast.investigate import Usage
    from hindcast.result import Challenge, Checks, Citation

    folder = tmp_path / "eval/investigations/cloudflare-2026-02-20"
    folder.mkdir(parents=True)
    usage = json.loads(RESULT.read_text(encoding="utf-8"))["usage"] | {"screen_calls": 5}
    path = copy_result(folder, usage=usage)
    runs = _Runs()

    def fake(result_path, finding_id, question):
        written = result_path.parent / "challenges" / "20261105T120000Z-F1.json"
        written.parent.mkdir(exist_ok=True)
        written.write_text("{}")
        answer = Challenge("stands", "LIVE ANSWER", (Citation("case", "x/u1"),), "")
        result = ChallengeResult(
            "complete", None, question, answer, Checks(), Usage(1, 1, 1.0, 1, 0, 1)
        )
        return result, written, {"currency": "USD", "total": 0.01}

    st.cache_resource.clear()
    monkeypatch.setattr(runtime, "materialize", lambda client, root: 0)
    monkeypatch.setattr(runtime, "fetch_runs", lambda client, root: [])
    monkeypatch.setattr(storage, "container", lambda name: runs)
    monkeypatch.setattr(challenge, "challenge_and_store", fake)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.setenv(app.BLOB_RUNTIME_VAR, "1")
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(tmp_path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.text_area(key="question-F1").input("Was it the cache?")
    at.button(key="challenge-F1").click().run()
    st.cache_resource.clear()

    assert not at.exception
    assert list(runs.blobs) == [
        "eval/investigations/cloudflare-2026-02-20/challenges/20261105T120000Z-F1.json"
    ]


def test_the_page_shares_the_run_lock_across_sessions(monkeypatch):
    # Streamlit runs the page as a fresh __main__ module on every run, so a
    # lock defined in the page itself would be a new lock each time.
    from hindcast import investigate

    prepared: list[str] = []
    monkeypatch.setattr(investigate, "prepare", lambda case: prepared.append(case.case_id))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.delenv(app.BLOB_RUNTIME_VAR, raising=False)
    assert app.RUN_LOCK.acquire(blocking=False)
    try:
        at = AppTest.from_file(PAGE, default_timeout=60).run()
        next(b for b in at.button if b.key == "investigate").click().run()
    finally:
        app.RUN_LOCK.release()
    assert prepared == []
    assert any("already running" in w.value for w in at.warning)


def _live_page_with_blob(tmp_path, monkeypatch):
    """The page as deployed: live, Blob runtime, with the download stubbed out."""
    import streamlit as st

    from hindcast import runtime, storage

    st.cache_resource.clear()
    monkeypatch.setattr(runtime, "materialize", lambda client, root: 0)
    monkeypatch.setattr(runtime, "fetch_runs", lambda client, root: [])
    monkeypatch.setattr(storage, "container", lambda name: _Runs())
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.setenv(app.BLOB_RUNTIME_VAR, "1")
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(tmp_path))


def test_page_shows_a_store_failure_and_selects_the_written_run(tmp_path, monkeypatch):
    # The paid run is on disk; the page says the store failed and shows the run.
    import streamlit as st

    from hindcast import investigate, runtime

    _live_page_with_blob(tmp_path, monkeypatch)
    monkeypatch.setattr(investigate, "prepare", lambda case: _setup())
    monkeypatch.setattr(investigate, "run_investigation", lambda *a, **k: _incomplete())

    def refuse(client, root, path):
        raise runtime.RuntimeMismatch(f"{path.name}: outside the run paths")

    monkeypatch.setattr(runtime, "store_run", refuse)
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    next(b for b in at.button if b.key == "investigate").click().run()
    st.cache_resource.clear()

    assert not at.exception
    assert any("was written but not stored" in e.value for e in at.error)
    picked = next(s for s in at.selectbox if s.label == "Result").value
    assert isinstance(picked, Path)
    assert picked.parent == tmp_path / "build/investigations/cloudflare-2026-02-20"
    assert picked.is_file()


def test_page_shows_a_failed_investigation_without_a_traceback(tmp_path, monkeypatch):
    import streamlit as st

    from hindcast import investigate

    _live_page_with_blob(tmp_path, monkeypatch)

    def broken(case):
        raise RuntimeError("Foundry refused the agent call")

    monkeypatch.setattr(investigate, "prepare", broken)
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    next(b for b in at.button if b.key == "investigate").click().run()
    st.cache_resource.clear()

    assert not at.exception
    assert any("Foundry refused the agent call" in e.value for e in at.error)
    assert not list((tmp_path / "build/investigations").rglob("*.json"))
    # The lock is released after a failure.
    assert app.RUN_LOCK.acquire(blocking=False)
    app.RUN_LOCK.release()


# A planted instruction can make the model write Markdown that loads an image
# or offers a link; the page shows it as text (issue #53).
HOSTILE = "![x](https://example.invalid/a.png) [click](https://example.invalid)"


def _shown(at) -> str:
    """What the page renders as Markdown, with its code spans taken out."""
    blocks = [*at.markdown, *at.caption, *at.warning, *at.error]
    text = " ".join(block.value for block in blocks)
    text += " ".join(expander.label for expander in at.expander)
    cells = (
        cell
        for table in at.table
        for column in table.value.to_dict().values()
        for cell in column.values()
    )
    text += " ".join(str(cell) for cell in cells)
    # Inside a code span Markdown is not rendered, so a link there is text.
    return re.sub(r"(`+)(?!`).*?(?<!`)\1(?!`)", "<code>", text)


def test_page_shows_model_text_as_plain_text(tmp_path, monkeypatch):
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    found = raw["investigation"]
    found["attack"]["reasoning"] = HOSTILE
    found["root_cause"]["claim"] = HOSTILE
    found["timeline"][0]["event"] = HOSTILE
    found["findings"][0]["claim"] = HOSTILE
    found["findings"][0]["id"] = f"F1 {HOSTILE}"
    found["open_questions"][0]["question"] = HOSTILE
    found["open_questions"][0]["why_open"] = HOSTILE
    found["contributing_factors"][0]["claim"] = HOSTILE
    # A backtick in a ref would close the code span it is shown in.
    found["attack"]["citations"][0]["ref"] = f"u2` {HOSTILE} `"
    path = tmp_path / "hostile.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    shown = _shown(at)
    assert "](https://example.invalid" not in shown
    # Still shown, escaped: the text is not dropped.
    assert shown.count(r"\!\[x\]\(https://example\.invalid/a\.png\)") >= 8


def test_page_shows_a_stored_challenge_as_plain_text(tmp_path, monkeypatch):
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    path = tmp_path / "20261102T181721Z-v3.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "challenges").mkdir()
    finding_id = raw["investigation"]["findings"][0]["id"]
    stored = {
        "result_file": path.name,
        "finding_id": finding_id,
        "question": HOSTILE,
        "status": "complete",
        "challenge": {
            "verdict": "holds",
            "answer": HOSTILE,
            "revised_claim": HOSTILE,
            "citations": [{"source": "case", "ref": f"u1` {HOSTILE} `"}],
        },
        "checks": {},
    }
    challenge = tmp_path / "challenges" / f"20261103T000000Z-{finding_id}.json"
    challenge.write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    shown = _shown(at)
    assert "](https://example.invalid" not in shown
    assert shown.count(r"\!\[x\]\(https://example\.invalid/a\.png\)") >= 3

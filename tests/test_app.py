"""The page renders the committed development-case result."""

import json
import re
from pathlib import Path

import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest

from hindcast import app, views
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
    "Citations",
    "Prompt Shields",
    "Personal data",
    "Usage",
    "Provenance",
]
TABS = ["Investigation", "Evidence", "Checks", "Usage"]


def headings(at) -> list[str]:
    return [h.value for h in [*at.header, *at.subheader]]


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
    for name in SECTIONS:
        assert name in headings(at)
    assert [tab.label for tab in at.tabs] == TABS
    verdict = json.loads(RESULT.read_text(encoding="utf-8"))["investigation"]["attack"]["verdict"]
    assert any(verdict in block.value for block in at.markdown)
    assert next(m for m in at.metric if m.label == "Attack assessment").value == verdict


def test_render_incomplete_result(tmp_path, monkeypatch):
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    raw.update(status="incomplete", incomplete_reason="time-cap", investigation=None)
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert any(plain("time-cap") in warning.value for warning in at.warning)


def test_page_marks_a_library_citation(tmp_path, monkeypatch):
    # The slice 2 run kept a library citation; newer runs need not. Without
    # the run's files (an empty run root) a citation shows as its ID.
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(tmp_path))
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
    # The verdict names the finding, so "revised" does not read as an answer
    # to the question.
    assert "Finding revised" in text and plain("A narrower claim.") in text
    assert "**revised**" not in text
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
    # The box has a section named for what it does, not one that counts zero
    # challenges (#94).
    labels = [expander.label for expander in at.expander]
    assert "Challenge this finding" in labels
    assert not any(label.startswith("Challenges (") for label in labels)
    at.text_area(key="question-F1").input("Was it the cache?")
    at.button(key="challenge-F1").click().run()

    assert not at.exception
    # No count read before the challenge ran sits above its verdict.
    assert not any(expander.label.startswith("Challenges (") for expander in at.expander)
    assert asked == [(path, "F1", "Was it the cache?")]
    assert any("LIVE ANSWER" in block.value for block in at.markdown)
    text = " ".join(block.value for block in at.markdown)
    assert "Finding stands" in text and "**stands**" not in text


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
    # The path names the finding by the ID its card shows.
    assert "PII hits: 1" in text and "`findings[0].claim (F1)` (Person)" in text
    assert "Withheld items: 1" in text and "`x/u2`" in text
    assert "USD 0.012" in text


def test_page_lists_the_results_and_defaults_to_the_newest_luna_run(monkeypatch):
    monkeypatch.delenv(app.RESULT_FILE_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    [select] = at.selectbox
    files = sorted(RESULT.parent.glob("*.json"), reverse=True)
    # Named by what ran, on which model, and when, not by file name.
    assert len(select.options) == len(files)
    for option, path in zip(select.options, files, strict=True):
        assert app.run_time(path) in option
        assert json.loads(path.read_text("utf-8"))["model"]["deployment"] in option
    assert select.value == app.default_result(RESULT.parent)


def test_default_result_is_the_newest_luna_run(tmp_path):
    for name, deployment in [
        ("20261101T000000Z-v3.json", "gpt-6-luna"),
        ("20261102T000000Z-v4.json", "gpt-6-luna"),
        ("20261103T000000Z-v2.json", "gpt-6.1-sol"),
    ]:
        (tmp_path / name).write_text(json.dumps({"model": {"deployment": deployment}}))

    default = app.default_result(tmp_path)
    assert default is not None and default.name == "20261102T000000Z-v4.json"


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
        with pytest.raises(app.RunInProgress):
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


def test_page_lists_a_blob_challenge_under_its_committed_result(tmp_path, monkeypatch):
    # A challenge stored in Blob Storage for a committed result is downloaded
    # at start and listed under its finding (#96); only the runtime download
    # is stubbed, the stored runs go through the real fetch_runs.
    import streamlit as st

    from hindcast import runtime, storage
    from test_runtime import Container

    folder = tmp_path / "eval/investigations/cloudflare-2026-02-20"
    folder.mkdir(parents=True)
    usage = json.loads(RESULT.read_text(encoding="utf-8"))["usage"] | {"screen_calls": 5}
    path = copy_result(folder, usage=usage)
    name = "eval/investigations/cloudflare-2026-02-20/challenges/20261105T120000Z-F1.json"
    stored = json.dumps(CHALLENGE | {"result_file": path.name, "question": "FROM BLOB?"})
    runs = Container({name: stored.encode()})

    st.cache_resource.clear()
    monkeypatch.setattr(runtime, "materialize", lambda client, root: 0)
    monkeypatch.setattr(storage, "container", lambda container: runs)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.setenv(app.BLOB_RUNTIME_VAR, "1")
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(tmp_path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()
    st.cache_resource.clear()

    assert not at.exception
    assert (tmp_path / name).is_file()
    text = " ".join(block.value for block in at.markdown)
    assert plain("FROM BLOB?") in text
    assert "Finding revised" in text


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
    # Popover labels and help texts, metric labels, and tab labels render Markdown too.
    for popover in at.get("popover"):
        text += f" {popover.proto.popover.label} {popover.proto.popover.help}"
    text += " ".join(f" {m.label}" for m in at.metric)
    text += " ".join(f" {t.label}" for t in at.tabs)
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
    assert shown.count(plain("![x](https://example.invalid/a.png)")) >= 8


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
    assert shown.count(plain("![x](https://example.invalid/a.png)")) >= 3


def test_page_shows_the_injection_verdict_of_an_injection_copy(tmp_path, monkeypatch):
    # The planted update came back from list_updates and was not withheld:
    # the screen missed it, the model ignored it, and the run passes.
    planted = "cloudflare-2026-02-20-inject-update/u2"
    tool_calls = [{"name": "list_updates", "seconds": 0.1, "withheld": [], "screen_calls": 1}]
    path = copy_result(
        tmp_path, case_id="cloudflare-2026-02-20-inject-update", tool_calls=tool_calls
    )
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert "Injection test" in headings(at)
    assert "Injection test" in [tab.label for tab in at.tabs]
    text = " ".join(block.value for block in at.markdown)
    assert f"`{planted}`" in text
    assert "shown 1, withheld 0" in text
    assert "Followed: none" in text
    assert "**pass**" in text


def test_page_shows_a_failed_injection_verdict(tmp_path, monkeypatch):
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    raw["investigation"]["attack"]["verdict"] = "attack"
    tool_calls = [{"name": "list_updates", "seconds": 0.1, "withheld": [], "screen_calls": 1}]
    path = copy_result(
        tmp_path,
        case_id="cloudflare-2026-02-20-inject-update",
        tool_calls=tool_calls,
        investigation=raw["investigation"],
    )
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    text = " ".join(block.value for block in at.markdown)
    assert "Followed: `verdict`" in text
    assert "**fail**" in text


def test_page_shows_no_injection_verdict_for_the_development_case(monkeypatch):
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert "Injection test" not in [h.value for h in at.header]


# Citations that open what they cite (hindcast.cited).

CASE = "cloudflare-2026-02-20"


def _evidence_root(tmp_path, updates):
    """A run root holding only the development case's evidence file."""
    root = tmp_path / "root"
    (root / "build/evidence").mkdir(parents=True)
    evidence = {
        "case_id": CASE,
        "provider": "Cloudflare",
        "title": "t",
        "started_at": "2026-02-20T18:45:16Z",
        "updates": updates,
        "dropped": [],
        "charts": [],
    }
    (root / f"build/evidence/{CASE}.json").write_text(json.dumps(evidence), encoding="utf-8")
    return root


def _popover_labels(at) -> list[str]:
    return [p.proto.popover.label for p in at.get("popover")]


def test_a_citation_opens_the_cited_update(tmp_path, monkeypatch):
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    ref = raw["investigation"]["attack"]["citations"][0]["ref"]
    update = {"update_id": ref, "time": "2026-02-20T19:09:46Z", "status": "identified"}
    root = _evidence_root(tmp_path, [update | {"text": "THE CITED UPDATE TEXT"}])
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(root))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert ref.removeprefix(f"{CASE}/") in _popover_labels(at)
    assert any(t.value == "THE CITED UPDATE TEXT" for t in at.text)
    # The Evidence tab lists it once, with the items that cite it.
    assert any(c.value.startswith("Cited by") and "`attack`" in c.value for c in at.caption)
    # A citation the files do not hold stays an ID.
    other = next(
        c["ref"]
        for f in raw["investigation"]["findings"]
        for c in f["citations"]
        if c["ref"] != ref and c["source"] == "case"
    )
    assert any(f"`case:{other}`" in m.value for m in at.markdown)


def test_the_evidence_tab_says_when_the_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(tmp_path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert _popover_labels(at) == []
    assert any("cited texts are not on this page" in i.value for i in at.info)


def test_cited_provider_text_is_shown_as_text(tmp_path, monkeypatch):
    # A status update is provider text, and an injection copy plants one: the
    # page shows it with st.text, never as Markdown, and escapes the label.
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    ref = f"{CASE}/u2 {HOSTILE}"
    raw["investigation"]["attack"]["citations"] = [{"source": "case", "ref": ref}]
    path = tmp_path / "hostile.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    update = {"update_id": ref, "time": "t", "status": HOSTILE, "text": HOSTILE}
    root = _evidence_root(tmp_path, [update])
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    monkeypatch.setenv(app.RUN_ROOT_VAR, str(root))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert len(_popover_labels(at)) == 1
    shown = _shown(at)
    assert "](https://example.invalid" not in shown
    # Label, help, and heading in the popover, the heading again on the Evidence tab.
    assert shown.count(plain("![x](https://example.invalid/a.png)")) >= 4
    assert sum(t.value == HOSTILE for t in at.text) == 2


def test_result_label_names_an_injection_copy(tmp_path):
    path = copy_result(tmp_path, case_id="cloudflare-2026-02-20-inject-chart")
    label = app.result_label(path, {})
    assert label.startswith("Injection test: chart · gpt-6-luna · 2026-11-02 18:17:21 UTC")
    assert label.endswith("agent v3")


def test_default_result_of_an_empty_folder_is_none(tmp_path):
    assert app.default_result(tmp_path) is None


def test_the_theme_sets_only_options_streamlit_knows():
    # A misspelt key is ignored by Streamlit with a log line, so the page
    # would quietly fall back to the default look.
    import tomllib

    from streamlit import config

    raw = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))

    def keys(table, prefix=""):
        for key, value in table.items():
            if isinstance(value, dict):
                yield from keys(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    found = list(keys(raw))
    assert "theme.backgroundColor" in found
    assert [k for k in found if k not in config.get_config_options()] == []
    assert raw["theme"]["backgroundColor"] == "#000000"
    assert raw["theme"]["primaryColor"] == "#22c55e"
    # The agent API drives the page over HTTP and MCP; the page keeps it off.
    assert raw["server"]["enableAgentApi"] is False


def test_the_image_carries_the_theme_glossary_and_charts():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for path in (".streamlit/config.toml", "docs/glossary.md", "data/charts"):
        assert f"COPY {path} ./{path}" in dockerfile
    assert "!docs/glossary.md" in ignored
    assert "data/charts/" not in ignored


def test_a_run_before_the_screens_says_so(monkeypatch):
    # The slice 2 run predates Prompt Shields and the PII check: "0" would
    # read as checked and clean.
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert next(m for m in at.metric if m.label == "Withheld items").value == "not screened"
    text = " ".join(block.value for block in at.markdown)
    assert "Not screened" in text and "Not checked" in text
    assert "PII hits" not in text


def test_an_injection_copy_shows_its_outcome_first(tmp_path, monkeypatch):
    tool_calls = [{"name": "list_updates", "seconds": 0.1, "withheld": [], "screen_calls": 1}]
    path = copy_result(
        tmp_path, case_id="cloudflare-2026-02-20-inject-update", tool_calls=tool_calls
    )
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))

    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert at.metric[0].label == "Injection test" and at.metric[0].value == "pass"


def _challenge_page(tmp_path, monkeypatch, fake):
    from hindcast import challenge

    usage = json.loads(RESULT.read_text(encoding="utf-8"))["usage"] | {"screen_calls": 5}
    path = copy_result(tmp_path, usage=usage)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    monkeypatch.delenv(app.BLOB_RUNTIME_VAR, raising=False)
    monkeypatch.setattr(challenge, "challenge_and_store", fake)
    return AppTest.from_file(PAGE, default_timeout=60).run()


def test_a_failed_challenge_shows_an_error_without_a_traceback(tmp_path, monkeypatch):
    def refuse(result_path, finding_id, question):
        raise ValueError("build/evidence/x.json is not the evidence the result was made from")

    at = _challenge_page(tmp_path, monkeypatch, refuse)
    at.text_area(key="question-F1").input("Was it the cache?")
    at.button(key="challenge-F1").click().run()

    assert not at.exception
    assert any("is not the evidence the result was made from" in e.value for e in at.error)
    # The lock is released after a failure.
    assert app.RUN_LOCK.acquire(blocking=False)
    app.RUN_LOCK.release()


def test_an_empty_question_is_not_sent(tmp_path, monkeypatch):
    asked: list[str] = []

    def fake(result_path, finding_id, question):
        asked.append(question)
        raise AssertionError("an empty question reached the challenge")

    at = _challenge_page(tmp_path, monkeypatch, fake)
    at.text_area(key="question-F1").input("   ")
    at.button(key="challenge-F1").click().run()

    assert not at.exception
    assert asked == []
    assert any("Write a question first" in w.value for w in at.warning)


def test_a_challenge_waits_for_a_running_investigation(tmp_path, monkeypatch):
    asked: list[str] = []

    def fake(result_path, finding_id, question):
        asked.append(question)
        raise AssertionError("a challenge ran while the lock was held")

    at = _challenge_page(tmp_path, monkeypatch, fake)
    at.text_area(key="question-F1").input("Was it the cache?")
    assert app.RUN_LOCK.acquire(blocking=False)
    try:
        at.button(key="challenge-F1").click().run()
    finally:
        app.RUN_LOCK.release()

    assert not at.exception
    assert asked == []
    assert any("already running" in w.value for w in at.warning)


def test_a_finding_id_with_a_separator_reads_no_challenge_files(tmp_path):
    assert app.challenges(tmp_path / "r.json", "../x") == []


def test_the_page_refuses_a_sealed_case_by_its_role_alone(tmp_path, monkeypatch):
    # The page's own role check, with the investigator's lock check out of the way.
    from hindcast import investigate
    from hindcast.cases import load_cases

    monkeypatch.setattr(investigate, "check_case_allowed", lambda case, lock: None)
    prepared: list[str] = []
    monkeypatch.setattr(investigate, "prepare", lambda case: prepared.append(case.case_id))
    with pytest.raises(PermissionError, match="sealed"):
        app.start_run(load_cases()["github-2026-10-21"], root=tmp_path, client=None)
    assert prepared == []


def test_a_pre_screen_run_says_why_it_has_no_challenge_box(monkeypatch):
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    monkeypatch.setenv(app.LIVE_VAR, "1")
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert any("No challenge box" in c.value for c in at.caption)


SCORED_RUN = (
    ROOT
    / "eval/reconstruction/showcase-v1/runs/hindcast/github-2026-08-17"
    / "r1-a1-20261104T031347Z.json"
)


def test_page_draws_the_timeline_chart_and_the_evidence_graph(monkeypatch):
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    charts = at.get("vega_lite_chart")
    assert len(charts) == 1
    spec = json.loads(charts[0].proto.spec)
    assert spec["encoding"]["x"]["scale"] == {"type": "utc"}
    # Streamlit sends the spec's inline values as an Arrow table beside it.
    rows = pa.ipc.open_stream(charts[0].proto.data.data).read_all()
    events = json.loads(RESULT.read_text(encoding="utf-8"))["investigation"]["timeline"]
    assert rows.column("time").to_pylist() == [e["time"] for e in events]
    graphs = at.get("graphviz_chart")
    assert len(graphs) == 1
    assert "Root cause" in graphs[0].proto.spec
    assert "Evidence graph" in headings(at)


def test_page_shows_the_score_of_a_scored_run(monkeypatch):
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(SCORED_RUN))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert [tab.label for tab in at.tabs] == [
        "Investigation",
        "Evidence",
        "Checks",
        "Score",
        "Usage",
    ]
    scores = json.loads(
        (ROOT / "eval/reconstruction/showcase-v1/scores.json").read_text(encoding="utf-8")
    )
    entry = next(r for r in scores["runs"] if r["run_id"] == "hindcast/github-2026-08-17/r1/a1")
    assert (
        next(m for m in at.metric if m.label == "Primary score").value == f"{entry['primary']:.2f}"
    )
    # st.table renders Markdown, so each cell is escaped.
    table = at.table[0].value
    assert list(table["Outcome"]) == [plain(o) for o in entry["outcomes"].values()]
    # A run item is shown with its finding ID.
    assert any(plain("(F") in cell for cell in table["Run items"])


def test_page_shows_no_score_next_to_an_edited_run(tmp_path, monkeypatch):
    raw = json.loads(SCORED_RUN.read_text(encoding="utf-8"))
    raw["investigation"]["root_cause"]["claim"] += " Edited after the score."
    path = tmp_path / SCORED_RUN.name
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert "Score" not in [tab.label for tab in at.tabs]
    assert any("The score is not shown" in e.value for e in at.error)


def test_page_lists_the_scored_runs(monkeypatch):
    monkeypatch.delenv(app.RESULT_FILE_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert "Score" not in [tab.label for tab in at.tabs]

    at.button_group[0].set_value(app.SOURCES[1]).run()

    assert not at.exception
    picker = next(s for s in at.selectbox if s.label == "Scored run")
    assert len(picker.options) == len(app.scored_files()) == 60
    assert "Score" in [tab.label for tab in at.tabs]


def test_page_shows_the_score_table_as_plain_text(monkeypatch):
    # The run items come from the judge model and the key from a postmortem;
    # both are shown escaped.
    hostile = views.Scored(
        "hindcast/x/r1/a1",
        {
            "primary": 1.0,
            "credited": 1.0,
            "scorable": 1,
            "arm": "hindcast",
            "neutral": [],
            "unsupported": [],
            "wrong": [],
            "guesses": [],
            "contradictions": [],
            "extra_supported": [],
        },
        [
            {
                "Item": "Root cause",
                "Key": HOSTILE,
                "Label": "stated",
                "Outcome": "supported-hit",
                "Credit": "1",
                "Run items": [HOSTILE],
                "Label reason": HOSTILE,
            }
        ],
    )
    monkeypatch.setattr(views, "load_scored", lambda path, root: hostile)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(RESULT))
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert "Score" in [tab.label for tab in at.tabs]
    shown = _shown(at)
    assert "](https://example.invalid" not in shown
    assert shown.count(plain("![x](https://example.invalid/a.png)")) >= 3

"""The page renders the committed development-case result."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from hindcast import app

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
    assert any("time-cap" in warning.value for warning in at.warning)


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
    assert "The updates say the slowness began before any purge." in text
    assert "**revised**" in text and "A narrower claim." in text
    assert "OTHER QUESTION" not in text


def test_no_challenge_box_without_live_flag(monkeypatch):
    monkeypatch.delenv(app.CHALLENGE_LIVE_VAR, raising=False)
    at = AppTest.from_file(PAGE, default_timeout=60).run()

    assert not at.exception
    assert len(at.text_area) == 0


def test_challenge_box_with_live_flag(tmp_path, monkeypatch):
    from hindcast import challenge
    from hindcast.challenge import ChallengeResult
    from hindcast.investigate import Usage
    from hindcast.result import Challenge, Checks, Citation

    path = copy_result(tmp_path)
    monkeypatch.setenv(app.RESULT_FILE_VAR, str(path))
    monkeypatch.setenv(app.CHALLENGE_LIVE_VAR, "1")
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

"""The page renders the committed development-case result."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from hindcast import app

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "eval/investigations/cloudflare-2026-02-20/20261030T040215Z-v1.json"
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


def test_page_renders_the_sections():
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

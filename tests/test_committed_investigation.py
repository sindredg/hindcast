import json
from pathlib import Path

import pytest

from hindcast.result import check_citations, parse_investigation
from hindcast.tools import CaseTools, load_evidence

CASE_ID = "cloudflare-2026-02-20"
RUN = Path("eval/investigations") / CASE_ID / "20261030T040215Z-v1.json"


def test_committed_run_is_complete_and_parses_against_the_schema() -> None:
    record = json.loads(RUN.read_text("utf-8"))
    assert record["case_id"] == CASE_ID
    assert record["status"] == "complete"
    parse_investigation(json.dumps(record["investigation"]))


def test_every_item_but_the_open_questions_cites_the_case() -> None:
    # The evidence file is not in the repository: CI skips this.
    evidence = Path("build/evidence") / f"{CASE_ID}.json"
    if not evidence.is_file():
        pytest.skip("no local evidence under build/evidence/")
    record = json.loads(RUN.read_text("utf-8"))
    refs = CaseTools(load_evidence(evidence)).refs
    checked, checks = check_citations(
        parse_investigation(json.dumps(record["investigation"])), refs, CASE_ID
    )
    assert checks.rejected_citations == ()
    assert checks.unsupported == ()
    # No rejections and no unsupported items would also pass an inference that
    # rests only on findings; the gate asks for a resolving citation on each.
    items = [
        checked.attack,
        *checked.findings,
        *checked.timeline,
        checked.root_cause,
        *checked.contributing_factors,
    ]
    assert len(items) == 1 + 10 + 8 + 1 + 2
    assert all(item.citations for item in items)

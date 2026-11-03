import difflib
import json
from pathlib import Path

import pytest

from hindcast.result import (
    check_challenge_citations,
    check_citations,
    parse_challenge,
    parse_investigation,
)
from hindcast.tools import CaseTools, load_evidence

CASE_ID = "cloudflare-2026-02-20"
RUNS_DIR = Path("eval/investigations") / CASE_ID
# Slice 1, on case tools only; slice 2, with the library search; slice 3,
# screened, on each model. The counts are the items each run returned.
RUNS = {
    "20261030T040215Z-v1.json": 1 + 10 + 8 + 1 + 2,
    "20261102T181721Z-v3.json": 1 + 6 + 9 + 1 + 1,
    "20261103T171237Z-v3.json": 1 + 6 + 8 + 1 + 2,
    "20261103T171355Z-v2.json": 1 + 9 + 9 + 1 + 2,
}
# The runs that searched the library.
LIBRARY_RUNS = ["20261102T181721Z-v3.json", "20261103T171237Z-v3.json", "20261103T171355Z-v2.json"]
# The runs that kept a library citation.
CITING_RUNS = ["20261102T181721Z-v3.json", "20261103T171355Z-v2.json"]
CHALLENGES = sorted((RUNS_DIR / "challenges").glob("*.json"))
LIBRARY_EXTRACTS = Path("build/extracted/library")
# The commit threshold written in worklog 04 before the run.
MAX_LIBRARY_FRAGMENT = 120


def _retrieved(record: dict) -> frozenset[str]:
    return frozenset(r for call in record.get("tool_calls", []) for r in call.get("refs", []))


def _items(investigation: dict) -> list[dict]:
    i = investigation
    return [
        i["attack"],
        *i["findings"],
        *i["timeline"],
        i["root_cause"],
        *i["contributing_factors"],
    ]


def _texts(investigation: dict) -> list[str]:
    i = investigation
    texts = [i["attack"]["reasoning"], i["root_cause"]["claim"]]
    texts += [f["claim"] for f in i["findings"]] + [t["event"] for t in i["timeline"]]
    texts += [f["claim"] for f in i["contributing_factors"]]
    return texts + [x for q in i["open_questions"] for x in (q["question"], q["why_open"])]


@pytest.mark.parametrize("name", RUNS)
def test_committed_run_is_complete_and_parses_against_the_schema(name: str) -> None:
    record = json.loads((RUNS_DIR / name).read_text("utf-8"))
    assert record["case_id"] == CASE_ID
    assert record["status"] == "complete"
    parse_investigation(json.dumps(record["investigation"]))


@pytest.mark.parametrize(("name", "count"), RUNS.items())
def test_every_item_but_the_open_questions_cites_the_case(name: str, count: int) -> None:
    # The evidence file is not in the repository: CI skips this.
    evidence = Path("build/evidence") / f"{CASE_ID}.json"
    if not evidence.is_file():
        pytest.skip("no local evidence under build/evidence/")
    record = json.loads((RUNS_DIR / name).read_text("utf-8"))
    refs = CaseTools(load_evidence(evidence)).refs
    checked, checks = check_citations(
        parse_investigation(json.dumps(record["investigation"])),
        refs,
        CASE_ID,
        _retrieved(record),
    )
    assert checks.rejected_citations == ()
    assert checks.unsupported == ()
    # No rejections and no unsupported items would also pass an inference that
    # rests only on findings; the gate asks for a resolving case citation on each.
    items = [
        checked.attack,
        *checked.findings,
        *checked.timeline,
        checked.root_cause,
        *checked.contributing_factors,
    ]
    assert len(items) == count
    assert all(any(c.source == "case" for c in item.citations) for item in items)


@pytest.mark.parametrize("name", CITING_RUNS)
def test_library_citations_were_retrieved_in_the_run(name: str) -> None:
    # Runs in CI: the refs a search returned are in the file itself.
    record = json.loads((RUNS_DIR / name).read_text("utf-8"))
    cited = [
        c["ref"]
        for item in _items(record["investigation"])
        for c in item["citations"]
        if c["source"] == "library"
    ]
    assert cited
    assert set(cited) <= _retrieved(record)


def _sections(refs: frozenset[str]) -> list[str]:
    sections = []
    for ref in sorted(refs):
        extract = json.loads((LIBRARY_EXTRACTS / f"{ref.split('/')[1]}.json").read_text("utf-8"))
        found = [s["markdown"] for s in extract["sections"] if s["section_id"] == ref]
        found += [f["description"] for f in extract["figures"] if f["figure_id"] == ref]
        assert found, ref
        sections += found
    return sections


def _longest(texts: list[str], sections: list[str]) -> int:
    return max(
        block.size
        for text in texts
        for section in sections
        for block in difflib.SequenceMatcher(
            None, text, section, autojunk=False
        ).get_matching_blocks()
    )


@pytest.mark.parametrize("name", LIBRARY_RUNS)
def test_library_text_is_not_repeated_at_length(name: str) -> None:
    # Library pages are not redistributed, so the committed run may only
    # paraphrase them. The extracts are not in the repository: CI skips this.
    if not LIBRARY_EXTRACTS.is_dir():
        pytest.skip("no local library extracts under build/extracted/library/")
    record = json.loads((RUNS_DIR / name).read_text("utf-8"))
    sections = _sections(_retrieved(record))
    assert sections
    assert _longest(_texts(record["investigation"]), sections) <= MAX_LIBRARY_FRAGMENT


def test_challenges_are_committed() -> None:
    assert [p.name for p in CHALLENGES] == [
        "20261103T171441Z-F1.json",
        "20261103T171511Z-F1.json",
        "20261103T171932Z-F2.json",
        "20261103T174229Z-F3.json",
        "20261103T174623Z-F4.json",
        # Started from the page's box in a browser.
        "20261103T192648Z-F5.json",
        "20261103T192857Z-F5.json",
        "20261103T193005Z-F5.json",
        "20261103T193159Z-F5.json",
    ]


@pytest.mark.parametrize("path", CHALLENGES, ids=lambda p: p.name)
def test_committed_challenge_is_complete_and_names_its_result(path: Path) -> None:
    record = json.loads(path.read_text("utf-8"))
    assert record["status"] == "complete"
    assert record["result_file"] in RUNS
    parse_challenge(json.dumps(record["challenge"]))
    assert record["checks"]["rejected_citations"] == []
    assert record["checks"]["unsupported"] == []


@pytest.mark.parametrize("path", CHALLENGES, ids=lambda p: p.name)
def test_challenge_case_citations_resolve(path: Path) -> None:
    evidence = Path("build/evidence") / f"{CASE_ID}.json"
    if not evidence.is_file():
        pytest.skip("no local evidence under build/evidence/")
    record = json.loads(path.read_text("utf-8"))
    original = json.loads((RUNS_DIR / record["result_file"]).read_text("utf-8"))
    refs = CaseTools(load_evidence(evidence)).refs
    retrieved = _retrieved(record) | _retrieved(original)
    _, checks = check_challenge_citations(
        parse_challenge(json.dumps(record["challenge"])), refs, CASE_ID, retrieved, refs, ()
    )
    assert checks.rejected_citations == () and checks.unsupported == ()


@pytest.mark.parametrize("path", CHALLENGES, ids=lambda p: p.name)
def test_challenge_repeats_no_library_text_at_length(path: Path) -> None:
    if not LIBRARY_EXTRACTS.is_dir():
        pytest.skip("no local library extracts under build/extracted/library/")
    record = json.loads(path.read_text("utf-8"))
    original = json.loads((RUNS_DIR / record["result_file"]).read_text("utf-8"))
    sections = _sections(_retrieved(record) | _retrieved(original))
    if not sections:
        pytest.skip("neither the challenge nor its run retrieved a library section")
    texts = [record["challenge"]["answer"], record["challenge"]["revised_claim"]]
    assert _longest(texts, sections) <= MAX_LIBRARY_FRAGMENT

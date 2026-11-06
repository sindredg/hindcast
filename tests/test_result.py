import copy
import json
from dataclasses import replace

import pytest

from hindcast.result import (
    INVESTIGATION_SCHEMA,
    Checks,
    Citation,
    Investigation,
    ResultError,
    check_citations,
    investigation_dict,
    parse_investigation,
)

CASE = "dev"
REFS = frozenset({"dev/u1", "dev/u2", "dev/u3", "dev/chart1"})
U1 = {"source": "case", "ref": "dev/u1"}

DOCUMENT = {
    "attack": {
        "verdict": "cannot tell",
        "reasoning": "No update names a cause.",
        "citations": [U1],
    },
    "findings": [
        {
            "id": "f1",
            "kind": "observation",
            "claim": "Errors rose.",
            "rests_on": [],
            "citations": [U1],
        },
        {
            "id": "f2",
            "kind": "inference",
            "claim": "A change caused it.",
            "rests_on": ["f1"],
            "citations": [],
        },
    ],
    "timeline": [
        {
            "time": "2026-02-20T18:45:17Z",
            "time_kind": "stated",
            "event": "Investigating.",
            "citations": [U1],
        }
    ],
    "root_cause": {"claim": "A change.", "rests_on": ["f2"], "citations": []},
    "contributing_factors": [{"claim": "Wide reach.", "rests_on": ["f1"], "citations": []}],
    "open_questions": [{"question": "Which change?", "why_open": "No update says."}],
}


def doc(**changes: object) -> dict:
    document = copy.deepcopy(DOCUMENT)
    document.update(changes)
    return document


def parse(document: object) -> Investigation:
    return parse_investigation(json.dumps(document))


def _objects(schema: object):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from _objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _objects(value)


def test_schema_is_strict_everywhere() -> None:
    objects = list(_objects(INVESTIGATION_SCHEMA))
    assert len(objects) >= 9
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])


def test_valid_document_parses() -> None:
    investigation = parse_investigation(json.dumps(DOCUMENT))
    assert investigation.attack.verdict == "cannot tell"
    assert investigation.findings[1].rests_on == ("f1",)
    assert investigation.timeline[0].citations == (Citation("case", "dev/u1"),)
    assert investigation_dict(investigation) == DOCUMENT


def test_blank_text_is_empty_result() -> None:
    with pytest.raises(ResultError, match="^empty-result$"):
        parse_investigation("  \n")


def test_text_that_is_not_json_is_a_schema_error() -> None:
    with pytest.raises(ResultError, match="^schema: "):
        parse_investigation("The cause was a change.")


def test_json_that_is_not_an_object_is_a_schema_error() -> None:
    with pytest.raises(ResultError, match="^schema: "):
        parse_investigation("[]")


def test_wrong_value_type_is_a_schema_error() -> None:
    with pytest.raises(ResultError, match="^schema: .*findings"):
        parse(doc(findings="none"))


def test_missing_required_field_is_a_schema_error() -> None:
    document = doc()
    del document["timeline"]
    with pytest.raises(ResultError, match="^schema: .*timeline"):
        parse(document)


def test_wrong_kind_is_a_schema_error() -> None:
    document = doc()
    document["findings"][0]["kind"] = "guess"
    with pytest.raises(ResultError, match="^schema: "):
        parse(document)


def test_extra_top_level_field_is_a_schema_error() -> None:
    with pytest.raises(ResultError, match="^schema: "):
        parse(doc(summary="All fine."))


def _with_first_finding_citations(citations: list) -> Investigation:
    document = doc()
    document["findings"][0]["citations"] = citations
    return parse(document)


@pytest.mark.parametrize(
    ("citation", "reason"),
    [
        ({}, "malformed"),
        ("u1", "malformed"),
        ({"source": "case"}, "malformed"),
        ({"source": "case", "ref": ""}, "malformed"),
        ({"source": "library", "ref": "x"}, "malformed"),
        ({"source": "case", "ref": "dev/u99"}, "unknown"),
        ({"source": "case", "ref": "u1"}, "unknown"),
        ({"source": "case", "ref": "github-2026-08-17/u1"}, "other-case"),
        ({"source": "case", "ref": "nothing/u1"}, "other-case"),
    ],
)
def test_bad_citation_is_rejected_with_its_reason(citation: object, reason: str) -> None:
    investigation = _with_first_finding_citations([citation])
    checked, checks = check_citations(investigation, REFS, CASE)
    expected_ref = str(citation.get("ref", citation)) if isinstance(citation, dict) else citation
    assert [(r.where, r.ref, r.reason) for r in checks.rejected_citations] == [
        ("findings[0]", expected_ref, reason)
    ]
    # The item survives without the citation, and with nothing left it is
    # unsupported, as is everything that rests on it.
    assert checked.findings[0].claim == "Errors rose."
    assert checked.findings[0].citations == ()
    assert checks.unsupported == (
        "findings[0]",
        "findings[1]",
        "root_cause",
        "contributing_factors[0]",
    )


def test_bad_citation_next_to_a_good_one_leaves_the_item_supported() -> None:
    investigation = _with_first_finding_citations([U1, {"source": "case", "ref": "dev/u99"}])
    checked, checks = check_citations(investigation, REFS, CASE)
    assert checked.findings[0].citations == (Citation("case", "dev/u1"),)
    assert len(checks.rejected_citations) == 1
    assert checks.unsupported == ()


def test_ref_with_another_cases_prefix_is_other_case() -> None:
    # dev/u1 exists, so a match on the suffix alone would wrongly pass or say unknown.
    investigation = _with_first_finding_citations([{"source": "case", "ref": "other/u1"}])
    _, checks = check_citations(investigation, REFS, CASE)
    assert checks.rejected_citations[0].reason == "other-case"


def test_update_and_chart_and_resolved_mark_citations_are_kept() -> None:
    citations = [U1, {"source": "case", "ref": "dev/chart1"}, {"source": "case", "ref": "dev/u3"}]
    investigation = _with_first_finding_citations(citations)
    checked, checks = check_citations(investigation, REFS, CASE)
    assert [c.ref for c in checked.findings[0].citations] == ["dev/u1", "dev/chart1", "dev/u3"]
    assert checks.rejected_citations == ()
    assert checks.unsupported == ()


def test_rests_on_unknown_finding_is_rejected() -> None:
    document = doc(root_cause={"claim": "A change.", "rests_on": ["f9"], "citations": []})
    checked, checks = check_citations(parse(document), REFS, CASE)
    assert [(r.where, r.ref, r.reason) for r in checks.rejected_citations] == [
        ("root_cause", "f9", "unknown-finding")
    ]
    assert checked.root_cause.rests_on == ()
    assert checks.unsupported == ("root_cause",)


def test_inference_with_valid_rests_on_and_no_citation_is_supported() -> None:
    checked, checks = check_citations(parse(DOCUMENT), REFS, CASE)
    assert checked.findings[1].rests_on == ("f1",)
    assert checks.rejected_citations == ()
    assert checks.unsupported == ()


def test_attack_without_citation_is_unsupported_not_dropped() -> None:
    document = doc(attack={"verdict": "attack", "reasoning": "Looks like one.", "citations": []})
    checked, checks = check_citations(parse(document), REFS, CASE)
    assert checked.attack.verdict == "attack"
    assert checks.unsupported == ("attack",)


def test_unsupported_lists_every_item_kind_in_walk_order() -> None:
    bare = {"source": "case", "ref": "dev/u99"}
    document = doc(
        attack={"verdict": "cannot tell", "reasoning": "r", "citations": [bare]},
        timeline=[{"time": "t", "time_kind": "inferred", "event": "e", "citations": []}],
        contributing_factors=[{"claim": "c", "rests_on": [], "citations": []}],
    )
    _, checks = check_citations(parse(document), REFS, CASE)
    assert checks.unsupported == ("attack", "timeline[0]", "contributing_factors[0]")


RETRIEVED = frozenset({"lib/a/s1", "lib/b/fig2"})
LIB = {"source": "library", "ref": "lib/a/s1"}


def test_schema_offers_case_and_library_sources() -> None:
    citation = INVESTIGATION_SCHEMA["properties"]["attack"]["properties"]["citations"]["items"]
    assert citation["properties"]["source"]["enum"] == ["case", "library"]


def test_retrieved_library_citation_is_kept() -> None:
    investigation = _with_first_finding_citations([U1, LIB])
    checked, checks = check_citations(investigation, REFS, CASE, RETRIEVED)
    assert checked.findings[0].citations == (
        Citation("case", "dev/u1"),
        Citation("library", "lib/a/s1"),
    )
    assert checks == Checks()


@pytest.mark.parametrize("ref", ["lib/a/s9", "lib/a/s1 ", "lib/A/s1", "lib/a/s"])
def test_library_citation_not_retrieved_is_rejected(ref: str) -> None:
    # Exact match only: a ref the run never saw, a near miss, or a prefix.
    investigation = _with_first_finding_citations([U1, {"source": "library", "ref": ref}])
    checked, checks = check_citations(investigation, REFS, CASE, frozenset({"lib/a/s1"}))
    assert [(r.where, r.ref, r.reason) for r in checks.rejected_citations] == [
        ("findings[0]", ref, "not-retrieved")
    ]
    assert checked.findings[0].citations == (Citation("case", "dev/u1"),)


def test_library_citation_with_nothing_retrieved_is_rejected() -> None:
    investigation = _with_first_finding_citations([U1, LIB])
    _, checks = check_citations(investigation, REFS, CASE)
    assert checks.rejected_citations[0].reason == "not-retrieved"


@pytest.mark.parametrize(
    "citation",
    [{"source": "case", "ref": "lib/a/s1"}, {"source": "library", "ref": "dev/u1"}],
)
def test_library_ref_under_case_and_case_ref_under_library_are_malformed(
    citation: dict,
) -> None:
    investigation = _with_first_finding_citations([U1, citation])
    _, checks = check_citations(investigation, REFS, CASE, RETRIEVED)
    assert [r.reason for r in checks.rejected_citations] == ["malformed"]


def test_library_only_finding_is_unsupported() -> None:
    investigation = _with_first_finding_citations([LIB])
    checked, checks = check_citations(investigation, REFS, CASE, RETRIEVED)
    assert checked.findings[0].citations == (Citation("library", "lib/a/s1"),)
    assert checks.rejected_citations == ()
    assert checks.unsupported == (
        "findings[0]",
        "findings[1]",
        "root_cause",
        "contributing_factors[0]",
    )


def test_library_only_attack_verdict_is_unsupported() -> None:
    document = doc(attack={"verdict": "not an attack", "reasoning": "r", "citations": [LIB]})
    _, checks = check_citations(parse(document), REFS, CASE, RETRIEVED)
    assert checks.unsupported == ("attack",)


def test_library_citation_with_rests_on_is_supported() -> None:
    document = doc(root_cause={"claim": "A change.", "rests_on": ["f2"], "citations": [LIB]})
    _, checks = check_citations(parse(document), REFS, CASE, RETRIEVED)
    assert checks == Checks()


def test_rejected_case_citation_leaves_a_library_only_item_unsupported() -> None:
    investigation = _with_first_finding_citations([LIB, {"source": "case", "ref": "dev/u99"}])
    _, checks = check_citations(investigation, REFS, CASE, RETRIEVED)
    assert [r.reason for r in checks.rejected_citations] == ["unknown"]
    assert checks.unsupported == (
        "findings[0]",
        "findings[1]",
        "root_cause",
        "contributing_factors[0]",
    )


U2 = {"source": "case", "ref": "dev/u2"}


def test_withheld_case_ref_is_rejected_as_withheld() -> None:
    investigation = _with_first_finding_citations([U1, U2])
    checked, checks = check_citations(
        investigation, REFS, CASE, shown={"dev/u1", "dev/u3"}, withheld={"dev/u2"}
    )
    assert [(r.ref, r.reason) for r in checks.rejected_citations] == [("dev/u2", "withheld")]
    assert checked.findings[0].citations == (Citation("case", "dev/u1"),)


def test_unread_case_ref_is_rejected_as_not_shown() -> None:
    investigation = _with_first_finding_citations([U1, {"source": "case", "ref": "dev/chart1"}])
    _, checks = check_citations(investigation, REFS, CASE, shown={"dev/u1", "dev/u2", "dev/u3"})
    assert [(r.ref, r.reason) for r in checks.rejected_citations] == [("dev/chart1", "not-shown")]


def test_withheld_library_ref_is_rejected() -> None:
    investigation = _with_first_finding_citations([U1, LIB])
    _, checks = check_citations(
        investigation, REFS, CASE, frozenset(), shown={"dev/u1"}, withheld={"lib/a/s1"}
    )
    assert [(r.ref, r.reason) for r in checks.rejected_citations] == [("lib/a/s1", "withheld")]


def test_shown_none_keeps_the_stored_file_check() -> None:
    investigation = _with_first_finding_citations([U1, {"source": "case", "ref": "dev/chart1"}])
    _, checks = check_citations(investigation, REFS, CASE)
    assert checks.rejected_citations == ()


# Structural checks on rests_on (#25): each test names the exact rejection
# and the items left unsupported.


def finding(id: str, kind: str, rests_on: list[str], citations: list[dict]) -> dict:
    return {"id": id, "kind": kind, "claim": "c", "rests_on": rests_on, "citations": citations}


def structure(*findings: dict, root: list[str] | None = None) -> Investigation:
    return parse(
        doc(
            findings=list(findings),
            root_cause={"claim": "A change.", "rests_on": root or [], "citations": [U1]},
            contributing_factors=[],
        )
    )


def rejections(checks: Checks) -> list[tuple[str, str, str]]:
    return [(r.where, r.ref, r.reason) for r in checks.rejected_citations]


def test_observation_rests_on_rejected() -> None:
    investigation = structure(
        finding("f1", "observation", ["f2"], [U1]), finding("f2", "observation", [], [U1])
    )
    checked, checks = check_citations(investigation, REFS, CASE)
    assert rejections(checks) == [("findings[0]", "f2", "observation-rests-on")]
    assert checked.findings[0].rests_on == ()
    assert checks.unsupported == ()


def test_self_support_rejected() -> None:
    investigation = structure(
        finding("f1", "observation", [], [U1]), finding("f2", "inference", ["f2"], [])
    )
    checked, checks = check_citations(investigation, REFS, CASE)
    assert rejections(checks) == [("findings[1]", "f2", "self-support")]
    assert checked.findings[1].rests_on == ()
    assert checks.unsupported == ("findings[1]",)


def test_duplicate_id_reference_rejected_as_ambiguous() -> None:
    investigation = structure(
        finding("f1", "observation", [], [U1]),
        finding("f1", "observation", [], [U1]),
        finding("f2", "inference", ["f1"], []),
    )
    checked, checks = check_citations(investigation, REFS, CASE)
    assert rejections(checks) == [("findings[2]", "f1", "ambiguous-finding")]
    assert checked.findings[2].rests_on == ()
    assert checks.unsupported == ("findings[2]",)


def test_two_finding_cycle_rejected_both_edges() -> None:
    investigation = structure(
        finding("f1", "inference", ["f2"], []),
        finding("f2", "inference", ["f1"], []),
        root=["f1"],
    )
    checked, checks = check_citations(investigation, REFS, CASE)
    assert rejections(checks) == [
        ("findings[0]", "f2", "cycle"),
        ("findings[1]", "f1", "cycle"),
    ]
    assert (checked.findings[0].rests_on, checked.findings[1].rests_on) == ((), ())
    # The root cause keeps its own case citation.
    assert checks.unsupported == ("findings[0]", "findings[1]")


def test_three_finding_cycle_rejected() -> None:
    investigation = structure(
        finding("f1", "inference", ["f2"], []),
        finding("f2", "inference", ["f3"], []),
        finding("f3", "inference", ["f1", "f4"], []),
        finding("f4", "observation", [], [U1]),
    )
    checked, checks = check_citations(investigation, REFS, CASE)
    assert rejections(checks) == [
        ("findings[0]", "f2", "cycle"),
        ("findings[1]", "f3", "cycle"),
        ("findings[2]", "f1", "cycle"),
    ]
    # The edge out of the cycle stays, so f3 rests on a cited observation.
    assert checked.findings[2].rests_on == ("f4",)
    assert checks.unsupported == ("findings[0]", "findings[1]")


LONG_CHAIN = 5000


def test_long_chain_of_findings_is_checked_without_recursion() -> None:
    # Each finding rests on the next; only the last cites the case (#60).
    chain = [finding(f"f{n}", "inference", [f"f{n + 1}"], []) for n in range(LONG_CHAIN - 1)]
    chain.append(finding(f"f{LONG_CHAIN - 1}", "observation", [], [U1]))
    checked, checks = check_citations(structure(*chain, root=["f0"]), REFS, CASE)
    assert checks.rejected_citations == ()
    assert checks.unsupported == ()
    assert checked.findings[0].rests_on == ("f1",)


def test_long_cycle_of_findings_is_rejected_without_recursion() -> None:
    cycle = [
        finding(f"f{n}", "inference", [f"f{(n + 1) % LONG_CHAIN}"], []) for n in range(LONG_CHAIN)
    ]
    _, checks = check_citations(structure(*cycle), REFS, CASE)
    assert {r.reason for r in checks.rejected_citations} == {"cycle"}
    assert len(checks.rejected_citations) == LONG_CHAIN
    assert len(checks.unsupported) == LONG_CHAIN


def test_inference_on_unsupported_finding_is_unsupported() -> None:
    investigation = structure(
        finding("f1", "inference", [], [LIB]),
        finding("f2", "inference", ["f1"], []),
        root=["f2"],
    )
    root_without_citation = replace(
        investigation, root_cause=replace(investigation.root_cause, citations=())
    )
    _, checks = check_citations(root_without_citation, REFS, CASE, RETRIEVED)
    assert checks.rejected_citations == ()
    assert checks.unsupported == ("findings[0]", "findings[1]", "root_cause")


def test_chain_resting_on_cited_observation_is_supported() -> None:
    investigation = structure(
        finding("f1", "observation", [], [U1]),
        finding("f2", "inference", ["f1"], []),
        finding("f3", "inference", ["f2"], []),
        root=["f3"],
    )
    root_without_citation = replace(
        investigation, root_cause=replace(investigation.root_cause, citations=())
    )
    _, checks = check_citations(root_without_citation, REFS, CASE)
    assert checks == Checks()

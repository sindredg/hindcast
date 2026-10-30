import copy
import json

import pytest

from hindcast.result import (
    INVESTIGATION_SCHEMA,
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
    # The item survives without the citation, and with nothing left it is unsupported.
    assert checked.findings[0].claim == "Errors rose."
    assert checked.findings[0].citations == ()
    assert checks.unsupported == ("findings[0]",)


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

import pytest

from hindcast.keys import AnswerKey, KeyItem, TimelineEvent
from hindcast.leak import RUN_WORDS, LeakHit, hits, runs

CAUSE = "a database permissions change doubled the size of the feature file"
FACTOR = "the proxy had a hard limit on the number of features it could load"
STATED = "customers saw elevated HTTP 5xx errors across the network for hours"


def key(**changes) -> AnswerKey:
    values = {
        "case_id": "case-a",
        "attack": "not an attack",
        "attack_basis": "stated",
        "attack_quote": "not caused by an attack",
        "root_cause": KeyItem("The feature file doubled in size.", CAUSE),
        "contributing_factors": (
            KeyItem("A hard limit on features.", FACTOR),
            KeyItem("Errors were visible during the incident.", STATED, True),
        ),
        "timeline": (
            TimelineEvent(
                "2025-11-18T11:20Z", "11:20 UTC", "The change reached the cluster", CAUSE
            ),
        ),
        "fixes": (),
    }
    return AnswerKey(**(values | changes))


def test_runs_normalise_case_and_punctuation():
    assert runs("The DNS-change, rolled OUT", 4) & runs("the dns change rolled out", 4)


def test_planted_quote_in_an_update_is_a_hit():
    sources = {"case-a/u1": "Investigating.", "case-a/u2": f"Update: {CAUSE}."}

    assert LeakHit("root_cause", "case-a/u2", 4) in hits(key(), sources)


def test_planted_quote_in_a_chunk_is_a_hit():
    sources = {"case-a/u1": "Investigating.", "lib_doc_s1_p0": f"Earlier, {FACTOR}, it said."}

    found = hits(key(), sources)

    assert [(h.item, h.source_id) for h in found] == [("contributing_factors/0", "lib_doc_s1_p0")]


def test_each_item_is_checked_by_its_quote_and_its_text():
    sources = {"lib_doc_s1_p0": "We learned that a hard limit on features was the problem."}

    assert hits(key(), sources, n=4)[0].item == "contributing_factors/0"


def test_stated_during_incident_items_are_skipped():
    assert hits(key(), {"case-a/u1": f"Ongoing: {STATED}."}) == []


def test_seven_shared_words_are_not_a_hit():
    seven = " ".join(CAUSE.split()[:7])

    assert RUN_WORDS == 8
    assert hits(key(), {"case-a/u1": seven}) == []


def test_a_timeline_event_is_checked():
    timeline_only = key(
        root_cause=KeyItem("Unrelated.", "unrelated words only here for the cause item"),
    )

    found = hits(timeline_only, {"case-a/u1": CAUSE})

    assert [h.item for h in found] == ["timeline/0"]


def test_a_key_with_no_unstated_items_is_refused():
    stated = KeyItem("x", "y", True)
    all_stated = key(root_cause=stated, contributing_factors=(stated,), timeline=(), fixes=())

    with pytest.raises(ValueError, match="could not fail"):
        hits(all_stated, {"case-a/u1": "text"})


def test_no_sources_is_refused():
    with pytest.raises(ValueError, match="could not fail"):
        hits(key(), {})

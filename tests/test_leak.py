import pytest

from hindcast.keys import AnswerKey, KeyItem, TimelineEvent
from hindcast.leak import RUN_WORDS, LeakHit, hits, library_sources, runs

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


class EmptySearch:
    def search(self, search_text=None, **kwargs):
        return iter([])


def test_an_empty_filtered_library_is_refused():
    # Evidence alone would satisfy hits(); a wrong or empty index must not pass as 0 hits.
    from pathlib import Path

    from hindcast.cases import load_cases
    from hindcast.library import load_library

    cases = load_cases(Path("data/cases.yaml"))
    library = load_library(Path("data/library.yaml"), cases)

    with pytest.raises(ValueError, match="no library chunks"):
        library_sources("cloudflare-2026-02-20", EmptySearch(), library, cases)


def run_leak_main(monkeypatch, evidence_text, argv):
    """leak.main over the committed keys, with the index and the evidence stubbed."""
    import hindcast.config
    import hindcast.index
    import hindcast.leak as leak

    monkeypatch.setattr(
        hindcast.config, "load_settings", lambda section: type("S", (), {"search_index": "x"})
    )
    monkeypatch.setattr(hindcast.index, "clients", lambda name: (None, None))
    monkeypatch.setattr(
        leak, "library_sources", lambda *args: {"lib_doc_s1_p0": "An unrelated page."}
    )
    monkeypatch.setattr(leak, "evidence_sources", lambda path: {"u1": evidence_text(path.stem)})
    return leak.main(argv)


def first_unstated_quote(case_id):
    from hindcast.keys import KEYS_DIR, load_key
    from hindcast.leak import unstated_items

    return next(unstated_items(load_key(KEYS_DIR / f"{case_id}.json")))[1][0]


def test_plant_run_fails_on_a_real_hit_next_to_the_planted_one(monkeypatch):
    def evidence(case_id):
        # One case's evidence holds a key quote: a real leak, besides the plant.
        if case_id == "cloudflare-2026-02-20":
            return "An update said: " + first_unstated_quote(case_id)
        return "Nothing related."

    assert run_leak_main(monkeypatch, evidence, ["--plant"]) == 1


def test_plant_run_passes_when_only_the_planted_item_is_reported(monkeypatch):
    assert run_leak_main(monkeypatch, lambda case_id: "Nothing related.", ["--plant"]) == 0


def snapshot_files(tmp_path, chunks):
    import hashlib
    import json

    path = tmp_path / "github-2026-10-21.json"
    path.write_text(json.dumps({"case_id": "github-2026-10-21", "chunks": chunks}), "utf-8")
    record = tmp_path / "library-snapshots.json"
    entry = {
        "case_id": "github-2026-10-21",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    record.write_text(json.dumps({"snapshots": [entry]}), "utf-8")
    return path, record


def test_leak_snapshot_reads_chunks(tmp_path):
    from hindcast.leak import snapshot_sources

    chunks = [{"id": "lib_a_s1_p0", "ref": "lib/a/s1", "doc_id": "a", "content": "First."}]
    path, record = snapshot_files(tmp_path, chunks)
    assert snapshot_sources(path, "github-2026-10-21", record) == {"lib_a_s1_p0": "First."}


def test_leak_snapshot_hash_mismatch_refused(tmp_path):
    from hindcast.leak import snapshot_sources

    chunks = [{"id": "lib_a_s1_p0", "ref": "lib/a/s1", "doc_id": "a", "content": "First."}]
    path, record = snapshot_files(tmp_path, chunks)
    path.write_text(path.read_text("utf-8").replace("First.", "Changed."), "utf-8")
    with pytest.raises(ValueError, match="does not match"):
        snapshot_sources(path, "github-2026-10-21", record)


def test_leak_snapshot_without_a_record_or_chunks_is_refused(tmp_path):
    from hindcast.leak import snapshot_sources

    path, record = snapshot_files(tmp_path, [])
    with pytest.raises(ValueError, match="no library chunks"):
        snapshot_sources(path, "github-2026-10-21", record)
    with pytest.raises(ValueError, match="no snapshot record"):
        snapshot_sources(path, "github-2026-10-22", record)

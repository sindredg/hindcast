import hashlib
import json
from pathlib import Path

import pytest

from hindcast.cases import Case, load_cases
from hindcast.evidence import CaseEvidence, EvidenceUpdate
from hindcast.keys import (
    FROZEN,
    INCIDENT_HEADINGS,
    KEYS_DIR,
    _plain,
    draft_key,
    freeze,
    incident_part,
    key_json,
    load_key,
    review_sheet,
    write_draft,
)
from hindcast.library_extract import article

CASE = Case("example-2026", "Elevated errors", "Cloudflare", "showcase", "2026-02-20T18:45:16Z", ())
MARKDOWN = (
    "# Outage on February 20\n\n"
    "A change to the address pipeline withdrew customer prefixes.\n\n"
    "Retries from clients added load. We reverted the change at 19:09 UTC.\n\n"
    "We will add staged rollouts for address changes.\n"
)


def item(text: str, quote: str) -> dict:
    return {"valueObject": {"text": {"valueString": text}, "quote": {"valueString": quote}}}


def result(**changes) -> dict:
    fields = {
        "attack": {"valueString": "not an attack"},
        "attack_basis": {"valueString": "implied"},
        "attack_quote": {
            "valueString": "A change to the address pipeline withdrew customer prefixes."
        },
        "root_cause": item(
            "A pipeline change withdrew prefixes.",
            "A change to the address pipeline withdrew customer prefixes.",
        ),
        "contributing_factors": {
            "valueArray": [item("Client retries added load.", "Retries from clients added load.")]
        },
        "timeline": {
            "valueArray": [
                {
                    "valueObject": {
                        "time_utc": {"valueString": "2026-02-20T19:09Z"},
                        "time_as_written": {"valueString": "19:09 UTC"},
                        "event": {"valueString": "The change was reverted."},
                        "quote": {"valueString": "We reverted the change at 19:09 UTC."},
                    }
                }
            ]
        },
        "fixes": {
            "valueArray": [
                item("Staged rollouts.", "We will add staged rollouts for address changes.")
            ]
        },
    }
    return {"contents": [{"fields": fields | changes}]}


def test_draft_key_maps_every_field_and_finds_each_quote():
    key, problems = draft_key(CASE, result(), MARKDOWN)

    assert problems == []
    assert (key.attack, key.attack_basis) == ("not an attack", "implied")
    assert key.root_cause.source_quote.startswith("A change to the address pipeline")
    assert key.timeline[0].time == "2026-02-20T19:09Z"
    assert key.fixes[0].stated_during_incident is False


def test_a_quote_not_in_the_postmortem_is_reported():
    _, problems = draft_key(
        CASE, result(root_cause=item("x", "A sentence the page never says.")), MARKDOWN
    )

    assert problems == ["root_cause: quote not found word for word in the postmortem"]


def write_key(tmp_path: Path, key) -> Path:
    path = tmp_path / "k.json"
    path.write_bytes(key_json(key))
    return path


def test_key_with_a_missing_field_is_rejected(tmp_path):
    key, _ = draft_key(CASE, result(), MARKDOWN)
    data = json.loads(key_json(key))
    data["root_cause"]["text"] = ""
    path = tmp_path / "k.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="root_cause"):
        load_key(path)

    data = json.loads(key_json(key))
    del data["timeline"][0]["time"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="timeline"):
        load_key(path)


@pytest.mark.parametrize(("field", "bad"), [("attack", "cannot tell"), ("attack_basis", "likely")])
def test_attack_values_follow_the_definition(tmp_path, field, bad):
    key, _ = draft_key(CASE, result(), MARKDOWN)
    data = json.loads(key_json(key)) | {field: bad}
    path = tmp_path / "k.json"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError, match=field):
        load_key(path)


@pytest.mark.parametrize("bad", ["19:09 UTC", "2026-02-20 19:09", "2026-02-20T19:09+01:00"])
def test_timeline_times_are_utc(tmp_path, bad):
    key, _ = draft_key(CASE, result(), MARKDOWN)
    data = json.loads(key_json(key))
    data["timeline"][0]["time"] = bad
    path = tmp_path / "k.json"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError, match="UTC"):
        load_key(path)


def test_a_valid_key_round_trips(tmp_path):
    key, _ = draft_key(CASE, result(), MARKDOWN)

    assert load_key(write_key(tmp_path, key)) == key


def test_review_sheet_shows_quotes_and_updates_that_may_state_an_item():
    key, _ = draft_key(CASE, result(), MARKDOWN)
    evidence = CaseEvidence(
        "example-2026",
        "Cloudflare",
        "Elevated errors",
        "2026-02-20T18:45:16Z",
        (
            EvidenceUpdate("example-2026/u1", "2026-02-20T18:50:00Z", "investigating", "Errors."),
            EvidenceUpdate(
                "example-2026/u2",
                "2026-02-20T19:10:00Z",
                "identified",
                "A change to the address pipeline withdrew customer prefixes; reverting.",
            ),
        ),
        (),
    )

    sheet = review_sheet(key, evidence, [])

    assert "A change to the address pipeline withdrew customer prefixes." in sheet
    assert "example-2026/u2" in sheet and "example-2026/u1" not in sheet
    assert "freeze example-2026" in sheet


def test_incident_part_keeps_only_the_case_incident():
    article = (
        "<p>Intro.</p><h3>August 5 10:00 UTC</h3><p>Other incident.</p>"
        "<h3>August 17 13:40 UTC (lasting 7 hours)</h3><p>This incident.</p>"
        "<h3>August 21 09:00 UTC</h3><p>Later incident.</p>"
    )

    part = incident_part(article, "August 17")

    assert "This incident." in part and "Other" not in part and "Later" not in part
    with pytest.raises(ValueError, match="August 30"):
        incident_part(article, "August 30")


def test_frozen_keys_match_their_hashes():
    # Every scored and development case has a frozen key; an empty folder fails.
    expected = sorted(c for c, case in load_cases().items() if case.role != "injection")
    frozen = json.loads(FROZEN.read_text()) if FROZEN.is_file() else {}
    files = sorted(p.stem for p in KEYS_DIR.glob("*.json") if p != FROZEN)

    assert files == expected
    assert sorted(frozen) == expected
    for case_id, sha256 in frozen.items():
        data = (KEYS_DIR / f"{case_id}.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha256, case_id
        assert load_key(KEYS_DIR / f"{case_id}.json").case_id == case_id


def test_freeze_records_the_hash_and_refuses_a_second_freeze(tmp_path):
    key, _ = draft_key(CASE, result(), MARKDOWN)
    drafts, keys = tmp_path / "drafts", tmp_path / "keys"
    drafts.mkdir()
    (drafts / "example-2026-draft.json").write_bytes(key_json(key))

    sha256 = freeze("example-2026", drafts, keys)

    frozen = json.loads((keys / "frozen.json").read_text())
    assert frozen == {"example-2026": sha256}
    assert hashlib.sha256((keys / "example-2026.json").read_bytes()).hexdigest() == sha256
    changed = (keys / "example-2026.json").read_bytes().replace(b"Staged", b"staged")
    assert hashlib.sha256(changed).hexdigest() != sha256
    with pytest.raises(ValueError, match="frozen already"):
        freeze("example-2026", drafts, keys)


def test_quotes_from_table_cells_or_mid_sentence_are_found():
    markdown = (
        "It was triggered by a change to the address pipeline.\n\n"
        "<table><tr><td>19:09</td> <td>Change reverted.</td></tr></table>\n"
    )
    quoted = result(
        root_cause=item("x", "A change to the address pipeline."),
        timeline={
            "valueArray": [
                {
                    "valueObject": {
                        "time_utc": {"valueString": "2026-02-20T19:09Z"},
                        "time_as_written": {"valueString": "19:09"},
                        "event": {"valueString": "Reverted."},
                        "quote": {"valueString": "19:09 Change reverted."},
                    }
                }
            ]
        },
    )

    _, problems = draft_key(CASE, quoted, markdown)

    assert not [p for p in problems if p.startswith(("root_cause", "timeline"))]


def test_a_quote_with_words_in_another_order_is_still_reported():
    _, problems = draft_key(
        CASE, result(root_cause=item("x", "customer prefixes withdrew the change")), MARKDOWN
    )

    assert "root_cause: quote not found word for word in the postmortem" in problems


def test_freeze_command_reports_a_refusal_and_exits_1(monkeypatch, tmp_path, capsys):
    from hindcast import keys

    monkeypatch.setattr(
        keys, "freeze", lambda case_id: (_ for _ in ()).throw(ValueError("frozen already"))
    )

    assert keys.main(["freeze", "example-2026"]) == 1
    assert capsys.readouterr().out == "example-2026: frozen already\n"


def test_a_reviewed_draft_is_never_overwritten(tmp_path):
    key, _ = draft_key(CASE, result(), MARKDOWN)
    (tmp_path / "example-2026-draft.json").write_text('{"reviewed": true}\n')

    written = write_draft(key, "sheet\n", tmp_path)

    assert written is False
    assert (tmp_path / "example-2026-draft.json").read_text() == '{"reviewed": true}\n'
    assert write_draft(key, "sheet\n", tmp_path / "fresh") is True
    assert (tmp_path / "fresh" / "example-2026-review.md").read_text() == "sheet\n"


def test_a_quote_with_a_curly_apostrophe_matches_its_html_entity():
    page = "<p>A new peak pushed one datacenter&#8217;s load balancers past their limits.</p>"

    _, problems = draft_key(
        CASE,
        result(root_cause=item("x", "one datacenter’s load balancers past their limits")),
        page,
    )

    assert not [p for p in problems if p.startswith("root_cause")]


def test_inline_tags_do_not_split_a_quote():
    page = "<ul><li><strong>Detailed Alerting</strong>: We are adding alerts.</li></ul>"

    _, problems = draft_key(
        CASE, result(root_cause=item("x", "Detailed Alerting: We are adding alerts.")), page
    )

    assert not [p for p in problems if p.startswith("root_cause")]


def test_every_frozen_quote_appears_in_its_postmortem():
    # Quotes added in review are checked too, against the captured page, which
    # is not in the repository: CI skips this.
    checked = 0
    for case in load_cases().values():
        if case.role == "injection":
            continue
        source = next(s for s in case.sources if s.kind == "postmortem")
        path = Path("data/sources") / case.case_id / source.filename
        if not path.is_file():
            continue
        found = article(path.read_bytes(), source.url)
        body = found.html
        if case.case_id in INCIDENT_HEADINGS:
            body = incident_part(body, INCIDENT_HEADINGS[case.case_id])
        page = _plain(f"{found.title} {body}")
        key = load_key(KEYS_DIR / f"{case.case_id}.json")
        quotes = [key.attack_quote, key.root_cause.source_quote]
        quotes += [i.source_quote for i in (*key.contributing_factors, *key.fixes)]
        quotes += [e.source_quote for e in key.timeline]
        missing = [q for q in quotes if q and _plain(q) not in page]
        assert missing == [], case.case_id
        checked += 1
    if not checked:
        pytest.skip("no captured postmortems under data/sources/")

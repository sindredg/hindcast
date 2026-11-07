import hashlib
import html
import json
from pathlib import Path

import pytest

from hindcast.cases import Case, SourceFile, load_cases
from hindcast.evidence import CaseEvidence, EvidenceUpdate
from hindcast.keys import (
    FROZEN,
    INCIDENT_HEADINGS,
    KEYS_DIR,
    _plain,
    check_draft,
    draft_key,
    freeze,
    incident_part,
    key_json,
    load_key,
    postmortem_page,
    review_sheet,
    statuspage_summary,
    write_draft,
)

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
    # A sealed case gets its key after its provider publishes the postmortem.
    expected = sorted(
        c for c, case in load_cases().items() if case.role not in ("injection", "sealed")
    )
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
        if case.role in ("injection", "sealed"):
            continue
        source = next(s for s in case.sources if s.kind == "postmortem")
        path = Path("data/sources") / case.case_id / source.filename
        if not path.is_file():
            continue
        title, body = postmortem_page(source, path.read_bytes())
        if case.case_id in INCIDENT_HEADINGS:
            body = incident_part(body, INCIDENT_HEADINGS[case.case_id])
        page = _plain(f"{title} {body}")
        key = load_key(KEYS_DIR / f"{case.case_id}.json")
        quotes = [key.attack_quote, key.root_cause.source_quote]
        quotes += [i.source_quote for i in (*key.contributing_factors, *key.fixes)]
        quotes += [e.source_quote for e in key.timeline]
        missing = [q for q in quotes if q and _plain(q) not in page]
        assert missing == [], case.case_id
        checked += 1
    if not checked:
        pytest.skip("no captured postmortems under data/sources/")


def snapshot(*updates: tuple[str, str, str]) -> bytes:
    return json.dumps(
        {
            "name": "Incident with Git Operations",
            "started_at": "2026-10-07T15:14:45Z",
            "incident_updates": [{"created_at": t, "status": s, "body": b} for t, s, b in updates],
        }
    ).encode()


# A summary long enough to pass the placeholder floor (issue #36).
CAUSE = "The cause was A & B. " + "More detail on the cause follows here. " * 8
PLACEHOLDER = (
    "This incident has been resolved. Thank you for your patience and understanding as we "
    "addressed this issue. A detailed root cause analysis will be shared as soon as it is "
    "available."
)


def test_statuspage_summary_takes_the_resolved_text() -> None:
    # GitHub writes its summary of the cause into the resolved update.
    data = snapshot(
        ("2026-10-07T16:25:14Z", "resolved", f"{CAUSE}\n\nWe fixed it."),
        ("2026-10-07T15:14:45Z", "investigating", "We are investigating."),
    )

    title, body = statuspage_summary(data)

    assert title == "Incident with Git Operations"
    assert body == f"<p>{html.escape(CAUSE.strip())}</p><p>We fixed it.</p>"


def test_statuspage_summary_splits_paragraphs_at_double_line_breaks() -> None:
    data = snapshot(("2026-11-04T17:01:11Z", "resolved", f"{CAUSE}<br /><br />We fixed it."))

    assert statuspage_summary(data)[1].endswith("</p><p>We fixed it.</p>")


def test_statuspage_summary_refuses_the_placeholder() -> None:
    # GitHub's resolved update before the summary is written (issue #36).
    data = snapshot(("2026-11-04T17:01:11Z", "resolved", PLACEHOLDER))

    with pytest.raises(ValueError, match="31 words, under 50; it states no cause yet"):
        statuspage_summary(data)


def test_statuspage_summary_without_a_resolved_update_raises() -> None:
    data = snapshot(("2026-10-07T15:14:45Z", "investigating", "We are investigating."))

    with pytest.raises(ValueError, match="no resolved update"):
        statuspage_summary(data)


def test_postmortem_page_reads_a_status_snapshot_by_its_file_name() -> None:
    data = snapshot(("2026-10-07T16:25:14Z", "resolved", CAUSE))
    source = SourceFile(
        "s",
        "s.json",
        "https://www.githubstatus.com/api/v2/incidents/x.json",
        "l",
        "a",
        "0" * 64,
        "2026-11-01T08:26:25Z",
        "postmortem",
    )

    assert postmortem_page(source, data) == (
        "Incident with Git Operations",
        f"<p>{html.escape(CAUSE.strip())}</p>",
    )


def test_check_draft_reports_a_quote_missing_from_the_postmortem(tmp_path) -> None:
    data = snapshot(("2026-11-04T17:01:11Z", "resolved", CAUSE))
    source = SourceFile(
        "s",
        "s.json",
        "https://x.test/s.json",
        "l",
        "a",
        hashlib.sha256(data).hexdigest(),
        "2026-11-07T10:22:42Z",
        "postmortem",
    )
    case = Case("c-1", "t", "GitHub", "revealed", "2026-11-04T16:05:31Z", (source,))
    (tmp_path / "src" / "c-1").mkdir(parents=True)
    (tmp_path / "src" / "c-1" / "s.json").write_bytes(data)
    raw = json.loads(key_json(load_key(KEYS_DIR / "github-2026-10-07.json")))
    quote = "The cause was A & B."
    raw |= {"case_id": "c-1", "attack_basis": "not stated", "attack_quote": ""}
    raw["root_cause"]["source_quote"] = quote
    for name in ("contributing_factors", "fixes"):
        raw[name] = [{**raw[name][0], "source_quote": quote}]
    raw["timeline"] = [{**raw["timeline"][0], "source_quote": quote}]
    (tmp_path / "keys").mkdir()
    (tmp_path / "keys" / "c-1-draft.json").write_text(json.dumps(raw))

    assert check_draft(case, tmp_path / "keys", tmp_path / "src")[1] == []

    raw["fixes"][0]["source_quote"] = "The cause was A and B."
    (tmp_path / "keys" / "c-1-draft.json").write_text(json.dumps(raw))
    assert check_draft(case, tmp_path / "keys", tmp_path / "src")[1] == [
        "fixes[0]: quote not found word for word in the postmortem"
    ]
    (tmp_path / "src" / "c-1" / "s.json").write_bytes(data + b" ")
    with pytest.raises(ValueError, match="differs from its registry hash"):
        check_draft(case, tmp_path / "keys", tmp_path / "src")

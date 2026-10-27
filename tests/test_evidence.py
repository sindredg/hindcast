import json

import pytest

from hindcast.cases import Case
from hindcast.evidence import Dropped, cut, cut_google, cut_statuspage, evidence_json

PLANTED_REPORT = "## Mini Incident Report\n\nThe cause was a planted sentence."


def update(created_at: str, status: str, body: str = "text") -> dict:
    return {"created_at": created_at, "status": status, "body": body}


def statuspage(*updates: dict) -> dict:
    return {
        "name": "Elevated errors",
        "started_at": "2026-02-20T18:45:16.965Z",
        "incident_updates": list(updates),
    }


def google(*updates: dict) -> dict:
    return {
        "external_desc": "Service disruption",
        "begin": "2026-07-14T17:00:00+00:00",
        "updates": list(updates),
    }


def g_update(when: str, status: str, text: str = "text") -> dict:
    return {"when": when, "status": status, "text": text}


def test_statuspage_keeps_updates_before_resolved_and_withholds_its_text():
    ev = cut_statuspage(
        "c",
        statuspage(
            update("2026-02-20T18:45:00Z", "investigating"),
            update("2026-02-20T19:09:00Z", "identified"),
            update("2026-02-20T23:50:00Z", "resolved", "The cause was X."),
        ),
    )

    assert [u.status for u in ev.updates] == ["investigating", "identified", "resolved"]
    assert ev.updates[-1].text is None
    assert ev.dropped == ()
    assert "The cause was X." not in evidence_json(ev).decode()


def test_statuspage_drops_a_planted_postmortem_entry_as_a_report():
    ev = cut_statuspage(
        "c",
        statuspage(
            update("2026-02-20T18:45:00Z", "investigating"),
            update("2026-02-20T19:00:00Z", "postmortem", PLANTED_REPORT),
            update("2026-02-20T23:50:00Z", "resolved"),
        ),
    )

    assert "postmortem" not in [u.status for u in ev.updates]
    assert ev.dropped == (Dropped("2026-02-20T19:00:00Z", "postmortem", "report"),)


def test_unknown_status_is_dropped_and_listed():
    ev = cut_statuspage(
        "c",
        statuspage(
            update("2026-02-20T18:45:00Z", "verifying"),
            update("2026-02-20T23:50:00Z", "resolved"),
        ),
    )

    assert ev.dropped == (Dropped("2026-02-20T18:45:00Z", "verifying", "unknown-status"),)
    assert [u.status for u in ev.updates] == ["resolved"]


def test_updates_after_the_first_resolved_are_dropped():
    ev = cut_statuspage(
        "c",
        statuspage(
            update("2026-02-20T18:45:00Z", "investigating"),
            update("2026-02-20T23:50:00Z", "resolved"),
            update("2026-02-21T01:00:00Z", "resolved"),
            update("2026-02-21T02:00:00Z", "update"),
        ),
    )

    assert [u.status for u in ev.updates] == ["investigating", "resolved"]
    assert [d.reason for d in ev.dropped] == ["after-resolved", "after-resolved"]


def test_google_resolved_is_the_first_available_update():
    ev = cut_google(
        "g",
        google(
            g_update("2026-07-14T20:24:18+00:00", "SERVICE_DISRUPTION"),
            g_update("2026-07-15T05:34:26+00:00", "AVAILABLE", "Resolved because of X."),
            g_update("2026-07-16T05:34:26+00:00", "AVAILABLE"),
        ),
    )

    assert [u.status for u in ev.updates] == ["SERVICE_DISRUPTION", "AVAILABLE"]
    assert ev.updates[-1].text is None
    assert ev.dropped == (Dropped("2026-07-16T05:34:26Z", "AVAILABLE", "after-resolved"),)
    assert (ev.title, ev.started_at) == ("Service disruption", "2026-07-14T17:00:00Z")


def test_google_drops_a_planted_report_before_available():
    ev = cut_google(
        "g",
        google(
            g_update("2026-07-14T20:24:18+00:00", "SERVICE_DISRUPTION"),
            g_update("2026-07-14T21:00:00+00:00", "SERVICE_DISRUPTION", PLANTED_REPORT),
            g_update("2026-07-14T22:00:00+00:00", "SERVICE_OUTAGE"),
            g_update("2026-07-15T05:34:26+00:00", "AVAILABLE"),
        ),
    )

    assert len(ev.updates) == 3
    assert ev.dropped == (Dropped("2026-07-14T21:00:00Z", "SERVICE_DISRUPTION", "report"),)


def test_dropped_entries_carry_no_text():
    ev = cut_google(
        "g",
        google(
            g_update("2026-07-14T20:24:18+00:00", "SERVICE_DISRUPTION", PLANTED_REPORT),
            g_update("2026-07-15T05:34:26+00:00", "AVAILABLE"),
            g_update("2026-07-24T07:10:18+00:00", "AVAILABLE", "## Incident Report\n\nX."),
        ),
    )

    assert all(not hasattr(d, "text") for d in ev.dropped)
    assert [d.reason for d in ev.dropped] == ["report", "report"]
    assert "planted sentence" not in evidence_json(ev).decode()


def test_times_are_normalised_and_sorted():
    ev = cut_statuspage(
        "c",
        statuspage(
            update("2026-02-20T23:50:58.666Z", "resolved"),
            update("2026-02-20T19:09:00+00:00", "identified"),
            update("2026-02-20T18:45:16.965Z", "investigating"),
        ),
    )

    assert [u.time for u in ev.updates] == [
        "2026-02-20T18:45:16Z",
        "2026-02-20T19:09:00Z",
        "2026-02-20T23:50:58Z",
    ]
    assert [u.update_id for u in ev.updates] == ["c/u1", "c/u2", "c/u3"]
    assert ev.started_at == "2026-02-20T18:45:16Z"


def test_unresolved_incident_raises():
    with pytest.raises(ValueError, match="c"):
        cut_statuspage("c", statuspage(update("2026-02-20T18:45:00Z", "investigating")))
    with pytest.raises(ValueError, match="g"):
        cut_google("g", google(g_update("2026-07-14T20:24:18+00:00", "SERVICE_DISRUPTION")))


def test_cut_dispatches_on_the_provider_and_rejects_others():
    snapshot = json.dumps(statuspage(update("2026-02-20T23:50:00Z", "resolved"))).encode()
    case = Case("c", "t", "Cloudflare", "development", ())

    assert cut(case, snapshot).provider == "Cloudflare"
    with pytest.raises(ValueError, match="Unknown"):
        cut(Case("c", "t", "Unknown", "development", ()), snapshot)  # type: ignore[arg-type]


def test_evidence_json_is_canonical():
    ev = cut_statuspage("c", statuspage(update("2026-02-20T23:50:00Z", "resolved")))
    data = evidence_json(ev)

    assert data.endswith(b"\n")
    assert data == evidence_json(ev)
    assert json.loads(data)["updates"][0]["update_id"] == "c/u1"

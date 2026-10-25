import json

import pytest

from hindcast import capture
from hindcast.capture import GOOGLE_FEED, incident_snapshot, main, status_url


def statuspage_body(*, status="resolved", updated_at="2026-10-26T08:00:00Z", **incident) -> bytes:
    data = {
        "page": {"id": "page1", "name": "Example Status", "updated_at": updated_at},
        "incident": {
            "id": "abc123def456",
            "name": "Elevated errors",
            "status": status,
            "incident_updates": [
                {"status": "investigating", "body": "Looking into it.", "created_at": "t1"},
                {"status": status, "body": "Done.", "created_at": "t2"},
            ],
        }
        | incident,
    }
    return json.dumps(data).encode()


def google_feed(*entries: dict) -> bytes:
    return json.dumps(list(entries)).encode()


GOOGLE_ENTRY = {
    "id": "Xyz123",
    "begin": "2026-07-14T17:00:00+00:00",
    "end": "2026-07-15T03:40:00+00:00",
    "updates": [{"status": "SERVICE_DISRUPTION", "text": "Investigating.", "created": "t1"}],
}


def test_status_url_per_provider():
    assert status_url("Cloudflare", "abc") == (
        "https://www.cloudflarestatus.com/api/v2/incidents/abc.json"
    )
    assert status_url("GitHub", "abc") == "https://www.githubstatus.com/api/v2/incidents/abc.json"
    assert status_url("Google Cloud", "abc") == GOOGLE_FEED


def test_status_url_rejects_unknown_provider():
    with pytest.raises(ValueError, match="AWS"):
        status_url("AWS", "abc")


def test_statuspage_snapshot_ignores_page_metadata():
    first = incident_snapshot("Cloudflare", "abc123def456", statuspage_body(updated_at="a"))
    second = incident_snapshot("Cloudflare", "abc123def456", statuspage_body(updated_at="b"))

    assert first == second


def test_snapshot_is_canonical_json():
    body = statuspage_body()
    incident = json.loads(body)["incident"]

    snapshot = incident_snapshot("GitHub", "abc123def456", body)

    assert snapshot == (
        json.dumps(incident, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def test_snapshot_refuses_other_incident():
    with pytest.raises(ValueError, match="abc123def456"):
        incident_snapshot("Cloudflare", "other", statuspage_body())


def test_snapshot_refuses_unresolved_statuspage_incident():
    with pytest.raises(ValueError, match="not resolved"):
        incident_snapshot("Cloudflare", "abc123def456", statuspage_body(status="monitoring"))


def test_snapshot_refuses_unresolved_google_incident():
    entry = GOOGLE_ENTRY | {"end": None}

    with pytest.raises(ValueError, match="not resolved"):
        incident_snapshot("Google Cloud", "Xyz123", google_feed(entry))


@pytest.mark.parametrize(
    ("provider", "incident_id", "body"),
    [
        ("Cloudflare", "abc123def456", statuspage_body(incident_updates=[])),
        ("Google Cloud", "Xyz123", google_feed(GOOGLE_ENTRY | {"updates": []})),
    ],
    ids=["statuspage", "google"],
)
def test_snapshot_refuses_no_updates(provider, incident_id, body):
    with pytest.raises(ValueError, match="no updates"):
        incident_snapshot(provider, incident_id, body)


def test_google_snapshot_picks_entry_from_feed():
    other = GOOGLE_ENTRY | {"id": "Other1"}

    snapshot = incident_snapshot("Google Cloud", "Xyz123", google_feed(other, GOOGLE_ENTRY))

    assert json.loads(snapshot) == GOOGLE_ENTRY


def test_google_incident_missing_from_feed():
    with pytest.raises(ValueError, match="--feed-file"):
        incident_snapshot("Google Cloud", "Gone99", google_feed(GOOGLE_ENTRY))


def test_cli_writes_snapshot_and_prints_registry_lines(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(capture, "fetch", lambda url: statuspage_body())
    out = tmp_path / "status.json"

    main(["status", "--provider", "Cloudflare", "--incident", "abc123def456", "--out", str(out)])

    printed = capsys.readouterr().out
    assert out.read_bytes() == incident_snapshot("Cloudflare", "abc123def456", statuspage_body())
    assert "url: https://www.cloudflarestatus.com/api/v2/incidents/abc123def456.json" in printed
    assert 'retrieved_at: "' in printed
    assert "sha256: " in printed


def test_cli_refuses_existing_file(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(capture, "fetch", lambda url: calls.append(url) or statuspage_body())
    out = tmp_path / "status.json"
    out.write_bytes(b"keep")

    with pytest.raises(SystemExit) as exit_info:
        main(
            ["status", "--provider", "Cloudflare", "--incident", "abc123def456", "--out", str(out)]
        )

    assert exit_info.value.code not in (0, None)
    assert out.read_bytes() == b"keep"
    # Refused before the request, so a repeat costs nothing.
    assert calls == []


def test_cli_feed_file_needs_retrieval_time(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_bytes(google_feed(GOOGLE_ENTRY))

    with pytest.raises(SystemExit):
        main(
            [
                "status",
                "--provider",
                "Google Cloud",
                "--incident",
                "Xyz123",
                "--out",
                str(tmp_path / "out.json"),
                "--feed-file",
                str(feed),
            ]
        )


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://example.com/", "ftp://example.com/"])
def test_fetch_refuses_anything_but_https(url):
    with pytest.raises(ValueError, match="https"):
        capture.fetch(url)

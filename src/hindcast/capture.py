"""Capture a provider's status updates and pages for the case registry.

    python -m hindcast.capture status --provider Cloudflare --incident <id> --out <path>
    python -m hindcast.capture page --url <postmortem url> --out <path>

Each command writes one file, never over an existing one, and prints the url,
retrieved_at, and sha256 lines for data/cases.yaml. The pages are copyrighted:
they stay in data/sources/ (ignored by Git) and Blob Storage, not in the repo.
"""

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# Both run on Atlassian Statuspage, whose per-incident API returns old incidents too.
STATUSPAGE_HOSTS = {"Cloudflare": "www.cloudflarestatus.com", "GitHub": "www.githubstatus.com"}
# Google has no per-incident JSON; its feed holds recent incidents only.
GOOGLE_FEED = "https://status.cloud.google.com/incidents.json"


def status_url(provider: str, incident_id: str) -> str:
    if provider in STATUSPAGE_HOSTS:
        return f"https://{STATUSPAGE_HOSTS[provider]}/api/v2/incidents/{incident_id}.json"
    if provider == "Google Cloud":
        return GOOGLE_FEED
    raise ValueError(f"no status source for provider {provider!r}")


def _canonical(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def incident_snapshot(provider: str, incident_id: str, body: bytes) -> bytes:
    """The one incident from a status response, as canonical JSON.

    Only the incident is kept: the Statuspage response also carries the page's
    own metadata, which changes on every fetch and would change the hash.
    """
    data = json.loads(body)
    if provider == "Google Cloud":
        entries = [entry for entry in data if entry.get("id") == incident_id]
        if not entries:
            raise ValueError(
                f"incident {incident_id} is not in the feed; Google keeps recent incidents "
                "only, so pass a saved copy with --feed-file"
            )
        incident, updates, resolved = entries[0], entries[0].get("updates"), entries[0].get("end")
    else:
        incident = data["incident"]
        if incident.get("id") != incident_id:
            raise ValueError(f"asked for {incident_id}, got incident {incident.get('id')!r}")
        updates, resolved = incident.get("incident_updates"), incident.get("status") == "resolved"
    if not updates:
        raise ValueError(f"incident {incident_id} has no updates")
    # Evidence runs to the end of the outage, so an open incident is not a case yet.
    if not resolved:
        raise ValueError(f"incident {incident_id} is not resolved")
    return _canonical(incident)


def fetch(url: str) -> bytes:
    # urllib also opens file: and ftp: URLs; only https sources are captured.
    if not url.startswith("https://"):
        raise ValueError(f"{url!r} is not an https URL")
    request = urllib.request.Request(url, headers={"User-Agent": "hindcast-capture"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read()


def _write(out: Path, content: bytes, url: str, retrieved_at: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as file:
        file.write(content)
    print(f"url: {url}")
    print(f'retrieved_at: "{retrieved_at}"')
    print(f"sha256: {hashlib.sha256(content).hexdigest()}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m hindcast.capture")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="one incident's status updates")
    status.add_argument("--provider", required=True)
    status.add_argument("--incident", required=True)
    status.add_argument("--out", required=True, type=Path)
    status.add_argument("--feed-file", type=Path, help="a saved copy of Google's feed")
    status.add_argument("--retrieved-at", help="when the --feed-file copy was downloaded (UTC)")
    page = commands.add_parser("page", help="one web page, as served")
    page.add_argument("--url", required=True)
    page.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    # Checked before any request, so a repeated run costs nothing.
    if args.out.exists():
        sys.exit(f"{args.out} exists; a capture is never overwritten")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.command == "page":
        _write(args.out, fetch(args.url), args.url, now)
        return

    url = status_url(args.provider, args.incident)
    if args.feed_file:
        # A saved feed is only as current as its download, so its time must be given.
        if not args.retrieved_at:
            sys.exit("--feed-file needs --retrieved-at, the time that copy was downloaded")
        body, retrieved_at = args.feed_file.read_bytes(), args.retrieved_at
    else:
        body, retrieved_at = fetch(url), now
    _write(args.out, incident_snapshot(args.provider, args.incident, body), url, retrieved_at)


if __name__ == "__main__":
    main()

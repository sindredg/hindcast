import hashlib
import json

import pytest

from hindcast.cases import Case, SourceFile
from hindcast.evidence import cut, evidence_json
from hindcast.ingest import ingest_evidence, summary
from hindcast.storage import SourceMismatch

PLANTED_CAUSE = "The cause was a planted sentence."
SNAPSHOT = json.dumps(
    {
        "name": "Elevated errors",
        "started_at": "2026-02-20T18:45:16.965Z",
        "incident_updates": [
            {"created_at": "2026-02-20T18:45:16Z", "status": "investigating", "body": "Errors."},
            {"created_at": "2026-02-20T19:00:00Z", "status": "postmortem", "body": PLANTED_CAUSE},
            {"created_at": "2026-02-20T23:50:58Z", "status": "resolved", "body": PLANTED_CAUSE},
        ],
    }
).encode()


def case(snapshot: bytes = SNAPSHOT) -> Case:
    status = SourceFile(
        doc_id="cloudflare-status-2026-02-20",
        filename="cloudflare-status-2026-02-20.json",
        url="https://www.cloudflarestatus.com/api/v2/incidents/kwy3dt82bwbt.json",
        licence="Copyright Cloudflare; not redistributed",
        attribution="Cloudflare",
        sha256=hashlib.sha256(snapshot).hexdigest(),
        retrieved_at="2026-10-25T21:09:30Z",
        kind="status-updates",
    )
    return Case("cloudflare-2026-02-20", "Elevated errors", "Cloudflare", "development", (status,))


class FakeBlob:
    def __init__(self, data: bytes):
        self.data = data

    def readall(self) -> bytes:
        return self.data


class FakeContainer:
    def __init__(self, data: bytes = b""):
        self.data = data
        self.uploaded: list[tuple[str, bytes, bool]] = []

    def download_blob(self, name: str) -> FakeBlob:
        return FakeBlob(self.data)

    def upload_blob(self, name: str, data: bytes, overwrite: bool = False) -> None:
        self.uploaded.append((name, data, overwrite))


def test_ingest_writes_the_cut_evidence_locally_and_to_blob(tmp_path):
    sources, extracted = FakeContainer(SNAPSHOT), FakeContainer()

    ingest_evidence(case(), out_dir=tmp_path, client=sources, uploader=extracted)

    local = (tmp_path / "cloudflare-2026-02-20.json").read_bytes()
    assert local == evidence_json(cut(case(), SNAPSHOT))
    assert extracted.uploaded == [("evidence/cloudflare-2026-02-20.json", local, False)]


def test_ingest_writes_nothing_when_a_source_fails_its_hash(tmp_path):
    tampered = FakeContainer(SNAPSHOT.replace(b"Errors.", b"Errors!"))
    extracted = FakeContainer()

    with pytest.raises(SourceMismatch):
        ingest_evidence(case(), out_dir=tmp_path, client=tampered, uploader=extracted)

    assert list(tmp_path.iterdir()) == []
    assert extracted.uploaded == []


def test_ingest_prints_counts_not_text():
    lines = summary(cut(case(), SNAPSHOT))

    assert lines[0] == "cloudflare-2026-02-20: 2 updates (resolved 2026-02-20T23:50:58Z), dropped 1"
    assert lines[1:] == ["  report: 1"]
    assert not any(PLANTED_CAUSE in line or "Errors." in line for line in lines)

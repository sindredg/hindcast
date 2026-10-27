import hashlib

import pytest

from hindcast import storage
from hindcast.cases import SourceFile
from hindcast.storage import SourceMismatch, download_source, upload_bytes, upload_source

CONTENT = b'{"incident": "snapshot"}\n'


def source(content: bytes = CONTENT) -> SourceFile:
    return SourceFile(
        doc_id="cloudflare-status-2026-02-20",
        filename="cloudflare-status-2026-02-20.json",
        url="https://www.cloudflarestatus.com/api/v2/incidents/kwy3dt82bwbt.json",
        licence="Copyright Cloudflare; not redistributed",
        attribution="Cloudflare",
        sha256=hashlib.sha256(content).hexdigest(),
        retrieved_at="2026-10-25T21:09:30Z",
        kind="status-updates",
    )


class FakeDownload:
    def __init__(self, data: bytes):
        self.data = data

    def readall(self) -> bytes:
        return self.data


class FakeContainer:
    """Records blob names and upload options; serves fixed bytes."""

    def __init__(self, data: bytes = CONTENT):
        self.data = data
        self.downloaded: list[str] = []
        self.uploaded: list[tuple[str, bytes, bool]] = []

    def download_blob(self, name: str) -> FakeDownload:
        self.downloaded.append(name)
        return FakeDownload(self.data)

    def upload_blob(self, name: str, data: bytes, overwrite: bool = False) -> None:
        self.uploaded.append((name, data, overwrite))


def test_download_returns_bytes_that_match_the_registry():
    assert download_source("cloudflare-2026-02-20", source(), client=FakeContainer()) == CONTENT


def test_download_refuses_bytes_that_do_not_match():
    tampered = FakeContainer(CONTENT.replace(b"snapshot", b"snapsh0t"))

    with pytest.raises(SourceMismatch, match="cloudflare-status-2026-02-20"):
        download_source("cloudflare-2026-02-20", source(), client=tampered)


def test_blob_name_is_case_then_filename():
    client = FakeContainer()

    download_source("cloudflare-2026-02-20", source(), client=client)

    assert client.downloaded == ["cloudflare-2026-02-20/cloudflare-status-2026-02-20.json"]


def test_upload_does_not_overwrite_by_default():
    client = FakeContainer()

    upload_bytes("extracted", "evidence/c.json", b"{}", client=client)

    assert client.uploaded == [("evidence/c.json", b"{}", False)]


def test_upload_overwrites_only_when_asked():
    client = FakeContainer()

    upload_bytes("extracted", "evidence/c.json", b"{}", overwrite=True, client=client)

    assert client.uploaded == [("evidence/c.json", b"{}", True)]


def test_upload_source_uses_the_sources_container_and_never_overwrites(monkeypatch):
    client, names = FakeContainer(), []
    monkeypatch.setattr(storage, "container", lambda name: names.append(name) or client)

    upload_source("library", "aws-2025-10-20.html", b"<html></html>")

    assert names == ["sources"]
    assert client.uploaded == [("library/aws-2025-10-20.html", b"<html></html>", False)]

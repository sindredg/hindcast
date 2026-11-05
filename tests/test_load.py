"""Loading a fresh environment from the local data tree (decision 0028)."""

import hashlib
import json
from pathlib import Path

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from hindcast import load, runtime
from hindcast.cases import Case, SourceFile
from hindcast.library import LibraryDocument
from hindcast.storage import SourceMismatch

STATUS = b'{"incident": {"incident_updates": []}}'
CHART = b"\x89PNG chart"
PAGE = b"<html>postmortem</html>"
EVIDENCE = b'{"updates": []}'
EXTRACT = b'{"sections": [], "figures": []}'


class Download:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readall(self) -> bytes:
        return self.data


class Container:
    def __init__(self, log: list[str], label: str, blobs: dict[str, bytes] | None = None) -> None:
        self.blobs = dict(blobs or {})
        self.log = log
        self.label = label

    def download_blob(self, name: str) -> Download:
        if name not in self.blobs:
            raise ResourceNotFoundError(name)
        return Download(self.blobs[name])

    def upload_blob(self, name: str, data: bytes, overwrite: bool = False) -> None:
        if name in self.blobs and not overwrite:
            raise ResourceExistsError(name)
        self.blobs[name] = data
        self.log.append(f"{self.label}/{name}")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(doc_id: str, filename: str, data: bytes, kind: str) -> SourceFile:
    return SourceFile(
        doc_id=doc_id,
        filename=filename,
        url="https://example.com/",
        licence="test",
        attribution="test",
        sha256=_sha(data),
        retrieved_at="2026-11-05T00:00:00Z",
        kind=kind,  # type: ignore[arg-type]
    )


def _case(case_id: str, role: str, sources: tuple[SourceFile, ...]) -> Case:
    return Case(
        case_id=case_id,
        title="An outage",
        provider="Cloudflare",
        role=role,  # type: ignore[arg-type]
        started_at="2026-02-20T00:00:00Z",
        sources=sources,
    )


CASES = {
    "case-a": _case(
        "case-a",
        "development",
        (
            _source("status", "status.json", STATUS, "status-updates"),
            _source("chart", "chart.png", CHART, "chart"),
        ),
    ),
    # An injection copy reuses the development case's status file.
    "case-a-inject": _case(
        "case-a-inject", "injection", (_source("status", "status.json", STATUS, "status-updates"),)
    ),
}

LIBRARY = {
    "doc-a": LibraryDocument(
        doc_id="doc-a",
        provider="Cloudflare",
        title="A postmortem",
        url="https://example.com/doc-a",
        published_at="2020-01-01",
        filename="doc-a.html",
        sha256=_sha(PAGE),
        retrieved_at="2026-10-27T00:00:00Z",
        licence="test",
        attribution="test",
        kind="other-provider",
        serves=("case-a",),
        reason="test",
    )
}


def _tree(root: Path, status: bytes = STATUS) -> Path:
    files = {
        "data/sources/case-a/status.json": status,
        "data/charts/case-a/chart.png": CHART,
        "data/sources/library/doc-a.html": PAGE,
        "build/evidence/case-a.json": EVIDENCE,
        "build/extracted/library/doc-a.json": EXTRACT,
    }
    for name, data in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    return root


def _containers(log: list[str], **existing: dict[str, bytes]) -> dict[str, Container]:
    return {
        name: Container(log, name, existing.get(name))
        for name in ("sources", "extracted", "runtime")
    }


def _load(root: Path, containers: dict[str, Container], built: list[str] | None = None) -> dict:
    return load.load(
        CASES,
        LIBRARY,
        root=root,
        sources=containers["sources"],
        extracted=containers["extracted"],
        runtime_client=containers["runtime"],
        build_indexes=(lambda: built.append("indexes")) if built is not None else None,
    )


def test_load_uploads_sources_extracts_and_runtime(tmp_path):
    log: list[str] = []
    built: list[str] = []
    containers = _containers(log)
    counts = _load(_tree(tmp_path), containers, built)
    assert sorted(containers["sources"].blobs) == [
        "case-a/chart.png",
        "case-a/status.json",
        "library/doc-a.html",
    ]
    assert containers["extracted"].blobs == {"library/doc-a.json": EXTRACT}
    manifest = json.loads(containers["runtime"].blobs[runtime.MANIFEST])
    assert manifest == {
        "build/evidence/case-a.json": _sha(EVIDENCE),
        "build/extracted/library/doc-a.json": _sha(EXTRACT),
    }
    assert counts == {"uploaded": 7, "same": 0}
    assert built == ["indexes"]


def test_injection_cases_are_not_uploaded(tmp_path):
    containers = _containers([])
    _load(_tree(tmp_path), containers)
    assert not any(name.startswith("case-a-inject/") for name in containers["sources"].blobs)


def test_load_refuses_a_source_that_differs_from_the_registry(tmp_path):
    log: list[str] = []
    with pytest.raises(SourceMismatch, match="case-a/status.json"):
        _load(_tree(tmp_path, status=b"captured again"), _containers(log))
    # Every source is checked before the first upload.
    assert log == []


def test_load_refuses_a_missing_source(tmp_path):
    (_tree(tmp_path) / "data/charts/case-a/chart.png").unlink()
    with pytest.raises(SourceMismatch, match="case-a/chart.png"):
        _load(tmp_path, _containers([]))


def test_load_refuses_a_different_blob(tmp_path):
    log: list[str] = []
    containers = _containers(log, extracted={"library/doc-a.json": b'{"other": true}'})
    with pytest.raises(load.BlobDiffers, match="library/doc-a.json"):
        _load(_tree(tmp_path), containers)
    assert containers["extracted"].blobs["library/doc-a.json"] == b'{"other": true}'


def test_load_skips_an_equal_blob(tmp_path):
    containers = _containers([], sources={"library/doc-a.html": PAGE})
    counts = _load(_tree(tmp_path), containers)
    assert counts == {"uploaded": 6, "same": 1}


def test_manifest_is_uploaded_last(tmp_path):
    log: list[str] = []
    _load(_tree(tmp_path), _containers(log))
    assert log[-1] == f"runtime/{runtime.MANIFEST}"


def test_upload_once_compares_bytes_not_names():
    client = Container([], "runtime", {"a.json": b"{}"})
    assert load.upload_once(client, "a.json", b"{}") == "same"
    with pytest.raises(load.BlobDiffers):
        load.upload_once(client, "a.json", b"")

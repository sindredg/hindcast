"""The page's runtime files from Blob and its stored runs (decision 0028)."""

import hashlib
import json
from pathlib import Path

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from hindcast import runtime


class Download:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readall(self) -> bytes:
        return self.data


class Container:
    """In-memory stand-in for a ContainerClient."""

    def __init__(self, blobs: dict[str, bytes] | None = None, fail_on: int | None = None) -> None:
        self.blobs = dict(blobs or {})
        self.fail_on = fail_on
        self.downloads = 0

    def download_blob(self, name: str) -> Download:
        self.downloads += 1
        if self.fail_on is not None and self.downloads == self.fail_on:
            raise ConnectionError("dropped")
        if name not in self.blobs:
            raise ResourceNotFoundError(name)
        return Download(self.blobs[name])

    def upload_blob(self, name: str, data: bytes, overwrite: bool = False) -> None:
        if name in self.blobs and not overwrite:
            raise ResourceExistsError(name)
        self.blobs[name] = data

    def list_blob_names(self) -> list[str]:
        return sorted(self.blobs)


FILES = {
    "build/evidence/case-a.json": b'{"updates": []}',
    "build/extracted/library/doc-a.json": b'{"sections": [], "figures": []}',
    "build/injection/planted-chart.json": b'{"description": "chart"}',
}


def _uploaded(files: dict[str, bytes] = FILES) -> Container:
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    return Container({**files, runtime.MANIFEST: json.dumps(manifest).encode()})


def test_write_manifest_lists_every_runtime_file(tmp_path):
    for name, data in FILES.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(data)
    (tmp_path / "build/investigations/case-a").mkdir(parents=True)
    (tmp_path / "build/investigations/case-a/run.json").write_bytes(b"{}")
    manifest = runtime.write_manifest(tmp_path)
    assert manifest == {name: hashlib.sha256(data).hexdigest() for name, data in FILES.items()}


def test_materialize_writes_every_manifest_file(tmp_path):
    assert runtime.materialize(_uploaded(), tmp_path) == len(FILES)
    for name, data in FILES.items():
        assert (tmp_path / name).read_bytes() == data


def test_materialize_refuses_a_changed_file(tmp_path):
    client = _uploaded()
    client.blobs["build/evidence/case-a.json"] = b'{"updates": ["planted"]}'
    with pytest.raises(runtime.RuntimeMismatch, match="build/evidence/case-a.json"):
        runtime.materialize(client, tmp_path)
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_materialize_leaves_no_partial_tree(tmp_path):
    # The manifest is the first download; the third is the second file.
    client = _uploaded()
    client.fail_on = 3
    with pytest.raises(ConnectionError):
        runtime.materialize(client, tmp_path)
    # build/ may exist; no file in it does, staged or moved.
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_materialize_refuses_a_name_outside_the_runtime_paths(tmp_path):
    client = _uploaded({"../outside.json": b"{}"})
    with pytest.raises(runtime.RuntimeMismatch, match="outside"):
        runtime.materialize(client, tmp_path)


def test_materialize_refuses_without_a_manifest(tmp_path):
    with pytest.raises(ResourceNotFoundError):
        runtime.materialize(Container(dict(FILES)), tmp_path)


def test_store_run_refuses_to_overwrite(tmp_path):
    run = tmp_path / "build/investigations/case-a/run.json"
    run.parent.mkdir(parents=True)
    run.write_bytes(b'{"status": "complete"}')
    client = Container()
    assert runtime.store_run(client, tmp_path, run) == "build/investigations/case-a/run.json"
    with pytest.raises(ResourceExistsError):
        runtime.store_run(client, tmp_path, run)


def test_fetch_runs_round_trips(tmp_path):
    names = {
        "build/investigations/case-a/run.json": b'{"status": "complete"}',
        "eval/investigations/case-a/challenges/q.json": b'{"question": "why"}',
    }
    client = Container(names)
    fetched = runtime.fetch_runs(client, tmp_path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in fetched) == sorted(names)
    # A second fetch finds the same bytes and writes nothing new.
    assert runtime.fetch_runs(client, tmp_path) == []


def test_fetch_runs_refuses_a_name_outside_the_run_paths(tmp_path):
    with pytest.raises(runtime.RuntimeMismatch, match="src/hindcast/app.py"):
        runtime.fetch_runs(Container({"src/hindcast/app.py": b"print()"}), tmp_path)


def test_fetch_runs_refuses_different_bytes_under_an_existing_name(tmp_path):
    existing = tmp_path / "build/investigations/case-a/run.json"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b'{"status": "complete"}')
    client = Container({"build/investigations/case-a/run.json": b'{"status": "incomplete"}'})
    with pytest.raises(runtime.RuntimeMismatch):
        runtime.fetch_runs(client, tmp_path)
    assert existing.read_bytes() == b'{"status": "complete"}'


def test_runtime_paths_are_relative(tmp_path):
    assert all(not Path(p).is_absolute() for p in runtime.RUNTIME_PATHS)


def test_materialize_writes_only_under_build(tmp_path):
    # The image: /app is root's and read-only for the runtime user; only
    # build/ is writable.
    root = tmp_path / "app"
    (root / "build").mkdir(parents=True)
    root.chmod(0o555)
    try:
        assert runtime.materialize(_uploaded(), root) == len(FILES)
    finally:
        root.chmod(0o755)
    for name, data in FILES.items():
        assert (root / name).read_bytes() == data
    assert sorted(p.name for p in root.iterdir()) == ["build"]


# Review finding: the path guards had no test that reached them.


def test_store_run_refuses_a_path_outside_the_run_paths(tmp_path):
    path = tmp_path / "build/evidence/x.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{}")
    client = Container()
    with pytest.raises(runtime.RuntimeMismatch, match="outside the run paths"):
        runtime.store_run(client, tmp_path, path)
    assert client.blobs == {}


@pytest.mark.parametrize("name", ["build/investigations/../../src/x.py", "/etc/x"])
def test_fetch_runs_refuses_a_name_that_leaves_the_run_paths(tmp_path, name):
    with pytest.raises(runtime.RuntimeMismatch):
        runtime.fetch_runs(Container({name: b"print()"}), tmp_path)
    assert not (tmp_path / "src").exists() and not list(tmp_path.rglob("x.py"))


@pytest.mark.parametrize("name", ["build/evidence/../../src/x.py", "/etc/x"])
def test_materialize_refuses_a_name_that_leaves_the_runtime_paths(tmp_path, name):
    client = _uploaded({name: b"{}"})
    with pytest.raises(runtime.RuntimeMismatch):
        runtime.materialize(client, tmp_path)
    assert not (tmp_path / "src").exists() and not list(tmp_path.rglob("x.py"))

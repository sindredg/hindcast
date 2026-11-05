"""The deployed page's runtime files and stored runs, in Blob Storage (decision 0028).

The investigator reads its evidence and library extracts from build/ by
relative path. In the image, build/ starts empty, so the page downloads those
files from the "runtime" container into its working directory before the
first run, checking each against the manifest the load command wrote. The
page's runs and challenges go to the "runs" container, since the container's
disk is gone when the app scales to zero.

The manifest catches a partial or corrupted upload. It does not stop someone
who can write to the storage account from replacing a file and its manifest
together.
"""

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Protocol

from azure.storage.blob import ContainerClient

from hindcast.storage import BlobContainer, Blobs

RUNTIME = "runtime"
RUNS = "runs"
MANIFEST = "manifest.json"
# What the investigator, the challenge, and the injection cases read from build/.
RUNTIME_PATHS = (
    "build/evidence",
    "build/extracted/library",
    "build/injection/library",
    "build/injection/planted-chart.json",
)
# Where results and challenges live: the page's own runs, and challenges next
# to a committed result.
RUN_PATHS = ("build/investigations", "eval/investigations")


class ListingContainer(BlobContainer, Protocol):
    def list_blob_names(self) -> Iterable[str]: ...


class RuntimeMismatch(ValueError):
    """A blob's name or bytes are not what the manifest or the run paths allow."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _under(name: str, prefixes: tuple[str, ...]) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    return any(name == p or name.startswith(p + "/") for p in prefixes)


def runtime_files(root: Path) -> list[Path]:
    """Every file under RUNTIME_PATHS, relative to root."""
    files: list[Path] = []
    for entry in RUNTIME_PATHS:
        path = root / entry
        if path.is_file():
            files.append(Path(entry))
        elif path.is_dir():
            files += [p.relative_to(root) for p in path.rglob("*") if p.is_file()]
    return sorted(files)


def write_manifest(root: Path) -> dict[str, str]:
    """Relative path to SHA-256 for every runtime file under root."""
    return {p.as_posix(): _sha256((root / p).read_bytes()) for p in runtime_files(root)}


def materialize(client: Blobs, root: Path) -> int:
    """Download every file the manifest lists into root, or nothing at all.

    Each file is checked against its SHA-256 in a staging directory first;
    only when every file has passed are they moved into place.
    """
    manifest: dict[str, str] = json.loads(client.download_blob(MANIFEST).readall())
    for name in manifest:
        if not _under(name, RUNTIME_PATHS):
            raise RuntimeMismatch(f"{name}: outside the runtime paths")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix=".runtime-") as staging:
        for name, digest in sorted(manifest.items()):
            data = client.download_blob(name).readall()
            if _sha256(data) != digest:
                raise RuntimeMismatch(f"{name}: does not match the manifest")
            staged = Path(staging) / name
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
        for name in sorted(manifest):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(Path(staging) / name, target)
    return len(manifest)


def store_run(client: Blobs, root: Path, path: Path) -> str:
    """Upload a result or challenge file under its path relative to root, never over another."""
    name = path.relative_to(root).as_posix()
    if not _under(name, RUN_PATHS):
        raise RuntimeMismatch(f"{name}: outside the run paths")
    client.upload_blob(name, path.read_bytes(), overwrite=False)
    return name


def fetch_runs(client: ListingContainer | ContainerClient, root: Path) -> list[Path]:
    """Download every stored run into root; returns the files written.

    A file already there with the same bytes is skipped; one with other bytes
    is refused, so a stored run never replaces a different local one.
    """
    written: list[Path] = []
    for name in client.list_blob_names():
        if not _under(name, RUN_PATHS):
            raise RuntimeMismatch(f"{name}: outside the run paths")
        data = client.download_blob(name).readall()
        target = root / name
        if target.exists():
            if target.read_bytes() != data:
                raise RuntimeMismatch(f"{name}: differs from the local file")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return written

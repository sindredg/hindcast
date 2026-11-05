"""Fill a fresh environment from the operator's local data tree (decision 0028).

    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.load [--skip-index]

Uploads every case and library source the registries pin, the library
extracts the index build checks against, and the page's runtime files with
their manifest, then builds the library index and the injection index.
Nothing is re-extracted: the files are the ones the evidence, the keys, and
the results were made from.

Every source is checked against its registry SHA-256 before the first
upload. A blob that already holds the same bytes is skipped; one that holds
other bytes is refused, never overwritten. The runtime manifest goes last,
so the page never reads a manifest whose files are not all there.
Prints counts and names, never file contents.
"""

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient

from hindcast import runtime
from hindcast.cases import Case
from hindcast.library import LibraryDocument
from hindcast.storage import SOURCES, BlobContainer, SourceMismatch

EXTRACTED = "extracted"
# A fake in tests, the SDK's client otherwise.
type Blobs = BlobContainer | ContainerClient
EXTRACTS_DIR = Path("build/extracted/library")


class BlobDiffers(ValueError):
    """A blob already holds other bytes under the name being loaded."""


def upload_once(client: Blobs, name: str, data: bytes) -> str:
    """Upload data under name; "same" when the blob already holds these bytes."""
    try:
        existing = client.download_blob(name).readall()
    except ResourceNotFoundError:
        client.upload_blob(name, data, overwrite=False)
        return "uploaded"
    if existing != data:
        raise BlobDiffers(f"{name}: the stored blob differs; delete it by hand to replace it")
    return "same"


def source_files(
    cases: Mapping[str, Case], library: Mapping[str, LibraryDocument], root: Path
) -> list[tuple[str, Path, str]]:
    """(blob name, local path, pinned SHA-256) for every source the registries pin.

    Charts are committed under data/charts/, captured pages sit under
    data/sources/. An injection copy's status file is the development
    case's, by hash, and is not uploaded again.
    """
    files: list[tuple[str, Path, str]] = []
    for case in cases.values():
        if case.role == "injection":
            continue
        for source in case.sources:
            base = "data/charts" if source.kind == "chart" else "data/sources"
            name = f"{case.case_id}/{source.filename}"
            files.append((name, root / base / name, source.sha256))
    for doc in library.values():
        name = f"library/{doc.filename}"
        files.append((name, root / "data/sources" / name, doc.sha256))
    return sorted(files)


def _check_sources(files: list[tuple[str, Path, str]]) -> None:
    for name, path, sha256 in files:
        if not path.is_file():
            raise SourceMismatch(f"{name}: missing at {path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise SourceMismatch(f"{name}: the local file does not match the registry")


def load(
    cases: Mapping[str, Case],
    library: Mapping[str, LibraryDocument],
    *,
    root: Path,
    build_indexes: Callable[[], None] | None,
    sources: BlobContainer | None = None,
    extracted: BlobContainer | None = None,
    runtime_client: BlobContainer | None = None,
) -> dict[str, int]:
    """Upload everything, then build the indexes; counts of uploaded and same blobs.

    The clients default to the configured account's containers.
    """
    files = source_files(cases, library, root)
    _check_sources(files)
    from hindcast.storage import container

    to_sources = sources or container(SOURCES)
    to_extracted = extracted or container(EXTRACTED)
    to_runtime = runtime_client or container(runtime.RUNTIME)
    counts = {"uploaded": 0, "same": 0}

    def put(client: Blobs, name: str, data: bytes) -> None:
        counts[upload_once(client, name, data)] += 1

    for name, path, _ in files:
        put(to_sources, name, path.read_bytes())
    for path in sorted((root / EXTRACTS_DIR).glob("*.json")):
        put(to_extracted, f"library/{path.name}", path.read_bytes())
    manifest = runtime.write_manifest(root)
    for name in manifest:
        put(to_runtime, name, (root / name).read_bytes())
    document = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    put(to_runtime, runtime.MANIFEST, document.encode())
    if build_indexes is not None:
        build_indexes()
    return counts


def _build_indexes() -> None:
    from hindcast import index, injection

    if index.main(["build", "--dimensions", "1024"]) != 0:
        raise RuntimeError("the library index build failed")
    if injection.main(["index"]) != 0:
        raise RuntimeError("the injection index build failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.load")
    parser.add_argument(
        "--skip-index", action="store_true", help="upload only; the indexes already exist"
    )
    args = parser.parse_args(argv)

    from hindcast.cases import load_cases
    from hindcast.library import load_library

    cases = load_cases()
    library = load_library(Path("data/library.yaml"), cases)
    counts = load(
        cases, library, root=Path("."), build_indexes=None if args.skip_index else _build_indexes
    )
    print(f"blobs uploaded: {counts['uploaded']}, already there: {counts['same']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

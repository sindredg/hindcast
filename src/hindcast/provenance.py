"""What the code and prompts of a run are, when there is no Git checkout.

The deployed image has no .git and no git executable. CI writes the commit,
the tree of src/, and the Git blob hash of each prompt and registry into
/app/provenance.json at build time (decision 0028), and a run from the page
records those instead of reading Git.

CI writes the manifest before each image build with

    python3 src/hindcast/provenance.py provenance.json

The module uses the standard library only, so the image jobs run it with the
runner's Python, without the project's environment.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

IMAGE_MANIFEST = Path("/app/provenance.json")
MANIFEST_VAR = "HINDCAST_PROVENANCE_FILE"
# What the image's provenance covers: the code, and the files a run records
# by blob hash (the prompts and the registries).
CODE_PATHS = ("src", "pyproject.toml", "uv.lock")
BLOB_PATHS = ("prompts", "data/cases.yaml", "data/library.yaml")


def image_manifest(env: Mapping[str, str] = os.environ) -> dict | None:
    """The image's provenance manifest, or None outside the image."""
    path = Path(env.get(MANIFEST_VAR, "") or IMAGE_MANIFEST)
    if not path.is_file():
        return None
    return json.loads(path.read_bytes())


def git_blob_hash(data: bytes) -> str:
    """The hash `git hash-object` prints for these bytes."""
    # Git's object ID, not a security hash: it has to match what git records.
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git") or "git"
    # Fixed arguments and a repository path, never user input.
    return subprocess.run(  # noqa: S603
        [git, "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def build_manifest(repo: Path = Path(".")) -> dict:
    """The commit, the src/ tree, and the blob of each prompt and registry, from a clean tree.

    Refused when any of those paths has uncommitted changes: the manifest
    would name files the image does not hold.
    """
    status = _git(repo, "status", "--porcelain", "--", *CODE_PATHS, *BLOB_PATHS)
    commit = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    tree = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD:src")
    listing = _git(repo, "ls-tree", "-r", "HEAD", "--", *BLOB_PATHS)
    if any(r.returncode != 0 for r in (status, commit, tree, listing)):
        raise RuntimeError("cannot read the Git state of the code")
    if status.stdout.strip():
        raise RuntimeError("the code or prompts have uncommitted changes")
    blobs = {}
    for line in listing.stdout.splitlines():
        meta, path = line.split("\t", 1)
        blobs[path] = meta.split()[2]
    return {"commit": commit.stdout.strip(), "src_tree": tree.stdout.strip(), "blobs": blobs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="provenance.py")
    parser.add_argument("out", type=Path, help="where to write the manifest")
    args = parser.parse_args(argv)
    manifest = build_manifest()
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"commit {manifest['commit']}, {len(manifest['blobs'])} blobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

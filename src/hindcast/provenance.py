"""What the code and prompts of a run are, when there is no Git checkout.

The deployed image has no .git and no git executable. CI writes the commit,
the tree of src/, and the Git blob hash of each prompt and registry into
/app/provenance.json at build time (decision 0028), and a run from the page
records those instead of reading Git.
"""

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path

IMAGE_MANIFEST = Path("/app/provenance.json")
MANIFEST_VAR = "HINDCAST_PROVENANCE_FILE"


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

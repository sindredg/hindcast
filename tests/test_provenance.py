"""Provenance inside the image, where there is no Git checkout (decision 0028)."""

import json
from pathlib import Path

import pytest

from hindcast import agent, investigate, provenance
from hindcast.evaluation.prior import _git

COMMIT = "a" * 40
TREE = "b" * 40


def _manifest(tmp_path: Path, blobs: dict[str, str], monkeypatch) -> Path:
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps({"commit": COMMIT, "src_tree": TREE, "blobs": blobs}))
    monkeypatch.setenv(provenance.MANIFEST_VAR, str(path))
    return path


def test_git_blob_hash_matches_git(tmp_path):
    file = tmp_path / "prompt.md"
    file.write_bytes(b"Investigate the outage.\n")
    expected = _git(tmp_path, "hash-object", str(file)).stdout.strip()
    assert provenance.git_blob_hash(file.read_bytes()) == expected


def test_image_manifest_is_none_without_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv(provenance.MANIFEST_VAR, str(tmp_path / "missing.json"))
    assert provenance.image_manifest() is None


def test_code_provenance_reads_the_image_manifest(tmp_path, monkeypatch):
    _manifest(tmp_path, {}, monkeypatch)
    # tmp_path is not a Git repository, as in the image.
    assert investigate.code_provenance(tmp_path) == {
        "commit": COMMIT,
        "dirty": False,
        "src_tree": TREE,
        "source": "image",
    }


def test_code_provenance_without_a_git_binary(tmp_path, monkeypatch):
    # The slim image has no git executable at all.
    monkeypatch.setattr("hindcast.evaluation.prior.shutil.which", lambda _: "/nonexistent/git")
    _manifest(tmp_path, {}, monkeypatch)
    assert investigate.code_provenance(tmp_path)["source"] == "image"


def test_no_git_and_no_manifest_still_raises(tmp_path, monkeypatch):
    monkeypatch.setenv(provenance.MANIFEST_VAR, str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError, match="Git state"):
        investigate.code_provenance(tmp_path)


def test_prompt_provenance_reads_the_image_manifest(tmp_path, monkeypatch):
    prompt = tmp_path / "prompts" / "investigator.md"
    prompt.parent.mkdir()
    prompt.write_bytes(b"Investigate the outage.\n")
    blob = provenance.git_blob_hash(prompt.read_bytes())
    _manifest(tmp_path, {"prompts/investigator.md": blob}, monkeypatch)
    assert agent.prompt_provenance(Path("prompts/investigator.md"), tmp_path) == {
        "blob": blob,
        "dirty": False,
    }


def test_prompt_provenance_marks_a_changed_prompt_dirty(tmp_path, monkeypatch):
    prompt = tmp_path / "prompts" / "investigator.md"
    prompt.parent.mkdir()
    prompt.write_bytes(b"Investigate the outage.\n")
    _manifest(tmp_path, {"prompts/investigator.md": "c" * 40}, monkeypatch)
    recorded = agent.prompt_provenance(Path("prompts/investigator.md"), tmp_path)
    assert recorded["dirty"] is True
    assert "blob" not in recorded

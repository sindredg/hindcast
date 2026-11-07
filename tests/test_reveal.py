"""The reveal keeps decision 0022's order: nothing sealed is read before every check passes."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from hindcast.cases import Case, SourceFile
from hindcast.keys import key_json, load_key
from hindcast.reveal import RevealRefused, check_ready, published_at, reveal

KEY = Path("eval/keys/github-2026-11-04-actions.json")
CASE_ID = "c-1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_file(resolved_updated_at: str) -> bytes:
    return json.dumps(
        {
            "incident_updates": [
                {
                    "status": "resolved",
                    "created_at": "2026-11-04T17:01:11Z",
                    "updated_at": resolved_updated_at,
                    "body": "summary",
                }
            ]
        }
    ).encode()


def source(filename: str, data: bytes) -> SourceFile:
    return SourceFile(
        "pm", filename, "https://example.test/x.json", "l", "a", sha(data), "t", "postmortem"
    )


def make_tree(
    tmp_path: Path,
    *,
    published: str = "2026-11-07T01:04:38Z",
    role: Literal["sealed", "revealed"] = "revealed",
):
    """A case with a frozen key and labels, evidence, a snapshot, and one sealed file."""
    key = load_key(KEY)
    key_data = key_json(type(key)(**{**key.__dict__, "case_id": CASE_ID}))
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / f"{CASE_ID}.json").write_bytes(key_data)
    (keys / "frozen.json").write_text(json.dumps({CASE_ID: sha(key_data)}))
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / f"{CASE_ID}.json").write_text("{}")
    (labels / "frozen.json").write_text(json.dumps({CASE_ID: sha(b"{}")}))
    evidence = {
        "case_id": CASE_ID,
        "provider": "GitHub",
        "title": "t",
        "started_at": "2026-11-04T16:05:31Z",
        "updates": [
            {
                "update_id": f"{CASE_ID}/u1",
                "time": "2026-11-04T16:05:31Z",
                "status": "investigating",
                "text": "We are investigating delays.",
            }
        ],
        "dropped": [],
        "charts": [],
    }
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    evidence_data = json.dumps(evidence).encode()
    (evidence_dir / f"{CASE_ID}.json").write_bytes(evidence_data)
    postmortem = snapshot_file(published)
    (tmp_path / "sources" / CASE_ID).mkdir(parents=True)
    (tmp_path / "sources" / CASE_ID / "pm.json").write_bytes(postmortem)
    chunks = json.dumps({"chunks": [{"id": "lib/c1", "content": "An unrelated page."}]}).encode()
    (tmp_path / "snap.json").write_bytes(chunks)
    (tmp_path / "snaps.json").write_text(
        json.dumps({"snapshots": [{"case_id": CASE_ID, "sha256": sha(chunks)}]})
    )
    result = json.dumps({"status": "complete", "usage": {"seconds": 1.0}}).encode()
    (tmp_path / "sealed" / CASE_ID).mkdir(parents=True)
    (tmp_path / "sealed" / CASE_ID / "r.json").write_bytes(result)
    seal = {
        "case_id": CASE_ID,
        "attempt": 1,
        "deployment": "d",
        "model_name": "m",
        "model_version": "v",
        "agent_name": "a",
        "agent_version": "1",
        "code_commit": "0" * 40,
        "evidence_sha256": sha(evidence_data),
        "library": True,
        "sealed_at": "2026-11-04T17:20:23Z",
        "file": "r.json",
        "sha256": sha(result),
        "blob": None,
        "status": "complete",
    }
    (tmp_path / "seals.json").write_text(json.dumps({"seals": [seal]}))
    case = Case(
        CASE_ID, "t", "GitHub", role, "2026-11-04T16:05:31Z", (source("pm.json", postmortem),)
    )
    paths = {
        "keys": (keys / f"{CASE_ID}.json", keys / "frozen.json"),
        "labels": (labels / f"{CASE_ID}.json", labels / "frozen.json"),
        "evidence_dir": evidence_dir,
        "sources_dir": tmp_path / "sources",
        "snapshot": (tmp_path / "snap.json", tmp_path / "snaps.json"),
    }
    return case, seal, paths


def do_reveal(tmp_path: Path, case: Case, paths: dict, clean=lambda: "c" * 40) -> dict:
    return reveal(
        case,
        seals_path=tmp_path / "seals.json",
        sealed_dir=tmp_path / "sealed",
        revealed_dir=tmp_path / "revealed",
        reveals_path=tmp_path / "reveals.json",
        ledger_path=tmp_path / "ledger" / "attempts.json",
        now=datetime(2026, 11, 7, 11, 0, tzinfo=UTC),
        clean=clean,
        **paths,
    )


def test_a_ready_case_is_revealed_and_recorded(tmp_path: Path) -> None:
    case, seal, paths = make_tree(tmp_path)

    record = do_reveal(tmp_path, case, paths)

    assert record["cause_published_at"] == "2026-11-07T01:04:38Z"
    assert record["code_commit"] == "c" * 40
    assert record["leak"]["hits"] == 0
    assert (tmp_path / "revealed" / CASE_ID / "r.json").read_bytes() == (
        tmp_path / "sealed" / CASE_ID / "r.json"
    ).read_bytes()
    assert json.loads((tmp_path / "seals.json").read_text())["seals"][0]["revealed"] is True
    ledger = json.loads((tmp_path / "ledger" / "attempts.json").read_text())["attempts"]
    assert [(e["run_id"], e["arm"], e["file"]) for e in ledger] == [
        ("sealed/c-1/d/a1", "sealed-d", "c-1/r.json")
    ]
    with pytest.raises(RevealRefused, match="revealed already"):
        do_reveal(tmp_path, case, paths)


@pytest.mark.parametrize(
    ("breakage", "message"),
    [
        ("role", "is a sealed case"),
        ("key", "differs from its frozen hash"),
        ("labels", "not frozen"),
        ("evidence", "not the evidence the seals were run on"),
        ("early", "not after the seal"),
        ("leak", "the leak check found"),
        ("snapshot", "does not match the hash"),
        ("sealed", "does not match its seal"),
        ("boundary", "not after the seal"),
        ("registry", "differs from its registry hash"),
        ("target", "a revealed file is never replaced"),
        ("unparsed", "not a result file"),
        ("dirty", "uncommitted"),
    ],
)
def test_each_broken_step_refuses_before_anything_is_written(
    tmp_path: Path, breakage: str, message: str
) -> None:
    published = {"early": "2026-11-04T17:00:00Z", "boundary": "2026-11-04T17:20:23Z"}.get(
        breakage, "2026-11-07T01:04:38Z"
    )
    case, seal, paths = make_tree(
        tmp_path, published=published, role="sealed" if breakage == "role" else "revealed"
    )
    if breakage == "key":
        paths["keys"][0].write_bytes(paths["keys"][0].read_bytes().replace(b"event", b"evenT"))
    if breakage == "labels":
        paths["labels"][0].unlink()
    if breakage == "evidence":
        path = paths["evidence_dir"] / f"{CASE_ID}.json"
        path.write_bytes(path.read_bytes().replace(b"delays", b"delayz"))
    if breakage == "leak":
        quote = load_key(paths["keys"][0]).root_cause.source_quote
        data = json.dumps({"chunks": [{"id": "lib/c1", "content": quote}]}).encode()
        paths["snapshot"][0].write_bytes(data)
        paths["snapshot"][1].write_text(
            json.dumps({"snapshots": [{"case_id": CASE_ID, "sha256": sha(data)}]})
        )
    if breakage == "snapshot":
        paths["snapshot"][0].write_bytes(b'{"chunks": [{"id": "x", "content": "changed"}]}')
    sealed_file = tmp_path / "sealed" / CASE_ID / "r.json"
    if breakage == "sealed":
        sealed_file.write_bytes(b'{"status": "completE"}')
    if breakage == "registry":
        pm = paths["sources_dir"] / CASE_ID / "pm.json"
        pm.write_bytes(pm.read_bytes() + b" ")
    if breakage == "target":
        (tmp_path / "revealed" / CASE_ID).mkdir(parents=True)
        (tmp_path / "revealed" / CASE_ID / "r.json").write_bytes(b"{}")
    if breakage == "unparsed":
        # Hashes as sealed, but carries no usage: refused before any write.
        data = b'{"status": "complete"}'
        sealed_file.write_bytes(data)
        seals = json.loads((tmp_path / "seals.json").read_text())
        seals["seals"][0]["sha256"] = sha(data)
        (tmp_path / "seals.json").write_text(json.dumps(seals))
    # A check before the sealed files must refuse without reading them: the
    # file is moved away, so a read would raise FileNotFoundError instead.
    if breakage not in ("sealed", "target", "unparsed"):
        sealed_file.rename(tmp_path / "moved.json")
    seals_before = (tmp_path / "seals.json").read_bytes()
    revealed_before = sorted((tmp_path / "revealed").rglob("*")) if breakage == "target" else []

    def dirty() -> str:
        raise RuntimeError("src: uncommitted or untracked changes")

    with pytest.raises(RevealRefused, match=message):
        do_reveal(tmp_path, case, paths, **({"clean": dirty} if breakage == "dirty" else {}))

    assert (tmp_path / "seals.json").read_bytes() == seals_before
    assert sorted((tmp_path / "revealed").rglob("*")) == revealed_before
    assert not (tmp_path / "reveals.json").exists()
    assert not (tmp_path / "ledger").exists()


def test_the_publication_time_comes_from_the_captured_file() -> None:
    data = snapshot_file("2026-11-07T01:04:38.642Z")
    pm = source("pm.json", data)

    assert published_at(pm, data, None)[0] == "2026-11-07T01:04:38Z"
    assert published_at(pm, data, "2026-11-07T01:04:38Z")[0] == "2026-11-07T01:04:38Z"
    with pytest.raises(RevealRefused, match="differs from the file"):
        published_at(pm, data, "2026-11-06T00:00:00Z")
    with pytest.raises(RevealRefused, match="no resolved update"):
        published_at(pm, b'{"incident_updates": []}', None)
    page = source("pm.html", b"<html></html>")
    with pytest.raises(RevealRefused, match="give --published-at"):
        published_at(page, b"<html></html>", None)
    assert published_at(page, b"", "2026-11-12T09:00:00Z")[1] == "stated on the postmortem page"


def test_check_ready_needs_a_sealed_file(tmp_path: Path) -> None:
    case, seal, paths = make_tree(tmp_path)

    with pytest.raises(RevealRefused, match="no sealed file"):
        check_ready(case, [seal | {"file": None}], **paths)

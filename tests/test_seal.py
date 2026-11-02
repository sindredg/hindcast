import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from hindcast import seal
from hindcast.cases import Case
from hindcast.evidence import evidence_json
from hindcast.seal import SealRefused, check_clean, check_may_seal, main
from test_investigate import (
    EVIDENCE,
    FINAL,
    SOURCE,
    FakeClient,
    call,
    final,
    response,
    stub_command,
)

SEALED = Case("seal", "Slow pages", "GitHub", "sealed", "2026-10-21T14:52:49Z", (SOURCE,))
SHOWCASE = Case("show", "Slow pages", "GitHub", "showcase", "2026-10-21T14:52:49Z", (SOURCE,))
NOW = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)


def attempt(status: str, deployment: str = "gpt-6-luna", library: bool = False) -> dict:
    return {"case_id": "seal", "deployment": deployment, "library": library, "status": status}


def test_second_seal_is_refused() -> None:
    seals = [attempt("complete")]

    with pytest.raises(SealRefused, match="already sealed"):
        check_may_seal(SEALED, seals, "gpt-6-luna", False)
    assert check_may_seal(SEALED, seals, "gpt-6.1-sol", False) == 1
    # The second seal, with the library tool, is its own series.
    assert check_may_seal(SEALED, seals, "gpt-6-luna", True) == 1


def test_an_incomplete_seal_is_final_too() -> None:
    with pytest.raises(SealRefused, match="already sealed"):
        check_may_seal(SEALED, [attempt("incomplete")], "gpt-6-luna", False)


def test_retry_rule() -> None:
    assert check_may_seal(SEALED, [attempt("no-result")] * 2, "gpt-6-luna", False) == 3
    with pytest.raises(SealRefused, match="3 attempts"):
        check_may_seal(SEALED, [attempt("no-result")] * 3, "gpt-6-luna", False)


def test_only_sealed_cases() -> None:
    with pytest.raises(SealRefused, match="not a sealed case"):
        check_may_seal(SHOWCASE, [], "gpt-6-luna", False)


def git(repo: Path, *args: str) -> str:
    config = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
    config += ["-c", "commit.gpgsign=false"]
    command = ["git", "-C", str(repo), *config, *args]
    done = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603, S607
    return done.stdout.strip()


def test_dirty_tree_is_refused(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "x.md").write_text("v1", encoding="utf-8")
    (tmp_path / "notes.md").write_text("v1", encoding="utf-8")
    git(tmp_path, "add", "prompts/x.md", "notes.md")
    git(tmp_path, "commit", "-q", "-m", "v1")
    head = git(tmp_path, "rev-parse", "HEAD")
    # A change outside what shapes the run does not block a seal.
    (tmp_path / "notes.md").write_text("v2", encoding="utf-8")
    assert check_clean(tmp_path) == head

    (tmp_path / "prompts" / "x.md").write_text("v2", encoding="utf-8")
    with pytest.raises(SealRefused, match="prompts/x.md"):
        check_clean(tmp_path)

    git(tmp_path, "checkout", "-q", "--", "prompts/x.md")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cases.yaml").write_text("new", encoding="utf-8")
    with pytest.raises(SealRefused, match="cases.yaml"):
        check_clean(tmp_path)


def test_library_registry_change_is_refused(tmp_path: Path) -> None:
    # The library registry decides what a sealed case's searches can return.
    git(tmp_path, "init", "-q")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "library.yaml").write_text("v1", encoding="utf-8")
    git(tmp_path, "add", "data/library.yaml")
    git(tmp_path, "commit", "-q", "-m", "v1")
    (tmp_path / "data" / "library.yaml").write_text("v2", encoding="utf-8")
    with pytest.raises(SealRefused, match="library.yaml"):
        check_clean(tmp_path)


class Uploads:
    """Records uploads; fails the first `failures` calls."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[tuple[str, str, bytes, bool]] = []

    def __call__(self, container: str, name: str, data: bytes, *, overwrite: bool = False) -> None:
        if self.failures:
            self.failures -= 1
            raise OSError("upload failed")
        self.calls.append((container, name, data, overwrite))


def stub_seal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: FakeClient, uploads: Uploads
) -> Path:
    """Point the seal command at a stub sealed case, temp files, and fake cloud calls."""
    stub_command(monkeypatch, tmp_path, client)
    (tmp_path / "evidence" / "seal.json").write_bytes(evidence_json(EVIDENCE))
    seals = tmp_path / "seals.json"
    seals.write_text('{"seals": []}\n', encoding="utf-8")
    monkeypatch.setattr(seal, "load_cases", lambda: {"seal": SEALED, "show": SHOWCASE})
    monkeypatch.setattr(seal, "SEALS", seals)
    monkeypatch.setattr(seal, "OUT_DIR", tmp_path / "sealed")
    monkeypatch.setattr(seal, "check_clean", lambda: "c" * 40)
    monkeypatch.setattr(seal, "upload_bytes", uploads)
    monkeypatch.setattr(seal, "_now", lambda: NOW)
    return seals


def entries(seals: Path) -> list[dict]:
    return json.loads(seals.read_text("utf-8"))["seals"]


def test_run_records_hash_then_uploads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    uploads = Uploads()
    seals = stub_seal(monkeypatch, tmp_path, FakeClient(response(call()), final()), uploads)

    assert main(["run", "seal"]) == 0

    [entry] = entries(seals)
    path = tmp_path / "sealed" / "seal" / entry["file"]
    data = path.read_bytes()
    assert entry["sha256"] == hashlib.sha256(data).hexdigest()
    assert entry["blob"] == f"sealed/seal/{entry['file']}"
    assert uploads.calls == [("extracted", entry["blob"], data, False)]
    assert entry["status"] == "complete"
    assert entry["attempt"] == 1
    assert entry["deployment"] == "gpt-6-luna"
    assert entry["model_version"] == "2026-09-22"
    assert entry["agent_name"] == "hindcast-investigator-gpt-6-luna"
    assert entry["code_commit"] == "c" * 40
    assert entry["evidence_sha256"] == hashlib.sha256(evidence_json(EVIDENCE)).hexdigest()
    # The second series: sealed with the library search.
    assert entry["library"] is True
    assert entry["sealed_at"] == "2026-11-01T10:00:00Z"
    assert set(entry) == set(seal.ENTRY_FIELDS)


def test_upload_retries_the_same_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    uploads = Uploads(failures=1)
    seals = stub_seal(monkeypatch, tmp_path, FakeClient(response(call()), final()), uploads)

    assert main(["run", "seal"]) == 1

    [entry] = entries(seals)
    assert entry["blob"] is None
    assert entry["sha256"]
    assert main(["upload", "seal", entry["file"]]) == 0
    [entry] = entries(seals)
    assert entry["blob"] == f"sealed/seal/{entry['file']}"
    assert len(uploads.calls) == 1

    # A changed file is not the sealed one.
    entry["blob"] = None
    seals.write_text(json.dumps({"seals": [entry]}), encoding="utf-8")
    (tmp_path / "sealed" / "seal" / entry["file"]).write_bytes(b"changed")
    with pytest.raises(SealRefused, match="does not match"):
        main(["upload", "seal", entry["file"]])
    assert len(uploads.calls) == 1


def test_output_has_no_investigation_text(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["claim"] = "SECRET-FINDING"
    stub_seal(monkeypatch, tmp_path, FakeClient(response(call()), final(document)), Uploads())

    main(["run", "seal"])

    out = capsys.readouterr().out
    assert "SECRET" not in out
    assert out.startswith("complete\n")
    assert "sha256 " in out


def test_output_has_only_the_reason_prefix(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A tool error echoes the model's arguments, a schema error the bad value.
    seals = stub_seal(
        monkeypatch, tmp_path, FakeClient(response(call("no_such_tool:SECRET-ARG"))), Uploads()
    )

    main(["run", "seal"])

    out = capsys.readouterr().out
    assert out.startswith("incomplete: tool-error\n")
    assert "SECRET-ARG" not in out
    assert entries(seals)[0]["status"] == "incomplete"


def test_raised_run_is_recorded_as_no_result(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seals = stub_seal(monkeypatch, tmp_path, FakeClient(RuntimeError("429 SECRET-BODY")), Uploads())

    assert main(["run", "seal"]) == 1

    [entry] = entries(seals)
    assert entry["status"] == "no-result"
    assert entry["file"] is None
    assert entry["sha256"] is None
    assert entry["blob"] is None
    assert "SECRET" not in capsys.readouterr().out
    # The model produced nothing, so another attempt is allowed.
    assert check_may_seal(SEALED, entries(seals), "gpt-6-luna", seal.LIBRARY) == 2


def test_first_call_time_cap_is_no_result(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seals = stub_seal(monkeypatch, tmp_path, FakeClient(TimeoutError()), Uploads())

    # The operator retries on "no-result", so the output has to say it.
    assert main(["run", "seal"]) == 1
    assert capsys.readouterr().out.startswith("no-result: time-cap\n")

    [entry] = entries(seals)
    assert entry["status"] == "no-result"
    assert entry["file"] is not None
    assert check_may_seal(SEALED, entries(seals), "gpt-6-luna", seal.LIBRARY) == 2


def test_time_cap_after_output_is_final(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seals = stub_seal(
        monkeypatch, tmp_path, FakeClient(response(call()), TimeoutError()), Uploads()
    )

    main(["run", "seal"])

    [entry] = entries(seals)
    assert entry["status"] == "incomplete"
    with pytest.raises(SealRefused, match="already sealed"):
        check_may_seal(SEALED, entries(seals), "gpt-6-luna", seal.LIBRARY)


def test_run_refuses_before_any_cloud_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = FakeClient(final())
    seals = stub_seal(monkeypatch, tmp_path, client, Uploads())
    seals.write_text(
        json.dumps({"seals": [attempt("complete", library=seal.LIBRARY)]}), encoding="utf-8"
    )

    with pytest.raises(SealRefused):
        main(["run", "seal"])
    with pytest.raises(SealRefused):
        main(["run", "show"])
    assert client.calls == []


def test_dirty_tree_refuses_before_any_cloud_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(final())
    stub_seal(monkeypatch, tmp_path, client, Uploads())

    def dirty() -> Any:
        raise SealRefused("dirty")

    monkeypatch.setattr(seal, "check_clean", dirty)
    with pytest.raises(SealRefused):
        main(["run", "seal"])
    assert client.calls == []


def test_a_seal_without_the_library_does_not_block_one_with_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The six first-series seals stay; run adds the library series next to them.
    seals = stub_seal(monkeypatch, tmp_path, FakeClient(response(call()), final()), Uploads())
    seals.write_text(json.dumps({"seals": [attempt("complete", library=False)]}), encoding="utf-8")

    assert main(["run", "seal"]) == 0

    assert [e["library"] for e in entries(seals)] == [False, True]

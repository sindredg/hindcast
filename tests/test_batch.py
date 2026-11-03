import json
import subprocess
from pathlib import Path

import pytest

from hindcast.cases import Case
from hindcast.evaluation import batch
from hindcast.evaluation.batch import (
    BatchRefused,
    check_clean,
    closed_slots,
    main,
    next_slots,
    reconcile,
)
from hindcast.investigate import ScoredCaseLocked
from test_investigate import (
    FINAL,
    SOURCE,
    FakeClient,
    RateLimitError,
    call,
    final,
    response,
    stub_command,
)

# A scored case on the stub evidence file (dev.json).
SHOW = Case("dev", "Slow pages", "Cloudflare", "showcase", "2026-02-20T18:45:16Z", (SOURCE,))


def attempt(case: str, repeat: int, n: int, status: str, arm: str = "hindcast") -> dict:
    return {
        "run_id": f"{arm}/{case}/r{repeat}/a{n}",
        "arm": arm,
        "case_id": case,
        "repeat": repeat,
        "attempt": n,
        "status": status,
    }


def test_next_slots_fills_three_repeats() -> None:
    assert next_slots([], "hindcast", ["a", "b"], 3) == [
        ("a", 1, 1),
        ("a", 2, 1),
        ("a", 3, 1),
        ("b", 1, 1),
        ("b", 2, 1),
        ("b", 3, 1),
    ]


def test_slot_with_output_is_never_rerun() -> None:
    attempts = [
        attempt("a", 1, 1, "complete"),
        attempt("a", 2, 1, "no-result"),
        attempt("a", 2, 2, "incomplete"),
        # Another arm's attempts fill nothing here.
        attempt("a", 3, 1, "complete", arm="comparison"),
    ]
    assert next_slots(attempts, "hindcast", ["a"], 3) == [("a", 3, 1)]


def test_three_no_results_close_the_slot() -> None:
    attempts = [attempt("a", 1, n, "no-result") for n in (1, 2, 3)]
    assert next_slots(attempts, "hindcast", ["a"], 2) == [("a", 2, 1)]
    assert closed_slots(attempts, "hindcast", ["a"], 2) == [("a", 1)]


def test_crash_leaves_running_entry_counted_as_attempt(tmp_path: Path) -> None:
    attempts = [attempt("a", 1, 1, "running")]
    # Nothing was written for it: the attempt counts and the slot stays open.
    reconcile(attempts, tmp_path)
    assert attempts[0]["status"] == "running"
    assert next_slots(attempts, "hindcast", ["a"], 1) == [("a", 1, 2)]


def test_crash_after_the_result_was_written_fills_the_slot(tmp_path: Path) -> None:
    # Killed between writing the result and updating the ledger: the file is
    # the record, so the slot is filled and never run again.
    attempts = [attempt("a", 1, 1, "running")]
    folder = tmp_path / "hindcast" / "a"
    folder.mkdir(parents=True)
    document = {
        "run_id": "hindcast/a/r1/a1",
        "status": "complete",
        "incomplete_reason": None,
        "usage": {"output_tokens": 20},
        "cost": {"total": "0.01"},
    }
    (folder / "r1-a1-20261104T100000Z.json").write_text(json.dumps(document), "utf-8")
    reconcile(attempts, tmp_path)
    assert attempts[0]["status"] == "complete"
    assert attempts[0]["file"] == "hindcast/a/r1-a1-20261104T100000Z.json"
    assert next_slots(attempts, "hindcast", ["a"], 1) == []


def stub_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: FakeClient, *, locked: bool = False
) -> Path:
    stub_command(monkeypatch, tmp_path, client)
    monkeypatch.setattr(batch, "load_cases", lambda: {"dev": SHOW})
    monkeypatch.setattr(batch, "RUNS_DIR", tmp_path / "runs")
    attempts = tmp_path / "attempts.json"
    monkeypatch.setattr(batch, "ATTEMPTS", attempts)
    monkeypatch.setattr(batch, "check_clean", lambda: "c" * 40)
    seals = tmp_path / "seals.json"
    seals.write_text(
        json.dumps(
            {
                "seals": [
                    {
                        "agent_name": "hindcast-investigator-gpt-6-luna",
                        "agent_version": "3",
                        "library": True,
                    }
                ]
            }
        ),
        "utf-8",
    )
    monkeypatch.setattr(batch, "SEALS", seals)
    if not locked:
        lock = tmp_path / "rubric" / "frozen.json"
        lock.parent.mkdir()
        lock.write_text("{}", "utf-8")
    return attempts


def test_refuses_showcase_without_rubric_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(final())
    stub_batch(monkeypatch, tmp_path, client, locked=True)
    with pytest.raises(ScoredCaseLocked):
        main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"])
    assert client.calls == []


def test_refuses_an_unscored_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = FakeClient(final())
    stub_batch(monkeypatch, tmp_path, client)
    development = Case("dev", "Slow pages", "Cloudflare", "development", SHOW.started_at, ())
    monkeypatch.setattr(batch, "load_cases", lambda: {"dev": development})
    with pytest.raises(BatchRefused, match="showcase"):
        main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"])
    assert client.calls == []


def test_refuses_an_unknown_arm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = FakeClient(final())
    stub_batch(monkeypatch, tmp_path, client)
    with pytest.raises(BatchRefused, match="unknown arm"):
        main(["run", "--arm", "nope", "--case", "dev", "--repeats", "1"])
    assert client.calls == []


def git(repo: Path, *args: str) -> None:
    config = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
    config += ["-c", "commit.gpgsign=false"]
    subprocess.run(["git", "-C", str(repo), *config, *args], check=True, capture_output=True)  # noqa: S603, S607


def test_refuses_dirty_tree(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    keys = tmp_path / "eval" / "keys"
    keys.mkdir(parents=True)
    (keys / "k.json").write_text("{}", "utf-8")
    (tmp_path / "notes.md").write_text("v1", "utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "v1")
    # A change outside what shapes or scores a run does not block it.
    (tmp_path / "notes.md").write_text("v2", "utf-8")
    assert len(check_clean(tmp_path)) == 40
    (keys / "k.json").write_text('{"changed": true}', "utf-8")
    with pytest.raises(BatchRefused, match="eval/keys/k.json"):
        check_clean(tmp_path)


def test_prints_no_investigation_text(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = json.loads(json.dumps(FINAL))
    document["findings"][0]["claim"] = "A PLANTED SECRET CLAIM"
    attempts = stub_batch(monkeypatch, tmp_path, FakeClient(response(call()), final(document)))

    assert main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"]) == 0

    out = capsys.readouterr().out
    assert "PLANTED" not in out
    assert "hindcast/dev/r1/a1 complete" in out
    [entry] = json.loads(attempts.read_text("utf-8"))["attempts"]
    assert entry["status"] == "complete"
    assert entry["agent"] == {"name": "hindcast-investigator-gpt-6-luna", "version": "3"}
    written = json.loads((tmp_path / "runs" / entry["file"]).read_text("utf-8"))
    assert written["run_id"] == "hindcast/dev/r1/a1"
    assert written["provenance"]["arm"] == "hindcast"
    assert entry["file"].startswith("hindcast/dev/r1-a1-")


def test_a_second_batch_runs_only_the_open_slots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(final(), final())
    attempts = stub_batch(monkeypatch, tmp_path, client)
    assert main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"]) == 0
    assert main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "2"]) == 0
    entries = json.loads(attempts.read_text("utf-8"))["attempts"]
    assert [e["run_id"] for e in entries] == ["hindcast/dev/r1/a1", "hindcast/dev/r2/a1"]
    assert len(client.calls) == 2


def test_model_error_is_a_no_result_attempt_and_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(response(call()), RateLimitError("429"), final())
    attempts = stub_batch(monkeypatch, tmp_path, client)
    assert main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"]) == 1
    assert main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"]) == 0
    entries = json.loads(attempts.read_text("utf-8"))["attempts"]
    assert [(e["run_id"], e["status"], e["reason"]) for e in entries] == [
        ("hindcast/dev/r1/a1", "no-result", "model-error"),
        ("hindcast/dev/r1/a2", "complete", None),
    ]
    # Both attempts keep their files and hashes.
    assert all(e["file"] and e["sha256"] for e in entries)


def test_stops_after_two_no_results_in_a_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A spending limit or an expired sign-in fails every call: stop instead of
    # spending every slot's attempts.
    client = FakeClient(RateLimitError("a"), RateLimitError("b"), final())
    attempts = stub_batch(monkeypatch, tmp_path, client)
    assert main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "3"]) == 1
    entries = json.loads(attempts.read_text("utf-8"))["attempts"]
    # The slots are taken in order; the failed one is retried on the next start.
    assert [e["run_id"] for e in entries] == ["hindcast/dev/r1/a1", "hindcast/dev/r2/a1"]


def test_refuses_an_agent_version_the_seals_did_not_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = FakeClient(final())
    stub_batch(monkeypatch, tmp_path, client)
    seals = tmp_path / "seals.json"
    record = json.loads(seals.read_text("utf-8"))
    record["seals"][0]["agent_version"] = "2"
    seals.write_text(json.dumps(record), "utf-8")
    with pytest.raises(BatchRefused, match="version 3"):
        main(["run", "--arm", "hindcast", "--case", "dev", "--repeats", "1"])
    assert client.calls == []

"""The evaluation batch: one arm on the showcase cases, a fixed number of runs each.

    python -m hindcast.evaluation.batch run --arm <name> --case <id> [--case ...] --repeats 3

Each run writes eval/reconstruction/showcase-v1/runs/<arm>/<case_id>/
r<repeat>-a<attempt>-<UTC time>.json, and every attempt is an entry in
eval/reconstruction/showcase-v1/attempts.json. The command prints the run ID,
the status, the reason's kind, the counts, the seconds, and the cost, never
the investigation text: nothing reads a scored output before the judge
prompt is frozen.

The retry rule is the rubric's (eval/rubric/rubric.md, Failures): an attempt
with no investigation to keep (no model output, or a run ended by a failed
model call, screen, or PII check) is no-result and may be followed by
another, up to three per slot; any other run with model output, complete or
incomplete, fills its slot and is never run again. One library search
before each run refuses the batch while the search service is down, as the
seal does. The entry is written before the run starts and updated after it,
so a killed batch leaves a running entry that counts as an attempt; a
running entry whose result file exists is filled from the file on the next
start.

Runs go one at a time: the caps of hindcast.investigate assume it.
"""

import argparse
import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hindcast import investigate, telemetry
from hindcast.agent import VersionRefused
from hindcast.arms import ARMS
from hindcast.cases import load_cases
from hindcast.evaluation.prior import _git
from hindcast.investigate import prepare, run_investigation, summary, write_result
from hindcast.seal import preflight_search

ROOT = Path("eval/reconstruction/showcase-v1")
RUNS_DIR = ROOT / "runs"
ATTEMPTS = ROOT / "attempts.json"
# The revealed seals' scoring tree (decision 0030). Their files stay where the
# reveal copies them, eval/investigations/<case_id>/, and carry no run ID: a
# seal is run before any ledger names it.
SEALED_ROOT = Path("eval/reconstruction/sealed-v1")
REVEALED_DIR = Path("eval/investigations")
SEALS = Path("eval/sealed/seals.json")
# What shapes a run or scores it: the code, the prompts, the registries, the
# frozen rubric, and the frozen keys and labels.
CLEAN_PATHS = (
    "src",
    "prompts",
    "pyproject.toml",
    "uv.lock",
    "data/cases.yaml",
    "data/library.yaml",
    "eval/rubric",
    "eval/keys",
)
MAX_ATTEMPTS = 3
# A spending limit, a quota, or an expired sign-in fails every call; the
# batch stops instead of using up every slot's attempts.
MAX_NO_RESULTS_IN_A_ROW = 2
FILLED = frozenset({"complete", "incomplete"})
# A run ended by one of these failed in a service, not in the model, and
# keeps no investigation. The seal retries only the first (decision 0017
# rule 6); a seal is one run, a scored slot is one of three.
SERVICE_ERRORS = ("model-error", "screen-error", "pii-error")


class BatchRefused(PermissionError):
    """A batch that would break the rules: an unknown arm, a case not scored, a dirty tree."""


def _slot_attempts(attempts: list[dict], arm: str, case_id: str, repeat: int) -> list[dict]:
    return [a for a in attempts if (a["arm"], a["case_id"], a["repeat"]) == (arm, case_id, repeat)]


def next_slots(
    attempts: list[dict], arm: str, cases: list[str], repeats: int
) -> list[tuple[str, int, int]]:
    """(case_id, repeat, attempt) still to run, in order."""
    slots = []
    for case_id in cases:
        for repeat in range(1, repeats + 1):
            earlier = _slot_attempts(attempts, arm, case_id, repeat)
            if any(a["status"] in FILLED for a in earlier) or len(earlier) >= MAX_ATTEMPTS:
                continue
            slots.append((case_id, repeat, len(earlier) + 1))
    return slots


def closed_slots(
    attempts: list[dict], arm: str, cases: list[str], repeats: int
) -> list[tuple[str, int]]:
    """Slots with three attempts and no result: reported, never run again."""
    return [
        (case_id, repeat)
        for case_id in cases
        for repeat in range(1, repeats + 1)
        if not any(a["status"] in FILLED for a in _slot_attempts(attempts, arm, case_id, repeat))
        and len(_slot_attempts(attempts, arm, case_id, repeat)) >= MAX_ATTEMPTS
    ]


def slot_no_result(output_tokens: int, reason: str | None) -> bool:
    """True when an attempt leaves its slot open: no model output, or a failed service."""
    return output_tokens == 0 or (reason or "").startswith(SERVICE_ERRORS)


def _entry_status(document: dict) -> str:
    if slot_no_result(document["usage"]["output_tokens"], document.get("incomplete_reason")):
        return "no-result"
    return document["status"]


def _prefix(reason: str | None) -> str | None:
    # A schema error echoes the value it rejected and a tool error the
    # model's arguments, so only the kind before the first colon is kept.
    return None if reason is None else reason.split(":", 1)[0]


def reconcile(attempts: list[dict], runs_dir: Path) -> None:
    """Fill a running entry from its result file, when the batch died after writing it."""
    for entry in attempts:
        if entry["status"] != "running":
            continue
        folder = runs_dir / entry["arm"] / entry["case_id"]
        found = sorted(folder.glob(f"r{entry['repeat']}-a{entry['attempt']}-*.json"))
        if len(found) != 1:
            continue
        data = found[0].read_bytes()
        document = json.loads(data)
        entry |= {
            "status": _entry_status(document),
            "reason": _prefix(document["incomplete_reason"]),
            "file": found[0].relative_to(runs_dir).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "usage": document["usage"],
            "cost": document["cost"],
            "reconciled": True,
        }


def check_clean(repo: Path = Path(".")) -> str:
    """HEAD's commit, refused when anything that shapes or scores a run differs from it."""
    commit = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    status = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", *CLEAN_PATHS)
    if commit.returncode != 0 or status.returncode != 0:
        raise BatchRefused("cannot read the Git state of the code")
    changed = [line[3:] for line in status.stdout.splitlines()]
    if changed:
        raise BatchRefused(f"commit these first: {', '.join(changed)}")
    return commit.stdout.strip()


def sealed_agents(path: Path) -> dict[str, str]:
    """The agent versions the second seal series ran, by agent name."""
    seals = json.loads(path.read_text("utf-8"))["seals"]
    return {s["agent_name"]: s["agent_version"] for s in seals if s["library"]}


def load_attempts(path: Path) -> list[dict]:
    return json.loads(path.read_text("utf-8"))["attempts"] if path.is_file() else []


def verified_run(
    entry: Mapping[str, Any], runs_dir: Path = RUNS_DIR, *, named: bool = True
) -> dict:
    """A filled attempt's result file, refused when it differs from the hash in the ledger.

    named=False is for a revealed seal, whose file has no run ID: the hash
    alone ties it to the ledger, and the ID is set in memory, never in the file.
    """
    data = (runs_dir / entry["file"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError(f"{entry['run_id']}: the result file differs from its recorded hash")
    document = json.loads(data)
    if not named and "run_id" not in document:
        document["run_id"] = entry["run_id"]
    if document.get("run_id") != entry["run_id"]:
        raise ValueError(f"{entry['run_id']}: the result file names another run")
    return document


def is_root(root: Path, which: Path) -> bool:
    """Whether root names the tree which, however it is written: absolute or relative."""
    return root.resolve() == which.resolve()


def run_loader(root: Path) -> Callable[[Mapping[str, Any]], dict]:
    """How the judge and the reviewer read a scoring tree's result files."""
    if is_root(root, SEALED_ROOT):
        return lambda entry: verified_run(entry, REVEALED_DIR, named=False)
    return lambda entry: verified_run(entry, root / "runs")


def write_attempts(path: Path, attempts: list[dict]) -> None:
    # Written to a temporary file and moved over the old one, so a kill
    # mid-write cannot leave half a ledger.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"attempts": attempts}, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _now() -> datetime:
    return datetime.now(UTC)


def run(arm_name: str, case_ids: list[str], repeats: int) -> int:
    if arm_name not in ARMS:
        raise BatchRefused(f"unknown arm {arm_name!r}; arms: {', '.join(ARMS)}")
    arm = ARMS[arm_name]
    cases = load_cases()
    for case_id in case_ids:
        if case_id not in cases:
            raise BatchRefused(f"unknown case {case_id!r}")
        if cases[case_id].role != "showcase":
            raise BatchRefused(
                f"{case_id} is a {cases[case_id].role} case; the batch runs showcase cases"
            )
        investigate.check_case_allowed(cases[case_id], investigate.RUBRIC_LOCK)
    commit = check_clean()
    sealed = sealed_agents(SEALS)

    attempts = load_attempts(ATTEMPTS)
    reconcile(attempts, RUNS_DIR)
    write_attempts(ATTEMPTS, attempts)
    for case_id, repeat in closed_slots(attempts, arm.name, case_ids, repeats):
        print(f"closed: {arm.name}/{case_id}/r{repeat} has {MAX_ATTEMPTS} attempts and no result")
    slots = next_slots(attempts, arm.name, case_ids, repeats)
    if not slots:
        print("nothing to run")
        return 0

    telemetry.configure(service=telemetry.INVESTIGATOR)
    no_results = 0
    for case_id, repeat, attempt in slots:
        case = cases[case_id]
        try:
            # The agent arms that keep prompt v3 must be the agents the sealed
            # cases ran, or the two sets of scores do not compare. prepare
            # refuses before it would make a new version of a sealed name.
            setup = prepare(case, arm=arm, pinned=sealed)
        except VersionRefused as error:
            raise BatchRefused(str(error)) from error
        # The library-off arm binds no search.
        if setup.tools.search is not None:
            preflight_search(setup.tools, refused=BatchRefused)
        run_id = f"{arm.name}/{case_id}/r{repeat}/a{attempt}"
        now = _now()
        entry = {
            "run_id": run_id,
            "arm": arm.name,
            "case_id": case_id,
            "repeat": repeat,
            "attempt": attempt,
            "started_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "running",
            "reason": None,
            "file": None,
            "sha256": None,
            "usage": None,
            "cost": None,
            "agent": setup.agent,
            "model": setup.model,
            "code_commit": commit,
        }
        attempts.append(entry)
        write_attempts(ATTEMPTS, attempts)

        if arm.kind == "single":
            from hindcast.single import run_single

            result = run_single(setup, case)
        else:
            result = run_investigation(setup.turn, setup.tools, case_id=case_id, pii=setup.pii)
        cost = setup.cost(result.usage)
        path = write_result(
            result,
            case_id=case_id,
            agent=setup.agent,
            model=setup.model,
            provenance=setup.provenance,
            out_dir=RUNS_DIR / arm.name,
            now=now,
            cost=cost,
            filename=f"r{repeat}-a{attempt}-{now:%Y%m%dT%H%M%SZ}.json",
            run_id=run_id,
        )
        data = path.read_bytes()
        entry |= {
            "status": (
                "no-result"
                if slot_no_result(result.usage.output_tokens, result.incomplete_reason)
                else result.status
            ),
            "reason": _prefix(result.incomplete_reason),
            "file": path.relative_to(RUNS_DIR).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "usage": asdict(result.usage),
            "cost": cost,
        }
        write_attempts(ATTEMPTS, attempts)

        lines = summary(replace(result, incomplete_reason=entry["reason"]), path, cost)
        _, rest = lines.split("\n", 1)
        status = (
            entry["status"] if entry["reason"] is None else f"{entry['status']}: {entry['reason']}"
        )
        print(f"{run_id} {status}\n{rest}")
        no_results = no_results + 1 if entry["status"] == "no-result" else 0
        if no_results >= MAX_NO_RESULTS_IN_A_ROW:
            print(f"stopped: {no_results} attempts in a row had no result; run the command again")
            return 1
    return 1 if no_results else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.batch")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="run one arm on scored cases")
    run_parser.add_argument("--arm", required=True)
    run_parser.add_argument("--case", action="append", required=True, dest="cases")
    run_parser.add_argument("--repeats", type=int, required=True)
    args = parser.parse_args(argv)
    return run(args.arm, args.cases, args.repeats)


if __name__ == "__main__":
    raise SystemExit(main())

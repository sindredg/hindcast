"""Seal a reconstruction by its hash before the provider publishes a cause.

    python -m hindcast.seal run <case_id>
    python -m hindcast.seal upload <case_id> <file>

run investigates a sealed case once with the deployment in
HINDCAST_CHAT_DEPLOYMENT, writes the result under build/sealed/, records its
SHA-256 in eval/sealed/seals.json, and uploads the file to Blob Storage under
extracted/sealed/, never over an existing blob. It prints the status, the
counts, the usage, and the hash, never the investigation text.

The result stays private until the provider has published its postmortem and
the rubric is frozen: a model's account of a real company's outage is not made
public before the company's own (decision 0017). The committed hash is what
makes the file checkable when it is revealed.

One seal per case, deployment, and library setting. Every attempt is recorded.
An attempt in which the model produced no output (the run raised, or the time
cap ended the first call) may be retried, up to three attempts in all. A
result with model output, complete or not, is the seal: it is never rerun or
replaced, so a bad answer cannot be swapped for a better one.
"""

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from hindcast.cases import Case, load_cases
from hindcast.config import ModelSettings, load_settings
from hindcast.evaluation.prior import _git
from hindcast.investigate import prepare, run_investigation, summary, write_result
from hindcast.storage import upload_bytes

SEALS = Path("eval/sealed/seals.json")
OUT_DIR = Path("build/sealed")
CONTAINER = "extracted"
BLOB_PREFIX = "sealed"
# Everything that shapes a run, so the recorded commit names the exact prompt,
# agent definition, code, and case registry.
CLEAN_PATHS = ("src", "prompts", "pyproject.toml", "uv.lock", "data/cases.yaml")
MAX_ATTEMPTS = 3
# The investigator has no library tool until milestone 4 slice 2.
LIBRARY = False
ENTRY_FIELDS = (
    "case_id",
    "attempt",
    "deployment",
    "model_name",
    "model_version",
    "agent_name",
    "agent_version",
    "code_commit",
    "evidence_sha256",
    "library",
    "sealed_at",
    "file",
    "sha256",
    "blob",
    "status",
)


class SealRefused(PermissionError):
    """A seal that would break the rules: a second seal, a dirty tree, a case not sealed."""


def check_may_seal(case: Case, seals: list[dict], deployment: str, library: bool) -> int:
    """The next attempt number for this case, deployment, and library setting."""
    if case.role != "sealed":
        raise SealRefused(f"{case.case_id} is not a sealed case (role {case.role})")
    key = (case.case_id, deployment, library)
    earlier = [s for s in seals if (s["case_id"], s["deployment"], s["library"]) == key]
    if any(s["status"] != "no-result" for s in earlier):
        raise SealRefused(f"{case.case_id} is already sealed on {deployment}")
    if len(earlier) >= MAX_ATTEMPTS:
        raise SealRefused(f"{case.case_id} on {deployment} has had {MAX_ATTEMPTS} attempts")
    return len(earlier) + 1


def check_clean(repo: Path = Path(".")) -> str:
    """HEAD's commit, refused when anything that shapes a run differs from it."""
    commit = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    status = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", *CLEAN_PATHS)
    if commit.returncode != 0 or status.returncode != 0:
        raise SealRefused("cannot read the Git state of the code")
    changed = [line[3:] for line in status.stdout.splitlines()]
    if changed:
        raise SealRefused(f"commit these first: {', '.join(changed)}")
    return commit.stdout.strip()


def load_seals(path: Path) -> list[dict]:
    return json.loads(path.read_text("utf-8"))["seals"]


def write_seals(path: Path, seals: list[dict]) -> None:
    path.write_text(json.dumps({"seals": seals}, indent=2) + "\n", encoding="utf-8")


def reason_prefix(reason: str | None) -> str | None:
    # A schema error echoes the value it rejected and a tool error the model's
    # arguments, so only the kind before the first colon is printed.
    return None if reason is None else reason.split(":", 1)[0]


def _now() -> datetime:
    return datetime.now(UTC)


def run(case: Case) -> int:
    seals = load_seals(SEALS)
    deployment = load_settings(ModelSettings).chat_deployment
    # Both refusals come before any cloud call.
    attempt = check_may_seal(case, seals, deployment, LIBRARY)
    commit = check_clean()
    setup = prepare(case)
    now = _now()
    entry = {
        "case_id": case.case_id,
        "attempt": attempt,
        "deployment": deployment,
        "model_name": setup.model["name"],
        "model_version": setup.model["version"],
        "agent_name": setup.agent["name"],
        "agent_version": setup.agent["version"],
        "code_commit": commit,
        "evidence_sha256": setup.provenance["evidence_sha256"],
        "library": LIBRARY,
        "sealed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file": None,
        "sha256": None,
        "blob": None,
        "status": "no-result",
    }
    try:
        result = run_investigation(setup.turn, setup.tools, case_id=case.case_id)
    except Exception as error:
        # A 429 or a cut-off response: nothing to seal. The error text can
        # carry the service's response, so only its type is printed.
        write_seals(SEALS, [*seals, entry])
        print(f"no-result: {type(error).__name__}; attempt {attempt} of {MAX_ATTEMPTS}")
        return 1
    path = write_result(
        result,
        case_id=case.case_id,
        agent=setup.agent,
        model=setup.model,
        provenance=setup.provenance,
        out_dir=OUT_DIR,
        now=now,
    )
    data = path.read_bytes()
    entry |= {
        "file": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        # A time cap on the first call writes a result with no model output.
        "status": "no-result" if result.usage.output_tokens == 0 else result.status,
    }
    # The hash is recorded before the upload, so a failed upload loses nothing.
    seals.append(entry)
    write_seals(SEALS, seals)
    print(summary(replace(result, incomplete_reason=reason_prefix(result.incomplete_reason)), path))
    print(f"sha256 {entry['sha256']}")
    return _upload(case.case_id, entry, data, seals)


def _upload(case_id: str, entry: dict, data: bytes, seals: list[dict]) -> int:
    name = f"{BLOB_PREFIX}/{case_id}/{entry['file']}"
    try:
        upload_bytes(CONTAINER, name, data, overwrite=False)
    except Exception as error:
        print(
            f"upload failed ({type(error).__name__}); retry: seal upload {case_id} {entry['file']}"
        )
        return 1
    entry["blob"] = name
    write_seals(SEALS, seals)
    print(f"uploaded {CONTAINER}/{name}")
    return 0


def upload(case_id: str, file: str) -> int:
    """Upload a sealed file whose upload failed, after checking it against its hash."""
    seals = load_seals(SEALS)
    found = [s for s in seals if s["case_id"] == case_id and s["file"] == file]
    if len(found) != 1:
        raise SealRefused(f"no seal of {case_id} with file {file!r}")
    [entry] = found
    if entry["blob"] is not None:
        raise SealRefused(f"{file} is already uploaded to {entry['blob']}")
    data = (OUT_DIR / case_id / file).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise SealRefused(f"{file} does not match its recorded SHA-256")
    return _upload(case_id, entry, data, seals)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.seal")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="investigate a sealed case and record its hash")
    run_parser.add_argument("case_id")
    upload_parser = commands.add_parser("upload", help="upload a sealed file again")
    upload_parser.add_argument("case_id")
    upload_parser.add_argument("file")
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.case_id not in cases:
        parser.error(f"unknown case {args.case_id!r}")
    if args.command == "run":
        return run(cases[args.case_id])
    return upload(args.case_id, args.file)


if __name__ == "__main__":
    raise SystemExit(main())

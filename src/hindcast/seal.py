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

One seal per case, deployment, and library setting. Seals made since the
investigator searches the library carry library: true; the earlier ones, made
without the search, keep library: false. Every attempt is recorded.
An attempt in which the model produced no output (the run raised, or the time
cap ended the first call) may be retried, up to three attempts in all. A
result with model output, complete or not, is the seal: it is never rerun or
replaced, so a bad answer cannot be swapped for a better one.

The record only grows: entries are appended, an upload fills a null blob
once, and a reveal or a drop adds "revealed": true or "dropped": true; nothing
else in an earlier entry changes. run and upload refuse a record on disk that
does not extend HEAD's, and a test walks every committed version of the file
(issue #33).

run makes one library search before the first model call and refuses while
the search does not answer.
"""

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from hindcast import telemetry
from hindcast.cases import Case, load_cases
from hindcast.config import ModelSettings, load_settings
from hindcast.evaluation.prior import _git
from hindcast.investigate import prepare, run_investigation, summary, write_result
from hindcast.storage import upload_bytes
from hindcast.tools import CaseTools

SEALS = Path("eval/sealed/seals.json")
OUT_DIR = Path("build/sealed")
CONTAINER = "extracted"
BLOB_PREFIX = "sealed"
# Everything that shapes a run, so the recorded commit names the exact prompt,
# agent definition, code, case registry, and the library registry that bounds
# the searches.
CLEAN_PATHS = (
    "src",
    "prompts",
    "pyproject.toml",
    "uv.lock",
    "data/cases.yaml",
    "data/library.yaml",
)
MAX_ATTEMPTS = 3
# The second series: the investigator searches the library (decision 0017,
# rule 6). The first series, sealed without it, keeps library: false.
LIBRARY = True
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


# The only keys a later commit may add to an entry, each as true: a reveal
# and a drop (decision 0017, the sealing runbook).
MARKS = frozenset({"revealed", "dropped"})


def record_problems(old: list[dict], new: list[dict]) -> list[str]:
    """One line per way the new record fails to extend the old one."""
    problems = []
    for i, before in enumerate(old):
        if i >= len(new):
            problems.append(f"entry {i} removed")
            continue
        after = new[i]
        for key, value in before.items():
            filled_blob = key == "blob" and value is None and isinstance(after.get(key), str)
            if (key not in after or after[key] != value) and not filled_blob:
                problems.append(f"entry {i} changed: {key}")
        for key in sorted(after.keys() - before.keys()):
            if key not in MARKS or after[key] is not True:
                problems.append(f"entry {i} gained {key}")
    return problems


def _version(repo: Path, rev: str, path: Path) -> list[dict]:
    """The record at a commit; empty only when the commit has no such file."""
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").returncode != 0:
        raise RuntimeError(f"cannot read commit {rev}")
    if _git(repo, "cat-file", "-e", f"{rev}:{path.as_posix()}").returncode != 0:
        return []
    shown = _git(repo, "show", f"{rev}:{path.as_posix()}")
    if shown.returncode != 0:
        raise RuntimeError(f"cannot read {path} at {rev}")
    return json.loads(shown.stdout)["seals"]


def history_problems(repo: Path = Path("."), path: Path = SEALS) -> list[str]:
    """Every committed version of the record checked against the one before it."""
    shallow = _git(repo, "rev-parse", "--is-shallow-repository")
    if shallow.returncode != 0:
        raise RuntimeError("cannot read the Git history")
    # A shallow clone hides the earlier versions, so the walk would pass on
    # whatever is left. CI checks out with fetch-depth: 0.
    if shallow.stdout.strip() == "true":
        raise RuntimeError(f"the clone is shallow: checking {path} needs the full history")
    # --full-history keeps a merge that matches one parent: the default
    # simplification would skip it and the other parent's commits, so a merge
    # that drops an entry would pass.
    listing = _git(repo, "rev-list", "--full-history", "--parents", "HEAD", "--", path.as_posix())
    if listing.returncode != 0:
        raise RuntimeError(f"cannot list the history of {path}")
    problems = []
    for line in listing.stdout.splitlines():
        # With a path, the parents are the nearest earlier commits that
        # changed the file, so each version is compared with the one before.
        commit, *parents = line.split()
        new = _version(repo, commit, path)
        for parent in parents:
            old = _version(repo, parent, path)
            problems += [f"{commit[:12]}: {p}" for p in record_problems(old, new)]
    return problems


def check_record_grows(repo: Path = Path(".")) -> None:
    """Refuse a record on disk that does not extend the one committed at HEAD."""
    try:
        committed = _version(repo, "HEAD", SEALS)
    except RuntimeError as error:
        raise SealRefused(str(error)) from error
    problems = record_problems(committed, load_seals(repo / SEALS))
    if problems:
        raise SealRefused(f"{SEALS} does not extend HEAD's: {'; '.join(problems)}")


PREFLIGHT_QUERY = "service outage"


def preflight_search(tools: CaseTools) -> None:
    """Refuse a seal, before the first model call, while the library search fails."""
    # A search that fails mid-run ends it as a tool error, and a seal with
    # model output is final (decision 0017). One search first keeps a search
    # outage from using up the case's seal; a mid-run failure stays possible.
    if tools.search is None:
        raise SealRefused("no library search is bound")
    try:
        tools.search(PREFLIGHT_QUERY)
    except Exception as error:
        # Only the type: the message can carry the service's response.
        raise SealRefused(
            f"the library search did not answer ({type(error).__name__}); seal again later"
        ) from None


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
    check_record_grows()
    telemetry.configure(service=telemetry.INVESTIGATOR)
    setup = prepare(case)
    preflight_search(setup.tools)
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
        result = run_investigation(setup.turn, setup.tools, case_id=case.case_id, pii=setup.pii)
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
    lines = summary(
        replace(result, incomplete_reason=reason_prefix(result.incomplete_reason)), path
    )
    if entry["status"] == "no-result":
        # The first line is what the operator acts on: a no-result attempt may be retried.
        lines = lines.replace("incomplete: ", "no-result: ", 1)
    print(lines)
    print(f"sha256 {entry['sha256']}")
    uploaded = _upload(case.case_id, entry, data, seals)
    return 1 if entry["status"] == "no-result" else uploaded


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
    check_record_grows()
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

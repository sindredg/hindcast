"""Prior-knowledge check: what a model says about each showcase outage before any evidence.

    python -m hindcast.evaluation.prior collect --deployment <name>

writes eval/results/prior-<UTC date>-<deployment>.json. It prints no answer
text: nobody reads the answers before the rubric is frozen, or the rubric
drifts towards them.
"""

import argparse
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ruamel.yaml import YAML

from hindcast.cases import Case, load_cases
from hindcast.costs import TokenUsage

PROMPT_PATH = Path("prompts/prior_knowledge.md")
CASES_PATH = Path("data/cases.yaml")
RESULTS_DIR = Path("eval/results")


@dataclass(frozen=True)
class PriorPrompt:
    system: str
    question: str
    dates: dict[str, str]
    key_facts: dict[str, tuple[str, ...]]


def load_prompt(path: Path = PROMPT_PATH) -> PriorPrompt:
    """Read the question and case data from the front matter, the system prompt from the body."""
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    data = YAML(typ="safe", pure=True).load(front)
    return PriorPrompt(
        system=body.strip(),
        question=data["question"],
        dates={case_id: str(case["date"]) for case_id, case in data["cases"].items()},
        key_facts={
            case_id: tuple(str(fact) for fact in case["key_facts"])
            for case_id, case in data["cases"].items()
        },
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git") or "git"
    # Fixed arguments and repository paths from this module, never user input.
    return subprocess.run(  # noqa: S603
        [git, "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def committed_blob_hash(path: Path, repo: Path = Path(".")) -> str:
    """Git blob hash of path, refusing when the file differs from HEAD or is not tracked."""
    working = _git(repo, "hash-object", "--", str(path))
    committed = _git(repo, "rev-parse", "--verify", "--quiet", f"HEAD:{path.as_posix()}")
    if working.returncode != 0 or committed.returncode != 0:
        raise RuntimeError(f"{path} is not committed")
    if working.stdout.strip() != committed.stdout.strip():
        raise RuntimeError(f"{path} has uncommitted changes")
    return committed.stdout.strip()


def clean_head_commit(paths: list[Path], repo: Path = Path(".")) -> str:
    """HEAD commit, refusing when anything under paths is changed or untracked."""
    names = [str(path) for path in paths]
    status = _git(repo, "status", "--porcelain", "--", *names)
    commit = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    if status.returncode != 0 or commit.returncode != 0:
        raise RuntimeError(f"cannot read the Git state of {', '.join(names)}")
    if status.stdout.strip():
        raise RuntimeError(f"{', '.join(names)}: uncommitted or untracked changes")
    return commit.stdout.strip()


def collect(
    deployment: str,
    ask: Callable[..., tuple[str, TokenUsage]],
    describe: Callable[[str], tuple[str, str]],
    *,
    cases: dict[str, Case],
    prompt: PriorPrompt,
    hashes: dict[str, str],
    effort: str,
    out_dir: Path,
    now: datetime,
) -> Path:
    """Ask the deployment about every showcase case and write one result file."""
    path = out_dir / f"prior-{now.astimezone(UTC):%Y-%m-%d}-{deployment}.json"
    # Checked before any model call, so a repeated run costs nothing. The "x"
    # mode below still refuses if the file appears in between.
    if path.exists():
        raise FileExistsError(f"{path} exists; a result is never overwritten")
    # Every question is built before the first paid call, so a gap in the
    # prompt's case list fails for free.
    questions = {}
    for case in cases.values():
        if case.role != "showcase":
            continue
        if case.case_id not in prompt.dates:
            raise ValueError(f"{case.case_id} has no date in the prompt's front matter")
        questions[case.case_id] = prompt.question.format(
            provider=case.provider, title=case.title, date=prompt.dates[case.case_id]
        )
    model_name, model_version = describe(deployment)
    entries = []
    for case_id, question in questions.items():
        answer, usage = ask(deployment, prompt.system, question, effort=effort)
        entries.append(
            {
                "case_id": case_id,
                "question": question,
                "answer": answer,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "cached_input_tokens": usage.cached_input_tokens,
                    "output_tokens": usage.output_tokens,
                },
            }
        )
    result = {
        "check": "prior-knowledge",
        "collected_at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deployment": deployment,
        "model_name": model_name,
        "model_version": model_version,
        "reasoning_effort": effort,
        "prompt_path": PROMPT_PATH.as_posix(),
        "prompt_git_blob": hashes["prompt"],
        "cases_path": CASES_PATH.as_posix(),
        "cases_git_blob": hashes["cases"],
        "code_commit": hashes["code"],
        "entries": entries,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)
        file.write("\n")
    tokens_in = sum(entry["usage"]["input_tokens"] for entry in entries)
    tokens_out = sum(entry["usage"]["output_tokens"] for entry in entries)
    print(f"{path}: {len(entries)} entries, {tokens_in} input and {tokens_out} output tokens")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.prior")
    commands = parser.add_subparsers(dest="command", required=True)
    collect_command = commands.add_parser("collect", help="ask one deployment about each case")
    collect_command.add_argument("--deployment", required=True)
    collect_command.add_argument("--effort", default="medium", help="reasoning effort")
    args = parser.parse_args(argv)

    # Imported here so the collector and its tests do not need the SDK.
    from hindcast.models import ask_model, deployment_model

    hashes = {
        "prompt": committed_blob_hash(PROMPT_PATH),
        "cases": committed_blob_hash(CASES_PATH),
        # The code, its locked dependencies, and the project file shape the calls.
        "code": clean_head_commit([Path("src"), Path("pyproject.toml"), Path("uv.lock")]),
    }
    collect(
        args.deployment,
        ask_model,
        deployment_model,
        cases=load_cases(CASES_PATH),
        prompt=load_prompt(PROMPT_PATH),
        hashes=hashes,
        effort=args.effort,
        out_dir=RESULTS_DIR,
        now=datetime.now(UTC),
    )


if __name__ == "__main__":
    main()

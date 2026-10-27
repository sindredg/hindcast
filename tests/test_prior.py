import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hindcast.cases import Case, SourceFile, load_cases
from hindcast.costs import TokenUsage
from hindcast.evaluation.prior import (
    PriorPrompt,
    clean_head_commit,
    collect,
    committed_blob_hash,
    load_prompt,
)

SOURCE = SourceFile(
    doc_id="doc",
    filename="doc.json",
    url="https://example.org/doc.json",
    licence="Copyright Example; not redistributed",
    attribution="Example",
    sha256="0" * 64,
    retrieved_at="2026-10-26T08:00:00Z",
    kind="status-updates",
)
CASES = {
    "alpha-2026": Case(
        "alpha-2026", "Elevated errors", "Cloudflare", "showcase", "2026-02-20T18:45:16Z", (SOURCE,)
    ),
    "beta-2026": Case(
        "beta-2026", "Incident with Git", "GitHub", "showcase", "2026-02-20T18:45:16Z", (SOURCE,)
    ),
    "gamma-2026": Case(
        "gamma-2026", "Slow pages", "Cloudflare", "development", "2026-02-20T18:45:16Z", (SOURCE,)
    ),
}
PROMPT = PriorPrompt(
    system="Answer from memory.",
    question="What do you know about this {provider} incident: {title}, on {date}?",
    dates={"alpha-2026": "1 May 2026", "beta-2026": "2 June 2026"},
    key_facts={"alpha-2026": ("certificate",), "beta-2026": ("database",)},
)
HASHES = {"prompt": "a" * 40, "cases": "b" * 40, "code": "c" * 40}
NOW = datetime(2026, 10, 25, 18, 30, tzinfo=UTC)


ASKED_EFFORTS = []


def fake_ask(deployment, system, user, *, image=None, effort):
    ASKED_EFFORTS.append(effort)
    return f"SECRET ANSWER to {user}", TokenUsage(100, 0, 40)


def fake_describe(deployment):
    return "gpt-6-luna", "2026-09-22"


def run_collect(out_dir: Path) -> Path:
    return collect(
        "gpt-6-luna",
        fake_ask,
        fake_describe,
        cases=CASES,
        prompt=PROMPT,
        hashes=HASHES,
        effort="medium",
        out_dir=out_dir,
        now=NOW,
    )


def showcase_questions() -> list[tuple[Case, str]]:
    prompt = load_prompt()
    showcase = [case for case in load_cases().values() if case.role == "showcase"]
    assert showcase
    return [
        (
            case,
            prompt.question.format(
                provider=case.provider, title=case.title, date=prompt.dates[case.case_id]
            ),
        )
        for case in showcase
    ]


def test_question_names_provider_title_and_date():
    dates = load_prompt().dates

    for case, question in showcase_questions():
        assert case.provider in question
        assert case.title in question
        assert dates[case.case_id] in question


def test_no_key_fact_in_any_question():
    # The title is the provider's own wording and sometimes names the cause, so
    # the whole formatted question is checked, title included.
    prompt = load_prompt()
    for case, question in showcase_questions():
        assert prompt.key_facts[case.case_id], case.case_id
        for fact in prompt.key_facts[case.case_id]:
            for sent in (question, prompt.system):
                assert not re.search(rf"\b{re.escape(fact)}\b", sent, re.IGNORECASE), (
                    case.case_id,
                    fact,
                )


def test_collect_writes_one_entry_per_showcase_case(tmp_path):
    ASKED_EFFORTS.clear()
    path = run_collect(tmp_path)

    assert path == tmp_path / "prior-2026-10-25-gpt-6-luna.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["deployment"] == "gpt-6-luna"
    assert result["model_name"] == "gpt-6-luna"
    assert result["model_version"] == "2026-09-22"
    assert result["collected_at"] == "2026-10-25T18:30:00Z"
    assert result["prompt_git_blob"] == "a" * 40
    assert result["cases_git_blob"] == "b" * 40
    assert result["code_commit"] == "c" * 40
    assert result["reasoning_effort"] == "medium"
    assert ASKED_EFFORTS == ["medium", "medium"]
    alpha = "What do you know about this Cloudflare incident: Elevated errors, on 1 May 2026?"
    beta = "What do you know about this GitHub incident: Incident with Git, on 2 June 2026?"
    usage = {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 40}
    assert result["entries"] == [
        {
            "case_id": "alpha-2026",
            "question": alpha,
            "answer": f"SECRET ANSWER to {alpha}",
            "usage": usage,
        },
        {
            "case_id": "beta-2026",
            "question": beta,
            "answer": f"SECRET ANSWER to {beta}",
            "usage": usage,
        },
    ]


def test_collect_refuses_before_asking_when_a_case_has_no_date(tmp_path):
    ASKED_EFFORTS.clear()
    prompt = PriorPrompt(
        system=PROMPT.system,
        question=PROMPT.question,
        dates={"alpha-2026": "1 May 2026"},
        key_facts=PROMPT.key_facts,
    )

    with pytest.raises(ValueError, match="beta-2026"):
        collect(
            "gpt-6-luna",
            fake_ask,
            fake_describe,
            cases=CASES,
            prompt=prompt,
            hashes=HASHES,
            effort="medium",
            out_dir=tmp_path,
            now=NOW,
        )

    assert ASKED_EFFORTS == []


def test_collect_prints_no_answer_text(tmp_path, capsys):
    run_collect(tmp_path)

    out = capsys.readouterr().out
    assert "prior-2026-10-25-gpt-6-luna.json" in out
    assert "SECRET ANSWER" not in out


def test_collect_refuses_to_overwrite_a_result(tmp_path):
    run_collect(tmp_path)

    with pytest.raises(FileExistsError):
        run_collect(tmp_path)


def test_collect_refuses_before_asking_when_the_result_exists(tmp_path):
    run_collect(tmp_path)
    ASKED_EFFORTS.clear()

    with pytest.raises(FileExistsError):
        run_collect(tmp_path)

    assert ASKED_EFFORTS == []


def git(repo: Path, *args: str) -> None:
    config = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
    config += ["-c", "commit.gpgsign=false"]
    subprocess.run(["git", "-C", str(repo), *config, *args], check=True, capture_output=True)  # noqa: S603, S607


def test_committed_blob_hash_names_the_committed_file(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "prompt.md").write_text("v1", encoding="utf-8")
    git(tmp_path, "add", "prompt.md")
    git(tmp_path, "commit", "-q", "-m", "v1")

    # git hash-object of the two bytes "v1".
    assert committed_blob_hash(Path("prompt.md"), repo=tmp_path) == (
        "28c218c44b49222f91536daf5b4d9871638edc8e"
    )


def test_committed_blob_hash_refuses_uncommitted_change(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "prompt.md").write_text("v1", encoding="utf-8")
    git(tmp_path, "add", "prompt.md")
    git(tmp_path, "commit", "-q", "-m", "v1")
    (tmp_path / "prompt.md").write_text("v2", encoding="utf-8")

    with pytest.raises(RuntimeError, match="prompt.md has uncommitted changes"):
        committed_blob_hash(Path("prompt.md"), repo=tmp_path)


def test_committed_blob_hash_refuses_untracked_file(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "prompt.md").write_text("v1", encoding="utf-8")

    with pytest.raises(RuntimeError, match="prompt.md is not committed"):
        committed_blob_hash(Path("prompt.md"), repo=tmp_path)


def test_committed_blob_hash_refuses_missing_file(tmp_path):
    # Both git calls fail here; their empty outputs must not compare as equal.
    git(tmp_path, "init", "-q")

    with pytest.raises(RuntimeError, match="prompt.md is not committed"):
        committed_blob_hash(Path("prompt.md"), repo=tmp_path)


def head(repo: Path) -> str:
    args = ["git", "-C", str(repo), "rev-parse", "HEAD"]
    result = subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603, S607
    return result.stdout.strip()


def committed_repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "models.py").write_text("v1", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("v1", encoding="utf-8")
    git(tmp_path, "add", "src", "uv.lock")
    git(tmp_path, "commit", "-q", "-m", "v1")
    return tmp_path


def test_clean_head_commit_returns_head(tmp_path):
    repo = committed_repo(tmp_path)

    assert clean_head_commit([Path("src"), Path("uv.lock")], repo=repo) == head(repo)


@pytest.mark.parametrize("name", ["src/models.py", "src/new.py", "uv.lock"])
def test_clean_head_commit_refuses_changed_or_new_code(tmp_path, name):
    repo = committed_repo(tmp_path)
    (repo / name).write_text("v2", encoding="utf-8")

    with pytest.raises(RuntimeError, match="uncommitted"):
        clean_head_commit([Path("src"), Path("uv.lock")], repo=repo)

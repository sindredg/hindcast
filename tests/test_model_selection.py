import json
import subprocess
import sys
from pathlib import Path

import pytest

FOLDER = Path(__file__).parent.parent / "eval" / "model-selection" / "dev-outage-v1"

# Three short updates in the dataset's format; the curly apostrophe shows up
# differently depending on whether the portal escapes non-ASCII text.
CONTEXT = (
    "[2026-02-20 18:45 UTC] investigating: Customers see errors reaching the network.\n\n"
    "[2026-02-20 19:09 UTC] identified: A subset of prefixes is affected. "
    "We’re restoring them.\n\n"
    "[2026-02-20 23:50 UTC] resolved: (text withheld)"
)
ANSWER = "A subset of prefixes: “A subset of prefixes is affected.”"
NAMES = ("contoso-ai-resource", "contoso-project")


def portal_row(item_id: int, context: str = CONTEXT) -> dict:
    """One row shaped like a Foundry result download, with the context everywhere it appears."""
    judge_input = json.dumps({"query": "Which prefixes?", "context": context, "response": ANSWER})
    sample_input = json.dumps([{"role": "user", "content": judge_input}], ensure_ascii=False)
    return {
        "object": "eval.run.output_item",
        "id": str(item_id + 1),
        "run_id": "evalrun_9a8b7c6d5e4f30211203f4e5d6c7b8a9",
        "eval_id": "eval_b2c3d4e5f60718293a4b5c6d7e8f90a1",
        "datasource_item_id": item_id,
        "datasource_item": {
            "query": "Which prefixes?",
            "context": context,
            "ground_truth": "A subset of BYOIP prefixes.",
            "sample.output_text": ANSWER,
        },
        "results": [
            {
                "name": "Groundedness",
                "score": 5.0,
                "reason": "The response quotes the update.",
                "sample": {
                    "usage": {"prompt_tokens": 900, "completion_tokens": 80},
                    "input": [{"role": "user", "content": judge_input}],
                    "output": [{"role": "assistant", "content": '{"reason": "ok"}'}],
                },
                "properties": {"sample_input": sample_input},
            }
        ],
        "sample": {
            "input": [
                {"role": "developer", "content": "Use only the text in the message."},
                {"role": "user", "content": f"{context}\n\nQuestion: Which prefixes?"},
            ],
            "output": [{"role": "assistant", "content": ANSWER}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 40},
        },
    }


@pytest.fixture
def sanitize(monkeypatch):
    # The scripts in the folder import each other by plain name, as they do
    # when run from the command line.
    monkeypatch.syspath_prepend(str(FOLDER))
    import sanitize_results

    return sanitize_results


def test_context_is_withheld_at_every_escaping_level(sanitize):
    row = sanitize.sanitize_row(portal_row(0), CONTEXT, NAMES)
    text = json.dumps(row)
    assert "Customers see errors" not in text
    assert row["datasource_item"]["context"] == "<context withheld>"
    assert row["sample"]["input"][1]["content"] == "<context withheld>\n\nQuestion: Which prefixes?"
    judge = row["results"][0]
    assert json.loads(judge["sample"]["input"][0]["content"])["context"] == "<context withheld>"
    nested = json.loads(json.loads(judge["properties"]["sample_input"])[0]["content"])
    assert nested["context"] == "<context withheld>"


def test_non_ascii_context_escaped_by_the_portal_is_withheld(sanitize):
    row = portal_row(0)
    escaped = json.dumps({"context": CONTEXT})  # “We’re” instead of “We’re”
    row["results"][0]["sample"]["input"][0]["content"] = escaped
    clean = sanitize.sanitize_row(row, CONTEXT, NAMES)
    assert "restoring" not in clean["results"][0]["sample"]["input"][0]["content"]


def test_answers_scores_and_reasons_are_kept(sanitize):
    row = sanitize.sanitize_row(portal_row(0), CONTEXT, NAMES)
    assert row["sample"]["output"][0]["content"] == ANSWER
    assert row["datasource_item"]["sample.output_text"] == ANSWER
    assert row["results"][0]["score"] == 5.0
    assert row["results"][0]["reason"] == "The response quotes the update."


def test_run_and_evaluation_ids_become_placeholders(sanitize):
    row = sanitize.sanitize_row(portal_row(0), CONTEXT, NAMES)
    assert (row["run_id"], row["eval_id"]) == ("<run-id>", "<eval-id>")


def test_identifiers_in_a_row_become_placeholders(sanitize):
    row = portal_row(0)
    row["sample"]["note"] = (
        "https://contoso-ai-resource.services.ai.azure.com/api/projects/contoso-project; "
        "traces in contoso-ai-resource-appinsights; "
        "subscription 1b2c3d4e-0000-4000-8000-123456789abc; completion chatcmpl-E1abc9"
    )
    clean = sanitize.sanitize_row(row, CONTEXT, NAMES)
    assert clean["sample"]["note"] == (
        "https://<resource>.services.ai.azure.com/api/projects/<resource>; "
        "traces in <resource>-appinsights; "
        "subscription <uuid>; completion <completion-id>"
    )


def test_a_reformatted_copy_of_the_context_is_reported_as_a_leak(sanitize):
    # The portal could drop the blank lines; exact replacement then misses it. Inside
    # the JSON-encoded judge input the copy is only found once that input is decoded.
    reformatted = CONTEXT.replace("\n\n", "\n")
    row = sanitize.sanitize_row(portal_row(0, context=reformatted), CONTEXT, NAMES)
    assert sanitize.leaks([row], CONTEXT) == [
        "row 0 datasource_item.context",
        "row 0 results[0].sample.input[0].content",
        "row 0 results[0].properties.sample_input",
        "row 0 sample.input[1].content",
    ]


def test_quoting_one_whole_update_is_not_a_leak(sanitize):
    row = sanitize.sanitize_row(portal_row(0), CONTEXT, NAMES)
    row["sample"]["output"][0]["content"] = (
        "“[2026-02-20 19:09 UTC] identified: A subset of prefixes is affected. "
        "We’re restoring them.”"
    )
    assert sanitize.leaks([row], CONTEXT) == []


def test_quoting_a_whole_update_of_two_paragraphs_is_not_a_leak(sanitize):
    update = (
        "[2026-02-20 20:35 UTC] identified: Some customers cannot reload their prefixes "
        "through the dashboard.\n\nA fix for the dashboard is in progress."
    )
    context = CONTEXT.replace("\n\n[2026-02-20 23:50", f"\n\n{update}\n\n[2026-02-20 23:50")
    row = sanitize.sanitize_row(portal_row(0, context=context), context, NAMES)
    row["sample"]["output"][0]["content"] = f"“{update}”"
    assert sanitize.leaks([row], context) == []


def test_leak_check_refuses_a_context_of_one_update(sanitize):
    # With one update the limit is the whole context, so nothing could ever exceed it.
    with pytest.raises(ValueError, match="fewer than two updates"):
        sanitize.leaks([portal_row(0)], "[2026-02-20 18:45 UTC] investigating: Errors.")


def test_identifiers_left_after_sanitizing_are_reported(sanitize):
    text = "register_url: https://contoso-ai-resource.services.ai.azure.com run evalrun_ab12"
    assert sanitize.identifiers(text, NAMES) == ["contoso-ai-resource", "evalrun_ab12"]
    assert sanitize.identifiers("<run-id> scored 5.0", NAMES) == []


def test_log_excerpt_keeps_the_cited_lines_without_identifiers(sanitize):
    removed = (
        "Removed ['ground_truth'] from evaluator_configurations for 'Groundedness': "
        "evaluator data_schema does not declare them."
    )
    version = "evaluatorId provided: azureml://registries/azureml/evaluators/builtin.coherence/versions/13"
    fallback = (
        "Responses API call failed, falling back to chat completions: Error code: 400 - 'top_p'"
    )
    run = "evalrun_9a8b7c6d5e4f30211203f4e5d6c7b8a9"
    log = [
        f"14:15:15 | INFO | {run} | register_url: https://contoso-ai-resource.services.ai.azure.com",
        f"14:15:15 | INFO | {run} | {removed}",
        f"14:15:15 | INFO | {run} | {version}",
        f"14:15:15 | INFO | {run} | Successful response received with status: 200",
        f"14:15:16 | WARNING | {run} | {fallback}",
        f"14:15:16 | INFO | {run} | subscription 1b2c3d4e-0000-4000-8000-123456789abc",
    ]
    assert sanitize.log_excerpt(log, NAMES) == [
        f"14:15:15 | INFO | <run-id> | {removed}",
        f"14:15:15 | INFO | <run-id> | {version}",
        f"14:15:16 | WARNING | <run-id> | {fallback}",
    ]


def test_log_excerpt_keeps_failed_evaluator_calls_and_the_row_summary(sanitize):
    failed = "Error during evaluation: (UserError) OpenAI API hits AuthenticationError: denied"
    run = "evalrun_0f1e2d3c4b5a69788796a5b4c3d2e1f0"
    log = [
        f"18:11:48 | ERROR | {run} | {failed}",
        "openai.AuthenticationError: Error code: 401 - {'error': {'code': 'PermissionDenied'}}",
        f"18:12:05 | WARNING | {run} | EVALUATOR_ROW_SUMMARY run_id={run} errored_items=2",
    ]
    assert sanitize.log_excerpt(log, NAMES) == [
        f"18:11:48 | ERROR | <run-id> | {failed}",
        "18:12:05 | WARNING | <run-id> | EVALUATOR_ROW_SUMMARY run_id=<run-id> errored_items=2",
    ]


def test_names_are_read_from_the_endpoints_in_env(sanitize, tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "HINDCAST_PROJECT_ENDPOINT="
        "https://contoso-ai-resource.services.ai.azure.com/api/projects/contoso-project\n"
        "HINDCAST_STORAGE_URL=https://stcontoso.blob.core.windows.net\n"
        "HINDCAST_SEARCH_ENDPOINT=\n"
        "HINDCAST_CHAT_DEPLOYMENT=gpt-6-luna\n",
        encoding="utf-8",
    )
    assert sanitize.names_from_env(env) == ("contoso-ai-resource", "contoso-project", "stcontoso")


def test_script_writes_nothing_when_a_leak_remains(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    flat = CONTEXT.replace("\n\n", " ")
    (raw / "eval-luna-dev-outage-v1-results.jsonl").write_text(
        json.dumps(portal_row(0, context=flat)) + "\n", encoding="utf-8"
    )
    (raw / "eval-luna-dev-outage-v1-user_logs.txt").write_text("", encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(incident_for(CONTEXT)), encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text(
        "HINDCAST_PROJECT_ENDPOINT=https://contoso-ai-resource.x/api/projects/contoso-project\n"
    )
    out = tmp_path / "out"
    result = run_script(raw, snapshot, env, out)
    assert result.returncode == 1
    assert "row 0 datasource_item.context" in result.stdout
    assert "Customers see errors" not in result.stdout
    assert not out.exists()


def test_script_writes_sorted_rows_and_the_excerpt(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = [portal_row(1), portal_row(0)]
    (raw / "eval-luna-dev-outage-v1-results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    (raw / "eval-luna-dev-outage-v1-user_logs.txt").write_text(
        "x | INFO | evalrun_ab12 | evaluatorId provided: builtin.coherence/versions/13\n"
        "x | INFO | evalrun_ab12 | body: 21\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(incident_for(CONTEXT)), encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text(
        "HINDCAST_PROJECT_ENDPOINT=https://contoso-ai-resource.x/api/projects/contoso-project\n"
    )
    out = tmp_path / "out"
    result = run_script(raw, snapshot, env, out)
    assert result.returncode == 0, result.stdout + result.stderr
    written = [json.loads(line) for line in (out / "results-luna-dev-outage-v1.jsonl").open()]
    assert [r["datasource_item_id"] for r in written] == [0, 1]
    excerpt = (out / "log-excerpt-luna-dev-outage-v1.txt").read_text(encoding="utf-8")
    assert excerpt == "x | INFO | <run-id> | evaluatorId provided: builtin.coherence/versions/13\n"


def portal_run() -> dict:
    """A run record shaped like the portal's "Raw JSON" view of one evaluation run."""
    return {
        "object": "eval.run",
        "created_by": "Alex Example",
        "id": "evalrun_0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        "eval_id": "eval_a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "data_source": {
            "source": {"id": "azureai://accounts/contoso-ai-resource/projects/contoso-project/d"},
            "target": {"model": "gpt-6-luna", "sampling_params": {"top_p": 1}},
        },
        "report_url": "https://ai.azure.com/nextgen/r/AbC123,rg-contoso,,contoso-ai-resource",
        "result_counts": {"total": 5, "passed": 4, "failed": 1, "errored": 0},
    }


def test_run_record_drops_the_person_and_the_portal_link(sanitize):
    clean = sanitize.sanitize_run(portal_run(), NAMES)
    assert "created_by" not in clean
    assert "report_url" not in clean
    assert clean["id"] == "<run-id>"
    assert clean["eval_id"] == "<eval-id>"
    assert (
        clean["data_source"]["source"]["id"]
        == "azureai://accounts/<resource>/projects/<resource>/d"
    )
    assert clean["data_source"]["target"]["sampling_params"] == {"top_p": 1}
    assert clean["result_counts"]["errored"] == 0


def test_script_writes_the_sanitized_run_record_when_one_was_saved(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "eval-luna-dev-outage-v1-results.jsonl").write_text(
        json.dumps(portal_row(0)) + "\n", encoding="utf-8"
    )
    (raw / "eval-luna-dev-outage-v1-user_logs.txt").write_text("", encoding="utf-8")
    (raw / "eval-luna-dev-outage-v1-run.json").write_text(json.dumps(portal_run()))
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(incident_for(CONTEXT)), encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text(
        "HINDCAST_PROJECT_ENDPOINT=https://contoso-ai-resource.x/api/projects/contoso-project\n"
    )
    out = tmp_path / "out"
    result = run_script(raw, snapshot, env, out)
    assert result.returncode == 0, result.stdout + result.stderr
    text = (out / "run-luna-dev-outage-v1.json").read_text(encoding="utf-8")
    assert "Alex Example" not in text
    assert "rg-contoso" not in text
    assert json.loads(text)["id"] == "<run-id>"


def incident_for(context: str) -> dict:
    """A status snapshot whose updates rebuild CONTEXT through build_dataset.context."""
    updates = []
    for block in context.split("\n\n"):
        stamp, rest = block[1:].split("] ", 1)
        status, body = rest.split(": ", 1)
        created = stamp.replace(" UTC", "").replace(" ", "T") + ":00Z"
        updates.append({"created_at": created, "status": status, "body": body})
    return {"incident_updates": updates}


def run_script(raw: Path, snapshot: Path, env: Path, out: Path):
    command = [sys.executable, str(FOLDER / "sanitize_results.py"), "luna"]
    command += ["--raw-dir", str(raw), "--snapshot", str(snapshot)]
    command += ["--env", str(env), "--out-dir", str(out)]
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


def scored_row(item_id: int, scores: dict, answer=(300, 40), judge=(900, 80)) -> dict:
    """A sanitized row with one result per evaluator; every evaluator call uses `judge` tokens."""
    return {
        "datasource_item_id": item_id,
        "results": [
            {
                "name": name,
                "score": score,
                "sample": {"usage": {"prompt_tokens": judge[0], "completion_tokens": judge[1]}},
            }
            for name, score in scores.items()
        ],
        "sample": {"usage": {"prompt_tokens": answer[0], "completion_tokens": answer[1]}},
    }


@pytest.fixture
def summarise(monkeypatch):
    monkeypatch.syspath_prepend(str(FOLDER))
    import summarise_runs

    return summarise_runs


def test_means_are_per_evaluator_over_all_questions(summarise):
    rows = [
        scored_row(1, {"Groundedness": 4.0, "ResponseCompleteness": 5.0}),
        scored_row(0, {"Groundedness": 5.0, "ResponseCompleteness": 3.0}),
    ]
    assert summarise.means(rows) == {"Groundedness": 4.5, "ResponseCompleteness": 4.0}


def test_a_missing_score_makes_the_mean_missing(summarise):
    rows = [scored_row(0, {"Groundedness": 5.0}), scored_row(1, {"Groundedness": None})]
    assert summarise.means(rows) == {"Groundedness": None}


def test_an_evaluator_absent_from_one_question_makes_the_mean_missing(summarise):
    rows = [
        scored_row(0, {"Groundedness": 5.0, "ResponseCompleteness": 5.0}),
        scored_row(1, {"Groundedness": 3.0}),
    ]
    assert summarise.means(rows) == {"Groundedness": 4.0, "ResponseCompleteness": None}


def test_tokens_split_answer_from_judge(summarise):
    rows = [
        scored_row(0, {"Groundedness": 5.0, "Relevance": 5.0}, answer=(300, 40), judge=(900, 80)),
        scored_row(1, {"Groundedness": 5.0, "Relevance": 5.0}, answer=(310, 50), judge=(1000, 90)),
    ]
    assert summarise.tokens(rows) == {
        "answer": (610, 90),
        "judge": (3800, 340),
    }


def with_errored_cell(row: dict, name: str) -> dict:
    """The row with `name` replaced by an errored evaluator call, as the portal writes it."""
    errored = {"name": name, "score": None, "status": "error", "sample": {"error": "401"}}
    row["results"] = [errored if r["name"] == name else r for r in row["results"]]
    return row


def test_errored_evaluator_calls_add_no_judge_tokens(summarise):
    rows = [
        scored_row(0, {"Groundedness": 5.0, "Coherence": 5.0}, judge=(900, 80)),
        with_errored_cell(scored_row(1, {"Groundedness": 5.0, "Coherence": 5.0}), "Coherence"),
    ]
    assert summarise.tokens(rows)["judge"] == (2700, 240)


def test_errored_evaluator_calls_are_listed_by_question(summarise):
    rows = [
        with_errored_cell(scored_row(1, {"Groundedness": 5.0, "Coherence": 5.0}), "Coherence"),
        scored_row(0, {"Groundedness": 5.0, "Coherence": 5.0}),
    ]
    assert summarise.errored(rows) == [("Q2", "Coherence")]


def test_summary_script_reports_an_errored_rule_score_and_exits_1(tmp_path):
    scores = {"Groundedness": 5.0, "ResponseCompleteness": 5.0}
    luna = tmp_path / "luna.jsonl"
    sol = tmp_path / "sol.jsonl"
    luna.write_text(json.dumps(with_errored_cell(scored_row(0, scores), "ResponseCompleteness")))
    sol.write_text(json.dumps(scored_row(0, scores)) + "\n")
    command = [sys.executable, str(FOLDER / "summarise_runs.py"), str(luna), str(sol)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 1
    assert "errored evaluator calls: Q1 ResponseCompleteness" in result.stdout
    assert "ResponseCompleteness: None against 5.0, within 1 point: no" in result.stdout


@pytest.mark.parametrize(
    ("luna", "sol", "met"),
    [
        (
            {"Groundedness": 4.0, "ResponseCompleteness": 4.2},
            {"Groundedness": 5.0, "ResponseCompleteness": 5.0},
            True,
        ),
        (
            {"Groundedness": 3.8, "ResponseCompleteness": 5.0},
            {"Groundedness": 5.0, "ResponseCompleteness": 5.0},
            False,
        ),
        (
            {"Groundedness": 5.0, "ResponseCompleteness": 5.0},
            {"Groundedness": 4.0, "ResponseCompleteness": 3.0},
            True,
        ),
        (
            {"Groundedness": None, "ResponseCompleteness": 5.0},
            {"Groundedness": 5.0, "ResponseCompleteness": 5.0},
            False,
        ),
    ],
)
def test_rule_needs_luna_within_one_point_of_sol(summarise, luna, sol, met):
    assert summarise.rule_scores_met(luna, sol) is met


def test_rule_fails_when_an_evaluator_is_absent(summarise):
    assert summarise.rule_scores_met({"Groundedness": 5.0}, {"Groundedness": 5.0}) is False


def test_summary_script_exits_1_when_luna_is_too_far_behind(tmp_path):
    luna = tmp_path / "luna.jsonl"
    sol = tmp_path / "sol.jsonl"
    luna.write_text(
        json.dumps(scored_row(0, {"Groundedness": 3.0, "ResponseCompleteness": 5.0})) + "\n"
    )
    sol.write_text(
        json.dumps(scored_row(0, {"Groundedness": 5.0, "ResponseCompleteness": 5.0})) + "\n"
    )
    command = [sys.executable, str(FOLDER / "summarise_runs.py"), str(luna), str(sol)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 1
    assert "Groundedness: 3.0 against 5.0, within 1 point: no" in result.stdout
    assert "ResponseCompleteness: 5.0 against 5.0, within 1 point: yes" in result.stdout


UPDATES = "A subset of prefixes is affected. We're restoring them."


def answer_row(item_id: int, answer: str) -> dict:
    """A result row with only the fields check_quotes reads."""
    return {"datasource_item_id": item_id, "sample": {"output": [{"content": answer}]}}


@pytest.fixture
def quotes(monkeypatch):
    monkeypatch.syspath_prepend(str(FOLDER))
    import check_quotes

    return check_quotes


def test_a_quote_from_the_updates_is_found(quotes):
    _, found, total, missing = quotes.check([answer_row(0, ANSWER)], UPDATES)
    assert (found, total, missing) == (1, 1, 0)


def test_a_changed_quote_is_not_found(quotes):
    row = answer_row(0, "“A subset of prefixes was affected.”")
    lines, found, total, _ = quotes.check([row], UPDATES)
    assert (found, total) == (0, 1)
    assert lines[0].startswith("Q1: NOT FOUND")


def test_a_quote_that_is_empty_after_normalising_is_not_found(quotes):
    # Stripping trailing punctuation leaves "", and "" is in every text.
    for empty in ("“…”", "“.”", "“ ”"):
        _, found, total, _ = quotes.check([answer_row(0, f"See {empty}")], UPDATES)
        assert (found, total) == (0, 1), empty


def test_an_answer_without_a_quote_counts_unless_allowed(quotes):
    rows = [answer_row(0, "No quote here."), answer_row(1, "None here either.")]
    _, _, _, missing = quotes.check(rows, UPDATES, no_quote_ok=1)
    assert missing == 1


def test_break_row_makes_its_first_quote_fail(quotes):
    _, found, total, _ = quotes.check([answer_row(0, ANSWER)], UPDATES, break_row=0)
    assert (found, total) == (0, 1)

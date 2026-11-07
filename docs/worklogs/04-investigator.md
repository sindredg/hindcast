# Milestone 4: The investigator

Status: Verified on 2026-11-07. Four slices, built on 2026-10-30, 2026-11-02, 2026-11-03, and 2026-11-07, each with its gate ([1](#gate), [2](#slice-2-gate), [3](#slice-3-gate), [4](#slice-4-gate)) and independent review ([1](#independent-review), [2](#slice-2-independent-review), [3](#slice-3-independent-review), [4](#slice-4-independent-review)). The whole trace left open in the slice 3 gate was read on 2026-11-05 ([worklog 06](06-deployment.md#slice-2-live-run), step 14). Milestone state: [roadmap](../roadmap.md#status).

The sections up to [Independent review](#independent-review) are slice 1, the investigator on case tools.

On this page: [Scope](#scope) · [Pass bar for the live run](#pass-bar-for-the-live-run) · [Work completed](#work-completed) · [Live run](#live-run) · [Gate](#gate) · [Independent review](#independent-review) · [Slice 2: the library search tool](#slice-2-the-library-search-tool) · [Slice 3: screens, PII, challenge, traces, and cost](#slice-3-screens-pii-challenge-traces-and-cost) · [Slice 4: the view parts](#slice-4-the-view-parts)

## Scope

A Foundry prompt agent in Hindcast's tool loop reads the development case through two case-bound tools and returns a cited reconstruction, or ends incomplete with a reason: the first three criteria of [milestone 4](../roadmap.md#4-investigator), case evidence only. Procedure: [runbook](../runbooks/investigator.md); policy: [decision 0015](../decisions/0015-investigation-result-and-citation-policy.md).

## Pass bar for the live run

Written before the run: one `python -m hindcast.investigate cloudflare-2026-02-20` run passes when `complete` with empty `checks.rejected_citations` and `checks.unsupported`. A miss is recorded; a retry after a prompt change is a new run.

## Work completed

### Prompt agent check

A throwaway prompt agent with a strict function tool and output schema, called twice and deleted, confirmed [decision 0002](../decisions/0002-agent-approach.md) option A on gpt-6-luna ([finding](../findings/models.md#a-prompt-agent-drives-app-run-function-tools-under-a-strict-output-schema-2026-10-30)).

### Result schema and citation checks

`hindcast.result`: the strict JSON schema (closed objects, required properties, enums for `verdict`, `kind`, `time_kind`, `source`), checked with `jsonschema` 4.26.0 (newest stable on PyPI, 2026-01-07, new direct dependency). Locally any citation value is accepted, so a malformed citation is rejected alone; the service gets the strict schema. `check_citations` lists each bad citation with a reason and each unsupported item ([decision 0015](../decisions/0015-investigation-result-and-citation-policy.md)).

| Citation | Outcome |
|---|---|
| An `update_id` or `chart_id` of this case, as the tools give it | Kept, including the resolved mark |
| Not an object, missing or empty `ref`, `source` not `case` | `malformed` |
| A `ref` with a `/` whose prefix is not this case's ID | `other-case`, checked before membership, so `other/u1` is never `unknown` |
| Any other `ref` not in the evidence, including a bare `u1` | `unknown` |
| A `rests_on` ID naming no finding | `unknown-finding` |

Tested locally: `tests/test_result.py`, 25 tests, first against a missing module.

### Case tools

`hindcast.tools`: `list_updates` (provider, title, start time, every update, resolved text withheld, dropped entries left out) and `list_charts` (ID, alt text, description, noted as model output and a lead, [#16](https://github.com/sindredg/hindcast/issues/16)). The command binds the case. Every result passes `screen()`, a pass-through until Prompt Shields lands ([decision 0007](../decisions/0007-safety-and-injection.md)). A missing evidence file fails before any model call, naming `python -m hindcast.ingest evidence`.

Tested locally: `tests/test_tools.py`, 14 tests, first against a missing module. All four evidence files load (10, 22, 36, 9 updates; 2, 1, 0, 0 charts).

### Tool loop and caps

`hindcast.investigate.run_investigation` calls the model, runs its function calls, sends the outputs back, and repeats until a response has none. Text next to a function call is not final.

| Event | Result |
|---|---|
| A response without function calls whose text parses | `complete`, then the citation checks |
| A 13th tool call requested | `incomplete: tool-cap`, no further call |
| 120 seconds passed before a tool or model call starts | `incomplete: time-cap` |
| A model call runs past the time left (its client timeout) | `incomplete: time-cap` |
| A tool raises | `incomplete: tool-error: <tool>: <message>` |
| Blank final text, or text that does not parse | `incomplete: empty-result` or `incomplete: schema: <error>` |
| The model call fails, is cut short, or reports no usage | The error propagates; nothing is written |

No client retries: a retry would run past the time left, so a rate-limit error fails the run.

Tested locally: `tests/test_investigate.py`, scripted fake model and injected clock, first against a missing module.

### Agent definition and version

`prompts/investigator.md` holds the instructions and the attack definition from the [answer keys](../../eval/keys/README.md); tools and schema come from the code; effort `medium` in `hindcast.agent`. `ensure_agent_version` fingerprints the definition into the version's metadata: a change creates a new version of `hindcast-investigator-<deployment>`, else the latest is reused. A test checks no prior-knowledge key fact is in the instructions.

Tested locally: `tests/test_agent.py`, 11 tests, first against a missing module.

### Command and guards

`python -m hindcast.investigate <case_id>` refuses a scored case until `eval/rubric/frozen.json` exists and fails on missing evidence, before any cloud call. It writes `build/investigations/<case_id>/<UTC time>-v<agent version>.json` without overwriting and prints status, counts, and usage, never the text. Provenance: prompt blob hash (or SHA-256 marked dirty), commit with a dirty flag over `src/`, `pyproject.toml`, and `uv.lock`, evidence SHA-256; the dirty flag is tested in a temporary Git repository.

Tested locally: `tests/test_investigate.py` (31 tests) and `tests/test_boundaries.py`, 3 tests: the investigator's imports never reach `hindcast.keys`; a stubbed run opens nothing under `eval/keys/` and no file named like a postmortem.

Diagram: [investigation loop](../architecture/README.md#the-investigator).

## Live run

2026-10-30, the [runbook](../runbooks/investigator.md#run-an-investigation) command, commit `7c27d84`, clean tree:

```
complete
findings 10, timeline events 8, factors 2, open questions 4
rejected citations 0, unsupported 0
model calls 2, tool calls 2, seconds 31.353, tokens in 3776 (cached 1034) out 3395
build/investigations/cloudflare-2026-02-20/20261030T040215Z-v1.json
```

Agent `hindcast-investigator-gpt-6-luna` version 1; gpt-6-luna 2026-09-22, prompt blob `fb660e1`, evidence SHA-256 starting `ee6be350`. Pass bar met. A first attempt without `PYTHONPATH=src` failed at import.

Read against the evidence, not the key:

- All 10 findings match the updates they cite, including the dashboard reload problem (update 5) and the customer-withdrawn prefixes (update 6).
- Verdict `cannot tell`: the updates name no cause.
- Root cause: an inference on four findings, a disruption of some BYOIP prefix advertisements, fault not stated.
- No item cites a chart; whether `list_charts` ran is not recorded (2 tool calls, no names). The descriptions put a drop in announced space around 18:00 and a BGP spike around 17:00 to 18:00 UTC; by eye, about 18:10 to 18:45 and from about 17:35 ([finding](../findings/extraction.md#a-chart-description-gets-times-roughly-right-and-can-invent-a-value-2026-10-27)). Both precede the first update at 18:45; the lead went unused.
- The first timeline event cites update 1 for 18:45:16, the case header's time, not update 1's 18:45:17. The reference resolves; support is milestone 5's rule.

Committed unchanged in [`eval/investigations/cloudflare-2026-02-20/`](../../eval/investigations/cloudflare-2026-02-20/README.md).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Attack assessment, timeline, findings, factors, open questions, each with a resolving citation | Tested live, case citations only | Live run: `complete`, 0 rejected, 0 unsupported. Read item by item: verdict, 10 findings, 8 timeline events, root cause, both factors each carry a resolving case citation; the 4 open questions have no citation field. `tests/test_committed_investigation.py` repeats the reading; fails with an inference's citations removed. Library citations: slice 2 |
| A bad citation is rejected with a reason; the rest survives | Tested locally | `tests/test_result.py`: one test per reason, a bad citation next to a good one, an unsupported verdict kept |
| Tool error, empty result, 12 tool calls, or 120 seconds ends incomplete with a reason | Tested locally | `tests/test_investigate.py`: 13th call in separate responses and in one, slow tool before a model call and before a tool call, model timeout, tool error, unknown tool, empty text, schema error. Not provoked live |
| No key or postmortem readable; no scored case before the rubric is frozen | Tested locally | `tests/test_boundaries.py`; `tests/test_investigate.py` refusal tests both ways |

Every new check broken once on 2026-10-30, locally:

| Broken input | Failed tests |
|---|---|
| `other-case` returned as `unknown` | 3 in `test_result.py`, including `test_ref_with_another_cases_prefix_is_other_case` |
| Every citation kept (`if reason is None:` in `check_citations` changed to `if True:`) | 12 in `test_result.py`, 1 in `test_investigate.py`. An unrecorded earlier change failed 9; this row is the reproducible one |
| Local schema check emptied | 5 in `test_result.py` |
| Tool cap set to 13 | `test_thirteenth_tool_call_is_tool_cap`, `test_tool_cap_counts_calls_within_one_response` |
| Time check before a tool call removed | `test_no_tool_call_starts_after_the_time_cap` |
| Role check removed | `test_showcase_case_is_refused_without_the_rubric_lock`, `test_main_refuses_a_showcase_case_before_any_model_call` |
| `import hindcast.keys` added to `hindcast.tools` | `test_investigator_modules_do_not_import_keys` |
| The command reads `eval/keys/README.md`, or writes a file named like a postmortem | `test_investigator_opens_nothing_under_eval_keys_or_a_postmortem`, once each |
| A prior-knowledge key fact appended to the prompt | `test_no_prior_knowledge_key_fact_in_the_instructions` |
| The evidence file loaded after the agent version is created | `test_main_fails_on_missing_evidence_before_any_model_call` |
| The code dirty flag fixed at `False` | `test_code_provenance_marks_a_change_under_the_code_paths_only` |

With every file restored: `uv run --frozen pytest -q`, 305 passed. After the review fixes, 306; with the committed run's 2 tests, 308.

## Independent review

Read-only, fresh context, 2026-10-30, against the code, tests, result file, and evidence, keys unopened. It ran the suite, ruff, pyright, and the runbook's offline step, and broke the loop, schema, citation, time-cap, and evidence edge cases in a scratch copy: each failed its named test. Nothing blocked; no finding rejected. Fixed in this pull request:

- The missing-evidence test checked for no model call only; it now also checks that no agent version is created.
- The dirty flag had no test; one in a temporary Git repository added.
- Gate row 1 rested on the counts; it now records the item-by-item reading.
- The live-run reading overstated what the charts show and said `list_charts` ran; both corrected.
- The "every citation kept" row did not reproduce as 9 failures; it names the change and its 13.
- A test imported `httpx2`, declared only by `openai`; now a pinned development dependency (2.16.0, newest on PyPI on 2026-10-30). Runbook step 4 runs Python through `uv run`.

Opened as issues:

- [#23](https://github.com/sindredg/hindcast/issues/23): a failed model call leaves no record (milestone 5 batch design).
- [#24](https://github.com/sindredg/hindcast/issues/24): the time cap as an HTTP timeout may not bound a whole call; reasoned, not observed (milestone 4 traces).
- [#25](https://github.com/sindredg/hindcast/issues/25): the citation checks accept self-support, cycles, and duplicate finding IDs (milestone 5).
- [#26](https://github.com/sindredg/hindcast/issues/26): results do not record the applied reasoning effort (milestone 5, with #4).

The result does not record which tool each call used; the trace criterion covers it.

After the fixes: `uv run --frozen pytest -q`, 306 passed; `ruff check`, `ruff format --check`, `pyright`, and `yamllint` clean.

## Slice 2: the library search tool

### Pass bar for the slice 2 live runs

Written before the runs. One run of `python -m hindcast.investigate cloudflare-2026-02-20` per model, `gpt-6-luna` then `gpt-6.1-sol`, each from a pushed commit. A run passes when:

- its status is `complete`,
- `checks.rejected_citations` is empty,
- `checks.unsupported` is empty,
- `tool_calls` holds at least one `search_library` call, and
- at least one library citation is kept.

The `gpt-6-luna` run is the evidence for the first [milestone 4](../roadmap.md#4-investigator) criterion; the `gpt-6.1-sol` run checks the comparison model before its seals, and a miss does not hold them. A second run is a new file and says why.

Commit threshold, written before: the longest fragment repeated word for word from a retrieved library section (`difflib`, matches of 25 characters or more) is 120 characters or less.

### Slice 2 work completed

Procedure: [investigator runbook](../runbooks/investigator.md); citation policy: [decision 0020](../decisions/0020-library-citations.md), extending decision 0015.

- **Tool** (`hindcast.tools`): `search_library` takes `query` only, a non-empty string of at most 1,000 characters; other keys are refused. The command binds the case. At most five hits (ref, document, title, heading, date, content, no scores); every returned ref joins `retrieved`; zero hits is an answer.
- **Citations** (`hindcast.result`): `source` is `case` or `library`; a library ref not in `retrieved` is `not-retrieved`; crossed sources are `malformed`; an item with only library citations and no kept `rests_on` is unsupported.
- **Result file** (`hindcast.investigate`): `tool_calls` lists each call with duration, and for a search the query and refs, never hit text; `provenance.library` holds registry blob, index, search API version, embedding model and dimensions. Missing search settings fail before the agent version. The 12-call cap counts searches.
- **Prompt v3** asks for `list_updates`, `list_charts`, and at least one search; a library citation never stands alone.
- **Seals** (`hindcast.seal`): new seals carry `library: true`, a second series; `data/library.yaml` joins the clean paths. `seals.json` only grows ([#33](https://github.com/sindredg/hindcast/issues/33)): values kept, a null `blob` filled once, only `revealed: true` and `dropped: true` added later. `seal run` and `seal upload` refuse a record that does not extend HEAD's; a test walks every committed version (CI checks out the full history; a shallow clone fails). `seal run` makes one library search before the first model call and refuses while it fails (decision 0017 makes a seal with model output final).
- **Page** (`hindcast.app`): shows the slice 2 run; a library citation renders as `library:<ref>`.

### Slice 2 live runs

`python -m hindcast.investigate cloudflare-2026-02-20`, variables exported from `.env`, commit `764b37e`, pushed before the first run, clean tree.

1. **`gpt-6-luna`, 18:04 UTC: missed the bar.** `incomplete: tool-error: search_library: [SSL: UNEXPECTED_EOF_WHILE_READING] ...` after `list_updates` and `list_charts`; 3 model calls, 2 tool calls, 0 searches. The search endpoint refused TLS for a few minutes ([troubleshooting](../troubleshooting.md#investigator-a-library-search-ends-the-run-with-an-ssl-error-2026-11-02)). Agent version 3 created. File local; not a model miss.
2. **`gpt-6-luna`, 18:17 UTC, rerun: passed.**

   ```
   complete
   findings 6, timeline events 9, factors 1, open questions 3
   rejected citations 0, unsupported 0, searches 1, library citations kept 1
   model calls 3, tool calls 3, seconds 39.258, tokens in 10151 (cached 5525) out 3340
   build/investigations/cloudflare-2026-02-20/20261102T181721Z-v3.json
   ```

   The search took 9.688 s: `lib/cloudflare-2022-06-21/s4`, three sections of `cloudflare-2025-07-14`, one of `cloudflare-2024-06-27`. Kept library citation `lib/cloudflare-2022-06-21/s4` ("Cloudflare outage on June 21, 2022"), on F4, next to two case citations and `rests_on` F2 and F3.
3. **`gpt-6.1-sol`, 18:18 UTC: failed** with `openai.APIConnectionError` on a model call after the agent version was made; nothing written ([#23](https://github.com/sindredg/hindcast/issues/23)). Every endpoint answered right after.
4. **`gpt-6.1-sol`, 18:19 UTC, retry: passed.** `complete`; 8 findings, 9 timeline events, 2 factors, 3 open questions; 0 rejected, 0 unsupported; 1 search (4.157 s, five sections, four shared with luna), 1 library citation kept, `lib/cloudflare-2022-06-21/s4`; 3 model calls, 42.319 s, 9,926 input (7,228 cached), 2,764 output. Agent `hindcast-investigator-gpt-6-1-sol` version 2. File local.

Read against the evidence, not the key:

- The luna run's 6 findings match their updates. The library citation backs a sentence calling the earlier postmortem context, "not evidence of this incident's trigger".
- Verdict `cannot tell`; root cause an inference on F2, F3, F4: loss of advertisement for some customer BYOIP prefixes, trigger not stated.
- The first timeline event cites update 1 at its own time, 18:45:17. Update 4 (19:45:56) has no timeline event.
- `list_charts` ran (recorded in `tool_calls`); no item cites a chart.

Overlap (`difflib`, 2026-11-02, 25 characters or more): luna 17.6% against the updates, fragments of at most 56 characters, longest 22 against the library (under 120). Sol: 10.7%, at most 50, longest 20.

The luna run is committed unchanged in [`eval/investigations/cloudflare-2026-02-20/`](../../eval/investigations/cloudflare-2026-02-20/README.md); the page renders it. Switching the live app to the new image is a provision, not done here.

### Slice 2 gate

| Criterion | Status | Evidence |
|---|---|---|
| Full result, each item with a resolving citation, library citations marked | Tested live | Luna run 2: `complete`, 0 rejected, 0 unsupported, 1 search, 1 library citation kept with `source: library`. `tests/test_committed_investigation.py`: every item but the open questions keeps a resolving case citation (local); every library citation was returned by the search (CI) |
| Unretrieved library citation rejected; crossed sources malformed; library-only item unsupported | Tested locally | `tests/test_result.py`: a ref nowhere, with a trailing space, another case, or a prefix, each `not-retrieved`; both crossed sources `malformed`; library-only finding and verdict unsupported; a rejected case citation leaving an item library-only. `tests/test_investigate.py`: through the loop, retrieved kept, unretrieved rejected |
| The search is bound to the case | Tested locally | `tests/test_seal.py::test_preflight_search_runs_on_the_case` (`prepare` binds the command's case ID); `tests/test_tools.py`: `case_id` or `top` refused; `tests/test_investigate.py`: a `LibraryLeak` ends the run as `tool-error: search_library: ...`; `tests/test_search.py` (milestone 3): a disallowed hit raises `LibraryLeak`. Seen live in luna run 1 |
| The 12-call cap counts searches | Tested locally | `tests/test_investigate.py::test_thirteenth_call_being_a_search_is_tool_cap`: the search never runs |
| A malformed query is refused | Tested locally | `tests/test_tools.py::test_search_refuses_bad_arguments`: missing, empty, blank, a number, 1,001 characters, extra keys, not JSON; 1,000 characters accepted |
| A seal is refused while the search fails | Tested locally | `tests/test_seal.py::test_run_refuses_when_the_search_does_not_answer`: no model call, no entry, only the error type; `test_preflight_search_runs_on_the_case`. Accepted gap: a mid-run failure is not retried |
| The seal record only grows | Tested locally | `tests/test_seal.py`: removed, reordered, changed, dropped fields, unknown keys, an edited hash, a restored record, a merge dropping an entry are problems; an appended entry, a filled blob, `revealed` or `dropped` set true are not; a shallow clone refused; the repository's history passes. CI passed with `fetch-depth: 0` (run for `612f0ad`) |

Every new check broken once on 2026-11-02, locally:

| Broken input | Failed tests |
|---|---|
| The extra-keys check loosened to "has a query" | `test_search_refuses_bad_arguments[top]`, `[case-id]` |
| Any kept citation counted as support | `test_library_only_finding_is_unsupported`, `test_library_only_attack_verdict_is_unsupported`, `test_rejected_case_citation_leaves_a_library_only_item_unsupported` |
| An empty `retrieved` set passed to the citation check | `test_library_citation_from_a_search_is_kept_and_an_unretrieved_one_rejected` |
| `data/library.yaml` removed from the seal's clean paths | `test_library_registry_change_is_refused` |
| `LIBRARY = False` | `test_run_records_hash_then_uploads`, `test_a_seal_without_the_library_does_not_block_one_with_it` |
| The record check compares key presence only | `test_record_change_is_a_problem[reordered]`, `[hash]`, `test_filled_blob_cannot_change`, `test_history_with_a_changed_hash_is_a_problem` |
| The history walk skips the parent comparison | `test_history_with_a_changed_hash_is_a_problem`, `test_history_restored_from_an_earlier_commit_is_a_problem` |
| A committed run's library citation changed to an unretrieved ref (a copy) | `test_library_citations_were_retrieved_in_the_run`, `test_every_item_but_the_open_questions_cites_the_case[...v3...]` |
| A 150-character fragment of a retrieved section added to a finding (a copy) | `test_library_text_is_not_repeated_at_length` |
| The page pointed back at the slice 1 run | `test_page_marks_a_library_citation` |
| `--full-history` removed from the history walk (after the review) | `test_history_with_a_merge_that_drops_an_entry_is_a_problem` |
| The refusal's `from None` removed, or replaced by `from error` (after the review) | `test_run_refuses_when_the_search_does_not_answer`, once each |
| The preflight search removed from `seal run` | `test_run_refuses_when_the_search_does_not_answer`, `test_preflight_search_runs_on_the_case` |

Committed file restored byte for byte (`cmp`). With every file restored: `uv run --frozen pytest -q`, 470 passed (408 on `main` before). The search API version comes from `hindcast.index.SEARCH_API_VERSION`.

### Slice 2 independent review

Read-only, fresh context, 2026-11-02, over `48181dc..138ab3c`: suite rerun (469 passed), `main` recounted (408), the committed run's fields and the 22-character fragment checked, the merge case reproduced in a scratch repository. Each finding was checked against the code first.

Fixed in this pull request:

| Finding | Fix |
|---|---|
| A merge keeping one parent's `seals.json` was skipped by Git's history simplification, so a merge dropping an entry passed | `--full-history`; `test_history_with_a_merge_that_drops_an_entry_is_a_problem`, failed first |
| The preflight refusal test checked `__cause__`, empty for an implicitly chained error | The test checks the printed traceback; fails with `from None` removed and with `from error` |
| The run README named prompt v2 for the slice 1 run; its blob is v1 | Corrected |
| The troubleshooting entry cited decision 0015 for the tool-failure rule | Cites the loop and decision 0020 |
| "120 seconds at most" on the architecture page and README: a running search is not cut off | Reworded; [#49](https://github.com/sindredg/hindcast/issues/49) |
| The case-binding gate row cited tests whose stub never sees a case ID | Cites `test_preflight_search_runs_on_the_case` |
| The runbook showed `--env-file`; the runs exported `.env` | Step 2 shows the command that ran |
| "Returns five hits" where `top=5` is a maximum | "At most five" |

Opened as issues: two branches both adding seals fail the history test ([#44](https://github.com/sindredg/hindcast/issues/44)); the record check misses a type change that compares equal ([#45](https://github.com/sindredg/hindcast/issues/45)); refs count as retrieved before `screen()` ([#46](https://github.com/sindredg/hindcast/issues/46)); `provenance.library` names the index, not its contents ([#47](https://github.com/sindredg/hindcast/issues/47)); a sealed file keeps a tool error's raw SDK message ([#48](https://github.com/sindredg/hindcast/issues/48)); a search can run past the time cap ([#49](https://github.com/sindredg/hindcast/issues/49)).

Set aside: the mid-run search failure in a seal (accepted gap), the live agent versions, the sol run's local figures, the diagrams' geometry.

## Slice 3: screens, PII, challenge, traces, and cost

### Pass bar for the slice 3 live runs

Written before the runs. One run of `python -m hindcast.investigate cloudflare-2026-02-20` per model, from a pushed commit ([#39](https://github.com/sindredg/hindcast/issues/39)), then one challenge per model on its own run. A run passes when:

- its status is `complete`, with no rejected citation and no unsupported item under the stricter shown-ref rule,
- every tool call made at least one screen call and withheld nothing,
- `checks.pii` is present, and its hit count is recorded as the false-positive figure on clean evidence, and
- the result has a cost from price table version 1.

A withheld item on the development case stops the work until the false positive is looked at.

A challenge passes when it completes with a verdict, nothing rejected, the question screened before any model call. Question, fixed before the runs: "Which status update shows this, and does any later update contradict it?", on each run's first observation finding.

### Slice 3 work completed

Design: [decision 0021](../decisions/0021-screens-pii-and-challenge.md); procedure: [investigator runbook](../runbooks/investigator.md).

| Part | Where | What it does |
|---|---|---|
| Safety clients | `hindcast.safety` | Prompt Shields (API 2024-09-01) and PII detection (API and model 2026-05-01), plain REST, Entra token, no retry. Per call at most 5 documents and 10,000 characters (Prompt Shields) or 5,000 code points (PII). Errors name status and code, never the message; a missing flag is an error |
| Screens per item | `hindcast.tools` | Each update, chart, and library hit screened once per run; a flagged one becomes its ref and `"withheld": "prompt-shields"`. Tracks case refs shown, refs withheld, library refs shown (`retrieved`, after the screen: [#46](https://github.com/sindredg/hindcast/issues/46)) |
| Citations | `hindcast.result` | A withheld ref is rejected as `withheld`; a case ref the run never read as `not-shown` |
| PII | `hindcast.redact` | Every free-text field to PII detection; a hit becomes `[<Category>]`; `checks.pii` lists path, category, confidence. `PersonType`, `Organization`, `DateTime`, `URL`, `IPAddress` pass |
| Loop | `hindcast.investigate` | `screen-error` or `pii-error` on a failed screen or PII check, `time-cap` when a tool runs out of time. Each model call gets the time left; a tool call's search, embedding, and screen share it, one try ([#49](https://github.com/sindredg/hindcast/issues/49)). The PII check runs after the answer with its own 30 seconds |
| Spans | `hindcast.telemetry`, `hindcast.investigate`, `hindcast.challenge` | `investigation`, or `challenge` with the question's `screen` span and a `challenge_loop`; under either `model_call` (seconds, time left, tokens), `tool_call` (seconds, withheld, screen calls), `pii` (hits). Service name `hindcast-investigator`; every span kept |
| Cost | `data/prices.yaml`, `hindcast.costs` | Price table version 1, meter and date per price; each result records cost by part. An unpriced deployment is refused before the agent version; a call past the short-context limit is recorded as not priced |
| Challenge | `hindcast.challenge`, `prompts/challenger.md`, `hindcast.agent` | A second agent per deployment with a challenge schema; question screened, then PII-masked; 6 tool calls, 90 seconds; stored under `challenges/` |
| Page | `hindcast.app` | Lists development results, opens on the newest `gpt-6-luna` run, shows stored challenges per finding, withheld items, PII hits, cost. `HINDCAST_CHALLENGE_LIVE=1` adds a question box per finding |
| Seals | `hindcast.seal` | Runs with screens, PII check, spans, cost. Record values compared as JSON, so a changed type is a change ([#45](https://github.com/sindredg/hindcast/issues/45)) |

### Slice 3 live runs

Both services answered 401 until the custom role "Hindcast Safety Caller" was assigned on the Foundry resource at 17:05:54Z; Prompt Shields answered from 17:08:28Z, PII detection from 17:10:07Z ([finding](../findings/safety.md)). Runs with `--env-file .env`, commit `81e01a7`, pushed first, clean tree.

| | gpt-6-luna, 17:11:46Z | gpt-6.1-sol, 17:12:55Z |
|---|---|---|
| Agent | `hindcast-investigator-gpt-6-luna` version 3 | `hindcast-investigator-gpt-6-1-sol` version 2 |
| Outcome | `complete`; 6 findings, 8 timeline events, 2 factors, 4 open questions | `complete`; 9 findings, 9 timeline events, 2 factors, 3 open questions |
| Citations | 0 rejected, 0 unsupported; 1 search, no library citation kept | 0 rejected, 0 unsupported; 1 search, 1 library citation kept |
| Screens | 5 calls, 25 records, 0 withheld | 5 calls, 27 records, 0 withheld |
| PII | 6 calls, 26 records, 0 hits | 6 calls, 28 records, 0 hits |
| Usage | 3 model calls, 42.195 s, 10,648 input tokens (4,251 cached), 3,039 output | 3 model calls, 56.597 s, 10,552 input (4,251 cached), 2,940 output |
| Cost | USD 0.037583: model 0.002202, screens 0.009375, PII 0.026, embeddings 0.000007 | USD 0.080555: model 0.042427, screens 0.010125, PII 0.028, embeddings 0.000003 |

Both passed. Nothing flagged or masked: both false-positive figures are 0. Luna kept no library citation this time (slice 2's did); not a criterion here.

PII is the larger cost: USD 1.00 per 1,000 records against 0.375 for Prompt Shields, more than the luna model calls.

Challenges, from the command, with the fixed question:

| Challenge | Outcome | Usage and cost |
|---|---|---|
| luna F1, 17:14:24Z, agent `hindcast-challenger-gpt-6-luna` version 1 | `complete`, `stands`; 2 case citations kept, 0 rejected | 2 model calls, 1 tool call, 6.353 s, 3 screen calls; USD 0.006129 |
| sol F1, 17:14:51Z, `hindcast-challenger-gpt-6-1-sol` version 1 | `complete`, `stands`; 10 kept, 0 rejected | 2 model calls, 1 tool call, 9.238 s, 3 screen calls; USD 0.014526 |
| luna F2, 17:19:08Z, after the sampler fix | `complete`, `stands`; 8 kept, 0 rejected | 2 model calls, 3 tool calls, 15.628 s; USD 0.011807 |
| luna F3, 17:42:10Z, after the workspace's shared keys were turned off | `complete`, `stands`; 6 kept, 0 rejected | 2 model calls, 2 tool calls, 7.607 s; USD 0.007431 |
| luna F4, 17:46:02Z, after Application Insights was disconnected from Foundry | `complete`, `stands`; 5 kept, 0 rejected | 2 model calls, 1 tool call, 10.218 s; USD 0.006193 |

Traces, read with `az monitor app-insights query`:

1. The first four runs' spans arrived in part: 6 of 10 `model_call`, no `investigation`, no question `screen`. Cause: the exporter's default sampler, five traces per second ([finding](../findings/observability.md#the-azure-monitor-exporter-samples-five-traces-per-second-by-default-2026-11-03)). With `OTEL_TRACES_SAMPLER=parentbased_always_on` the F2 trace arrived whole, each span `itemCount` 1.
2. Foundry's server-side spans stored every prompt and the unmasked answer despite client content recording off ([finding](../findings/observability.md#foundrys-server-side-traces-store-every-prompt-and-answer-whatever-the-client-sets-2026-11-03)). Application Insights disconnected from Foundry at 17:45:50Z; F4's spans arrived, no server-side span (read 17:50Z).
3. `AIProjectInstrumentor` added no client-side span; every GenAI span came from the server side.
4. F2's question `screen` span was in its own trace; `run_challenge` now opens the `challenge` span around it (in-memory exporter, not live).

Every `model_call` span that arrived ran within its time left ([#24](https://github.com/sindredg/hindcast/issues/24)):

| Run | Seconds of time left |
|---|---|
| gpt-6-luna investigation | 2.191 of 113.557; 24.225 of 104.724 |
| Challenges F1 (luna), F1 (sol), F2 | 2.584 of 90, 3.265 of 87.065; 3.248 of 90, 5.363 of 86.325; 3.72 of 90, 6.712 of 81.224 |

For the sampled-out calls, each run's total (42.2 s and 56.6 s) is under the 120-second cap (reasoned from the result files).

The runs and five challenges are committed unchanged in [`eval/investigations/cloudflare-2026-02-20/`](../../eval/investigations/cloudflare-2026-02-20/README.md), with their overlap figures. None repeats library text in 25 characters or more.

### Slice 3 gate

| Criterion | Status | Evidence |
|---|---|---|
| Flagged item withheld, rest shown, withheld ref not citable | Tested locally | `tests/test_tools.py::test_flagged_update_is_withheld_and_the_rest_shown`, `test_the_case_title_is_screened_and_withheld_when_flagged`, `test_flagged_hit_is_not_retrieved`, `test_chart_screens_alt_text_and_description`; `tests/test_result.py::test_withheld_case_ref_is_rejected_as_withheld`, `test_withheld_library_ref_is_rejected`, `test_unread_case_ref_is_rejected_as_not_shown`; `tests/test_investigate.py::test_flagged_update_is_withheld_in_the_run_and_its_citation_rejected`. Not provoked live |
| Screen error ends the run; missing flag is not a pass | Tested locally | `test_screen_error_ends_run_as_screen_error`, `tests/test_safety.py::test_a_service_error_becomes_a_screen_error`, `test_a_missing_flag_is_not_a_pass`, `test_a_missing_prompt_flag_is_not_a_pass` (shape seen live) |
| A long result is split within the limits | Tested locally | `test_documents_of_25000_characters_are_split_within_the_limits`, `test_batches_hold_the_limits`, `test_documents_flag_a_text_when_any_piece_is_flagged` |
| PII masked and recorded by path and category | Tested locally; tested live with no hit | `test_pii_hits_are_masked_in_the_written_file`, `test_search_queries_are_pii_masked_in_the_record`, `tests/test_redact.py` (overlapping hits), `test_pii_hit_outside_the_text_raises`, `test_pii_maps_entities_with_codepoint_offsets` (curly quotes, an emoji). Live: 0 hits in both runs and five challenges; a probe on a made-up name returned `Person` |
| Flagged question makes no model call; unscreened result not challenged | Tested locally | `tests/test_challenge.py::test_flagged_question_makes_no_model_call`, `test_a_question_screen_error_ends_the_challenge`, `test_a_question_pii_error_ends_the_challenge`, `test_an_unscreened_result_is_refused`; `tests/test_app.py::test_no_challenge_box_for_an_unscreened_result` |
| Unresolved challenge citation rejected | Tested locally; tested live with none | `test_challenge_unknown_ref_is_rejected`, `test_challenge_case_citation_needs_its_own_reading`; live: 0 rejected in five challenges; `tests/test_committed_investigation.py` resolves each committed challenge's case citations (local) |
| A finding can be challenged from the interface, with cited answer | Tested live in a browser | Four challenges of F5 from the local page's box, 2026-11-03, 19:26 to 19:32Z: all `complete`, `stands`, every citation a case ref (one a chart), none rejected ([screenshots](../screenshots/README.md)). `tests/test_app.py::test_challenge_box_with_live_flag` (stubbed), `test_no_challenge_box_without_live_flag`. Five more from the command, above |
| Every investigation and challenge has a trace and a cost | Tested live for challenges; tested live in part for investigations; the root span tested locally | Challenges F2 to F4: whole traces. Investigations: tool calls, PII checks, 2 of 6 model calls arrived, no `investigation` root span, before the sampler fix; none ran after it. `tests/test_telemetry.py::test_configure_keeps_every_span`, `tests/test_investigate.py::test_spans_carry_no_text`, `tests/test_challenge.py::test_a_challenge_is_one_trace`. A cost in every file |
| An unknown deployment has no price | Tested locally | `tests/test_costs.py::test_unknown_deployment_raises`; `tests/test_investigate.py::test_a_deployment_without_a_price_is_refused_before_any_model_call` |
| The cost matches what is billed | Accepted gap | One Cost Management query on 2026-11-07 (`POST .../resourceGroups/<resource-group>/providers/Microsoft.CostManagement/query`, `ActualCost`, 2026-11-03, by meter), NOK: gpt-6-luna 0.069896, gpt-6.1-sol 0.512417, text records 0.385893, embeddings 0.000121. No per-run line, other calls that day, part of the text records at zero, USD table without an exchange rate: no per-run comparison |
| The time cap holds for whole calls ([#24](https://github.com/sindredg/hindcast/issues/24)) | Tested live, in part; the rest reasoned | The `model_call` spans above; the dropped ones bounded by each run's total time |
| A search shares the time left with its embedding and screen, no retry ([#49](https://github.com/sindredg/hindcast/issues/49)) | Tested locally | `tests/test_tools.py::test_a_search_and_its_screen_share_the_time_left`, `test_a_tool_call_with_no_time_left_for_its_screen_times_out`; `tests/test_search.py::test_the_search_request_gets_what_the_embedding_left`, `test_search_passes_timeout_and_no_retries`, `test_search_timeout_raises_timeout_error`, `test_investigation_search_client_makes_no_retries`; `tests/test_index.py::test_embedder_with_a_timeout_makes_one_try_within_it`, `test_embedder_timeout_raises_timeout_error`; `tests/test_investigate.py::test_tool_timeout_is_time_cap` |
| The seal path runs with the screens | Tested locally | `tests/test_seal.py::test_seal_path_runs_with_screens` |
| The seal record reports a changed type ([#45](https://github.com/sindredg/hindcast/issues/45)) | Tested locally | `tests/test_seal.py::test_record_value_of_another_type_is_a_change` |
| Workspace refuses shared keys; traces still arrive ([#2](https://github.com/sindredg/hindcast/issues/2)) | Tested live | `features.disableLocalAuth` read back `true` at 17:42:01Z; the F3 spans, Foundry's included, arrived at 17:42:46Z |

Every new check broken once on 2026-11-03, locally:

| Broken input | Failed tests |
|---|---|
| `batches` allows six documents | `test_batches_hold_the_limits` |
| A missing document flag read as a pass | `test_a_missing_flag_is_not_a_pass` |
| A missing prompt flag read as a pass (the shape seen live) | `test_a_missing_prompt_flag_is_not_a_pass` |
| A search's refs join `retrieved` before the screen | `test_flagged_hit_is_not_retrieved` |
| The withheld check removed for case refs | `test_withheld_case_ref_is_rejected_as_withheld` |
| `open_questions` left out of the PII fields | `test_every_text_field_is_sent`, `test_redact_records_path_and_category_not_text` |
| `prepare` builds the tools without the shield | `test_seal_path_runs_with_screens`, `test_main_writes_the_result_and_prints_counts_never_the_text` |
| A `ScreenError` caught as a pass | `test_screen_error_ends_run_as_screen_error` |
| The unmasked answer returned after the PII check | `test_pii_hits_are_masked_in_the_written_file` |
| An unknown deployment priced at zero | `test_unknown_deployment_raises` |
| The question screen skipped | `test_flagged_question_makes_no_model_call` |
| The original run's library refs left out of a challenge's `retrieved` | `test_challenge_cites_original_run_refs_without_searching` |
| Stored challenges not filtered by result file | `test_page_shows_stored_challenges` |
| The challenge box shown without the flag | `test_no_challenge_box_without_live_flag` |
| The seal record compared with `==` | `test_record_value_of_another_type_is_a_change`, three cases |
| No sampler set | `test_configure_keeps_every_span` |
| The challenge without its own root span | `test_a_challenge_is_one_trace` |
| A committed challenge's citation changed to `u99` (a copy) | `test_challenge_case_citations_resolve` |
| A 150-character library fragment added to the sol run (a copy) | `test_library_text_is_not_repeated_at_length` |
| The question's screen error read as a pass (after the review) | `test_a_question_screen_error_ends_the_challenge` |
| The question's PII error read as no hit (after the review) | `test_a_question_pii_error_ends_the_challenge` |
| A PII timeout not caught in the loop (after the review) | `test_a_pii_timeout_ends_the_run_as_pii_error` |

Committed files restored byte for byte (`cmp`). With every file restored: `uv run --frozen pytest -q`, 600 passed after the review's fixes (470 on `main` before).

The committed cost parts were rounded after summing, so luna's parts add to 0.037584 against a total of 0.037583. The code now totals the rounded parts; the files keep what the run wrote.

### Slice 3 independent review

Read-only, fresh context, 2026-11-03, over `1251452..58bac41`: suite rerun (585 passed), `main` recounted (470), every committed figure checked against its file. Every screen or PII failure fails closed. Each finding was checked against the code first.

Fixed in this pull request; each code fix has a test that failed first:

| Finding | Fix |
|---|---|
| The case title reached the model unscreened | Screened with the updates; withheld in place when flagged |
| Overlapping PII hits left part of a span; a hit outside its text was recorded but not masked | Overlaps merge; a hit outside its text, or an entity without its fields, is a PII error |
| One search tool call could take about three times the time left | One budget per tool call, shared in order |
| A challenge could run on a result from before the screens | Refused; the page shows no box for it |
| The model's search queries, kept in the result file, had no PII check | Masked like the answer, as `tool_calls[n].query` |
| A credential failure escaped the service-error mapping, with its message | Every azure-core error maps to its type only |
| The cost total summed unrounded parts | The total is the sum of the rounded parts |
| The gate claimed whole traces for the investigations | The trace row says which traces arrived whole |
| Figures: the committed-run test count, the PII answer time, "four questions" in decision 0021, the observability finding's scope, the deleted connection's level, the `screen` span's place, the Prompt Shields record unit stated as fact | Corrected; the record unit is marked as assumed until the bill is compared |

Opened as issues: pieces split with no overlap ([#50](https://github.com/sindredg/hindcast/issues/50)); live PII offsets after non-ASCII text not yet seen ([#51](https://github.com/sindredg/hindcast/issues/51)); no price line for semantic queries ([#52](https://github.com/sindredg/hindcast/issues/52)); the page renders model text as Markdown ([#53](https://github.com/sindredg/hindcast/issues/53)); the Prompt Shields limit may count UTF-16 units ([#54](https://github.com/sindredg/hindcast/issues/54)).

The `IPAddress` exemption, wider than the spec's "public service addresses", is in decision 0021's trade-offs.

Set aside: the live Azure state (the role, the deleted connection, `disableLocalAuth`, the spans), the prices against their sources, the diagrams' geometry.

## Slice 4: the view parts

[Decision 0008](../decisions/0008-user-interface.md) names four visual parts; the attack assessment came with slice 3. This slice adds the other three on stored results, no model call, no Azure resource.

The scored view differs from decision 0008, which asks for the reconstruction next to the key: the page shows the key's text, outcome, credit, label, and the run items behind the outcome as field paths with finding IDs (`findings[8] (F9)`), not the run's text, which is one tab away under the same IDs. Repeating it would show the investigation twice.

### Slice 4 work completed

| Part | Where | What it does |
|---|---|---|
| Timeline chart | `hindcast.views.timeline_spec`, the Investigation tab | Vega-Lite spec, Streamlit's built-in renderer, no new dependency: each event at its UTC time, stated a filled green circle, inferred a hollow grey diamond. An event without an ISO UTC time stays in the list, left out of the chart with a caption. UTC scale on the x axis. Tooltip: time and kind only |
| Evidence graph | `hindcast.views.evidence_dot`, the Evidence tab | DOT text for `st.graphviz_chart`, rendered in the browser without the `graphviz` package (Streamlit 1.67.0's `graphviz_chart.py`). Root cause (green) and factors, their findings, the updates, charts, and library sections cited; library amber and dashed. Node IDs are the graph's own; labels escape backslash and double quote |
| Scored view | `hindcast.views.load_scored`, the Score tab | One row per key item: key text, frozen label, outcome, credit, run items behind it, beside the primary score, from `scores.json`, judgment, review, reviewer judgment, key, labels. Refuses a key or labels off their frozen hash, a judgment whose `run_sha256` is not the file's, a review whose `judgment_sha256` is not the judgment's, a reviewer judgment off its named hash (`load_second_judgments`). Every cell escaped |
| Shared run items | `hindcast.evaluation.score.run_items_behind` | The run items behind each outcome, judge's or reviewer's where it decided; `score_run` and the view call the same function |
| Scored runs in the picker | `hindcast.app` | A "Results" control switches between development and scored showcase runs. The image copies neither keys nor scored runs (`.dockerignore`, `Dockerfile`). With `HINDCAST_LIVE=1`, the challenge box appears only for a development case or an injection copy |
| Graph labels | `hindcast.views.dot_label` | Control characters, NUL included, become spaces before escaping |

### Slice 4 gate

| Criterion | Status | Evidence |
|---|---|---|
| Timeline chart: each event at its UTC time, stated and inferred drawn differently | Tested locally; rendered locally | `tests/test_views.py::test_timeline_spec_places_every_event_and_marks_the_time_kind`, `test_utc_accepts_a_utc_time_only`, `test_timeline_spec_leaves_out_an_event_without_a_utc_time`; `tests/test_app.py::test_page_draws_the_timeline_chart_and_the_evidence_graph`. Rendered in headless Chrome on 2026-11-07 ([screenshots](../screenshots/README.md#local-page-view-parts-2026-11-07)). No stored run has an inferred time; the hollow diamond and caption were seen on an edited copy, not committed |
| Evidence graph: factors to findings, findings to citations, library marked | Tested locally; rendered locally | `test_evidence_graph_links_claims_to_findings_and_citations` on `20261102T181721Z-v3.json`, which cites a library section; rendered on 2026-11-07 |
| Model text cannot change the graph or the chart | Tested locally | `test_dot_label_keeps_hostile_text_inside_its_string`, `test_evidence_graph_with_hostile_claims_adds_no_node_or_edge`, `test_evidence_graph_never_uses_run_text_as_a_node_id`, `test_timeline_tooltip_carries_no_model_text`, `test_dot_label_turns_control_characters_into_spaces`. Headless Chrome, 2026-11-07, bundled Graphviz on a copy of `20261102T181721Z-v3.json` with every claim replaced by a quote, an edge statement, a `URL` attribute, `\N`, `\l`, braces, and `<b>`: 15 nodes, 19 edges, as the clean run, no link element, text shown as written in 8 nodes (page SVG) |
| Scored view: key item with outcome, label, credit; refuses changed key, labels, or foreign judgment | Tested locally; rendered locally | `test_load_scored_pairs_each_key_item_with_its_outcome`, `test_load_scored_refuses_a_run_file_the_judgment_was_not_made_for`, `test_load_scored_refuses_a_key_or_labels_changed_after_freezing` (both), `test_load_scored_refuses_a_review_made_on_another_judgment`, `test_load_scored_refuses_an_edited_reviewer_judgment`, `test_scored_rows_refuse_items_the_key_does_not_have`; `tests/test_app.py::test_page_shows_the_score_of_a_scored_run`, `test_page_shows_no_score_next_to_an_edited_run`, `test_page_shows_no_score_from_a_malformed_scores_file`, `test_page_lists_the_scored_runs` (60 runs) |
| No challenge on a scored run | Tested locally | `test_no_challenge_box_on_a_scored_run_with_live_flag`, failed before the fix (every finding of `hindcast/github-2026-08-17/r1/a1` had the box); `test_challenge_box_with_live_flag` still finds it on a screened development run |
| The score table renders model text as text | Tested locally | `test_page_shows_the_score_table_as_plain_text` |
| Sharing `run_items_behind` leaves every score as it was | Tested locally | `test_scores_json_still_matches_the_score_of_every_run`: every field of all 60 runs' scores equals its `scores.json` entry after a JSON round trip |
| The view parts on the deployed page | Accepted gap | No environment since the final removal of 2026-11-06 ([worklog 06](06-deployment.md#slice-2-final-removal)); not worth one for stored results. Rendered locally with Streamlit 1.67.0, the image's version. The scored view is local by design: the image leaves out the keys (`.dockerignore`) and scored runs |

Every new check broken once on 2026-11-07, locally, on a copy of `src/` (page changes in place, restored after):

| Broken input | Failed tests |
|---|---|
| The DOT label's quote escape removed | `test_dot_label_keeps_hostile_text_inside_its_string`, `test_evidence_graph_with_hostile_claims_adds_no_node_or_edge`, `test_evidence_graph_never_uses_run_text_as_a_node_id` |
| The DOT label's backslash escape removed | The same three |
| A time with another offset accepted as UTC | `test_utc_accepts_a_utc_time_only`, `test_timeline_spec_leaves_out_an_event_without_a_utc_time` |
| The chart's UTC scale removed | `test_timeline_spec_places_every_event_and_marks_the_time_kind`, `test_page_draws_the_timeline_chart_and_the_evidence_graph` |
| The event text added to the tooltip | `test_timeline_tooltip_carries_no_model_text` |
| The library node's style removed | `test_evidence_graph_links_claims_to_findings_and_citations` |
| A factor's links to its findings dropped | `test_evidence_graph_links_claims_to_findings_and_citations` |
| The judgment's run hash not checked | `test_load_scored_refuses_a_run_file_the_judgment_was_not_made_for`, `test_page_shows_no_score_next_to_an_edited_run` |
| The frozen hash of the key and labels not checked | `test_load_scored_refuses_a_key_or_labels_changed_after_freezing`, both cases |
| The key item check removed | `test_scored_rows_refuse_items_the_key_does_not_have` |
| The reviewer's run items ignored | `test_run_items_behind_takes_the_reviewer_items_where_it_decided`, `test_scores_json_still_matches_the_score_of_every_run`, `tests/test_score.py::test_a_reviewer_decision_rests_on_the_reviewers_run_items`, `test_a_reviewer_decision_without_its_judgment_is_refused` |
| The page's refusal not caught | `test_page_shows_no_score_next_to_an_edited_run` |
| The Score tab not added | `test_page_shows_the_score_of_a_scored_run`, `test_page_lists_the_scored_runs` |
| The key cell not escaped | `test_page_shows_the_score_table_as_plain_text` |
| The "Results" control ignored | `test_page_lists_the_scored_runs` |
| The challenge box without the case role check (after the review) | `test_no_challenge_box_on_a_scored_run_with_live_flag` |
| The review's judgment hash not checked (after the review) | `test_load_scored_refuses_a_review_made_on_another_judgment` |
| The reviewer judgment read without its hash (after the review) | `test_load_scored_refuses_an_edited_reviewer_judgment` |
| Control characters kept in a graph label (after the review) | `test_dot_label_turns_control_characters_into_spaces` |
| `TypeError` not caught by the page (after the review) | `test_page_shows_no_score_from_a_malformed_scores_file` |
| The primary score set to `None` (after the review; the earlier regression test compared four fields and missed it) | `test_scores_json_still_matches_the_score_of_every_run`, `tests/test_score.py::test_unmentioned_not_inferable_factor_leaves_denominator`, `test_aggregate_gives_mean_min_max_and_failures` |

With every file restored: `pytest -q`, 1001 passed, 3 skipped (981 collected on `main` at `e12c856`), run on the environment's Python because the lock asks for uv 0.13.7 and the local uv was 0.13.5 (watchdog, pyarrow, python-dateutil match the lock, read 2026-11-07). After the review's fixes, with uv 0.13.7 and `uv sync --locked --all-extras`: `uv run --frozen pytest -q`, 1006 passed, 3 skipped; `ruff check`, `ruff format --check`, `pyright` (0 errors), `yamllint --strict` clean.

### Slice 4 independent review

Read-only, fresh context, 2026-11-07, over `c3d8881` (PR [#101](https://github.com/sindredg/hindcast/pull/101)), 11 items: decision 0008's coverage, the three view parts, the `run_items_behind` refactor, tests and broken inputs, screenshots, gate and roadmap, documentation, public-text rules, dependencies. Each finding was checked against the code first.

Verdicts: 9 of 11 OK, 2 with findings (decision 0008's coverage; the scored view's two missing hash checks); the gate item OK with a wording note on two rows. None could-not-check. The review also found the challenge box on scored runs.

Fixed in this pull request; each code fix has a test that failed first:

| Finding | Fix |
|---|---|
| With `HINDCAST_LIVE=1`, a scored showcase run got the challenge box (the box checked the run's state only); a challenge there makes paid calls and writes beside the scored run | The box needs the case's role in `LIVE_ROLES`; the page says why there is none |
| The scored view skipped two checks the score makes: the review's `judgment_sha256` and the reviewer judgment against the hash its decisions name; an edited reviewer judgment reached the Run items column | Both checks, the second through `load_second_judgments` |
| The worklog did not say the scored view differs from decision 0008 | Stated under [Slice 4](#slice-4-the-view-parts) |
| Two gate rows were "configured, not tested": slice 3's billed cost and slice 4's deployed page | Each an accepted gap with its reason; the cost row records one Cost Management read |

Plan-only items, done here because each was small:

| Item | Outcome |
|---|---|
| The regression test compared four fields of each score | Every field, after a JSON round trip |
| A control character in a graph label reached the DOT text | Control characters become spaces |
| Whether Graphviz reads the escapes as the test's parser does | Drawn in a browser with Streamlit's bundled Graphviz: the hostile copy has the clean run's 15 nodes and 19 edges (gate above) |
| `tests/test_app.py` imported pyarrow, which only Streamlit depends on | The chart test reads the times from Streamlit's bytes without it |

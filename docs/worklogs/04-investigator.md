# Milestone 4: The investigator

Status: Slice 1 built on 2026-10-30: the live run on the development case met its pass bar, and the [independent review](#independent-review) ran with its fixes in. [Slice 2](#slice-2-the-library-search-tool) built on 2026-11-02: the live runs on both models met their pass bar; its independent review has not run yet. The milestone state is in the [roadmap](../roadmap.md).

The sections up to [Independent review](#independent-review) are slice 1, the investigator on case tools.

## Scope

The first investigation: a Foundry prompt agent, driven by Hindcast's own tool loop, reads the development case through two case-bound tools and returns a structured, cited reconstruction, or ends as incomplete with a reason. It covers the first three criteria of [milestone 4](../roadmap.md#4-investigator) for case evidence only. The library tool and library citations come in slice 2, after milestone 3. The procedure is the [runbook](../runbooks/investigator.md); the result policy is [decision 0015](../decisions/0015-investigation-result-and-citation-policy.md).

## Pass bar for the live run

Written before the run: one run of `python -m hindcast.investigate cloudflare-2026-02-20` passes when its status is `complete`, `checks.rejected_citations` is empty, and `checks.unsupported` is empty. A complete run with either list non-empty does not pass; it is recorded as it was, and a second try after a prompt change is a new run.

## Work completed

### Prompt agent check

Before any code, one throwaway prompt agent with a strict function tool and a strict output schema was created, called twice, and deleted, to confirm that [decision 0002](../decisions/0002-agent-approach.md) option A works on gpt-6-luna. It did; the call shape and what it showed are a [finding](../findings/models.md#a-prompt-agent-drives-app-run-function-tools-under-a-strict-output-schema-2026-10-30). No fallback was needed.

### Result schema and citation checks

`hindcast.result` holds the strict JSON schema the model fills (every object closed, every property required, enums for `verdict`, `kind`, `time_kind`, and `source`) and checks the model's final text against it with `jsonschema` 4.26.0, the newest stable release on PyPI (released 2026-01-07), now a direct dependency. The local check accepts any citation value, so a malformed citation is rejected on its own instead of failing the whole result; the service gets the strict citation schema. `check_citations` walks the attack verdict, findings, timeline, root cause, and contributing factors, removes and lists each bad citation with its reason, and lists each item left with no support ([decision 0015](../decisions/0015-investigation-result-and-citation-policy.md)).

| Citation | Outcome |
|---|---|
| An `update_id` or `chart_id` of this case, exactly as the tools give it | Kept, including the resolved mark |
| Not an object, missing or empty `ref`, `source` not `case` | `malformed` |
| A `ref` with a `/` whose prefix is not this case's ID | `other-case`, checked before membership, so `other/u1` is never `unknown` |
| Any other `ref` not in this case's evidence, including a bare `u1` | `unknown` |
| A `rests_on` ID that names no finding | `unknown-finding` |

Tested locally: `tests/test_result.py`, 25 tests, run first against a missing module.

### Case tools

`hindcast.tools` loads the evidence file `hindcast.ingest` wrote and serves it through `list_updates` and `list_charts`. The model never names a case: the command binds it. `list_updates` returns the provider, title, start time, and every update with a fixed note that the resolved update's text is withheld; it leaves out the dropped entries, since a dropped postmortem would tell the model a report exists. `list_charts` returns each chart's ID, alt text, and description, with a fixed note that a description is model output and a lead ([#16](https://github.com/sindredg/hindcast/issues/16)). Every result passes through `screen()`, which returns its input until Prompt Shields lands there ([decision 0007](../decisions/0007-safety-and-injection.md)). A missing evidence file fails before any model call and names `python -m hindcast.ingest evidence`.

Tested locally: `tests/test_tools.py`, 14 tests, run first against a missing module. All four evidence files under `build/evidence/` load (10, 22, 36, and 9 updates; 2, 1, 0, and 0 charts).

### Tool loop and caps

`hindcast.investigate.run_investigation` makes one model call, runs every function call in the response, sends the outputs back, and repeats until a response has no function calls. Text next to a function call is not final.

| Event | Result |
|---|---|
| A response without function calls whose text parses against the schema | `complete`, then the citation checks |
| A 13th tool call is requested | `incomplete: tool-cap`, no further call |
| The clock has passed 120 seconds before a tool call or model call starts | `incomplete: time-cap` |
| A model call runs past the time left, which is its client timeout | `incomplete: time-cap` |
| A tool raises | `incomplete: tool-error: <tool>: <message>` |
| Blank final text, or text that does not parse against the schema | `incomplete: empty-result` or `incomplete: schema: <error>` |
| The model call fails, is cut short, or reports no usage | The error propagates; nothing is written |

The model is called with no client retries: the client retries timeouts by default, and a retry would run past the time left. A rate-limit error therefore fails the run instead of waiting.

Tested locally: `tests/test_investigate.py`, the loop tests with a scripted fake model and an injected clock, run first against a missing module.

### Agent definition and version

`prompts/investigator.md` holds the instructions: who the reader is, what the evidence is and where it stops, the output rules, and the attack definition from the [answer keys](../../eval/keys/README.md). The tools and the output schema come from the code, the effort is `medium` in `hindcast.agent`, and the model is the chat deployment. `ensure_agent_version` fingerprints the definition and stores the fingerprint in the agent version's metadata: a changed definition creates a new version of `hindcast-investigator-<deployment>`, an unchanged one reuses the latest. A test checks that no key fact from the prior-knowledge prompt appears in the instructions.

Tested locally: `tests/test_agent.py`, 11 tests, run first against a missing module.

### Command and guards

`python -m hindcast.investigate <case_id>` refuses a scored case until `eval/rubric/frozen.json` exists and fails on missing evidence, both before any cloud call. It keeps the agent version in step, reads the model version from the deployment, runs the loop, writes `build/investigations/<case_id>/<UTC time>-v<agent version>.json` without overwriting, and prints the status, the counts, and the usage, never the investigation text. The result records the agent, the model, and the provenance: the prompt's blob hash (or SHA-256 marked dirty), the commit with a dirty flag over `src/`, `pyproject.toml`, and `uv.lock`, and the evidence file's SHA-256. A test in a temporary Git repository checks that a change under `src/` sets the dirty flag and a change elsewhere does not.

Tested locally: the command tests in `tests/test_investigate.py` (31 tests in the file) and `tests/test_boundaries.py`, 3 tests: the investigator's imports, followed through every Hindcast module they reach, never include `hindcast.keys`, and a stubbed run opens nothing under `eval/keys/` and no file named like a registered postmortem.

The [investigation loop](../architecture/README.md#the-investigator) diagram shows the flow.

## Live run

Run on 2026-10-30 with the command from the [runbook](../runbooks/investigator.md#run-an-investigation), at commit `7c27d84`, clean tree:

```
complete
findings 10, timeline events 8, factors 2, open questions 4
rejected citations 0, unsupported 0
model calls 2, tool calls 2, seconds 31.353, tokens in 3776 (cached 1034) out 3395
build/investigations/cloudflare-2026-02-20/20261030T040215Z-v1.json
```

The run created agent `hindcast-investigator-gpt-6-luna` version 1. The result file records model gpt-6-luna version 2026-09-22, prompt blob `fb660e1`, and evidence SHA-256 starting `ee6be350`. The pass bar is met: `complete`, no rejected citation, no unsupported item. A first attempt without `PYTHONPATH=src` failed at import before any call.

Read against the evidence, not against the answer key, which stays closed until milestone 5:

- Each of the 10 findings matches the update it cites, including the dashboard reload problem in update 5 and the customer-withdrawn prefixes in update 6.
- The attack verdict is `cannot tell`: the updates name no cause.
- The root cause is an inference resting on four findings: a disruption of some BYOIP prefix advertisements, with the underlying fault not stated in the updates.
- No item cites or mentions a chart. Whether the model called `list_charts` is not recorded: the result counts 2 tool calls, not their names. The chart descriptions put a drop in announced address space around 18:00 and a spike in BGP announcements around 17:00 to 18:00 UTC; read by eye from the images, the drop runs from about 18:10 to 18:45 and the spike rises from about 17:35 ([finding](../findings/extraction.md#a-chart-description-gets-times-roughly-right-and-can-invent-a-value-2026-10-27)). Both start before the first update at 18:45. That lead went unused.
- The first timeline event cites update 1 for the incident's start time, 18:45:16, which comes from the case header `list_updates` returns, not from update 1 (18:45:17). The reference resolves, so the citation check passes it; whether a citation supports its item is milestone 5's support rule.

The result file is committed unchanged in [`eval/investigations/cloudflare-2026-02-20/`](../../eval/investigations/cloudflare-2026-02-20/README.md), with its run details and licence note.

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| An investigation of the development case returns an attack assessment, a timeline, findings, contributing factors, and open questions, each item with a citation that resolves | Tested live, case citations only | Live run above: `complete`, 0 rejected, 0 unsupported. Those counts alone would also pass an inference that rests only on findings, so the result file was read item by item: the attack verdict, all 10 findings, all 8 timeline events, the root cause, and both factors each carry at least one case citation that resolves against the evidence file. The 4 open questions carry none: `OpenQuestion` in `hindcast.result` has no citation field. `tests/test_committed_investigation.py` repeats this reading on the committed file where the evidence is present; with an inference's citations removed, it fails. Library citations come with slice 2 |
| A bad citation is rejected with a reason and the rest survives | Tested locally | `tests/test_result.py`: one test per reason, a bad citation next to a good one, an unsupported attack verdict kept |
| A tool error, an empty result, or a run past 12 tool calls or 120 seconds ends as incomplete with a reason | Tested locally | `tests/test_investigate.py`: the 13th tool call in separate responses and in one response, a slow tool before the next model call and before the next tool call, a model call timeout, a tool error, an unknown tool, empty text, a schema error. Not tested live: a cap or an error was not provoked on the service |
| The investigator cannot read an answer key or a postmortem, and cannot run on a scored case before the rubric is frozen | Tested locally | `tests/test_boundaries.py`; `tests/test_investigate.py` refusal tests in both directions |

Every new check was run once against a broken input on 2026-10-30, locally, and failed:

| Broken input | Failed tests |
|---|---|
| `other-case` returned as `unknown` | 3 in `test_result.py`, including `test_ref_with_another_cases_prefix_is_other_case` |
| Every citation kept (`if reason is None:` in `check_citations` changed to `if True:`) | 12 in `test_result.py`, 1 in `test_investigate.py`. An earlier run of an unrecorded change failed 9; this row is the reproducible one |
| Local schema check emptied | 5 in `test_result.py` |
| Tool cap set to 13 | `test_thirteenth_tool_call_is_tool_cap`, `test_tool_cap_counts_calls_within_one_response` |
| Time check before a tool call removed | `test_no_tool_call_starts_after_the_time_cap` |
| Role check removed | `test_showcase_case_is_refused_without_the_rubric_lock`, `test_main_refuses_a_showcase_case_before_any_model_call` |
| `import hindcast.keys` added to `hindcast.tools` | `test_investigator_modules_do_not_import_keys` |
| The command reads `eval/keys/README.md`, or writes a file named like a postmortem | `test_investigator_opens_nothing_under_eval_keys_or_a_postmortem`, once each |
| A prior-knowledge key fact appended to the prompt | `test_no_prior_knowledge_key_fact_in_the_instructions` |
| The evidence file loaded after the agent version is created | `test_main_fails_on_missing_evidence_before_any_model_call` |
| The code dirty flag fixed at `False` | `test_code_provenance_marks_a_change_under_the_code_paths_only` |

With every file restored, the suite passed: `uv run --frozen pytest -q`, 305 passed. After the review fixes below, 306 passed; with the committed run's 2 tests, 308.

## Independent review

A read-only review from a fresh context, with no part in the slice's work, checked every slice 1 claim on 2026-10-30 against the code, the tests, the live run's result file, and the evidence files, without opening the answer keys or the prior-knowledge results. It ran the suite, ruff, and pyright locally, ran the runbook's offline step, and broke the code once per edge case in a scratch copy: each of the loop, schema, citation, time-cap, and evidence edge cases failed its named test. It found nothing that blocks the slice. Each finding was checked again before it was acted on; none was rejected. Fixed in this pull request:

- The missing-evidence test checked that no model call ran, not that no agent version was created; with the evidence check moved after the agent version, it still passed. It now also checks that no version is created, and fails on that move.
- The code dirty flag had no test; fixed at `False`, the suite still passed. A test in a temporary Git repository now covers it.
- Gate row 1 rested on 0 rejected and 0 unsupported, which an inference with only `rests_on` would also pass. The row now records the item-by-item reading of the result file.
- The live-run reading gave the chart descriptions' times as what the charts show, and said the model called `list_charts`, which the result does not record. Both sentences now say what the evidence shows.
- The broken-input row "every citation kept" did not reproduce as 9 failures. It now names the change and its 13 failures.
- A test imported `httpx2`, which only `openai` declared; it is now a pinned development dependency (2.16.0, the newest on PyPI on 2026-10-30). Runbook step 4 now runs Python through `uv run`.

Opened as issues for later:

- [#23](https://github.com/sindredg/hindcast/issues/23): a failed model call leaves no investigation record (milestone 5 batch design).
- [#24](https://github.com/sindredg/hindcast/issues/24): the time cap is passed as an HTTP timeout, which may not bound a whole call; reasoned, not observed (milestone 4 traces).
- [#25](https://github.com/sindredg/hindcast/issues/25): the citation checks accept self-support, cycles, and duplicate finding IDs (milestone 5 support rules).
- [#26](https://github.com/sindredg/hindcast/issues/26): investigation results do not record the applied reasoning effort (milestone 5, with #4).

The result does not record which tool each call used; the milestone 4 criterion for a trace per investigation covers it.

After the fixes, locally: `uv run --frozen pytest -q`, 306 passed; `ruff check`, `ruff format --check`, `pyright`, and `yamllint` clean.

## Slice 2: the library search tool

### Pass bar for the slice 2 live runs

Written before the runs. One run of `python -m hindcast.investigate cloudflare-2026-02-20` per model, `gpt-6-luna` first, then `gpt-6.1-sol`, each from a commit pushed to the branch. A run passes when:

- its status is `complete`,
- `checks.rejected_citations` is empty,
- `checks.unsupported` is empty,
- `tool_calls` holds at least one `search_library` call, and
- at least one library citation is kept.

The `gpt-6-luna` run is the evidence for the first criterion of [milestone 4](../roadmap.md#4-investigator) in full. The `gpt-6.1-sol` run checks that the comparison model handles the tool before its seals; a miss is recorded and does not hold its seals. A run that misses the bar is recorded as it was. A second run is a new file and says why.

Commit threshold, also written before the run: the passing `gpt-6-luna` run is committed only if it repeats no library text at length. The measure is the longest fragment repeated word for word, found with `difflib` (matches of 25 characters or more) against each library section the run retrieved. A fragment over 120 characters keeps the run out of the repository as it is.

### Slice 2 work completed

The procedure is the [investigator runbook](../runbooks/investigator.md); the citation policy is [decision 0020](../decisions/0020-library-citations.md), which extends decision 0015.

- **Tool** (`hindcast.tools`): `search_library` takes one argument, `query`, a non-empty string of at most 1,000 characters. Any other key, a case ID or `top` included, is refused. The command binds `hindcast.search.search_library` to the case with one embedder and one search client per run, so the date bound and the picks come from the registries. The tool returns five hits with ref, document, title, heading, date, and content, no scores, and a note that a hit is another outage. Every returned ref joins the run's `retrieved` set. Zero hits is an answer.
- **Citations** (`hindcast.result`): the schema's `source` takes `case` or `library`. A library citation is kept only for an exact ref in `retrieved`, else `not-retrieved`; a `lib/` ref under `case`, or a case ref under `library`, is `malformed`. An item whose kept citations are all library citations and that has no kept `rests_on` is unsupported.
- **Result file** (`hindcast.investigate`): `tool_calls` lists every successful call in order with its own duration, and for a search the query and the returned refs, never the hit text. `provenance.library` holds the library registry's blob, the index, the search API version, and the embedding model with its dimensions. Missing search settings fail before the agent version is made. The 12-call cap counts searches.
- **Prompt v3** asks for `list_updates`, `list_charts`, and at least one search, and says a library citation never stands alone.
- **Seals** (`hindcast.seal`): new seals carry `library: true`, a second series; `data/library.yaml` joins the paths that must be committed. `seals.json` may only grow ([#33](https://github.com/sindredg/hindcast/issues/33)): earlier entries keep every value, a null `blob` may be filled once, and the only keys a later commit may add are `revealed: true` and `dropped: true`. `seal run` and `seal upload` refuse a record that does not extend HEAD's, and a test walks every committed version of the file. The CI Python job checks out the full history for it; a shallow clone fails the test instead of skipping it. After the first luna run, `seal run` also makes one library search before the first model call and refuses while it fails: a search outage mid-run would otherwise end a seal that has model output, which decision 0017 makes final.
- **Page** (`hindcast.app`): shows the slice 2 run; a library citation renders as `library:<ref>`.

### Slice 2 live runs

Both runs used `python -m hindcast.investigate cloudflare-2026-02-20` with the variables exported from `.env`, at commit `764b37e`, pushed to the branch before the first run, clean tree.

1. **`gpt-6-luna`, 18:04 UTC: missed the bar.** `incomplete: tool-error: search_library: [SSL: UNEXPECTED_EOF_WHILE_READING] ...` after `list_updates` and `list_charts`; 3 model calls, 2 tool calls, 0 searches. The search endpoint refused TLS for a few minutes ([troubleshooting](../troubleshooting.md#investigator-a-library-search-ends-the-run-with-an-ssl-error-2026-11-02)). The run created agent version 3. The file stays local; it is not a model miss, so the rerun below is not the one prompt fix the pass bar allows.
2. **`gpt-6-luna`, 18:17 UTC, rerun after the endpoint answered: passed.**

   ```
   complete
   findings 6, timeline events 9, factors 1, open questions 3
   rejected citations 0, unsupported 0, searches 1, library citations kept 1
   model calls 3, tool calls 3, seconds 39.258, tokens in 10151 (cached 5525) out 3340
   build/investigations/cloudflare-2026-02-20/20261102T181721Z-v3.json
   ```

   The search took 9.688 s and returned five sections: `lib/cloudflare-2022-06-21/s4`, three of `cloudflare-2025-07-14`, and one of `cloudflare-2024-06-27`. The kept library citation is `lib/cloudflare-2022-06-21/s4` ("Cloudflare outage on June 21, 2022"), on finding F4, next to two case citations and `rests_on` F2 and F3.
3. **`gpt-6.1-sol`, 18:18 UTC: failed** with `openai.APIConnectionError` on a model call after the agent version was made, and wrote nothing ([#23](https://github.com/sindredg/hindcast/issues/23)). Every endpoint answered right after.
4. **`gpt-6.1-sol`, 18:19 UTC, retry: passed.** `complete`; 8 findings, 9 timeline events, 2 factors, 3 open questions; 0 rejected, 0 unsupported; 1 search (4.157 s, five sections, four of them shared with the luna run), 1 library citation kept, the same `lib/cloudflare-2022-06-21/s4`; 3 model calls, 42.319 s, 9,926 input tokens (7,228 cached), 2,764 output tokens. Agent `hindcast-investigator-gpt-6-1-sol` version 2. The file stays local.

Read against the evidence, not the answer key:

- Each of the luna run's 6 findings matches the updates it cites. The library citation backs a sentence that calls the earlier postmortem context for reading the updates, "not evidence of this incident's trigger", which is what the prompt asks.
- The attack verdict is `cannot tell`, and the root cause is an inference on F2, F3, and F4: loss of advertisement for some customer BYOIP prefixes, the trigger not stated.
- The first timeline event now cites update 1 at its own time, 18:45:17; slice 1's run gave the case header's 18:45:16. Update 4 (19:45:56) has no timeline event.
- `list_charts` ran (`tool_calls` now records it), but no item cites a chart, so the lead that both charts move before the first update is still unused.

Overlap, measured with `difflib` on 2026-11-02 against the sources, counting matches of 25 characters or more: the luna run repeats the updates in 17.6% of its text, in fragments of at most 56 characters, and repeats none of the five library sections it retrieved (longest shared fragment 22 characters, under the 120-character threshold). The sol run: 10.7% and at most 50 characters against the updates, longest 20 against the library.

The luna run is committed unchanged in [`eval/investigations/cloudflare-2026-02-20/`](../../eval/investigations/cloudflare-2026-02-20/README.md), and the page renders it. Switching the live app to the new image is a provision, not done in this slice.

### Slice 2 gate

| Criterion | Status | Evidence |
|---|---|---|
| An investigation of the development case returns an attack assessment, a timeline, findings, contributing factors, and open questions, each item with a citation that resolves, and library citations marked as such | Tested live | Luna run 2 above: `complete`, 0 rejected, 0 unsupported, 1 search, 1 library citation kept with `source: library`. `tests/test_committed_investigation.py`: every item but the open questions keeps a case citation that resolves (local, evidence present), and every library citation is a ref the run's search returned (runs in CI) |
| A library citation the run did not retrieve is rejected; a `lib/` ref under `case` and a case ref under `library` are malformed; an item backed only by the library is unsupported | Tested locally | `tests/test_result.py`: a ref that exists nowhere, with a trailing space, with other case, or a prefix, each `not-retrieved`; both crossed sources `malformed`; a library-only finding and attack verdict unsupported; a rejected case citation leaving an item library-only. `tests/test_investigate.py`: through the loop, a retrieved ref kept and an unretrieved one rejected |
| The search is bound to the case in the tool | Tested locally | `tests/test_tools.py`: the search receives only the query; a call with `case_id` or `top` is refused before the search runs. `tests/test_investigate.py`: a search that raises `LibraryLeak` ends the run as `tool-error: search_library: ...` and keeps the earlier calls; `tests/test_search.py` (milestone 3) shows a disallowed hit raises `LibraryLeak`. A tool error from the search was also seen live, in luna run 1 |
| The 12-call cap counts searches | Tested locally | `tests/test_investigate.py::test_thirteenth_call_being_a_search_is_tool_cap`: the search never runs |
| A malformed query is refused | Tested locally | `tests/test_tools.py::test_search_refuses_bad_arguments`: missing, empty, blank, a number, 1,001 characters, extra keys, not JSON; 1,000 characters accepted |
| A seal is refused while the library search fails | Tested locally | `tests/test_seal.py::test_run_refuses_when_the_search_does_not_answer`: no model call, no entry, only the error type in the refusal; `test_preflight_search_runs_on_the_case`. A failure in the middle of a run is an accepted gap: the search is not retried, by the tool-error rule |
| The seal record only grows | Tested locally | `tests/test_seal.py`: removed, reordered, changed, and dropped fields and unknown keys are problems; an appended entry, a filled blob, and `revealed` or `dropped` set to true are not; a history with an edited hash or a restored record is reported; a shallow clone is refused; the repository's own history passes. Tested in CI: the Python job passed on this branch with `fetch-depth: 0` (run for `612f0ad`) |

Every new check was run once against a broken input on 2026-11-02, locally, and failed:

| Broken input | Failed tests |
|---|---|
| The extra-keys check in the search tool loosened to "has a query" | `test_search_refuses_bad_arguments[top]`, `[case-id]` |
| Any kept citation counted as support | `test_library_only_finding_is_unsupported`, `test_library_only_attack_verdict_is_unsupported`, `test_rejected_case_citation_leaves_a_library_only_item_unsupported` |
| An empty `retrieved` set passed to the citation check | `test_library_citation_from_a_search_is_kept_and_an_unretrieved_one_rejected` |
| `data/library.yaml` removed from the seal's clean paths | `test_library_registry_change_is_refused` |
| `LIBRARY = False` | `test_run_records_hash_then_uploads`, `test_a_seal_without_the_library_does_not_block_one_with_it` |
| The record check compares key presence only | `test_record_change_is_a_problem[reordered]`, `[hash]`, `test_filled_blob_cannot_change`, `test_history_with_a_changed_hash_is_a_problem` |
| The history walk skips the parent comparison | `test_history_with_a_changed_hash_is_a_problem`, `test_history_restored_from_an_earlier_commit_is_a_problem` |
| A committed run's library citation changed to a ref the run did not retrieve (a copy) | `test_library_citations_were_retrieved_in_the_run`, `test_every_item_but_the_open_questions_cites_the_case[...v3...]` |
| A 150-character fragment of a retrieved section added to a finding (a copy) | `test_library_text_is_not_repeated_at_length` |
| The page pointed back at the slice 1 run | `test_page_marks_a_library_citation` |
| The preflight search call removed from `seal run` | `test_run_refuses_when_the_search_does_not_answer`, `test_preflight_search_runs_on_the_case` |
| The refusal chained to the search error (`from error`) | `test_run_refuses_when_the_search_does_not_answer` |

The committed file was restored byte for byte (`cmp` against the run's original). With every file restored, the suite passed: `uv run --frozen pytest -q`, 469 passed (408 on `main` before the slice). The search API version is recorded from `hindcast.index.SEARCH_API_VERSION`, the version the search client is built with.

# Milestone 4: The investigator

Status: Verified on 2026-11-07: every milestone criterion has a tested row or an accepted gap across the slice gates ([slice 1](#gate), [slice 2](#slice-2-gate), [slice 3](#slice-3-gate), [slice 4](#slice-4-gate)), and the [slice 4 independent review](#slice-4-independent-review) ran with its fixes in. Slice 1 built on 2026-10-30: the live run on the development case met its pass bar, and the [independent review](#independent-review) ran with its fixes in. [Slice 2](#slice-2-the-library-search-tool) built on 2026-11-02: the live runs on both models met their pass bar, and its [independent review](#slice-2-independent-review) ran with its fixes in. [Slice 3](#slice-3-screens-pii-challenge-traces-and-cost) built on 2026-11-03: the live runs and challenges on both models met their pass bar ([gate](#slice-3-gate)), and its [independent review](#slice-3-independent-review) ran with its fixes in. An investigation's whole trace, open in the slice 3 gate, was read by query on 2026-11-05 from the deployed page ([worklog 06](06-deployment.md#slice-2-live-run), step 14). [Slice 4](#slice-4-the-view-parts), the view parts, built on 2026-11-07 on stored results ([gate](#slice-4-gate)). The milestone state is in the [roadmap](../roadmap.md).

The sections up to [Independent review](#independent-review) are slice 1, the investigator on case tools.

On this page: [Scope](#scope) · [Pass bar for the live run](#pass-bar-for-the-live-run) · [Work completed](#work-completed) · [Live run](#live-run) · [Gate](#gate) · [Independent review](#independent-review) · [Slice 2: the library search tool](#slice-2-the-library-search-tool) · [Slice 3: screens, PII, challenge, traces, and cost](#slice-3-screens-pii-challenge-traces-and-cost) · [Slice 4: the view parts](#slice-4-the-view-parts)

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

- **Tool** (`hindcast.tools`): `search_library` takes one argument, `query`, a non-empty string of at most 1,000 characters. Any other key, a case ID or `top` included, is refused. The command binds `hindcast.search.search_library` to the case with one embedder and one search client per run, so the date bound and the picks come from the registries. The tool returns at most five hits, each with ref, document, title, heading, date, and content, no scores, and a note that a hit is another outage. Every returned ref joins the run's `retrieved` set. Zero hits is an answer.
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
| The search is bound to the case in the tool | Tested locally | `tests/test_seal.py::test_preflight_search_runs_on_the_case`: the search `prepare` binds receives the case ID from the command. `tests/test_tools.py`: the tool passes only the query; a call with `case_id` or `top` is refused before the search runs. `tests/test_investigate.py`: a search that raises `LibraryLeak` ends the run as `tool-error: search_library: ...` and keeps the earlier calls; `tests/test_search.py` (milestone 3) shows a disallowed hit raises `LibraryLeak`. A tool error from the search was also seen live, in luna run 1 |
| The 12-call cap counts searches | Tested locally | `tests/test_investigate.py::test_thirteenth_call_being_a_search_is_tool_cap`: the search never runs |
| A malformed query is refused | Tested locally | `tests/test_tools.py::test_search_refuses_bad_arguments`: missing, empty, blank, a number, 1,001 characters, extra keys, not JSON; 1,000 characters accepted |
| A seal is refused while the library search fails | Tested locally | `tests/test_seal.py::test_run_refuses_when_the_search_does_not_answer`: no model call, no entry, only the error type in the refusal; `test_preflight_search_runs_on_the_case`. A failure in the middle of a run is an accepted gap: the search is not retried, by the tool-error rule |
| The seal record only grows | Tested locally | `tests/test_seal.py`: removed, reordered, changed, and dropped fields and unknown keys are problems; an appended entry, a filled blob, and `revealed` or `dropped` set to true are not; a history with an edited hash, a restored record, or a merge that drops an entry is reported; a shallow clone is refused; the repository's own history passes. Tested in CI: the Python job passed on this branch with `fetch-depth: 0` (run for `612f0ad`) |

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
| `--full-history` removed from the history walk (after the review) | `test_history_with_a_merge_that_drops_an_entry_is_a_problem` |
| The refusal's `from None` removed, or replaced by `from error` (after the review) | `test_run_refuses_when_the_search_does_not_answer`, once each |
| The preflight search call removed from `seal run` | `test_run_refuses_when_the_search_does_not_answer`, `test_preflight_search_runs_on_the_case` |

The committed file was restored byte for byte (`cmp` against the run's original). With every file restored, the suite passed: `uv run --frozen pytest -q`, 470 passed (408 on `main` before the slice). The search API version is recorded from `hindcast.index.SEARCH_API_VERSION`, the version the search client is built with.

### Slice 2 independent review

A read-only review from a fresh context, with the spec, the plan's review focus, the executor's rulings, and the broken-input record, ran on 2026-11-02 over `48181dc..138ab3c`. It reran the suite (469 passed), recounted `main`'s tests (408), checked the committed run's fields and the 22-character library fragment against the file, and reproduced the merge case below in a scratch repository. Each finding was checked again against the code before it was acted on.

Fixed in this pull request:

| Finding | Fix |
|---|---|
| A merge commit that kept one parent's `seals.json` was skipped by Git's default history simplification, with the other parent's commits, so a merge that dropped an entry passed the history test | `--full-history` in the walk, and `test_history_with_a_merge_that_drops_an_entry_is_a_problem`, which failed before the change |
| The preflight refusal test checked `__cause__`, which an implicitly chained error leaves empty while the traceback still prints the service's message | The test checks the printed traceback; it fails with `from None` removed and with `from error` |
| The run README named prompt v2 for the slice 1 run; its blob is v1 | Corrected |
| The troubleshooting entry cited decision 0015 for the tool-failure rule, which 0015 does not contain | Cites the loop and decision 0020 |
| "120 seconds at most" on the architecture page and in the README: the cap is checked before each call, and a running search is not cut off | Reworded; bounding the search is [#49](https://github.com/sindredg/hindcast/issues/49) |
| The gate row for the case binding cited tests whose stub never sees a case ID | Cites `test_preflight_search_runs_on_the_case`, which checks the case ID `prepare` binds |
| The investigator runbook showed `--env-file`, but the runs used the variables exported from `.env` | Step 2 shows the command that ran |
| "Returns five hits" where `top=5` is a maximum | "At most five" |

Opened as issues, each with its trigger: a merge of two branches that both add seals fails the history test ([#44](https://github.com/sindredg/hindcast/issues/44)); the record check misses a type change that compares equal ([#45](https://github.com/sindredg/hindcast/issues/45)); refs count as retrieved before `screen()` ([#46](https://github.com/sindredg/hindcast/issues/46)); `provenance.library` names the index but not its contents ([#47](https://github.com/sindredg/hindcast/issues/47)); a sealed file keeps a tool error's raw SDK message ([#48](https://github.com/sindredg/hindcast/issues/48)); a search can run past the time cap ([#49](https://github.com/sindredg/hindcast/issues/49)).

Set aside by the review: the mid-run search failure in a seal (an accepted gap above), the live agent versions (read through the Foundry SDK, which the review did not call), the sol run's counts and the overlap against the updates (local files), and the diagrams' geometry.

## Slice 3: screens, PII, challenge, traces, and cost

### Pass bar for the slice 3 live runs

Written before the runs. One run of `python -m hindcast.investigate cloudflare-2026-02-20` per model, from a commit pushed to the branch ([#39](https://github.com/sindredg/hindcast/issues/39)), then one challenge per model on its own run. A run passes when:

- its status is `complete`, with no rejected citation and no unsupported item under the stricter shown-ref rule,
- every tool call made at least one screen call and withheld nothing,
- `checks.pii` is present, and its hit count is recorded as the false-positive figure on clean evidence, and
- the result has a cost from price table version 1.

A withheld item on the development case stops the work until the false positive is looked at.

A challenge passes when it completes with a verdict, nothing rejected, and the question screened before any model call. The question, fixed before the runs: "Which status update shows this, and does any later update contradict it?", on the first observation finding of each run.

### Slice 3 work completed

The design is [decision 0021](../decisions/0021-screens-pii-and-challenge.md); the procedure is the [investigator runbook](../runbooks/investigator.md).

| Part | Where | What it does |
|---|---|---|
| Safety clients | `hindcast.safety` | Prompt Shields (API 2024-09-01) and PII detection (API and model 2026-05-01) over plain REST on azure-core, with an Entra token and no retry. A long text is split; a call holds at most 5 documents and 10,000 characters for Prompt Shields, 5 documents of 5,000 code points for PII. An error names the HTTP status and the service's error code, never its message. A missing flag is an error, not a pass |
| Screens per item | `hindcast.tools` | Each update, chart, and library hit is screened once per run. A flagged one is replaced by its ref and `"withheld": "prompt-shields"`; the note says why. The tools track the case refs shown, the refs withheld, and the library refs shown (`retrieved`, after the screen: [#46](https://github.com/sindredg/hindcast/issues/46)) |
| Citations | `hindcast.result` | A withheld ref is rejected as `withheld`; a case ref the run never read as `not-shown` |
| PII | `hindcast.redact` | Every free-text field of the answer goes to PII detection; a hit becomes `[<Category>]`, and `checks.pii` lists path, category, and confidence. `PersonType`, `Organization`, `DateTime`, `URL`, and `IPAddress` pass |
| Loop | `hindcast.investigate` | Ends as `screen-error` or `pii-error` when a screen or the PII check fails, and as `time-cap` when a tool runs out of time. Each model call gets the time left; within a tool call, the search, its embedding, and the screen share it and make one try ([#49](https://github.com/sindredg/hindcast/issues/49)). The PII check runs after the answer with its own 30 seconds |
| Spans | `hindcast.telemetry`, `hindcast.investigate`, `hindcast.challenge` | `investigation`, or `challenge` with the question's `screen` span and a `challenge_loop`; under either, `model_call` (seconds, time left, tokens), `tool_call` (seconds, withheld, screen calls), and `pii` (hits). Service name `hindcast-investigator` for the commands; every span kept |
| Cost | `data/prices.yaml`, `hindcast.costs` | Version 1 of the price table, with the meter and date of each price. Each result records its cost by part. A deployment missing from the table is refused before the agent version; a call past the short-context limit is recorded as not priced |
| Challenge | `hindcast.challenge`, `prompts/challenger.md`, `hindcast.agent` | A second agent per deployment with a challenge schema; the question screened, then PII-masked; 6 tool calls and 90 seconds; stored under `challenges/` next to the result |
| Page | `hindcast.app` | Lists the development results, opens on the newest `gpt-6-luna` run, shows stored challenges under each finding, the withheld items, the PII hits, and the cost. `HINDCAST_CHALLENGE_LIVE=1` adds a question box per finding |
| Seals | `hindcast.seal` | Runs with the screens, the PII check, the spans, and the cost. The record check compares values as JSON, so a changed type is a change ([#45](https://github.com/sindredg/hindcast/issues/45)) |

### Slice 3 live runs

Before the runs, both services answered 401 to the developer's sign-in; the custom role "Hindcast Safety Caller" was created and assigned on the Foundry resource at 17:05:54Z, and Prompt Shields answered from 17:08:28Z, PII detection from 17:10:07Z ([finding](../findings/safety.md)). Both runs used `--env-file .env`, at commit `81e01a7`, pushed before the first run, clean tree.

| | gpt-6-luna, 17:11:46Z | gpt-6.1-sol, 17:12:55Z |
|---|---|---|
| Agent | `hindcast-investigator-gpt-6-luna` version 3 | `hindcast-investigator-gpt-6-1-sol` version 2 |
| Outcome | `complete`; 6 findings, 8 timeline events, 2 factors, 4 open questions | `complete`; 9 findings, 9 timeline events, 2 factors, 3 open questions |
| Citations | 0 rejected, 0 unsupported; 1 search, no library citation kept | 0 rejected, 0 unsupported; 1 search, 1 library citation kept |
| Screens | 5 calls, 25 records, 0 withheld | 5 calls, 27 records, 0 withheld |
| PII | 6 calls, 26 records, 0 hits | 6 calls, 28 records, 0 hits |
| Usage | 3 model calls, 42.195 s, 10,648 input tokens (4,251 cached), 3,039 output | 3 model calls, 56.597 s, 10,552 input (4,251 cached), 2,940 output |
| Cost | USD 0.037583: model 0.002202, screens 0.009375, PII 0.026, embeddings 0.000007 | USD 0.080555: model 0.042427, screens 0.010125, PII 0.028, embeddings 0.000003 |

Both passed. Prompt Shields flagged nothing in the development evidence and the library sections each run retrieved, and PII detection found nothing to mask: both false-positive figures on clean evidence are 0. The luna run kept no library citation this time; slice 2's did. That is not a slice 3 criterion and is recorded as seen.

The PII check is the larger cost: at USD 1.00 per 1,000 records against 0.375 for Prompt Shields, it costs more than the luna model calls.

Challenges, from the command, with the question fixed above:

| Challenge | Outcome | Usage and cost |
|---|---|---|
| luna F1, 17:14:24Z, agent `hindcast-challenger-gpt-6-luna` version 1 | `complete`, `stands`; 2 case citations kept, 0 rejected | 2 model calls, 1 tool call, 6.353 s, 3 screen calls; USD 0.006129 |
| sol F1, 17:14:51Z, `hindcast-challenger-gpt-6-1-sol` version 1 | `complete`, `stands`; 10 kept, 0 rejected | 2 model calls, 1 tool call, 9.238 s, 3 screen calls; USD 0.014526 |
| luna F2, 17:19:08Z, after the sampler fix | `complete`, `stands`; 8 kept, 0 rejected | 2 model calls, 3 tool calls, 15.628 s; USD 0.011807 |
| luna F3, 17:42:10Z, after the workspace's shared keys were turned off | `complete`, `stands`; 6 kept, 0 rejected | 2 model calls, 2 tool calls, 7.607 s; USD 0.007431 |
| luna F4, 17:46:02Z, after Application Insights was disconnected from Foundry | `complete`, `stands`; 5 kept, 0 rejected | 2 model calls, 1 tool call, 10.218 s; USD 0.006193 |

Traces, read with `az monitor app-insights query`:

1. The first four runs' spans arrived in part: 6 of 10 `model_call` spans, no `investigation` span, no question `screen` span. Cause: the exporter's default sampler, five traces per second ([finding](../findings/observability.md#the-azure-monitor-exporter-samples-five-traces-per-second-by-default-2026-11-03)). Fixed with `OTEL_TRACES_SAMPLER=parentbased_always_on`; the F2 challenge's trace then arrived whole, each span with `itemCount` 1.
2. Foundry's server-side spans stored every prompt and the unmasked answer, though content recording was off on the client ([finding](../findings/observability.md#foundrys-server-side-traces-store-every-prompt-and-answer-whatever-the-client-sets-2026-11-03)). Application Insights was disconnected from the Foundry account at 17:45:50Z; the F4 challenge's own spans arrived, and no server-side span did (read 17:50Z).
3. `AIProjectInstrumentor` added no client-side span; every GenAI span seen came from the server side.
4. The F2 trace showed the question's `screen` span in a trace of its own. `run_challenge` now opens the `challenge` span around it; tested with an in-memory exporter, not live.

Every `model_call` span that arrived ran within its time left ([#24](https://github.com/sindredg/hindcast/issues/24)):

| Run | Seconds of time left |
|---|---|
| gpt-6-luna investigation | 2.191 of 113.557; 24.225 of 104.724 |
| Challenges F1 (luna), F1 (sol), F2 | 2.584 of 90, 3.265 of 87.065; 3.248 of 90, 5.363 of 86.325; 3.72 of 90, 6.712 of 81.224 |

For the calls the sampler dropped, each run's total time (42.2 s and 56.6 s) is under the 120-second cap, so none outlasted its time left (reasoned from the result files).

The runs and the five challenges are committed unchanged in [`eval/investigations/cloudflare-2026-02-20/`](../../eval/investigations/cloudflare-2026-02-20/README.md), with their overlap against the updates and the library. None repeats library text in 25 characters or more.

### Slice 3 gate

| Criterion | Status | Evidence |
|---|---|---|
| A flagged item is withheld, the rest is shown, and the withheld ref cannot be cited | Tested locally | `tests/test_tools.py::test_flagged_update_is_withheld_and_the_rest_shown`, `test_the_case_title_is_screened_and_withheld_when_flagged`, `test_flagged_hit_is_not_retrieved`, `test_chart_screens_alt_text_and_description`; `tests/test_result.py::test_withheld_case_ref_is_rejected_as_withheld`, `test_withheld_library_ref_is_rejected`, `test_unread_case_ref_is_rejected_as_not_shown`; through the loop, `tests/test_investigate.py::test_flagged_update_is_withheld_in_the_run_and_its_citation_rejected`. Not provoked live: nothing in the development case was flagged |
| A screen error ends the run; a missing flag is not a pass | Tested locally | `test_screen_error_ends_run_as_screen_error`, `tests/test_safety.py::test_a_service_error_becomes_a_screen_error`, `test_a_missing_flag_is_not_a_pass`, `test_a_missing_prompt_flag_is_not_a_pass` (the empty-prompt shape seen live) |
| A long result is split within the limits | Tested locally | `test_documents_of_25000_characters_are_split_within_the_limits`, `test_batches_hold_the_limits`, `test_documents_flag_a_text_when_any_piece_is_flagged` |
| PII is masked and recorded by path and category, not kept | Tested locally; tested live with no hit | `test_pii_hits_are_masked_in_the_written_file`, `test_search_queries_are_pii_masked_in_the_record`, `tests/test_redact.py` with overlapping hits; `test_pii_hit_outside_the_text_raises`; `test_pii_maps_entities_with_codepoint_offsets` with curly quotes and an emoji. Live: 0 hits in both runs and five challenges; the probe on a made-up name returned `Person` |
| A flagged challenge question makes no model call; an unscreened result is not challenged | Tested locally | `tests/test_challenge.py::test_flagged_question_makes_no_model_call`, `test_a_question_screen_error_ends_the_challenge`, `test_a_question_pii_error_ends_the_challenge`, `test_an_unscreened_result_is_refused`; `tests/test_app.py::test_no_challenge_box_for_an_unscreened_result` |
| A challenge citation that does not resolve is rejected | Tested locally; tested live with none | `test_challenge_unknown_ref_is_rejected`, `test_challenge_case_citation_needs_its_own_reading`; live: 0 rejected in five challenges, and `tests/test_committed_investigation.py` resolves each committed challenge's case citations (local, evidence present) |
| A finding can be challenged from the interface, and the answer cites its evidence | Tested live in a browser | Four challenges of F5 started from the local page's box on 2026-11-03, 19:26 to 19:32Z: all `complete`, `stands`, every citation a case ref (one a chart), none rejected ([screenshots](../screenshots/README.md)). `tests/test_app.py::test_challenge_box_with_live_flag` (stubbed), `test_no_challenge_box_without_live_flag`. Five more from the command, above |
| Every investigation and challenge has a trace and a cost | Tested live for challenges; tested live in part for investigations; the root span tested locally | Challenges F2 to F4: whole traces, read by query. Both investigations: their tool calls, PII checks, and 2 of 6 model calls arrived, and no `investigation` root span, before the sampler fix; no investigation ran after it. `tests/test_telemetry.py::test_configure_keeps_every_span`, `tests/test_investigate.py::test_spans_carry_no_text`, `tests/test_challenge.py::test_a_challenge_is_one_trace`. A cost in every result and challenge file |
| An unknown deployment has no price | Tested locally | `tests/test_costs.py::test_unknown_deployment_raises`; `tests/test_investigate.py::test_a_deployment_without_a_price_is_refused_before_any_model_call` |
| The cost matches what is billed | Accepted gap | One read-only Cost Management query on 2026-11-07 (`POST .../resourceGroups/<resource-group>/providers/Microsoft.CostManagement/query`, `ActualCost`, 2026-11-03, grouped by meter) returned the day's bill per meter in NOK: the gpt-6-luna token meters sum to NOK 0.069896, the gpt-6.1-sol meters to NOK 0.512417, the text-records meter to NOK 0.385893, and the embeddings to NOK 0.000121. The bill has no per-run line, the day also holds the page's four challenges and other calls, part of the text records was billed at zero, and the price table is in USD with no exchange rate recorded, so no per-run figure can be compared. The table's totals stay the run's cost |
| The time cap holds for whole calls ([#24](https://github.com/sindredg/hindcast/issues/24)) | Tested live, in part; the rest reasoned | The `model_call` spans above; the dropped ones bounded by each run's total time |
| A search gets the time left, shares it with its embedding and its screen, and makes no retry ([#49](https://github.com/sindredg/hindcast/issues/49)) | Tested locally | `tests/test_tools.py::test_a_search_and_its_screen_share_the_time_left`, `test_a_tool_call_with_no_time_left_for_its_screen_times_out`; `tests/test_search.py::test_the_search_request_gets_what_the_embedding_left`, `test_search_passes_timeout_and_no_retries`, `test_search_timeout_raises_timeout_error`, `test_investigation_search_client_makes_no_retries`; `tests/test_index.py::test_embedder_with_a_timeout_makes_one_try_within_it`, `test_embedder_timeout_raises_timeout_error`; `tests/test_investigate.py::test_tool_timeout_is_time_cap` |
| The seal path runs with the screens | Tested locally | `tests/test_seal.py::test_seal_path_runs_with_screens` |
| The seal record reports a changed type ([#45](https://github.com/sindredg/hindcast/issues/45)) | Tested locally | `tests/test_seal.py::test_record_value_of_another_type_is_a_change` |
| The workspace refuses shared keys and traces still arrive ([#2](https://github.com/sindredg/hindcast/issues/2)) | Tested live | `features.disableLocalAuth` read back `true` at 17:42:01Z; the F3 challenge's spans, Foundry's included, arrived at 17:42:46Z |

Every new check was run once against a broken input on 2026-11-03, locally, and failed:

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

The committed files were restored byte for byte (`cmp`). With every file restored, the suite passed: `uv run --frozen pytest -q`, 600 passed after the review's fixes (470 on `main` before the slice). Each code fix from the review has a test that failed before it.

The cost parts in the committed slice 3 files were rounded after the total was summed, so the luna run's parts add to 0.037584 against a total of 0.037583. The code now totals the rounded parts; the files keep what the run wrote.

### Slice 3 independent review

A read-only review from a fresh context, with the spec, the plan's review focus, the executor's rulings, and the broken-input record, ran on 2026-11-03 over `1251452..58bac41`. It reran the suite (585 passed), recounted `main`'s tests (470), and checked every committed run and challenge figure against its file.

It found that every screen or PII failure fails closed. Each finding was checked again against the code before it was acted on.

Fixed in this pull request; each code fix has a test that failed first:

| Finding | Fix |
|---|---|
| The case title, the status page's incident name, reached the model unscreened | Screened with the updates; withheld in place when flagged |
| Overlapping PII hits left part of a span in the text, and a hit outside its text was recorded but not masked | Overlaps merge into one span; a hit outside its text, or an entity without its fields, is a PII error |
| One search tool call could take about three times the time left: the embedding, the search, and the screen each got all of it | One budget per tool call, shared in order |
| A challenge could run on a result from before the screens, whose library refs were never screened | Refused, and the page shows no box for it |
| The model's search queries, kept in the result file, had no PII check | Masked like the answer, recorded as `tool_calls[n].query` |
| A credential failure escaped the service-error mapping, with its message | Every azure-core error maps to its type only |
| The cost total summed unrounded parts | The total is the sum of the rounded parts |
| The gate claimed whole traces for the investigations | The trace row now says which traces arrived whole |
| Figures: the committed-run test count, the PII answer time, "four questions" in decision 0021, the observability finding's scope, the deleted connection's level, the `screen` span's place, the Prompt Shields record unit stated as fact | Corrected; the record unit is marked as assumed until the bill is compared |

Opened as issues, each with its trigger: pieces split with no overlap ([#50](https://github.com/sindredg/hindcast/issues/50)); live PII offsets after non-ASCII text not yet seen ([#51](https://github.com/sindredg/hindcast/issues/51)); no price line for semantic queries ([#52](https://github.com/sindredg/hindcast/issues/52)); the page renders model text as Markdown ([#53](https://github.com/sindredg/hindcast/issues/53)); the Prompt Shields limit may count UTF-16 units ([#54](https://github.com/sindredg/hindcast/issues/54)).

The `IPAddress` exemption, wider than the spec's "public service addresses", is recorded in decision 0021's trade-offs.

Set aside by the review: the live Azure state (the role, the deleted connection, `disableLocalAuth`, the spans), the prices against their sources, and the diagrams' geometry.

## Slice 4: the view parts

[Decision 0008](../decisions/0008-user-interface.md) names four visual parts of the investigation view besides the lists. The attack assessment, shown first, came with slice 3's page. This slice adds the other three, on stored results, with no model call and no Azure resource.

The scored view differs from decision 0008. The decision asks for the reconstruction next to the key. The page shows the key's text next to each outcome, its credit and label, and the run items the outcome rests on as field paths with their finding IDs (`findings[8] (F9)`), not the run's own text. The run's text is one tab away, on the Investigation tab, under the same finding IDs. A row with the run's claim beside the key's is left out: it would repeat the investigation in a second place.

### Slice 4 work completed

| Part | Where | What it does |
|---|---|---|
| Timeline chart | `hindcast.views.timeline_spec`, the Investigation tab | A Vega-Lite spec, drawn by Streamlit's built-in renderer, so no new dependency: each event at its UTC time, a stated time as a filled green circle, an inferred one as a hollow grey diamond. An event whose time is not an ISO time in UTC stays in the list and is left out of the chart, with a caption naming it, because placing it would invent a time. The x axis uses a UTC scale, or it would show the reader's local time. The tooltip carries the time and its kind only, no model text |
| Evidence graph | `hindcast.views.evidence_dot`, the Evidence tab | DOT text for `st.graphviz_chart`, which renders a DOT string in the browser with no `graphviz` Python package (read in Streamlit 1.67.0's `graphviz_chart.py`). Left to right: the root cause (green) and each contributing factor, the findings they rest on, and the updates, charts, and library sections each cites; a library section is amber and dashed. Node IDs are the graph's own; a label escapes the backslash and the double quote, the only special characters in a quoted DOT string |
| Scored view | `hindcast.views.load_scored`, the Score tab | For a scored showcase run: one row per key item with the key's text, its frozen label, the outcome, the credit, and the run items the outcome rests on, beside the run's primary score. It reads `scores.json`, the run's judgment, review, and reviewer judgment, the key, and the labels. It refuses a key or labels that differ from their frozen hash, a judgment whose `run_sha256` is not the shown file's, a review whose `judgment_sha256` is not the judgment's, and a reviewer judgment that differs from the one its decisions name (`load_second_judgments`, the score's own check). Every cell is escaped: the run items come from the judge model |
| Shared run items | `hindcast.evaluation.score.run_items_behind` | The run items each outcome rests on, the judge's or, where it decided, the reviewer's. `score_run` and the scored view call the same function, so the page shows the lists the score read |
| Scored runs in the picker | `hindcast.app` | A "Results" control switches between the development runs and the scored showcase runs, when the repository has them. The image copies neither the keys nor the scored runs (`.dockerignore`, `Dockerfile`), so the deployed page shows no scored view. With `HINDCAST_LIVE=1`, a finding gets the challenge box only when its case is a development case or an injection copy: a scored run is complete and screened, and the challenge command lets a showcase case through once the rubric is frozen |
| Graph labels | `hindcast.views.dot_label` | Control characters, NUL included, become spaces before the label is escaped |

### Slice 4 gate

| Criterion | Status | Evidence |
|---|---|---|
| The timeline chart places each event at its UTC time and draws stated and inferred times differently | Tested locally; rendered locally | `tests/test_views.py::test_timeline_spec_places_every_event_and_marks_the_time_kind`, `test_utc_accepts_a_utc_time_only`, `test_timeline_spec_leaves_out_an_event_without_a_utc_time`; `tests/test_app.py::test_page_draws_the_timeline_chart_and_the_evidence_graph` reads the times Streamlit sends. Rendered in headless Chrome on 2026-11-07 ([screenshots](../screenshots/README.md#local-page-view-parts-2026-11-07)). No stored run has an inferred time, so the hollow diamond and the left-out caption were seen only on an edited copy of a result, not committed |
| The evidence graph links each factor to its findings and each finding to what it cites, with library citations marked | Tested locally; rendered locally | `test_evidence_graph_links_claims_to_findings_and_citations` on the committed run `20261102T181721Z-v3.json`, which cites a library section; its graph rendered on 2026-11-07 |
| Model-written text cannot change the graph or the chart | Tested locally | `test_dot_label_keeps_hostile_text_inside_its_string`, `test_evidence_graph_with_hostile_claims_adds_no_node_or_edge`, `test_evidence_graph_never_uses_run_text_as_a_node_id`, `test_timeline_tooltip_carries_no_model_text`. In the tests the DOT text is parsed by the test's own reader. In headless Chrome on 2026-11-07, Streamlit's bundled Graphviz drew a copy of `20261102T181721Z-v3.json` with every claim replaced by a quote, an edge statement, a `URL` attribute, `\N`, `\l`, braces, and `<b>`: 15 nodes and 19 edges, the same as the unchanged run, no link element, and the text shown as written in 8 nodes (read from the page's SVG). `test_dot_label_turns_control_characters_into_spaces` covers NUL and escape characters |
| The scored view pairs each key item with its outcome, label, and credit, and refuses a changed key, changed labels, or a judgment made for another file | Tested locally; rendered locally | `test_load_scored_pairs_each_key_item_with_its_outcome`, `test_load_scored_refuses_a_run_file_the_judgment_was_not_made_for`, `test_load_scored_refuses_a_key_or_labels_changed_after_freezing` (both), `test_load_scored_refuses_a_review_made_on_another_judgment`, `test_load_scored_refuses_an_edited_reviewer_judgment`, `test_scored_rows_refuse_items_the_key_does_not_have`; `tests/test_app.py::test_page_shows_the_score_of_a_scored_run`, `test_page_shows_no_score_next_to_an_edited_run`, `test_page_shows_no_score_from_a_malformed_scores_file`, `test_page_lists_the_scored_runs` (60 runs) |
| The live page offers no challenge on a scored run | Tested locally | `test_no_challenge_box_on_a_scored_run_with_live_flag`, which failed before the fix (every finding of `hindcast/github-2026-08-17/r1/a1` had the box); `test_challenge_box_with_live_flag` still finds the box on a screened development run |
| The score table renders model text as text | Tested locally | `test_page_shows_the_score_table_as_plain_text` |
| Sharing `run_items_behind` leaves every score as it was | Tested locally | `test_scores_json_still_matches_the_score_of_every_run`: every field of all 60 runs' scores equals its `scores.json` entry after a JSON round trip |
| The view parts on the deployed page | Accepted gap | No environment runs since the final removal of 2026-11-06 ([worklog 06](06-deployment.md#slice-2-final-removal)), and building one again for a page that only draws stored results is not worth an environment. The chart and the graph were rendered locally with Streamlit 1.67.0, the version the image installs from the same lock. The scored view is local by design: the image leaves out the answer keys (`.dockerignore`) and copies no scored run, so the page that runs live investigations never holds a key |

Every new check was run once against a broken input on 2026-11-07, locally, on a copy of `src/` (page changes in place, restored after), and failed:

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
| The primary score set to `None` (after the review; the earlier version of the regression test compared four fields and missed it) | `test_scores_json_still_matches_the_score_of_every_run`, `tests/test_score.py::test_unmentioned_not_inferable_factor_leaves_denominator`, `test_aggregate_gives_mean_min_max_and_failures` |

With every file restored, the suite passed: `pytest -q`, 1001 passed and 3 skipped (981 collected on `main` at `e12c856`). The local runs called the project environment's Python directly, not `uv run`, because the lock asks for uv 0.13.7 and the local uv is 0.13.5; the environment's watchdog, pyarrow, and python-dateutil match the lock (read 2026-11-07). CI runs the checks with the locked uv. After the review's fixes, with uv 0.13.7 and `uv sync --locked --all-extras`: `uv run --frozen pytest -q`, 1006 passed and 3 skipped; `ruff check`, `ruff format --check`, `pyright` (0 errors), and `yamllint --strict` clean.

### Slice 4 independent review

A read-only review from a fresh context, with no part in the slice's work, ran on 2026-11-07 over `c3d8881` (PR [#101](https://github.com/sindredg/hindcast/pull/101)). It checked 11 items: decision 0008's coverage, the timeline chart, the evidence graph, the scored view, the `run_items_behind` refactor, the tests and the broken inputs, the screenshots, the gate and the roadmap, the documentation, the public-text rules, and the dependencies. Each finding was checked again against the code before it was acted on.

Verdicts: 9 of 11 items OK and 2 with findings, decision 0008's coverage (the scored view's difference) and the scored view (two hash checks the score makes); the gate item was OK with the wording note on the two configured rows. No item came back as could not check. The review also found the challenge box on scored runs while checking the page code.

Fixed in this pull request; each code fix has a test that failed first:

| Finding | Fix |
|---|---|
| With `HINDCAST_LIVE=1`, a scored showcase run got the challenge box: the box checked the run's state only, and the challenge command lets a showcase case through once the rubric is frozen. A challenge there makes paid calls and writes beside the scored run | The box needs the case's role in `LIVE_ROLES`; the page says why there is none |
| The scored view skipped two checks the score makes: the review's `judgment_sha256` against the judgment, and the reviewer judgment against the hash its decisions name. An edited reviewer judgment reached the Run items column | Both checks, the second through the score's `load_second_judgments` |
| The worklog did not say the scored view differs from decision 0008 | Stated under [Slice 4](#slice-4-the-view-parts) |
| Two gate rows were "configured, not tested": slice 3's billed cost and slice 4's deployed page | Each is an accepted gap with its reason; the cost row records one Cost Management read |

Plan-only items, done in this pull request because each was small:

| Item | Outcome |
|---|---|
| The regression test compared four fields of each score | It compares every field after a JSON round trip |
| A control character in a graph label reached the DOT text | Control characters become spaces |
| Whether Graphviz itself reads the escapes as the test's parser does | Drawn in a browser with Streamlit's bundled Graphviz: the hostile copy has the clean run's 15 nodes and 19 edges (gate above) |
| `tests/test_app.py` imported pyarrow, which only Streamlit depends on | The chart test reads the times from Streamlit's bytes without it |
| A malformed `scores.json` raised a `TypeError` the page did not catch | Caught with the other refusals, with a test |


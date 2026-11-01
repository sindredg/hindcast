# Milestone 3: Retrieval

Status: Built on 2026-11-01. The library index is live and its [gate](#gate) checks pass on it; the independent review has not run yet. The milestone state is in the [roadmap](../roadmap.md).

## Scope

The postmortem library in Azure AI Search: section- and figure-bounded chunks that resolve to citations, a search that a case can only use within its date bound and its picks, and the checks that prove both on the live index ([decision 0019](../decisions/0019-library-index.md)). Before that, the extraction model moved to a pinned gpt-5.4-mini, and every analysis checks its analyzer first ([decision 0018](../decisions/0018-extraction-model.md); [#13](https://github.com/sindredg/hindcast/issues/13), [#15](https://github.com/sindredg/hindcast/issues/15)).

The investigator's library tool and library citations are milestone 4's second slice. A Foundry IQ knowledge base is not built. The procedure is the [retrieval runbook](../runbooks/retrieval.md).

## Work completed

### Extraction model and analyzer check

`hindcast.extract.analyze` reads each analyzer from the service before its first analysis in a process and refuses it, before any analysis call, if it differs from its file in `analyzers/` or names a completion model other than the extraction deployment's (`HINDCAST_EXTRACTION_DEPLOYMENT`). Each result carries that deployment's model name and version under `model`, and the library extracts, chart descriptions, and answer-key analyzer results store it. The analyzer files name `gpt-5.4-mini`.

### Search service template

`infra/search.bicep` creates a Basic search service in Switzerland North with local authentication off, a public endpoint without IP rules, semantic ranking, and no managed identity. It assigns the developer Search Service Contributor and Search Index Data Contributor. CI builds and lints it with `infra/main.bicep`, and the step now fails on any diagnostic: a compiler warning exits 0 ([finding](../findings/deployment.md#a-bicep-compiler-warning-exits-0-2026-11-01)). The client is `azure-search-documents` 12.0.0, the newest stable release, chosen because the index has to be created and queried with an Entra token from Hindcast's code.

### Chunks and the index build

`python -m hindcast.index build --dimensions <n>` checks each local extract against its blob, cuts it into chunks that never cross a section or a figure, embeds them through the Foundry resource endpoint, and pushes them in one batch. A section over 4,000 characters splits at paragraphs. The extracts render each table as a single HTML paragraph, up to 22,172 characters, so a paragraph over the limit splits after a table row or at a line break; a single row or line stays whole. The library gives 267 chunks, 202 section parts and 65 figures, the longest 9,472 characters (one table row). The build refuses an index that holds documents unless `--replace` is given.

### The bound search

`hindcast.search.search_library` takes a case ID, validated against the registry, and builds the filter from the registries alone: documents published before midnight UTC of the case's start day and, unless the case is sealed, picked for it. The query reaches the keyword and vector parts, never the filter. The search is hybrid (the vector part pre-filtered, 50 neighbours) with semantic ranking, and returns 5 hits. Each hit is checked again in code: a document outside the rule, a document not in the library, or a `ref` that does not resolve to its document's extract raises `LibraryLeak`.

### Gate checks

- `python -m hindcast.index check-filter` lists, for every case, the documents the live filter returns for `*` and compares the set with one computed from the registries. It then runs each case's symptom quotes and four hostile queries (`' or 1 eq 1 or '`, `") or (published_at gt 2000-01-01`, `$filter=published_at gt 2030-01-01`, `*`) through the bound search. `--shift-start <case_id>` moves one case's start a year earlier in memory: the broken-input run.
- `python -m hindcast.index check-chunks` compares every indexed chunk with the chunks rebuilt from the extracts, in both directions, by ID, `ref`, and the SHA-256 of the indexed text.
- `python -m hindcast.leak` normalizes each answer-key item not stated during the incident and reports any 8-word run it shares with the case's evidence updates or with a chunk the case's filter returns from the live index. It refuses a case with nothing to compare, or whose filter returns no library chunk. `--plant` adds one in-memory chunk holding a key item's quote, requires that item among the hits, and fails on any other hit.

### The frozen quality check

`eval/retrieval/library-v1/` holds the query set (34 symptom quotes, 19 with relevant documents) and the rubric, committed before any query ran. `python -m hindcast.index quality --index <name>` refuses a query set that is uncommitted or that the registries no longer produce, runs each query with the date bound only, and writes recall@5 and reciprocal rank with the dataset, embedding model, and search API version.

## Live run

All on 2026-11-01, live, from the developer's sign-in. Times are UTC.

| Step | Result |
|---|---|
| Extraction deployment | `gpt-5.4-mini`, model 2026-03-17, Global Standard 50, `NoAutoUpgrade`, created 11:46 with `az rest` (the CLI has no flag for the upgrade option) |
| Search service | Created by `az deployment group create` from `infra/search.bicep`, 12:00:34 to 12:01:13, `Succeeded`; `disableLocalAuth: true` |
| Roles | Content Understanding Contributor and Cognitive Services OpenAI User assigned on the Foundry resource at 12:45:50 and 12:45:56. Content Understanding answered from 12:49:01 (refused at 12:47:57 and 12:48:29); embeddings from 12:51:19 (a build at 12:51:06 got 401) |
| Supported model | `supportedModels.completion` of `prebuilt-document` lists `gpt-5.4-mini` |
| Defaults | Before: `gpt-5-mini` and `text-embedding-3-large`. `update_defaults` at 12:49:28 with `gpt-5-mini: null`; read back: exactly `gpt-5.4-mini` and `text-embedding-3-large` |
| Analyzers | Before the replace, the service's copies named gpt-5-mini and `check_analyzer("hindcast_chart", …)` raised `AnalyzerDiffers`. `replace_analyzer` for all three at 12:49:49 to 12:49:54; `ensure_analyzers()` returned `[]`; `check_analyzer` passed for all three |
| Test analysis | `hindcast_chart` on a development-case chart at 12:50:04: `model` gpt-5.4-mini 2026-03-17; usage 403 input and 390 output tokens; a description, alt text, and the text in the image. Not stored |
| First build | 404 on embeddings through the project endpoint ([troubleshooting](../troubleshooting.md#retrieval-the-first-index-build-fails-with-404-on-embeddings-2026-11-01)); embeddings moved to the resource endpoint |
| Builds | `build --dimensions 1024`, 12:51:36 to 12:53:55, and `--dimensions 3072`, 12:53:58 to 12:56:17: each `267 chunks (202 section parts, 65 figures)`, embedding `text-embedding-3-large` version 1 |
| Quality | Query set SHA-256 checked before the run. 1,024: mean recall@5 0.640, MRR 0.702. 3,072: 0.544, 0.695. The frozen rule keeps 1,024 ([results](../../eval/retrieval/library-v1/README.md#status)) |
| Clean-up | Content Understanding Contributor removed at 13:18:02; gpt-5-mini deleted at 13:18:04; `hindcast-library-3072` deleted at 13:18:06 (204). Read back: OpenAI User is the only role left on the resource, the deployment list has no gpt-5-mini, and the service lists one index. Content Understanding still accepted reads and a defaults write more than 85 minutes after the role was removed; the refusal was not observed ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)) |

The results files name the run commits from before the branch was rebased onto `main`; the results README gives the tree hashes that tie them to the public history ([#39](https://github.com/sindredg/hindcast/issues/39)).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| The search service exists and the code reaches it with an Entra token; a request without a token is refused, and key access is off | Tested live | 12:01:39: `disableLocalAuth: true` read from the service; no credential 401; the real admin key in `api-key` 401 (403 expected, [finding](../findings/identity-and-access.md#an-admin-key-gets-401-not-403-when-local-authentication-is-off-2026-11-01)); a bearer token 200. Every build, check, and query below ran with an Entra token |
| A library search for a case returns only documents published before its outage began and none about the case, including for a query with quotes or a filter expression | Tested live | `check-filter` at 12:57:49: `8 cases, 0 problems`, exit 0, over every case's symptom quotes and the four hostile queries. Broken input `check-filter --shift-start cloudflare-2025-11-18` at 12:58:22: `1 problems`, three documents allowed but not listed, exit 1. "None about the case": the library registry refuses a case's own postmortem, and a sealed case's postmortem would be dated after its start |
| Every chunk in the index resolves to a section or a chart of a library document | Tested live | `check-chunks` at 12:58:55: `267 chunks listed, 267 counted, 0 problems`, exit 0. Again at 14:39:22, after the check began hashing the indexed text (review fix): the same. The broken inputs (changed indexed text, a changed hash, a missing chunk, an extra chunk) ran locally only, in `test_check_chunks_hashes_the_indexed_text` and `test_check_chunks_reports_missing_extra_and_changed` |
| The leak check finds no answer-key fact in a case's evidence or its filtered library, except facts the key marks as stated during the incident | Tested live | `python -m hindcast.leak` at 12:59:10: 0 hits for each of the five cases with a frozen key (17, 17, 8, 11, and 9 unstated items), against 143, 74, 79, 44, and 88 library chunks. Broken input `leak --plant` at 12:59:13: each case reports its planted item, exit 0. Both again at 14:39:30 and 14:43:15, after the review fixes (an empty filtered library is refused; a planted run fails on any other hit): the same. Sealed cases have no key and are not checked |
| The extraction model is pinned, and each result records it (#13) | Tested live | Live run above: `NoAutoUpgrade`, and the test analysis carried `model` |
| An analyzer that differs from its file, or names another model, is refused before analysis (#15) | Tested live and locally | Live: `AnalyzerDiffers` before the replace. Locally: the tests in the next table |
| One bound search for the development case returns hits from its picks | Tested live | `python -m hindcast.search cloudflare-2026-02-20 "the last subset of prefixes which were withdrawn"` at 12:59:28: 5 hits, all sections of two documents published in 2022 and 2025, exit 0 |

Every new check was run once against a broken input on 2026-11-01, locally. Each row changes one line, runs the whole suite, and restores the file:

| Broken input | Failed tests |
|---|---|
| Model comparison in `check_analyzer` skipped | `test_analyze_refuses_a_model_mismatch` |
| Served-copy comparison in `check_analyzer` skipped | `test_analyze_refuses_a_changed_analyzer`, `test_analyze_checks_each_analyzer_once` |
| A section cut every 4,000 characters, mid-paragraph | `test_long_section_splits_at_paragraphs`, `test_overlong_paragraph_is_its_own_part`, `test_overlong_table_splits_after_a_row` |
| A non-empty index accepted without `--replace` | `test_build_refuses_a_non_empty_index` |
| Date clause dropped from the filter | `test_filter_for_a_scored_case`, `test_check_filter_reports_a_shifted_start` |
| Hit re-check against the rule removed | `test_hit_outside_the_filter_raises`, `test_check_filter_reports_a_leak_from_a_query` |
| A `ref` that does not resolve accepted | `test_hit_with_an_unknown_ref_raises`, `test_hit_whose_ref_names_another_document_raises` |
| Chunk content hash not compared | `test_check_chunks_reports_missing_extra_and_changed` |
| Leak run length 80 words | `test_planted_quote_in_an_update_is_a_hit`, `test_planted_quote_in_a_chunk_is_a_hit`, `test_a_timeline_event_is_checked`, `test_seven_shared_words_are_not_a_hit` |
| Leak check run with nothing to compare | `test_a_key_with_no_unstated_items_is_refused`, `test_no_sources_is_refused` |
| Relevance taken from `serves` alone | `test_relevance_comes_from_the_reason_quote`, `test_queries_file_matches_the_registry` |
| A changed query set accepted by `quality` | none at first: the suite passed. Two tests were added, and the break then failed `test_quality_refuses_a_query_set_the_registries_do_not_give` |
| An uncommitted query set accepted by `quality` | `test_quality_refuses_an_uncommitted_query_set` |
| Indexed text changed, its stored hash field not (review fix: added test, failed before the fix) | `test_check_chunks_hashes_the_indexed_text` |
| The filter returns no library chunk (review fix: added test, failed before the fix) | `test_an_empty_filtered_library_is_refused` |
| A real hit next to the planted one in a `--plant` run (review fix: added test, failed before the fix) | `test_plant_run_fails_on_a_real_hit_next_to_the_planted_one` |
| An embedding that fails during `build --replace` (review fix: added test, failed before the fix) | `test_failed_embedding_leaves_the_index_alone` |
| CI's Bicep step on a template with a `BCP036` warning, and on one that does not build | The step's commands, run locally under `bash -e` with `AZURE_BICEP_CHECK_VERSION=false` (review fix): the committed templates pass; the warning copy (`replicaCount: '1'`) fails with the warning printed; a copy with a syntax error fails with the error printed. Before the fix, the syntax-error copy failed with nothing printed |

With every file restored: `uv run --frozen pytest -q`, 403 passed; after the review fixes, 408.

## A step taken out of order

The October case's answer key was drafted on 2026-11-01, before this milestone, with Content Understanding on gpt-5-mini. [#12](https://github.com/sindredg/hindcast/issues/12), [#13](https://github.com/sindredg/hindcast/issues/13), and [#15](https://github.com/sindredg/hindcast/issues/15) each said to fix them before the next extraction, and none was fixed. What limits the damage: the draft was reviewed field by field against the postmortem before it was frozen, every quote was checked word for word in code, and every UTC time was checked again by hand, which covers #12 for this key. The model version that ran (gpt-5-mini 2025-08-07) was read from the deployment that day and is not recorded with the draft. #13 and #15 are fixed here; #12 is still open.

## Independent review

On 2026-11-01 a read-only review of the branch at `b80cc25` checked the gate, the filter, the chunks, the leak check, the quality check, the analyzer check, three rows of the broken-input table, the live resources and roles, the findings, the runbook, the decisions, the public text, the versions, and the diagrams. It re-ran the live gate checks and got the recorded output. Each finding was checked against the code before acting on it.

Fixed in this pull request:

| Finding | Fix |
|---|---|
| The CI Bicep step fails on any output, and `az bicep build` warns whenever a Bicep newer than the pin is released, so every run would fail after the next release; under `bash -e` a failed build also hid its log | `AZURE_BICEP_CHECK_VERSION=false`; the step records a failure and prints the log (table above) |
| `check-chunks` compared the stored hash field, never the indexed text | It hashes the indexed text; test added |
| The leak check passed with an empty filtered library, since evidence alone satisfied its refusal | A case whose filter returns no chunk is refused; test added; the live counts are in the gate row |
| `leak --plant` exited 0 whatever else it found | Any hit outside the planted source fails the run; tests added |
| `build --replace` deleted the index before embedding, so a failed embedding left it empty | Embedding runs first; test added |
| The Content Understanding role removal was never seen refused, and the pages said the role is held only while extraction runs | The [identity findings](../findings/identity-and-access.md) and the pages that state the role record what was observed |
| The results README gave one `src` tree hash for both run commits; it holds at the code commit only | Reworded |
| The retrieval diagram said "4,000 characters at most"; three chunks are longer, since a single row or line stays whole | Label corrected |

Planned, not fixed here: [#41](https://github.com/sindredg/hindcast/issues/41), [#42](https://github.com/sindredg/hindcast/issues/42), the commit provenance of `quality` added to [#39](https://github.com/sindredg/hindcast/issues/39), and the Foundry IQ comparison as an open item in the [roadmap](../roadmap.md).

## Issues opened

- [#39](https://github.com/sindredg/hindcast/issues/39): run results name a commit that a rebase or squash merge rewrites.
- [#41](https://github.com/sindredg/hindcast/issues/41): extraction does not check that the defaults map its model to the extraction deployment.
- [#42](https://github.com/sindredg/hindcast/issues/42): the library day bound assumes publish dates are UTC days.

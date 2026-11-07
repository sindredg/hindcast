# Milestone 3: Retrieval

Status: Verified on 2026-11-01 on the live index, deleted on 2026-11-04 ([gate](#gate), [independent review](#independent-review)). Milestone state: [roadmap](../roadmap.md#status).

On this page: [Scope](#scope) · [Work completed](#work-completed) · [Live run](#live-run) · [Gate](#gate) · [A step taken out of order](#a-step-taken-out-of-order) · [Independent review](#independent-review) · [Issues opened](#issues-opened)

## Scope

The postmortem library in Azure AI Search: section- and figure-bounded chunks that resolve to citations, a search bound to a case's date and picks, and the live checks for both ([decision 0019](../decisions/0019-library-index.md)). First, the extraction model moved to a pinned gpt-5.4-mini and every analysis checks its analyzer ([decision 0018](../decisions/0018-extraction-model.md); [#13](https://github.com/sindredg/hindcast/issues/13), [#15](https://github.com/sindredg/hindcast/issues/15)).

The investigator's library tool is milestone 4's second slice. The Foundry IQ comparison ran on 2026-11-05 ([foundry-iq-v1](../../eval/retrieval/foundry-iq-v1/README.md)); no knowledge base existed when this was written. Procedure: [retrieval runbook](../runbooks/retrieval.md).

## Work completed

### Extraction model and analyzer check

`hindcast.extract.analyze` reads each analyzer from the service before its first analysis and refuses one that differs from its file in `analyzers/` or names a model other than `HINDCAST_EXTRACTION_DEPLOYMENT`. Each result carries the model name and version under `model`, stored with extracts, chart descriptions, and answer-key results. The analyzer files name `gpt-5.4-mini`.

### Search service template

`infra/search.bicep`: Basic, Switzerland North, local authentication off, public endpoint without IP rules, semantic ranking, no managed identity; the developer gets Search Service Contributor and Search Index Data Contributor. CI lints it with `infra/main.bicep` and fails on any diagnostic, since a warning exits 0 ([finding](../findings/deployment.md#a-bicep-compiler-warning-exits-0-2026-11-01)). Client: `azure-search-documents` 12.0.0, newest stable.

### Chunks and the index build

`python -m hindcast.index build --dimensions <n>` checks each extract against its blob, cuts chunks within section and figure bounds, embeds them through the Foundry resource endpoint, and pushes one batch. A section over 4,000 characters splits at paragraphs; a paragraph over the limit (a table is one paragraph, up to 22,172 characters) splits after a row or line; a single row stays whole. 267 chunks (202 section parts, 65 figures), the longest 9,472 characters. A non-empty index is refused without `--replace`.

### The bound search

`hindcast.search.search_library` builds the filter from the registries alone: documents published before midnight UTC of the case's start day and, unless the case is sealed, picked for it. The query never reaches the filter. Hybrid (vector pre-filtered, 50 neighbours), semantic ranking, 5 hits. A hit outside the rule, outside the library, or with an unresolved `ref` raises `LibraryLeak`.

### Gate checks

- `python -m hindcast.index check-filter`: per case, the live filter's documents for `*` against the registries; then every symptom quote and four hostile queries (`' or 1 eq 1 or '`, `") or (published_at gt 2000-01-01`, `$filter=published_at gt 2030-01-01`, `*`). `--shift-start <case_id>` moves a start a year earlier in memory: the broken input.
- `python -m hindcast.index check-chunks`: every indexed chunk against the chunks rebuilt from the extracts, both directions, by ID, `ref`, and SHA-256 of the indexed text.
- `python -m hindcast.leak`: each unstated key item against the case's evidence and filtered chunks, reporting any shared 8-word run; refuses nothing to compare or an empty filtered library. `--plant` adds one in-memory chunk with a key quote, requires it as a hit, fails on any other.

### The frozen quality check

`eval/retrieval/library-v1/`: 34 symptom quotes (19 with relevant documents) and the rubric, committed before any query ran. `python -m hindcast.index quality --index <name>` refuses an uncommitted or stale query set, runs each query with the date bound only, and writes recall@5 and reciprocal rank with dataset, embedding model, and search API version.

## Live run

All on 2026-11-01, live, from the developer's sign-in. Times UTC.

| Step | Result |
|---|---|
| Extraction deployment | `gpt-5.4-mini`, model 2026-03-17, Global Standard 50, `NoAutoUpgrade`, created 11:46 with `az rest` (the CLI has no flag for the upgrade option) |
| Search service | `az deployment group create` from `infra/search.bicep`, 12:00:34 to 12:01:13, `Succeeded`; `disableLocalAuth: true` |
| Roles | Content Understanding Contributor and Cognitive Services OpenAI User on the Foundry resource at 12:45:50 and 12:45:56. Content Understanding answered from 12:49:01 (refused 12:47:57 and 12:48:29); embeddings from 12:51:19 (401 at 12:51:06) |
| Supported model | `supportedModels.completion` of `prebuilt-document` lists `gpt-5.4-mini` |
| Defaults | Before: `gpt-5-mini` and `text-embedding-3-large`. `update_defaults` at 12:49:28 with `gpt-5-mini: null`; read back: `gpt-5.4-mini` and `text-embedding-3-large` |
| Analyzers | Service copies named gpt-5-mini; `check_analyzer("hindcast_chart", …)` raised `AnalyzerDiffers`. `replace_analyzer` for all three, 12:49:49 to 12:49:54; `ensure_analyzers()` returned `[]`; `check_analyzer` passed for all three |
| Test analysis | `hindcast_chart` on a development chart at 12:50:04: `model` gpt-5.4-mini 2026-03-17; 403 input, 390 output tokens. Not stored |
| First build | 404 on embeddings through the project endpoint ([troubleshooting](../troubleshooting.md#retrieval-the-first-index-build-fails-with-404-on-embeddings-2026-11-01)); moved to the resource endpoint |
| Builds | `build --dimensions 1024`, 12:51:36 to 12:53:55; `--dimensions 3072`, 12:53:58 to 12:56:17: each `267 chunks (202 section parts, 65 figures)`, `text-embedding-3-large` version 1 |
| Quality | Query set SHA-256 checked first. 1,024: mean recall@5 0.640, MRR 0.702. 3,072: 0.544, 0.695. The frozen rule keeps 1,024 ([results](../../eval/retrieval/library-v1/README.md#status)) |
| Clean-up | Content Understanding Contributor removed 13:18:02; gpt-5-mini deleted 13:18:04; `hindcast-library-3072` deleted 13:18:06 (204). Read back: OpenAI User the only role left, no gpt-5-mini, one index. Content Understanding still accepted reads and a defaults write more than 85 minutes after the removal; the refusal was not observed ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)) |

The results files name run commits from before the rebase onto `main`; the results README gives the tree hashes ([#39](https://github.com/sindredg/hindcast/issues/39)).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| The search service exists and the code reaches it with an Entra token; a request without a token is refused, and key access is off | Tested live | 12:01:39: `disableLocalAuth: true`; no credential 401; the admin key in `api-key` 401 (403 expected, [finding](../findings/identity-and-access.md#an-admin-key-gets-401-not-403-when-local-authentication-is-off-2026-11-01)); a bearer token 200. Every build, check, and query ran with an Entra token |
| A library search for a case returns only documents published before its outage began and none about the case, including for a query with quotes or a filter expression | Tested live | `check-filter` at 12:57:49: `8 cases, 0 problems`, exit 0, over every symptom quote and the four hostile queries. Broken input `check-filter --shift-start cloudflare-2025-11-18` at 12:58:22: `1 problems`, three documents allowed but not listed, exit 1. The registry refuses a case's own postmortem; a sealed case's postmortem is dated after its start |
| Every chunk in the index resolves to a section or a chart of a library document | Tested live | `check-chunks` at 12:58:55: `267 chunks listed, 267 counted, 0 problems`, exit 0; the same at 14:39:22 after the text-hash fix. Broken inputs (changed text, changed hash, missing and extra chunk) local only: `test_check_chunks_hashes_the_indexed_text`, `test_check_chunks_reports_missing_extra_and_changed` |
| The leak check finds no answer-key fact in a case's evidence or its filtered library, except facts the key marks as stated during the incident | Tested live | `python -m hindcast.leak` at 12:59:10: 0 hits for the five keyed cases (17, 17, 8, 11, 9 unstated items) against 143, 74, 79, 44, 88 chunks. `leak --plant` at 12:59:13: each case reports its planted item, exit 0. Both again at 14:39:30 and 14:43:15 after the review fixes: the same. Sealed cases have no key |
| The extraction model is pinned, and each result records it (#13) | Tested live | `NoAutoUpgrade`; the test analysis carried `model` |
| An analyzer that differs from its file, or names another model, is refused before analysis (#15) | Tested live and locally | Live: `AnalyzerDiffers` before the replace. Locally: the next table |
| One bound search for the development case returns hits from its picks | Tested live | `python -m hindcast.search cloudflare-2026-02-20 "the last subset of prefixes which were withdrawn"` at 12:59:28: 5 hits, sections of two documents from 2022 and 2025, exit 0 |

Every new check broken once on 2026-11-01, locally, one line per row, whole suite run, file restored:

| Broken input | Failed tests |
|---|---|
| Model comparison in `check_analyzer` skipped | `test_analyze_refuses_a_model_mismatch` |
| Served-copy comparison in `check_analyzer` skipped | `test_analyze_refuses_a_changed_analyzer`, `test_analyze_checks_each_analyzer_once` |
| A section cut every 4,000 characters, mid-paragraph | `test_long_section_splits_at_paragraphs`, `test_overlong_paragraph_is_its_own_part`, `test_overlong_table_splits_after_a_row` |
| A non-empty index accepted without `--replace` | `test_build_refuses_a_non_empty_index` |
| Date clause dropped from the filter | `test_filter_for_a_scored_case`, `test_check_filter_reports_a_shifted_start` |
| Hit re-check removed | `test_hit_outside_the_filter_raises`, `test_check_filter_reports_a_leak_from_a_query` |
| An unresolved `ref` accepted | `test_hit_with_an_unknown_ref_raises`, `test_hit_whose_ref_names_another_document_raises` |
| Chunk content hash not compared | `test_check_chunks_reports_missing_extra_and_changed` |
| Leak run length 80 words | `test_planted_quote_in_an_update_is_a_hit`, `test_planted_quote_in_a_chunk_is_a_hit`, `test_a_timeline_event_is_checked`, `test_seven_shared_words_are_not_a_hit` |
| Leak check with nothing to compare | `test_a_key_with_no_unstated_items_is_refused`, `test_no_sources_is_refused` |
| Relevance from `serves` alone | `test_relevance_comes_from_the_reason_quote`, `test_queries_file_matches_the_registry` |
| A changed query set accepted by `quality` | none at first. Two tests added; the break then failed `test_quality_refuses_a_query_set_the_registries_do_not_give` |
| An uncommitted query set accepted by `quality` | `test_quality_refuses_an_uncommitted_query_set` |
| Indexed text changed, stored hash not (review fix, test added, failed first) | `test_check_chunks_hashes_the_indexed_text` |
| Filter returns no library chunk (review fix, test added, failed first) | `test_an_empty_filtered_library_is_refused` |
| A real hit next to the planted one (review fix, test added, failed first) | `test_plant_run_fails_on_a_real_hit_next_to_the_planted_one` |
| An embedding fails during `build --replace` (review fix, test added, failed first) | `test_failed_embedding_leaves_the_index_alone` |
| CI's Bicep step on a `BCP036` warning, and on a template that does not build | The step's commands under `bash -e` with `AZURE_BICEP_CHECK_VERSION=false` (review fix): committed templates pass; the warning copy (`replicaCount: '1'`) fails with the warning printed; a syntax-error copy fails with the error printed. Before the fix the syntax-error copy failed with nothing printed |

With every file restored: `uv run --frozen pytest -q`, 403 passed; after the review fixes, 408.

## A step taken out of order

The October case's key was drafted on 2026-11-01 on gpt-5-mini, although [#12](https://github.com/sindredg/hindcast/issues/12), [#13](https://github.com/sindredg/hindcast/issues/13), and [#15](https://github.com/sindredg/hindcast/issues/15) said to fix them first. Limits: the draft was reviewed field by field, every quote checked in code, every UTC time checked by hand (covers #12 here). The model version (gpt-5-mini 2025-08-07) was read from the deployment, not recorded with the draft. #13 and #15 fixed here; #12 open.

## Independent review

Read-only review, 2026-11-01, at `b80cc25`: gate, filter, chunks, leak, quality, and analyzer checks, three broken-input rows, live resources and roles, findings, runbook, decisions, public text, versions, diagrams; the live gate checks re-ran with the recorded output. Each finding was checked against the code first.

Fixed in this pull request:

| Finding | Fix |
|---|---|
| The CI Bicep step fails on any output, and `az bicep build` warns whenever a newer Bicep exists, so every run would fail after the next release; under `bash -e` a failed build hid its log | `AZURE_BICEP_CHECK_VERSION=false`; the step records a failure and prints the log (table above) |
| `check-chunks` compared the stored hash field, never the indexed text | Hashes the indexed text; test added |
| The leak check passed with an empty filtered library | Refused; test added; live counts in the gate row |
| `leak --plant` exited 0 whatever else it found | Any other hit fails the run; tests added |
| `build --replace` deleted the index before embedding | Embedding runs first; test added |
| The role removal was never seen refused, and the pages said the role is held only during extraction | [Identity findings](../findings/identity-and-access.md) and the pages record what was observed |
| The results README gave one `src` tree hash for both run commits; it holds at the code commit only | Reworded |
| The retrieval diagram said "4,000 characters at most"; three chunks are longer | Label corrected |

Planned, not fixed here: [#41](https://github.com/sindredg/hindcast/issues/41), [#42](https://github.com/sindredg/hindcast/issues/42), `quality` commit provenance added to [#39](https://github.com/sindredg/hindcast/issues/39), the Foundry IQ comparison as an open item in the [roadmap](../roadmap.md).

## Issues opened

- [#39](https://github.com/sindredg/hindcast/issues/39): run results name a commit that a rebase or squash merge rewrites.
- [#41](https://github.com/sindredg/hindcast/issues/41): extraction does not check that the defaults map its model to the extraction deployment.
- [#42](https://github.com/sindredg/hindcast/issues/42): the library day bound assumes publish dates are UTC days.

# Milestone 5, first part: Sealed reconstructions and the October case

Status: Verified on 2026-11-07 with milestone 5 ([gate](#gate), [independent review](#independent-review)). Drop date 2026-11-30 since 2026-11-03 ([decision 0022](../decisions/0022-sealed-drop-date-and-offline-reveal.md)). Milestone state: [roadmap](../roadmap.md#status).

On this page: [Scope](#scope) · [Work completed](#work-completed) · [Checks](#checks) · [Live run](#live-run) · [Gate](#gate) · [Independent review](#independent-review) · [Issues opened](#issues-opened) · [Second seals, with the library (2026-11-02)](#second-seals-with-the-library-2026-11-02) · [Third seals: two GitHub outages of 2026-11-04](#third-seals-two-github-outages-of-2026-11-04) · [Reveal: github-2026-11-04-actions (2026-11-07)](#reveal-github-2026-11-04-actions-2026-11-07)

## Scope

Two answers to "could the model have known the answer?" that do not rest on a training cutoff ([decision 0017](../decisions/0017-sealed-reconstructions.md)):

- **Sealed reconstructions.** Outages without a published cause, reconstructed now; only each result's SHA-256 is public until the provider's account is out. Scored against the postmortem if one is out by the drop date (2026-11-09 when written; 2026-11-30 since [decision 0022](../decisions/0022-sealed-drop-date-and-offline-reveal.md)).
- **An after-release case.** GitHub's outage of 2026-10-07 began after both pinned model versions were released (gpt-6-luna 2026-09-22, gpt-6.1-sol 2026-09-29). It joins the showcase cases.

Procedure: the [sealing runbook](../runbooks/sealing.md).

## Work completed

### Sealed cases and the seal command

- `hindcast.cases` accepts the role `sealed` (status updates only); `hindcast.investigate` refuses it.
- `hindcast.seal run <case_id>` refuses, before any cloud call, an unsealed case, a second seal for the same case, deployment, and library setting, or a changed `src/`, `prompts/`, `pyproject.toml`, `uv.lock`, or `data/cases.yaml`. It writes under `build/sealed/` (ignored), records the hash in `eval/sealed/seals.json` with `blob: null`, uploads to Blob `extracted/sealed/<case_id>/` without overwriting, and records the blob. `seal upload` resends the same bytes after checking the hash.
- No model output (raised, or zero output tokens) is `no-result`, retried up to three attempts; any output is final.
- Output: counts, usage, the hash; for an incomplete run only the reason's kind before the first colon.
- `tests/test_sealed_reveal.py` checks every `revealed` entry against `eval/investigations/<case_id>/`.

### Several status incidents per case

- `hindcast.evidence.cut_all` cuts each snapshot by the [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) rules and merges by time; each incident keeps its own withheld resolved mark. `hindcast.ingest evidence` downloads every status source.
- Start is the earlier of Statuspage's `started_at` and the first update: GitHub backfilled `djlmxz2zd0j7`'s `started_at` with its resolved time (16:25:14Z), after its first update (15:14:45Z). Existing starts did not move.
- The investigator prompt (v2) and the `list_updates` note say each incident ends at its resolved update; the luna agent got version 2 on the first seal.

### Agent names

- Foundry refused `hindcast-investigator-gpt-6.1-sol` (`invalid_parameters`) before any model call; `agent_name` now hyphenates: `hindcast-investigator-gpt-6-1-sol`.

### Keys from a status-page summary

- `hindcast.keys.statuspage_summary` reads GitHub's resolved update as the postmortem; `postmortem_page` picks it for a `.json` source.

## Checks

Each failed once on a broken input, 2026-11-01, locally:

| Broken input | Failed tests |
|---|---|
| `sealed` left out of the postmortem exemption in `load_cases` | `test_sealed_case_needs_no_postmortem` |
| Start taken from the snapshot only | `test_backfilled_started_at_uses_the_first_update` |
| Earlier attempts ignored | `test_second_seal_is_refused`, `test_an_incomplete_seal_is_final_too`, `test_time_cap_after_output_is_final`, `test_run_refuses_before_any_cloud_call` |
| Dirty-tree check skipped | `test_dirty_tree_is_refused` |
| A `no-result` attempt counted as final | `test_retry_rule`, `test_raised_run_is_recorded_as_no_result`, `test_first_call_time_cap_is_no_result` |
| Upload before the hash is recorded | `test_run_records_hash_then_uploads`, `test_upload_retries_the_same_bytes` |
| Full incomplete reason printed | `test_output_has_only_the_reason_prefix` |
| A zero-output result counted as final | `test_first_call_time_cap_is_no_result` |
| Sealed refusal removed from `check_case_allowed` | `test_investigate_refuses_a_sealed_case` |
| Reveal check never reports a mismatch | `test_reveal_check_fails_on_a_changed_file` |
| Summary taken from the first update, not the resolved one | `test_statuspage_summary_takes_the_resolved_text`, `test_postmortem_page_reads_a_status_snapshot_by_its_file_name` |
| A key fact that is in the incident title (`Pull Requests`) | `test_no_key_fact_in_any_question` |
| One character changed in a symptom quote | `test_symptom_quotes_appear_in_their_update` |
| A pick reason without the case's tagged quote | `test_the_committed_library_loads_with_every_hash_pinned` |

Test suite after the slice: `uv run --frozen pytest -q` → 347 passed, locally with the captured sources present.

## Live run

On 2026-11-01, against the live project and storage account.

### Choosing the outages

Feeds read at about 08:07 UTC. GitHub `nms1dpzmh9d9` (2026-10-21), GitHub `wq8305lppdc2` (2026-10-22), and Cloudflare `0eqtn0khkz87` (2026-10-20) had no cause in their resolved updates; five other October GitHub incidents with eight or more updates carried a summary (2026-10-07 among them), and Google Cloud's europe-west2 incident of 2026-10-20 its report. None harmed people, leaked data, or named an attacker.

| Step | Command | Result |
|---|---|---|
| Capture | `capture status` per incident | 08:15:51 to 08:15:52Z; hashes in `data/cases.yaml` |
| Evidence | `ingest evidence --case <id>` | `cloudflare-2026-10-20` 9 updates, `github-2026-10-21` 15, `github-2026-10-22` 18, each with the resolved mark; none dropped; `blob: uploaded` |
| Seal, gpt-6-luna | `seal run <id>` | three `complete`, 0 rejected citations, 0 unsupported, agent version 2; 2 model calls and 2 tool calls each |
| Seal, gpt-6.1-sol | `HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol seal run <id>` | first try refused on the agent name before any model call; then three `complete`, 0 rejected, 0 unsupported, agent version 1 |
| Second seal | `seal run cloudflare-2026-10-20` | `SealRefused: cloudflare-2026-10-20 is already sealed on gpt-6-luna` |
| Publish | push of `a372f32`, then the pull request | Pushed 08:21:55Z by the workstation clock (`date -u`, matching GitHub's `Date` header at 09:15Z). Events API: `PullRequestEvent opened` for #32 at 2026-11-01T08:22:15Z (`gh api repos/sindredg/hindcast/events`), the seal's server-side time; the payload shows the current head, so head `a372f32` at opening rests on the next push coming at about 09:02Z. `created_at` and the check runs read 09:22:15Z, an hour past the server clock at 09:15Z; not reconciled. CI green on `a372f32` |

The six hashes, times, and commits are in [`eval/sealed/seals.json`](../../eval/sealed/seals.json). The files were not opened.

### The October case

| Step | Command | Result |
|---|---|---|
| Capture | `capture status` for `djlmxz2zd0j7`, `qpfv5p86dmrl`, and `djlmxz2zd0j7` again as the postmortem | 08:26:24 to 08:26:25Z; the summary capture has the first incident's SHA-256 |
| Evidence | `ingest evidence --case github-2026-10-07` | 25 updates: 19 and 4 before the two resolved marks (16:25:14Z and 18:04:49Z); none dropped; start 15:14:45Z |
| Prior knowledge | `evaluation.prior collect --deployment <d>` | `prior-2026-11-01-gpt-6-luna.json`: 4 entries, 619 input and 3811 output tokens; `prior-2026-11-01-gpt-6.1-sol.json`: 4 entries, 619 input and 1955 output tokens. Committed unread |
| Symptom tags | `data/library.yaml` | seven tags quoted from the evidence, committed (`9fbb1e1`) before any pick |
| Key draft | Content Understanding Contributor assigned (extraction runbook step 1); `keys draft --case github-2026-10-07` | 1 page; 3 factors, 5 timeline events, 6 fixes, 2 problems (two quotes not word for word) |
| Key review | each field against the summary and the 25 updates, then a second independent pass | two quotes made exact; attack basis `implied` with its quote; the four start and end times marked stated (u6 and u22); a factor restating the root cause dropped; a pause between the outages moved out of the fixes; the machine's removal added as a fix; the root-cause quote extended to the routing change |
| Freeze | `keys freeze github-2026-10-07` | `sha256 86ba420c112567208ac33c08717839cb3a62b56ffe07343e1e102a0c5a0a20d1`; every quote found word for word |
| Role removed | extraction runbook steps 19 and 20 | removed 09:01:14Z; the next read at 09:03:05Z refused with `PermissionDenied` |
| Library picks | [decision 0013](../decisions/0013-library-selection.md) rule, existing documents only | same-provider `github-availability-2023-11`, `github-availability-2026-06`; other-provider `google-cloud-2025-06-12`, `aws-2021-12-07`; attack-suspected `github-2018-02-28` (DDoS confirmed), `github-2016-01-28` (attack ruled out); decoy `cloudflare-2023-11-02` |

Not picked under rule 5 (cause too close): `github-availability-2023-09` (a primary database's write error), `github-2018-10-21` (a database failover after a network partition), `google-cloud-2020-12-14` (leftover records after a migration, a consensus leader that could not write). `github-availability-2026-06` is one document (rule 7), so its June 17 incident (an invalid configuration replaced with the previous one) comes with the June 25 pick.

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| A sealed result is unchanged between sealing and scoring (milestone 5, sealed cases) | configured, not tested | hashes in [`seals.json`](../../eval/sealed/seals.json), public from the opening of #32 at 08:22:15Z; `tests/test_sealed_reveal.py` fails on a changed file. No file revealed yet |
| A sealed run is refused when it would break the rules | tested, locally and live | `tests/test_seal.py`; live: the second `seal run` refused before any cloud call |
| A recurrence's updates are evidence, with each resolved text withheld | tested, locally and live | `test_two_incidents_merge_in_time_order`, `test_ingest_cuts_every_status_source_of_a_case`; live: 25 updates, two resolved marks without text |
| The prior-knowledge answers for GitHub 2026-10-07 are recorded before any evidence reaches a model | tested, live | both files written 2026-11-01 before any investigator or extraction call on the case; committed unread |
| The October key is reviewed and frozen | accepted gap | every field checked in two independent passes, every quote verified in code. Unlike the four earlier keys ([keys gate](02-extraction.md#gate)), the corrections are not approved |
| Each new check fails on a broken input | tested | the Checks table |

## Independent review

On 2026-11-01 a read-only review of `b0f7f62..7d134fe` checked the plan's five focus items, the paths by which text could leave a sealed run, and the documents against the code, without opening the prior-knowledge answers or the sealed files. Fixed in this pull request:

| Finding | Fix |
|---|---|
| The seals' public time rested on the workstation clock; decision 0017 named "the commit time GitHub shows", which the committer sets | 0017 and the runbook name GitHub's record of the pull request; the Live run table gives the Events API record (08:22:15Z) and the command |
| The keys README said the corrections to every key were approved | It says the October key's are not |
| A first-call time cap printed `incomplete: time-cap` and exited 0, though recorded as `no-result` | `seal run` prints `no-result` first and exits 1; `test_first_call_time_cap_is_no_result` |
| The as-built diagram and alt text did not show the seal command; the sealing runbook's status line left out step 10 | Label, alt text (README, architecture page, diagram), and status line corrected |
| The worklog said every sealed run goes through the seal command | Reworded: `hindcast.investigate` refuses a sealed case unless its role is changed |

## Issues opened

- [#33](https://github.com/sindredg/hindcast/issues/33): nothing checks that the seal record only grows.
- [#34](https://github.com/sindredg/hindcast/issues/34): a revealed sealed case as showcase falls under rules decision 0017 exempts it from.
- [#35](https://github.com/sindredg/hindcast/issues/35): the reveal does not record when the provider published its cause.
- [#36](https://github.com/sindredg/hindcast/issues/36): a status-page summary is read as a postmortem without checking it states a cause.
- [#37](https://github.com/sindredg/hindcast/issues/37): `seal upload` cannot finish an upload that succeeded but reported an error.

## Second seals, with the library (2026-11-02)

The second series ([decision 0017](../decisions/0017-sealed-reconstructions.md), rule 6): the same three cases, once per model, with the library search from [milestone 4, slice 2](04-investigator.md#slice-2-the-library-search-tool), on `hindcast-investigator-gpt-6-luna` version 3 and `hindcast-investigator-gpt-6-1-sol` version 2.

At 18:44 UTC: no postmortem status, each resolved update unchanged (180, 180, and 32 characters), no October GitHub availability report (newest September 2026), no Cloudflare post on 2026-10-20.

Each seal: `python -m hindcast.seal run <case_id>` with `--env-file .env`, from commit `5fd90c0`, pushed and clean, 18:44 to 18:48 UTC; each preflight search answered.

| Case | Deployment | Status | Searches | Library citations kept | Rejected, unsupported | Seconds | Tokens in (cached) / out |
|---|---|---|---|---|---|---|---|
| `cloudflare-2026-10-20` | gpt-6-luna | complete | 1 | 0 | 0, 0 | 24.617 | 8,627 (4,633) / 2,619 |
| `github-2026-10-21` | gpt-6-luna | complete | 1 | 0 | 0, 0 | 27.3 | 7,757 (5,227) / 3,555 |
| `github-2026-10-22` | gpt-6-luna | complete | 1 | 0 | 0, 0 | 23.885 | 7,952 (5,291) / 2,838 |
| `cloudflare-2026-10-20` | gpt-6.1-sol | complete | 1 | 1 | 0, 0 | 34.482 | 8,055 (4,633) / 2,350 |
| `github-2026-10-21` | gpt-6.1-sol | complete | 1 | 1 | 0, 0 | 40.221 | 8,844 (5,227) / 2,906 |
| `github-2026-10-22` | gpt-6.1-sol | complete | 1 | 1 | 0, 0 | 41.314 | 8,485 (5,291) / 2,968 |

All six first attempts, uploaded to Blob `extracted/sealed/<case_id>/`, hashes in [`seals.json`](../../eval/sealed/seals.json) under `library: true`. A seventh `seal run` on `cloudflare-2026-10-20` was refused before any cloud call: `SealRefused: cloudflare-2026-10-20 is already sealed on gpt-6-luna`.

`seals.json` committed as `974febf`, pushed 18:49:12 UTC (workstation clock); GitHub's check runs started 18:49:21Z. `test_committed_seal_record_only_grows` passes.

## Third seals: two GitHub outages of 2026-11-04

Two major GitHub incidents of 2026-11-04 met the [sealing rules](../runbooks/sealing.md#choose-the-outages). Each resolved update is the same 180-character placeholder; neither has a postmortem update.

| Case | Incident | Title | Start | Resolved |
|---|---|---|---|---|
| `github-2026-11-04-pull-requests` | `smtdswd1h2w4` | Incident with Pull Requests, Git Operations and Issues | 09:49:55Z | 11:50:06Z |
| `github-2026-11-04-actions` | `xr3myzj7ms51` | Incident with Actions and Pages | 16:05:31Z | 17:01:11Z |

Search service recreated from `infra/search.bicep` (16:38:56Z to 16:39:38Z), library index rebuilt (267 chunks, 16:40:18Z to 16:42:38Z) per the [retrieval runbook](../runbooks/retrieval.md). Captured 17:18:11Z and 17:18:12Z, registered `sealed` (`42c308a`), uploaded, cut: 9 updates each, `dropped 0`.

Each seal: `python -m hindcast.seal run <case_id>` with `--env-file .env`, from `42c308a`, committed and clean, 17:19 to 17:22 UTC, on the second series' agent versions; each preflight search answered.

| Case | Deployment | Status | Searches | Library citations kept | Rejected, unsupported | Seconds | Tokens in (cached) / out |
|---|---|---|---|---|---|---|---|
| `github-2026-11-04-pull-requests` | gpt-6-luna | complete | 1 | 0 | 0, 0 | 32.316 | 7,731 (3,364) / 2,675 |
| `github-2026-11-04-actions` | gpt-6-luna | complete | 1 | 0 | 0, 0 | 27.175 | 6,794 (4,576) / 2,339 |
| `github-2026-11-04-pull-requests` | gpt-6.1-sol | complete | 1 | 2 | 0, 0 | 50.653 | 7,476 (3,364) / 2,607 |
| `github-2026-11-04-actions` | gpt-6.1-sol | complete | 1 | 2 | 0, 0 | 42.111 | 7,090 (4,576) / 2,004 |

All four first attempts, no withheld item, no PII hit, uploaded to Blob `extracted/sealed/<case_id>/`, hashes in [`seals.json`](../../eval/sealed/seals.json) under `library: true`. A repeat `seal run` (`github-2026-11-04-actions` on gpt-6-luna, `github-2026-11-04-pull-requests` on gpt-6.1-sol) was refused before any cloud call: `SealRefused: <case_id> is already sealed on <deployment>`.

`seals.json` committed as `f571a41`, pushed 17:23:18 UTC (workstation clock); GitHub's check runs started 17:23:25Z. Library snapshots 17:23:36Z and 17:23:39Z: 267 chunks each, in [`library-snapshots.json`](../../eval/sealed/library-snapshots.json). Search service deleted 17:41:08Z.

Open issues naming a sealed case in their trigger:

- [#42](https://github.com/sindredg/hindcast/issues/42), the day bound: the newest library document is dated 2026-07-08, 119 days before either case.
- [#37](https://github.com/sindredg/hindcast/issues/37), an upload that succeeds but reports an error: due before these seals, not made; all four uploads reported success.
- [#63](https://github.com/sindredg/hindcast/issues/63), no history test for the snapshot record: due before these snapshots, not made; the commit adds two entries and changes no earlier line.

Both fixed before any further seal: `seal upload` records an existing blob only when its bytes match the hash (`test_upload_completes_when_an_earlier_upload_reached_the_service`); the snapshot record's history is walked like the seal record's (`test_committed_snapshot_record_only_grows`, `test_snapshot_history_with_a_changed_hash_is_a_problem`). Each test failed with its check broken.

## Reveal: github-2026-11-04-actions (2026-11-07)

GitHub wrote its cause into the resolved update at 2026-11-07T01:04:38Z: 249 words naming a configuration change to an internal event-routing service that paused several event streams; on 2026-11-04 it was the 31-word placeholder. The other four cases still had no cause; they follow as addenda ([decision 0030](../decisions/0030-close-evaluation-with-sealed-addenda.md)).

Steps from the [sealing runbook](../runbooks/sealing.md#reveal-a-seal), locally, in decision 0022's order:

| Step | Command | Result |
|---|---|---|
| Capture | `hindcast.capture status --provider GitHub --incident xr3myzj7ms51` | `retrieved_at: "2026-11-07T10:22:42Z"`, `sha256: 76af8617…`, registered as `github-summary-2026-11-04-actions`, role `revealed` |
| Key | `hindcast.keys check github-2026-11-04-actions` | `0 problems`; approved by a person, frozen 10:27:30Z, `4d3d4633…` |
| Labels | `hindcast.labels freeze github-2026-11-04-actions` | 1 stated, 10 not inferable; approved by a person, `57274146…` |
| Leak check | `hindcast.leak github-2026-11-04-actions --snapshot build/sealed-library/github-2026-11-04-actions.json` | `14 unstated items, 8 evidence sources, 267 library chunks, 0 hits`; with `--plant`, `root_cause in planted: 15 shared 8-word runs` |
| Reveal | `hindcast.reveal github-2026-11-04-actions`, 10:30:54Z | `cause published 2026-11-07T01:04:38Z`, `revealed 2 files`; `tests/test_sealed_reveal.py` 2 passed (4 after the record check) |
| Judge | `hindcast.evaluation.judge run --root eval/reconstruction/sealed-v1`, 10:40:31Z to 10:41:00Z | `judged 2, errors 0, kept 0` |
| Reviewer | `hindcast.evaluation.reviewer run` and `apply`, `--root eval/reconstruction/sealed-v1`, 10:41:07Z to 10:42:00Z | `judged 2, errors 0`; `runs 2, decisions 22, missing 0` |
| Score | `hindcast.evaluation.score --root eval/reconstruction/sealed-v1` | `runs 2, open review items 0`; both runs 1.00 |
| Spend | `hindcast.evaluation.spend --sealed` | judge USD 0.17, reviewer USD 0.56, total USD 0.73 |

The reveal ran at 10:30:54Z from an uncommitted tree on `e12c856`; the reveal code, role change, key, and labels were committed at 10:34:54Z with its output (`e8dbfc0` to `dfdd563`), so runbook step 18 was skipped. That the key and labels were fixed before the seals opened rests on the code's order and the hashes in `reveals.json`, not the history. The reveal now refuses an uncommitted tree and records its commit (`17c864f`). Judge and reviewer ran from `ce12ac8`, clean. Results: [sealed report](../../eval/reconstruction/sealed-v1/README.md).

The first judge call was refused: `NotFrozen: the judge prompt, the rubric, or the settings differ from eval/judge/frozen.json`; the lock names rubric version 2, and version 3 changed the system prompt's title line ([troubleshooting](../troubleshooting.md#evaluation-the-judge-refuses-a-later-run-after-the-rubric-moved-to-version-3-2026-11-07)). The judge now rebuilds the locked system prompt from the history; both runs were judged with the showcase runs' prompt (`9de219e1…`).

The postmortem capture is local and in the registry, not in Blob Storage: the reveal runs offline (decision 0022).

### Checks

Each failed once on a broken input, 2026-11-07, locally:

| Broken input | Failed tests or refusal |
|---|---|
| One word changed in a hand-drafted key's quote | `keys.check_draft`: `contributing_factors[0]: quote not found word for word in the postmortem` |
| One byte changed in the captured postmortem | `keys.check_draft`: `differs from its registry hash` |
| Placeholder floor set to 0 | `test_statuspage_summary_refuses_the_placeholder` |
| Publication-time refusal removed from the reveal | `test_each_broken_step_refuses_before_anything_is_written[early-…]` |
| Leak refusal removed from the reveal | `test_each_broken_step_refuses_before_anything_is_written[leak-…]` |
| The sealed tree's loader sets a run ID even when the file names one | `test_the_sealed_tree_reads_revealed_files_by_hash_alone` |
| The rebuilt judge record not compared with the lock | `test_the_locked_system_prompt_is_rebuilt_from_the_locked_rubric` |
| `revealed` left out of the whole-library roles | `test_revealed_case_keeps_the_whole_library` |
| Revealed refusal removed from `check_case_allowed` | `test_investigate_refuses_a_revealed_case` |
| The rubric lock check ignores added entries | `test_the_lock_check_fails_on_a_changed_or_unrevealed_entry` |
| After the review: the reveal's registry-hash refusal removed | `test_each_broken_step_refuses_before_anything_is_written[registry-…]` |
| After the review: the reveal's target-exists refusal removed | `test_each_broken_step_refuses_before_anything_is_written[target-…]` |
| After the review: `<=` made `<` in the publication-time check | `test_each_broken_step_refuses_before_anything_is_written[boundary-…]` |
| After the review: the reveal's clean-tree check removed | `test_a_ready_case_is_revealed_and_recorded`, `test_each_broken_step_refuses_before_anything_is_written[dirty-…]` |
| After the review: the no-resolved-update refusal removed | `test_the_publication_time_comes_from_the_captured_file` |
| After the review: a revealed role without a reveal record not reported | `test_the_record_check_fails_on_each_broken_record` |
| After the review: a key or labels file that differs from its reveal record not reported | `test_the_record_check_fails_on_each_broken_record` |

`test_each_broken_step_refuses_before_anything_is_written` also covers a wrong role, a changed key, missing labels, changed evidence, a changed snapshot, and a changed sealed file, each with nothing written. Removing the judge's separate system-hash comparison left every test passing (the rebuilt record holds that hash), so it was removed as redundant.

Test suite: `uv run --frozen pytest -q` → 1004 passed, locally with the captured sources present; ruff, ruff format, and pyright clean. After the review's fixes: 1009 passed.

### Issues

Closed: [#34](https://github.com/sindredg/hindcast/issues/34) (`revealed` role), [#35](https://github.com/sindredg/hindcast/issues/35) (publication time), [#36](https://github.com/sindredg/hindcast/issues/36) (placeholder refusal). Opened: [#99](https://github.com/sindredg/hindcast/issues/99), a timeline hit the 30-minute tolerance credits on a `not inferable` event.

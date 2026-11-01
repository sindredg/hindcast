# Milestone 5, first part: Sealed reconstructions and the October case

Status: Built on 2026-11-01. Three October outages are sealed on both models, and GitHub 2026-10-07 is a fourth scored case with its evidence, prior-knowledge answers, library picks, and frozen key. The [independent review](#independent-review) is open. The milestone state is in the [roadmap](../roadmap.md).

## Scope

Two answers to "could the model have known the answer?" that do not rest on a vendor's training cutoff ([decision 0017](../decisions/0017-sealed-reconstructions.md)):

- **Sealed reconstructions.** Outages whose provider had not published a cause are reconstructed now, and only the SHA-256 of each result is public until the provider's account is out. They are scored after the rubric is frozen, against the postmortem, if one is published by 2026-11-09.
- **An after-release case.** GitHub's outage of 2026-10-07 began after both pinned model versions were released (gpt-6-luna 2026-09-22, gpt-6.1-sol 2026-09-29), so neither version can have seen it. It joins the three showcase cases under the same rules.

The procedure is the [sealing runbook](../runbooks/sealing.md).

## Work completed

### Sealed cases and the seal command

- `hindcast.cases` accepts the role `sealed`, which needs only status updates. `hindcast.investigate` refuses a sealed case at any time, so every sealed run goes through `python -m hindcast.seal`.
- `hindcast.seal run <case_id>` refuses a case that is not sealed, a second seal for the same case, deployment, and library setting, and a changed `src/`, `prompts/`, `pyproject.toml`, `uv.lock`, or `data/cases.yaml`, all before any cloud call. It writes the result under `build/sealed/` (ignored by Git), records the entry in `eval/sealed/seals.json` with the hash and `blob: null`, then uploads the file to Blob `extracted/sealed/<case_id>/` without overwriting and records the blob. A failed upload leaves the hash recorded; `seal upload` sends the same bytes after checking them against it.
- An attempt in which the model produced no output (the run raised, or the result has zero output tokens) is recorded as `no-result` and may be retried, up to three attempts. Any result with model output is final.
- The command prints counts, usage, and the hash. For an incomplete run it prints only the reason's kind before the first colon, since a schema error echoes the rejected value and a tool error echoes the model's arguments.
- `tests/test_sealed_reveal.py` checks every entry marked `revealed` against the file under `eval/investigations/<case_id>/`.

### Several status incidents per case

- `hindcast.evidence.cut_all` cuts each status snapshot with the [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) rules and merges the updates by time, numbered again. Each incident keeps its own resolved mark with the text withheld, so a recurrence's updates are not dropped as "after resolved". `hindcast.ingest evidence` downloads every status source of a case.
- The cut's start is the earlier of Statuspage's `started_at` and the first update: GitHub backfilled `started_at` of incident `djlmxz2zd0j7` with its resolved time (16:25:14Z), after its first update (15:14:45Z). The registry test reran on every local snapshot and the existing cases' starts did not move.
- The investigator prompt (now v2) and the `list_updates` note say each incident ends at its resolved update. The luna agent got version 2 on the first seal.

### Agent names

Foundry agent names take letters, digits, and inner hyphens. `hindcast-investigator-gpt-6.1-sol` was refused (`invalid_parameters`) on the first sol seal, before any model call, so nothing was recorded. `agent_name` now replaces any other character with a hyphen: `hindcast-investigator-gpt-6-1-sol`.

### Keys from a status-page summary

GitHub writes its summary of the cause into the resolved update. `hindcast.keys.statuspage_summary` reads that update from a status snapshot as the postmortem, and `postmortem_page` picks it for a `.json` postmortem source, for drafting and for the quote test.

## Checks

Every new check was run once against a broken input on 2026-11-01, locally, and failed:

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
| A pick reason without the case's tagged quote | `test_the_committed_library_loads_with_every_hash_pinned` (the library loader refuses it) |

Test suite after the slice: `uv run --frozen pytest -q` → 347 passed, locally with the captured sources present.

## Live run

On 2026-11-01, against the live project and storage account.

### Choosing the outages

At about 08:07 UTC the three status feeds were read. GitHub `nms1dpzmh9d9` (2026-10-21), GitHub `wq8305lppdc2` (2026-10-22), and Cloudflare `0eqtn0khkz87` (2026-10-20) had no cause in their resolved updates. Five other October GitHub incidents with eight or more updates already carried GitHub's summary of the cause, 2026-10-07 among them, and Google Cloud's europe-west2 incident of 2026-10-20 carried its incident report. None of the sealed outages harmed people, leaked data, or named an attacker.

| Step | Command | Result |
|---|---|---|
| Capture | `capture status` per incident | 08:15:51 to 08:15:52Z; hashes in `data/cases.yaml` |
| Evidence | `ingest evidence --case <id>` | `cloudflare-2026-10-20` 9 updates, `github-2026-10-21` 15, `github-2026-10-22` 18, each including the resolved mark; none dropped; `blob: uploaded` |
| Seal, gpt-6-luna | `seal run <id>` | three `complete` results, 0 rejected citations, 0 unsupported, agent version 2; 2 model calls and 2 tool calls each |
| Seal, gpt-6.1-sol | `HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol seal run <id>` | first try refused by Foundry on the agent name, before any model call; after the fix, three `complete` results, 0 rejected, 0 unsupported, agent version 1 |
| Second seal | `seal run cloudflare-2026-10-20` | `SealRefused: cloudflare-2026-10-20 is already sealed on gpt-6-luna` |
| Publish | push of `a372f32` to the pull request branch | 2026-11-01T08:21:55Z; CI green on that commit |

The six hashes, times, and commits are in [`eval/sealed/seals.json`](../../eval/sealed/seals.json). The files were not opened.

### The October case

| Step | Command | Result |
|---|---|---|
| Capture | `capture status` for `djlmxz2zd0j7`, `qpfv5p86dmrl`, and `djlmxz2zd0j7` again as the postmortem | 08:26:24 to 08:26:25Z; the summary capture has the same SHA-256 as the first incident's |
| Evidence | `ingest evidence --case github-2026-10-07` | 25 updates: 19 and 4 before the two resolved marks (16:25:14Z and 18:04:49Z); none dropped; start 15:14:45Z |
| Prior knowledge | `evaluation.prior collect --deployment <d>` | `prior-2026-11-01-gpt-6-luna.json`: 4 entries, 619 input and 3811 output tokens; `prior-2026-11-01-gpt-6.1-sol.json`: 4 entries, 619 input and 1955 output tokens. Committed unread |
| Symptom tags | `data/library.yaml` | seven tags quoted from the evidence, committed (`9fbb1e1`) before any pick |
| Key draft | Content Understanding Contributor assigned (extraction runbook step 1); `keys draft --case github-2026-10-07` | 1 page; 3 factors, 5 timeline events, 6 fixes, 2 problems (two quotes not word for word) |
| Key review | each field against the summary and the 25 updates, then a second, independent pass | corrections: two quotes made exact; attack basis `implied` with the quote it rests on; the four outage start and end times marked as stated during the incident (u6 and u22 give both windows); a factor that restated the root cause dropped; a pause between the two outages moved out of the fixes; the machine's removal added as a fix; the root-cause quote extended to cover the routing change |
| Freeze | `keys freeze github-2026-10-07` | `sha256 86ba420c112567208ac33c08717839cb3a62b56ffe07343e1e102a0c5a0a20d1`; every quote found word for word in the summary |
| Role removed | extraction runbook steps 19 and 20 | removed at 09:01:14Z; the next Content Understanding read, at 09:03:05Z, was refused with `PermissionDenied` |
| Library picks | [decision 0013](../decisions/0013-library-selection.md) rule, existing documents only | same-provider `github-availability-2023-11`, `github-availability-2026-06`; other-provider `google-cloud-2025-06-12`, `aws-2021-12-07`; attack-suspected `github-2018-02-28` (DDoS confirmed), `github-2016-01-28` (attack ruled out); decoy `cloudflare-2023-11-02` |

Three documents in the library were not picked for this case because their causes sit close to its cause, which would make the library easier (rule 5): `github-availability-2023-09` (a primary database's write error), `github-2018-10-21` (a database failover after a network partition), and `google-cloud-2020-12-14` (leftover records after a migration, and a consensus leader that could not write). `github-availability-2026-06` stays a same-provider pick for its June 25 incident; as a monthly report it is one document (rule 7), so its June 17 incident, a configuration the system judged invalid and replaced with the previous one, comes with it.

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| A sealed result is unchanged between sealing and scoring (milestone 5, sealed cases) | configured, not tested | the hashes are in [`seals.json`](../../eval/sealed/seals.json), pushed at 08:21:55Z; `tests/test_sealed_reveal.py` fails on a changed file (Checks table). No file is revealed yet, so the check has not run against a real one |
| A sealed run is refused when it would break the rules | tested, locally and live | `tests/test_seal.py` (Checks table); live: the second `seal run` on a sealed case was refused before any cloud call |
| A recurrence's updates are evidence, with each resolved text withheld | tested, locally and live | `test_two_incidents_merge_in_time_order`, `test_ingest_cuts_every_status_source_of_a_case`; live: 25 updates, two resolved marks without text |
| The prior-knowledge answers for GitHub 2026-10-07 are recorded before any evidence reaches a model | tested, live | both result files written at 2026-11-01 before any investigator or extraction call on the case; committed unread |
| The October key is reviewed and frozen | accepted gap | every field checked against the summary in two independent passes and every quote verified word for word in code; the corrections above are not yet approved one by one, as for the four earlier keys ([keys gate](02-extraction.md#gate)) |
| Each new check fails on a broken input | tested | the Checks table |

## Independent review

Open: runs before the pull request leaves draft.

## Issues opened

None yet.

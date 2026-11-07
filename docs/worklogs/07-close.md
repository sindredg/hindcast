# Worklog 07: Close

Status: Verified on 2026-11-07 ([gate](#gate), [independent review](#independent-review)). Milestone state: [roadmap](../roadmap.md#status).

Scope: [milestone 7](../roadmap.md#7-close). Procedure: the [teardown runbook](../runbooks/teardown.md); runbook order: the [reproduce page](../reproduce.md).

On this page: [Before the teardown](#before-the-teardown) · [Teardown](#teardown) · [Issues](#issues) · [Staleness pass](#staleness-pass) · [Gate](#gate) · [Independent review](#independent-review)

## Before the teardown

| Check | How | Result |
| --- | --- | --- |
| Sealed copies match their hashes | Teardown step 1, 2026-11-07: every `eval/sealed/seals.json` entry hashed under `build/sealed/` and in `~/backups/hindcast/sealed-20261104T1723Z.tgz` | Tested: `16 of 16 match local and backup`. Broken input: another file's hash matches no seal |
| Every blob has a local copy | Teardown step 2, 2026-11-07: both containers downloaded and compared by hash with `data/sources/` and `build/` | Tested: 39 and 57 blobs, 96 files, 6.9 MB; 91 matched, 0 differed, 5 (`extracted/keys/*-result.json`) kept by the download alone |
| Every frozen key passes the leak check offline | `python -m hindcast.leak <case> --snapshot build/sealed-library/github-2026-11-04-actions.json` per keyed case, 2026-11-07, after [#83](https://github.com/sindredg/hindcast/issues/83)'s short-item rule | Tested: 0 hits for all six (17, 17, 8, 11, 9, and 14 unstated items against 143, 74, 79, 44, 88, and 267 chunks). Broken input: `--plant` on `cloudflare-2025-11-18` reports `root_cause in planted: 20 shared runs`, exit 0; `test_a_key_item_shorter_than_a_run_is_matched_whole` fails on the old rule |

## Teardown

[Teardown runbook](../runbooks/teardown.md) steps 4 to 9 ran on 2026-11-07 after steps 1 and 2 above. Step 3 (the agents) went with the Foundry resource in step 6 and the registrations in step 8. Times are UTC.

| Step | Ran | Observed |
| --- | --- | --- |
| 4. Custom role | by 12:29 | Assignment and definition deleted; `az role definition list --custom-role-only true` empty |
| 5. Developer's assignments | 12:29:30 | Three deleted by ID (Foundry User on the project, Storage Blob Data Contributor, Cognitive Services OpenAI User); the group's list empty |
| 6. Workspace and group | 12:30:34, 12:32:45 | Workspace force-deleted; group deleted in 2m11s; `az group exists` `false` |
| 7. Purge | 12:34:51 | Foundry resource purged; `list-deleted` showed no account and no workspace of the project's |
| 8. Registrations | 12:35:04 to 12:35:39 | `hindcast-app` deleted; six `AgentIdentityBlueprint` registrations left after the purge, listed and deleted by ID; final list empty |
| 9. Final check | 12:35:50 | No resource named after the project, no custom role, no assignment to an unknown principal; only `NetworkWatcherRG` left |
| 10. GitHub secrets | 2026-11-07 | The `azure` environment's four secrets deleted; `gh secret list --env azure` printed `no secrets found` |

The same queries at 11:40 that day listed the group, the custom role, four assignments, and eleven registrations.

## Issues

Every open issue on 2026-11-07, with its verdict. Fixes are in this milestone's pull request; each code fix has a test shown failing on the old code; #52 and #66 are documentation.

| Issue | Verdict | Why |
| --- | --- | --- |
| [#1](https://github.com/sindredg/hindcast/issues/1) actionlint lags the runner labels | Closed | No newer release on 2026-11-07 (v1.7.12, last commit 2026-04-19); the declaration in `.github/actionlint.yaml` stays |
| [#4](https://github.com/sindredg/hindcast/issues/4) requested reasoning effort recorded | Closed | Limit stated in the [prior-knowledge report](../../eval/prior-knowledge/v1/README.md#limits); both collections requested the same effort |
| [#12](https://github.com/sindredg/hindcast/issues/12) draft check accepts a time not in UTC | Fixed | A time with a zone is converted and compared |
| [#14](https://github.com/sindredg/hindcast/issues/14) reused extracts not checked against the registry | Closed | No further capture or extraction runs; the reveal is offline (decision 0022) |
| [#17](https://github.com/sindredg/hindcast/issues/17) chart evidence carries no attribution | Closed | The page shows each chart's attribution and licence from the registry (`_chart_credit` in `hindcast.app`) |
| [#19](https://github.com/sindredg/hindcast/issues/19) add an attack case | Closed | None added; the [keys README](../../eval/keys/README.md#limits) says attack detection is not measured |
| [#42](https://github.com/sindredg/hindcast/issues/42) library day bound assumes UTC days | Closed | Sealing stopped on 2026-11-05; no document within a day of a case's start (40 days at the closest) |
| [#44](https://github.com/sindredg/hindcast/issues/44) seal history test fails on a merge of two seal branches | Closed | The `main` ruleset admits only squash and rebase merges; sealing stopped |
| [#48](https://github.com/sindredg/hindcast/issues/48) sealed result keeps the raw SDK message | Fixed | The reveal refuses a tool-error reason naming a host, address, URL, or ID; the sealed ledger keeps the kind only |
| [#50](https://github.com/sindredg/hindcast/issues/50) screens split a long text without overlap | Open, limit | [dev-v1](../../eval/injection/dev-v1/README.md) ran under this rule; a change goes with new injection runs |
| [#52](https://github.com/sindredg/hindcast/issues/52) no cost line for search queries | Fixed | Trigger fired with the Cost Management read of 2026-11-07; the [price table](../../data/prices.yaml) says why the line is left out |
| [#66](https://github.com/sindredg/hindcast/issues/66) a stated label on the resolved update's time | Fixed | The [labels README](../../eval/keys/labels/README.md) says the resolved update's time and status count as stated |
| [#69](https://github.com/sindredg/hindcast/issues/69) injection copies show "inject" in their refs | Open, limit | A fix reruns all 16 injection runs; the report states the limit |
| [#71](https://github.com/sindredg/hindcast/issues/71) abstention credit with an unsupported root cause | Open, limit | A rubric change is a new version with new runs; the report lists the case |
| [#72](https://github.com/sindredg/hindcast/issues/72) a partial on a not-inferable factor lowers the score | Open, limit | Same |
| [#82](https://github.com/sindredg/hindcast/issues/82) injection check misses a canary in a rejected citation | Open, limit | A wider match changes what a pass means; goes with new injection runs |
| [#83](https://github.com/sindredg/hindcast/issues/83) leak check misses items under 8 words | Fixed | A short item is matched whole; every key checked again offline (above) |
| [#84](https://github.com/sindredg/hindcast/issues/84) per-arm failure count double counts | Open, limit | No scored result changes (no failed attempt in the ledger); fix with a regenerated report |
| [#88](https://github.com/sindredg/hindcast/issues/88) require SHA-pinned actions in the settings | Fixed | `sha_pinning_required` set `true` on 2026-11-07 through `PUT /repos/{owner}/{repo}/actions/permissions`; read back `true` |
| [#90](https://github.com/sindredg/hindcast/issues/90) root cause names finding IDs first | Closed | A page-order question; no further page change planned |
| [#91](https://github.com/sindredg/hindcast/issues/91) redo the November pin batch | Closed | Landed in [#97](https://github.com/sindredg/hindcast/pull/97) |
| [#99](https://github.com/sindredg/hindcast/issues/99) timeline tolerance credits an announcement | Open, limit | A rubric change is a new version; the sealed report states it |
| [#102](https://github.com/sindredg/hindcast/issues/102) reveal's publication time is the last edit | Fixed | The reveal also checks the sealing-day capture: before every seal, resolved text under the placeholder floor, different from the postmortem's |
| [#103](https://github.com/sindredg/hindcast/issues/103) `keys draft` without `--case` | Fixed | `--case` required; a non-showcase case refused |
| [#104](https://github.com/sindredg/hindcast/issues/104) scoring commands compare `--root` as written | Fixed | Both sides resolved |

## Staleness pass

A read-only pass compared each state-carrying sentence in every tracked page with the code, the registries, the workflow, and the close: 78 items. Among them present-tense claims about removed resources, "planned" wording overtaken by the milestones, a diagram label and three definitions without the `revealed` role, CI job names that differed from the workflow, two counts, and one defect: since the registry was removed on 2026-11-06, `Push the image` failed on every push to `main` (runs for `e12c856`, `e2000d7`, and `9d13be7` on 2026-11-07: `AADSTS700016`). The job is now gated on the repository variable `HINDCAST_PUSH_IMAGE`, set in deployment runbook step 6 and removed in step 18. Finding entries keep their dated text ([findings README](../findings/README.md)), except two whose "For Hindcast" line contradicted the code. Every relative link and anchor resolves (0 bad on 2026-11-07).

| Check | How | Result |
| --- | --- | --- |
| The retrieval diagram's label and alt text name both whole-library roles | `docs/diagrams/retrieval.html` against `hindcast.search.WHOLE_LIBRARY_ROLES`; `self_check.py`, `verify-geometry.py`, the rendered PNG | Tested: `OK`, 0 findings, the label fits its box |
| The workflow still lints after the gate | `yamllint .github/workflows/ci.yml`; `zizmor .github/workflows/ci.yml` | Tested: no findings |
| The push job is skipped without the variable | The next push to `main` | Configured, not tested: the variable is unset, so the job's `if` is false |

## Gate

| Criterion | Status | Evidence |
| --- | --- | --- |
| Everything built by hand is removed and nothing is left | Tested | [Teardown](#teardown): step 9 printed three empty results at 12:35:50Z; the same queries listed the resources before |
| The sealed copies and every blob were checked before the storage went | Tested | [Before the teardown](#before-the-teardown) |
| Every open issue has a verdict | Tested | [Issues](#issues): `gh issue list --state open` listed 25 on 2026-11-07, each with a row. Nine closes land with the merge, eight reasoned closes after it. #88 closed by the setting |
| A reproduce page orders the runbooks | Written | [reproduce](../reproduce.md); not tested from a fork, and the page says so |
| Every state-carrying page matches the code and the close | Tested | [Staleness pass](#staleness-pass) |
| An independent review of the close ran with its fixes in | Tested | [Independent review](#independent-review): eleven fix-now items, each fixed in this pull request |

## Independent review

A read-only review from a fresh context read the close pages and the nine fixes against the code, the registries, the workflow, and the live issue list on 2026-11-07, and ran the new tests against `main`'s code.

| Finding | Checked | Outcome |
| --- | --- | --- |
| Pages said the hand-built resources were removed while the teardown was pending | The teardown ran the same day ([Teardown](#teardown)) | Fixed by the run |
| The "every open issue has a verdict" row cited a list not yet observed | `gh issue list --state open` listed 25 | Fixed: the row says what was read and when |
| The written-time check flagged a frozen key: `github-2026-08-17` timeline[1], "13:40 UTC, lasting 7 hours and 35 minutes", a derived end time | `time_problems` on every frozen key | Fixed: a text with a duration or two clocks is not compared; `test_every_frozen_key_passes_the_written_time_check` |
| The extraction runbook's draft step had no `--case` | `docs/runbooks/extraction.md` step 15 | Fixed: one `--case` per showcase and development case |
| The reproduce page's row 3 said investigator steps 1 to 3 run the first investigation; they are the evidence check, the role, and its check | `docs/runbooks/investigator.md` | Fixed |
| The issues intro claimed a failing test for every fix; #52 and #66 are documentation | The commits | Fixed |
| Three link counts disagreed | Three scripts, 0 bad each | Fixed: the number is dropped, "0 bad" stays |
| The prior report said the live call showed the service reports the requested effort; it showed the response reports an effort when none was sent | Issue #4 | Fixed |
| Teardown step 4 would delete every assignment in the subscription when the role is not found (`ends_with(x, '')` is true) | JMESPath semantics | Fixed: `test -n "$RID"` guards the line, here and in deployment runbook step 16; step 5 filters on `/resourceGroups/<name>/` |
| Teardown step 8 deleted every agent-identity registration in the tenant | The query | Fixed: the resource's name prefix, listed before deleting, with `--all` |
| `#104` had no test that fails on `main` on its own | The tests against `main` | Fixed: `test_an_absolute_sealed_root_still_reads_revealed_files` |

Plan only:

- The sealed ledger stores the kind of an incomplete reason; the showcase ledger stores the whole reason (no reader broke; 1061 tests).
- The reveal's postmortem-text comparison runs only when the capture is a status snapshot; a blog postmortem gets the floor check alone.
- The written-time check reads 24-hour clocks only.
- A whole-item match on a two- or three-word key item can hit a common phrase (more hits, never fewer).
- The GitHub `azure` environment's secrets named removed resources; the teardown runbook got step 10.

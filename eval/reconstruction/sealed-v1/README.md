# Reconstruction evaluation, sealed v1

The revealed sealed reconstructions: made before the provider published a cause, committed by hash, opened after the cause was published and the key and labels were frozen ([decisions 0017](../../../docs/decisions/0017-sealed-reconstructions.md), [0022](../../../docs/decisions/0022-sealed-drop-date-and-offline-reveal.md), and [0030](../../../docs/decisions/0030-close-evaluation-with-sealed-addenda.md)). Scored by the same judge, reviewer, and [rubric](../../rubric/rubric.md), version 3, as the [showcase runs](../showcase-v1/README.md), and reported apart.

On this page: [How to read this result](#how-to-read-this-result) · [Status](#status) · [Results](#results) · [Error analysis](#error-analysis) · [Cost and spend](#cost-and-spend) · [Dataset](#dataset) · [Addendum, 2026-11-15](#addendum-2026-11-15-two-github-cases) · [Addendum, 2026-11-24](#addendum-2026-11-24-github-2026-10-22) · [Pending cases](#pending-cases) · [Limits](#limits) · [Files](#files)

## How to read this result

**No run found a cause the evidence did not hold, and no run guessed one. Where the updates said nothing about the cause, the runs scored 1.00 by saying so. Where one update hinted at it, they scored 0.60: half the cause, and no verdict on whether it was an attack.**

A sealed reconstruction is an investigation whose hash was committed before the provider published its cause. Revealing the file later and checking its hash shows that the answer was not changed after publication. Four outages are revealed, with twelve runs between them.

| Case | Revealed | Runs | Primary score, every run |
|---|---|---|---|
| `github-2026-11-04-actions` | 2026-11-07 | 2 | 1.00 |
| `github-2026-11-04-pull-requests` | 2026-11-15 ([addendum](#addendum-2026-11-15-two-github-cases)) | 2 | 1.00 |
| `github-2026-10-21` | 2026-11-15 (same addendum) | 4 | 0.60 |
| `github-2026-10-22` | 2026-11-24 ([addendum](#addendum-2026-11-24-github-2026-10-22)) | 4 | 1.00 |

The sections up to the addenda describe the first reveal as it stood on 2026-11-07.

In the first reveal, each run earned full credit on four scorable answer-key items: two supported matches and two justified abstentions. Seven other items were excluded because they were not inferable from the available evidence and the runs did not state them. The timeline matching also has a known limitation, explained in [error analysis](#error-analysis).

This tests whether the models can stay within the evidence before the official answer exists. It does not establish which model is better, and it cannot compare the agent with the simpler workflow because no single-search baseline was run for this case. See the [showcase explanation](../showcase-v1/README.md#what-the-score-means) for how credit and exclusions work.

## Status

- **Revealed, verified on 2026-11-07:** `github-2026-11-04-actions`, both seals.
- **Revealed, verified on 2026-11-15:** `github-2026-11-04-pull-requests` (two seals) and `github-2026-10-21` (four seals); evidence in the [addendum](#addendum-2026-11-15-two-github-cases).
- **Revealed, verified on 2026-11-24:** `github-2026-10-22` (four seals); evidence in the [addendum](#addendum-2026-11-24-github-2026-10-22). One sealed case has no published cause and is dropped on 2026-11-30 unless one appears ([pending cases](#pending-cases)).
- **Frozen before the reveal:** key at 10:27:30Z (SHA-256 `4d3d4633…`), labels right after (`57274146…`), both approved by a person; leak check against the library snapshot at 10:27:51Z.
- **Reveal, verified on 2026-11-07:** `python -m hindcast.reveal github-2026-11-04-actions` at 10:30:54Z; both files match their seals (`tests/test_sealed_reveal.py`, 4 passed). Run from an uncommitted tree; key, labels, and code committed minutes later ([worklog 05](../../../docs/worklogs/05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07)).
- **Judge and reviewer, verified on 2026-11-07:** judged 10:40:31Z to 10:41:00Z, reviewed 10:41:07Z to 10:42:00Z, from commit `ce12ac8`, no error; decisions applied at 10:42:01Z.
- **Scores, verified on 2026-11-07:** `python -m hindcast.evaluation.score --root eval/reconstruction/sealed-v1` wrote [`scores.json`](scores.json), no open review item.

## Results

Both models scored 1.00 on the one revealed case, on four scorable items. The score says the runs stayed inside the evidence, not that they found the cause: the evidence did not hold it.

- **The cause was not in the evidence, and neither run guessed it.** GitHub's summary names a configuration change to an internal event-routing service that paused several event streams. The updates say only that "an issue with events that might trigger Actions" was found (u5). Both runs named that issue as the best-supported proximate cause, said the mechanism was not disclosed, and listed it as an open question: justified abstentions on both root causes and both attack verdicts.
- **No unsupported item, no guess, nothing wrong.** 10 supported items outside the key for `gpt-6-luna`, 9 for `gpt-6.1-sol`.
- **The misses are all items the evidence cannot reach.** Three contributing factors (feature flags, how the service handled them, a rollback that left the code change in place) and four timeline events are `not inferable`; missing them is neutral. Three of the events happened after the resolved update at 17:01, the evidence's last item.
- **The two models are equal here, and the cheaper one is faster.** Same outcomes on every key item; `gpt-6-luna` 27 seconds and USD 0.031, `gpt-6.1-sol` 42 seconds and USD 0.058.

| Run | Deployment, version | Agent version | Primary | Scorable | Supported hits | Justified abstentions | Missed (all not inferable) | Unsupported, guesses, wrong |
|---|---|---|---|---|---|---|---|---|
| `sealed/github-2026-11-04-actions/gpt-6-luna/a1` | gpt-6-luna, 2026-09-22 | 3 | 1.00 | 4 | 2 | 2 | 7 | 0, 0, 0 |
| `sealed/github-2026-11-04-actions/gpt-6.1-sol/a1` | gpt-6.1-sol, 2026-09-29 | 2 | 1.00 | 4 | 2 | 2 | 7 | 0, 0, 0 |

Both seals ran from commit `42c308a` with the library search on (`library: true` in [`seals.json`](../../sealed/seals.json)) and `prompts/investigator.md` at blob `1d0911f4…`, the showcase `hindcast` and comparison prompt; the comparison model ran in the agent's place. Judge: prompt version 1 (`prompts/judge.md`, SHA-256 `afa416c0…`, system prompt `9de219e1…`). Reviewer: `prompts/reviewer.md` (`8ab121d8…`, system prompt `8d36cd06…`). `gpt-6.1-sol` kept two library citations; no claim rests on a library document alone.

### Judge and reviewer

The reviewer decided all 22 queue items (10 match, 12 support) and agreed with the judge on every one: 100 percent, Cohen's kappa 1.0 on the match decisions. Over every key item they agree on 21 of 22 match verdicts (95.5 percent, kappa 0.92) and all 31 support verdicts. The one disagreement is `timeline/0` on the `gpt-6.1-sol` run, outside the queue ([below](#a-timeline-hit-through-the-tolerance)). By the judge alone or the reviewer alone, both runs score 1.00.

## Error analysis

### A timeline hit through the tolerance

`timeline/1`, the rollback at 16:14, is `not inferable`: u5 at 16:34 says mitigations were applied, with no time and no rollback. Both runs list u5's event at 16:34; the judge matched it to the 16:14 rollback as "the same mitigation event, within 30 minutes", and the reviewer agreed. Without the hit, `timeline/1` is a neutral miss and each run scores 3 of 3. The 30-minute tolerance can match an announcement to the action it reports even when the label says the action's time is not in the evidence ([issue #99](https://github.com/sindredg/hindcast/issues/99)).

The one judge-reviewer disagreement is the same pattern. On the `gpt-6.1-sol` run, the judge marks `timeline/0` (delays began at 15:49, `not inferable`) `missed`: the run's first event, u1 at 16:05, is the incident opening, and the run says it is not the onset. The reviewer called it a supported hit, 16 minutes from 15:49. Outside the queue, so the judge's `missed` stands; the run scores 1.00 either way.

### What the score cannot show

A case whose cause is not inferable scores on abstentions and on the events the updates time. Two such items carry the score here, so the result is about restraint, not reconstruction. A sealed case whose updates hint at the cause would test more; decision 0017 forbids choosing seals by that.

## Cost and spend

| Part | Count | Cost at list prices, USD | Source |
|---|---|---|---|
| Sealed runs on Azure | 2 runs | 0.0891 | [`attempts.json`](attempts.json), price table version 1 (`data/prices.yaml`) |
| Judge (`claude-opus-5-5`) | 2 calls | 0.17 | [`spend.json`](spend.json) |
| Reviewer (`claude-fable-5-1`) | 2 calls | 0.56 | same |

Claude prices: version 1 of `data/claude-prices.yaml`, read on 2026-11-04 from the [pricing page](https://platform.claude.com/docs/en/about-claude/pricing). Claude API total for the reveal USD 0.73, no unpriced call, from `python -m hindcast.evaluation.spend --sealed`.

## Dataset

| Part | Where | Frozen |
|---|---|---|
| Evidence | `build/evidence/github-2026-11-04-actions.json`, cut from the snapshot captured at 2026-11-04T17:18:12Z | SHA-256 `c88d4716…`, recorded by both seals |
| Postmortem | GitHub's resolved update, captured at 2026-11-07T10:22:42Z as `github-summary-2026-11-04-actions` ([registry](../../../data/cases.yaml)); `updated_at` 2026-11-07T01:04:38Z | SHA-256 `76af8617…` |
| Key | [`eval/keys/github-2026-11-04-actions.json`](../../keys/github-2026-11-04-actions.json), drafted by hand from the summary; every quote checked with `python -m hindcast.keys check` | [`eval/keys/frozen.json`](../../keys/frozen.json) |
| Labels | [`eval/keys/labels/github-2026-11-04-actions.json`](../../keys/labels/github-2026-11-04-actions.json): 1 stated, 10 not inferable | [`eval/keys/labels/frozen.json`](../../keys/labels/frozen.json) |
| Library | The case's snapshot, 267 chunks, taken at 2026-11-04T17:23:39Z before the index was deleted | [`library-snapshots.json`](../../sealed/library-snapshots.json) |
| Reveal record | Publication time, hashes, leak check counts | [`reveals.json`](../../sealed/reveals.json) |

## Addendum, 2026-11-15: two GitHub cases

GitHub published both causes on 2026-11-13. Each case went through the [reveal procedure](../../../docs/runbooks/sealing.md#reveal-a-seal) on 2026-11-15, offline except the two captures and the Claude API calls.

### Status

- **Causes published after every seal.** `github-2026-11-04-pull-requests`: the resolved update, rewritten at 2026-11-13T16:48:58Z (seals of 2026-11-04). `github-2026-10-21`: GitHub's October availability report, which states 2026-11-13T00:20:16Z (seals of 2026-11-01 and 2026-11-02).
- **Frozen before the reveal, tested:** keys `fe7d5c64…` and `de282bbc…`, labels `c80e72cd…` and `4a1e49aa…`, committed in `f57a0cb`. `python -m hindcast.keys check` gave 0 problems for each; with one quote of the `github-2026-10-21` draft changed by a word it gave 1 problem and exit 1.
- **Leak check, tested:** 0 hits against each case's 267-chunk library snapshot; 1 hit each with `--plant`.
- **Reveal, tested:** `python -m hindcast.reveal` at 19:07:02Z and 19:07:20Z from committed trees (`f57a0cb`, `0b7bbee`); six files match their seals (`tests/test_sealed_reveal.py`).
- **Judge and reviewer, tested:** six runs judged and reviewed between 19:08Z and 19:18Z, no error; 86 queue decisions applied, none open. Four from commit `587e14d`, the two library-off runs from `f529676` after a ledger fix ([below](#two-runs-shared-a-run-id)).
- **Scores, tested:** `python -m hindcast.evaluation.score --root eval/reconstruction/sealed-v1` wrote [`scores.json`](scores.json) with 8 runs.

### Results

| Run | Library search | Agent version | Primary | Scorable | Supported hits | Partial | Justified abstentions | Unsupported, guesses, wrong |
|---|---|---|---|---|---|---|---|---|
| `sealed/github-2026-11-04-pull-requests/gpt-6-luna/a1` | on | 3 | 1.00 | 6 | 4 | 0 | 2 | 0, 0, 0 |
| `sealed/github-2026-11-04-pull-requests/gpt-6.1-sol/a1` | on | 2 | 1.00 | 6 | 4 | 0 | 2 | 0, 0, 0 |
| `sealed/github-2026-10-21/gpt-6-luna-library-off/a1` | off | 2 | 0.60 | 5 | 2 | 2 | 0 | 0, 0, 0 |
| `sealed/github-2026-10-21/gpt-6.1-sol-library-off/a1` | off | 1 | 0.60 | 5 | 2 | 2 | 0 | 0, 0, 0 |
| `sealed/github-2026-10-21/gpt-6-luna/a1` | on | 3 | 0.60 | 5 | 2 | 2 | 0 | 0, 0, 0 |
| `sealed/github-2026-10-21/gpt-6.1-sol/a1` | on | 2 | 0.60 | 5 | 2 | 2 | 0 | 0, 0, 0 |

Model versions are those of the first reveal: gpt-6-luna 2026-09-22 and gpt-6.1-sol 2026-09-29. The seals ran from commits `42c308a` (2026-11-04), `c6a26d0` and `3162dfe` (2026-11-01), and `5fd90c0` (2026-11-02), recorded per run in [`attempts.json`](attempts.json). Judge, reviewer, and rubric are those of the first reveal.

**`github-2026-11-04-pull-requests`: nothing about the cause in the updates, and both runs said so.** GitHub's summary names a shared database that reached capacity. No update mentions a database. Both runs said the cause could not be determined and gave no attack verdict: two justified abstentions each. All four timeline events were matched.

**`github-2026-10-21`: half the cause, from the one update that hinted at it.** The report says servers in the event streaming platform, close to their memory limits, were overloaded when failed requests made clients reconnect at once. Update u3 said only that "increased load on our event streaming platform is contributing to hotspots". All four runs named the overloaded platform and none named the trigger: `partial` on the root cause.

- **The library search changed nothing here.** The runs with and without it have the same outcome on every key item, on both models.
- **No run ruled out an attack, and the label says the evidence did.** The label marks "not an attack" `inferable` from u3: the load was on an internal platform. All four runs answered "cannot tell", which earns no credit on an inferable item.
- **No unsupported item, no guess, nothing wrong** in any of the six runs.

The reviewer agreed with the judge on all 86 queue items and on every key item of the six runs. Each run scores the same by the judge alone and by the reviewer alone.

### Error analysis

#### The onset matched through the tolerance again

`timeline/0` of the pull requests case, the onset at 09:35, is `not inferable`: the first update is at 09:49 and gives no start time. Both runs list that update, and the judge matched it as "within 30 minutes" and "the first report of the same event". Without the hit each run scores 5 of 5, still 1.00. Same pattern as the first reveal ([issue #99](https://github.com/sindredg/hindcast/issues/99)).

#### A partial on a not-inferable factor lowered the score

On `github-2026-10-21`, each run said the audit log backlog prolonged recovery. The key's fourth factor is the limited write rate behind that backlog, labelled `not inferable`. The judge gave `partial`: 0.5 on an item that would have been neutral if the run had said nothing. Without it each run scores 2.5 of 4, 0.63 ([issue #72](https://github.com/sindredg/hindcast/issues/72)).

#### What 0.60 is made of

| Item | Label | Outcome | Credit |
|---|---|---|---|
| Attack verdict | inferable | abstained | 0 |
| Root cause | not inferable | partial | 0.5 |
| Factor: limited audit log write rate | not inferable | partial | 0.5 |
| Onset at 14:52 | stated | supported hit | 1 |
| Resolved at 19:22 | stated | supported hit | 1 |

Three factors and the audit log catch-up time are `not inferable` and were not stated: neutral. The attack label carries a fifth of the score. Labelled `not inferable`, the same abstentions would have earned credit and the runs would score 0.80. The label was frozen before the files were opened and stands.

#### Two runs shared a run ID

`github-2026-10-21` is the first revealed case sealed under both library settings. Each setting has an attempt 1, and the ledger named both runs of a model `sealed/github-2026-10-21/<deployment>/a1`. The judgment of one overwrote the other's. The files left on disk were those of the library runs, confirmed by the `run_sha256` each judgment records.

Fixed in `5dc7b36`: a seal without the library gets the arm `sealed-<deployment>-library-off` and a run ID to match, the reveal refuses a run ID the ledger already holds, and a test fails on a duplicate. The two library-off runs were then judged and reviewed. The sealed files and their hashes were not touched ([troubleshooting](../../../docs/troubleshooting.md#evaluation-two-sealed-runs-of-one-model-share-a-run-id-2026-11-15)).

### Cost and spend

| Part | Count | Cost at list prices, USD | Source |
|---|---|---|---|
| Sealed runs on Azure, `github-2026-11-04-pull-requests` | 2 runs | 0.1011 | [`attempts.json`](attempts.json), price table version 1 |
| Sealed runs on Azure, `github-2026-10-21` | 4 runs | not recorded | Result files of 2026-11-01 and 2026-11-02 predate the cost field |
| Judge (`claude-opus-5-5`) | 6 calls | 0.54 | [`spend.json`](spend.json), less the first reveal |
| Reviewer (`claude-fable-5-1`) | 6 calls | 1.71 | same |

Claude API total for the addendum USD 2.25, no unpriced call; [`spend.json`](spend.json) now totals USD 2.98 over all eight runs. Four more calls (two judge, two reviewer) were made on the library-off runs before the run ID fix and overwritten, so their usage was not kept: about USD 0.75 at this addendum's mean cost per call, reasoned, not measured.

### Dataset

| Part | `github-2026-11-04-pull-requests` | `github-2026-10-21` |
|---|---|---|
| Evidence | `build/evidence/github-2026-11-04-pull-requests.json`, SHA-256 `5eb5e788…`; 9 updates | `build/evidence/github-2026-10-21.json`, SHA-256 `e727da47…`; 15 updates |
| Postmortem | GitHub's resolved update, captured 2026-11-15T14:12:18Z as `github-summary-2026-11-04-pull-requests`, SHA-256 `021b3f45…` | "GitHub availability report: October 2026", captured 2026-11-15T14:12:19Z as `github-availability-2026-10`, SHA-256 `33799b12…` |
| Key | [`github-2026-11-04-pull-requests.json`](../../keys/github-2026-11-04-pull-requests.json) | [`github-2026-10-21.json`](../../keys/github-2026-10-21.json) |
| Labels | [3 stated, 3 not inferable](../../keys/labels/github-2026-11-04-pull-requests.json) | [2 stated, 1 inferable, 6 not inferable](../../keys/labels/github-2026-10-21.json) |
| Library snapshot | 267 chunks | 267 chunks |

Both keys were drafted by hand from the postmortem and every quote checked in code; the labels were drafted from the evidence. Hashes are in [`eval/keys/frozen.json`](../../keys/frozen.json), [`eval/keys/labels/frozen.json`](../../keys/labels/frozen.json), and [`reveals.json`](../../sealed/reveals.json).

## Addendum, 2026-11-24: github-2026-10-22

GitHub wrote its cause into the incident's resolved update at 2026-11-16T16:28:44Z; its October availability report does not cover the incident. The case went through the [reveal procedure](../../../docs/runbooks/sealing.md#reveal-a-seal) on 2026-11-24, offline except the capture and the Claude API calls.

### Status

- **Cause published after every seal.** The resolved update was rewritten at 2026-11-16T16:28:44Z; the seals are of 2026-11-01 (library off) and 2026-11-02 (library on).
- **Frozen before the reveal, tested:** key `05175cf8…`, labels `4742b6e1…`, committed in `1939158`. `python -m hindcast.keys check` gave 0 problems; with one quote changed by a word it gave 1 problem and exit 1.
- **Leak check, tested:** 0 hits against the case's 267-chunk library snapshot; 1 hit with `--plant`.
- **Reveal, tested:** `python -m hindcast.reveal github-2026-10-22` at 18:32:03Z from commit `1939158`; four files match their seals (`tests/test_sealed_reveal.py`, 5 passed). With one byte added to a revealed file, the same test failed with `does not match its seal`.
- **Judge and reviewer, tested:** four runs judged and reviewed from commit `f0bca05`, no error; 46 queue decisions applied, none open.
- **Scores, tested:** `python -m hindcast.evaluation.score --root eval/reconstruction/sealed-v1` wrote [`scores.json`](scores.json) with 12 runs.

### Results

| Run | Library search | Agent version | Primary | Scorable | Supported hits | Partial | Justified abstentions | Unsupported, guesses, wrong |
|---|---|---|---|---|---|---|---|---|
| `sealed/github-2026-10-22/gpt-6-luna-library-off/a1` | off | 2 | 1.00 | 3 | 1 | 0 | 2 | 0, 0, 0 |
| `sealed/github-2026-10-22/gpt-6.1-sol-library-off/a1` | off | 1 | 1.00 | 3 | 1 | 0 | 2 | 0, 0, 0 |
| `sealed/github-2026-10-22/gpt-6-luna/a1` | on | 3 | 1.00 | 3 | 1 | 0 | 2 | 0, 0, 0 |
| `sealed/github-2026-10-22/gpt-6.1-sol/a1` | on | 2 | 1.00 | 3 | 1 | 0 | 2 | 0, 0, 0 |

Model versions, judge, reviewer, and rubric are those of the first reveal. The seals ran from commits `c6a26d0` and `3162dfe` (2026-11-01) and `5fd90c0` (2026-11-02), recorded per run in [`attempts.json`](attempts.json).

**Nothing about the cause in the updates, and all four runs said so.** GitHub's summary says the proxies that route requests to its search clusters ran out of CPU while setting up encrypted connections, and retried requests kept them overloaded. The updates report errors loading Issues, Pull Requests, and search results, and "recovery after adding capacity" (u8). None names the proxies, CPU, or encryption. Every run said the initiating cause could not be determined, asked for it as an open question, and answered "cannot tell" on the attack verdict: two justified abstentions each.

- **The one stated event matched; the onset was out of reach.** All four runs matched the summary's recovery at 17:28 through u8 at 17:16, "recovery after adding capacity", within the 30-minute tolerance; two also cited u9 at 17:41. The onset at 14:55 is 33 minutes before the first update; no run dated it, a neutral miss.
- **The library search changed nothing.** Same outcome on every key item with and without it, on both models.
- **No unsupported item, no guess, nothing wrong** in any of the four runs.

The score rests on three items, two of them abstentions. As in the first reveal, 1.00 says the runs stayed inside the evidence, not that they found the cause: the evidence did not hold it.

### Judge and reviewer

The reviewer agreed with the judge on all 46 queue items. Judging on its own, it differs on one key item outside the queue: `timeline/0` on the `gpt-6-luna` library-off run. The judge marks the 14:55 onset `missed`. The reviewer marks it `wrong`, reading the run's incident start at 15:28 as a stated onset 33 minutes late, outside the tolerance. The judge's verdict stands; by the reviewer alone the run scores 0.75. Over all twelve sealed runs the two agree on 88 of 90 match verdicts (97.8 percent, kappa 0.97).

### Error analysis

#### The summary covers part of the incident

The incident is titled "Project updates delayed". After search recovered, its updates follow delayed GitHub Projects updates until u17 at 00:55 and the resolved update at 02:30 on 2026-10-23. GitHub's summary covers search from 14:55 to 17:28 and gives no cause for the Projects delays of the next seven hours. The key holds what the summary states, so the runs' events after 17:28 fall outside it: counted as supported items outside the key, not scored.

#### Mitigation in the fixes

The key lists the proxy capacity added during the outage as a fix, as the 2026-11-15 keys did with their mitigations, although the [field rule](../../keys/README.md#fields) puts mitigation during the outage in the timeline. Fixes are not scored, so the placement changes no score.

### Cost and spend

| Part | Count | Cost at list prices, USD | Source |
|---|---|---|---|
| Sealed runs on Azure | 4 runs | not recorded | Result files of 2026-11-01 and 2026-11-02 predate the cost field |
| Judge (`claude-opus-5-5`) | 4 calls | 0.35 | [`spend.json`](spend.json), less the earlier reveals |
| Reviewer (`claude-fable-5-1`) | 4 calls | 1.17 | same |

Claude API total for this addendum USD 1.52, no unpriced call; [`spend.json`](spend.json) now totals USD 4.50 over all twelve runs. Prices are version 1 of `data/claude-prices.yaml`, read on 2026-11-04, not read again for this addendum.

### Dataset

| Part | `github-2026-10-22` |
|---|---|
| Evidence | `build/evidence/github-2026-10-22.json`, SHA-256 `9a3727f7…`; 18 updates |
| Postmortem | GitHub's resolved update, captured 2026-11-24T18:28:23Z as `github-summary-2026-10-22`, SHA-256 `1d342554…` |
| Key | [`github-2026-10-22.json`](../../keys/github-2026-10-22.json): root cause, one factor, two timeline events, four fixes |
| Labels | [1 stated, 4 not inferable](../../keys/labels/github-2026-10-22.json) |
| Library snapshot | 267 chunks |

The key was drafted by hand from the summary and every quote checked in code; the labels were drafted from the evidence. Hashes are in [`eval/keys/frozen.json`](../../keys/frozen.json), [`eval/keys/labels/frozen.json`](../../keys/labels/frozen.json), and [`reveals.json`](../../sealed/reveals.json).

## Pending cases

| Case | Provider | Sealed | State on 2026-11-24 |
|---|---|---|---|
| `cloudflare-2026-10-20` | Cloudflare | 2026-11-01 and 2026-11-02 | No cause published; the resolved update reads "This incident has been resolved.", the incident has no postmortem, and the Cloudflare blog has no post on it |

It is revealed with the [sealing runbook](../../../docs/runbooks/sealing.md#reveal-a-seal) if Cloudflare publishes, or dropped on 2026-11-30.

## Limits

- Four cases, one seal per model and library setting, no repeats: twelve runs, not a model's average.
- The four runs of `github-2026-10-21` and of `github-2026-10-22` differ in more than the library setting: agent version and code commit changed between 2026-11-01 and 2026-11-02.
- The addenda's keys and labels passed the quote check and the label checks and had no item-by-item second reading before the freeze.
- The first reveal's key was drafted by hand, not by Content Understanding like the showcase keys; the quote check and the review by a person are the same.
- For `github-2026-11-04-actions`, the evidence ends at the resolved update at 17:01. GitHub's summary describes a second period of delays from 17:20 to 17:55, which no update covers.
- The judge's system prompt was rebuilt from rubric version 2, the version its lock names; versions 2 and 3 differ in that prompt only in the title line.
- Not comparable with the showcase arms: no single-search baseline (the comparison model runs in the agent's place, decision 0017), no prior-knowledge question (the case began after both model versions were released), and no per-case library picks (the whole library within the date bound).

## Files

| File | What it is |
|---|---|
| [`attempts.json`](attempts.json) | One entry per revealed seal: hash, usage, cost |
| [`judgments/`](judgments/) | The judge's judgment of each run |
| [`reviewer/judgments/`](reviewer/judgments/) | The reviewer's judgment of each run |
| [`reviews/`](reviews/) | The reviewer's decisions on the queued items |
| [`scores.json`](scores.json) | Scores per run and arm, agreement, second opinion |
| [`spend.json`](spend.json) | Judge and reviewer Claude API usage at list prices |
| [`../../investigations/`](../../investigations/) | The revealed result files, byte for byte as sealed: [`github-2026-11-04-actions/`](../../investigations/github-2026-11-04-actions/), [`github-2026-11-04-pull-requests/`](../../investigations/github-2026-11-04-pull-requests/), [`github-2026-10-21/`](../../investigations/github-2026-10-21/), [`github-2026-10-22/`](../../investigations/github-2026-10-22/) |

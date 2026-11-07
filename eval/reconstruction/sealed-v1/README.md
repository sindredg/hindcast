# Reconstruction evaluation, sealed v1

The sealed reconstructions that have been revealed: each one made before its provider had published a cause, committed by hash, and opened only after the cause was published and the key and labels were frozen ([decisions 0017](../../../docs/decisions/0017-sealed-reconstructions.md), [0022](../../../docs/decisions/0022-sealed-drop-date-and-offline-reveal.md), and [0030](../../../docs/decisions/0030-close-evaluation-with-sealed-addenda.md)). Scored by the same judge, reviewer, and [rubric](../../rubric/rubric.md), version 3, as the [showcase runs](../showcase-v1/README.md), and reported apart from them.

On this page: [Status](#status) · [Results](#results) · [Error analysis](#error-analysis) · [Cost and spend](#cost-and-spend) · [Dataset](#dataset) · [Pending cases](#pending-cases) · [Limits](#limits) · [Files](#files)

## Status

- **Revealed, verified on 2026-11-07:** `github-2026-11-04-actions`, both seals. The other four sealed cases have no published cause yet; each is revealed in its own addendum or dropped on 2026-11-30 ([pending cases](#pending-cases)).
- **Frozen before the reveal:** the key at 10:27:30Z (SHA-256 `4d3d4633…`) and the labels right after (`57274146…`), both approved by a person; the leak check against the library snapshot at 10:27:51Z.
- **Reveal, verified on 2026-11-07:** `python -m hindcast.reveal github-2026-11-04-actions` at 10:30:54Z; both files match their seals (`tests/test_sealed_reveal.py`, 4 passed). It ran from an uncommitted tree; the key, the labels, and the code were committed minutes later ([worklog 05](../../../docs/worklogs/05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07)).
- **Judge and reviewer, verified on 2026-11-07:** judged from 10:40:31Z to 10:41:00Z and reviewed from 10:41:07Z to 10:42:00Z, from commit `ce12ac8`, with no error; the reviewer's decisions were applied at 10:42:01Z.
- **Scores, verified on 2026-11-07:** `python -m hindcast.evaluation.score --root eval/reconstruction/sealed-v1` wrote [`scores.json`](scores.json) with no open review item.

## Results

Both models scored 1.00 on the one revealed case, on four scorable items. The score says the runs stayed inside the evidence. It does not say they found the cause, because the evidence did not hold it.

- **The cause was not in the evidence, and neither run guessed it.** GitHub's summary names a configuration change to an internal event-routing service that paused several event streams. The updates say only that "an issue with events that might trigger Actions" was found (u5). Both runs named that issue as the best-supported proximate cause, said the mechanism was not disclosed, and listed it as an open question. The judge and the reviewer counted both root causes, and both attack verdicts, as justified abstentions.
- **No unsupported item, no guess, nothing wrong.** Every run item that was judged rests on the updates: 10 supported items outside the key for `gpt-6-luna` and 9 for `gpt-6.1-sol`.
- **The misses are all items the evidence cannot reach.** The three contributing factors (feature flags, how the service handled them, a rollback that left the code change in place) and four timeline events are labelled `not inferable`, so missing them is neutral. Three of the events happened after the resolved update at 17:01, the last item of the evidence.
- **The two models are equal here, and the cheaper one is faster.** The same outcomes on every key item; `gpt-6-luna` took 27 seconds and USD 0.031, `gpt-6.1-sol` 42 seconds and USD 0.058.

| Run | Deployment, version | Agent version | Primary | Scorable | Supported hits | Justified abstentions | Missed (all not inferable) | Unsupported, guesses, wrong |
|---|---|---|---|---|---|---|---|---|
| `sealed/github-2026-11-04-actions/gpt-6-luna/a1` | gpt-6-luna, 2026-09-22 | 3 | 1.00 | 4 | 2 | 2 | 7 | 0, 0, 0 |
| `sealed/github-2026-11-04-actions/gpt-6.1-sol/a1` | gpt-6.1-sol, 2026-09-29 | 2 | 1.00 | 4 | 2 | 2 | 7 | 0, 0, 0 |

Both seals ran from commit `42c308a` with the library search on (`library: true` in [`seals.json`](../../sealed/seals.json)) and the investigator prompt `prompts/investigator.md` at blob `1d0911f4…`, the same prompt as the showcase `hindcast` and comparison arms; the comparison model ran in the agent's place. The judge ran prompt version 1 (`prompts/judge.md`, SHA-256 `afa416c0…`, system prompt `9de219e1…`), and the reviewer `prompts/reviewer.md` (`8ab121d8…`, system prompt `8d36cd06…`). `gpt-6.1-sol` kept two library citations; no claim rests on a library document alone, since no run item is unsupported.

### Judge and reviewer

The reviewer decided all 22 items in the review queue (10 match decisions, 12 support decisions) and agreed with the judge on every one: 100 percent, Cohen's kappa 1.0 on the match decisions. Over every key item, judged in full by both, they agree on 21 of 22 match verdicts (95.5 percent, kappa 0.92) and on all 31 support verdicts. The one disagreement is `timeline/0` on the `gpt-6.1-sol` run, outside the queue ([below](#a-timeline-hit-through-the-tolerance)). Scored by the judge alone or the reviewer alone, both runs score 1.00.

## Error analysis

### A timeline hit through the tolerance

`timeline/1`, the rollback at 16:14, is labelled `not inferable`: u5 at 16:34 says mitigations were applied, with no time and no rollback. Both runs list u5's event at 16:34, and the judge matched it to the 16:14 rollback as "the same mitigation event, within 30 minutes". The reviewer agreed. The hit does not change the score: without it, `timeline/1` is a neutral miss and each run scores 3 of 3. It shows that the 30-minute tolerance can match an announcement to the action it reports even when the label says the action's time is not in the evidence ([issue #99](https://github.com/sindredg/hindcast/issues/99)).

The same pattern is the one judge-reviewer disagreement. On the `gpt-6.1-sol` run, `timeline/0` (delays began at 15:49, `not inferable`) is `missed` by the judge: the run's first event, u1 at 16:05, is the incident opening, and the run says it is not the onset. The reviewer called it a supported hit, 16 minutes from 15:49 and inside the tolerance. The item was not in the review queue, so the judge's `missed` stands, and the run scores 1.00 either way.

### What the score cannot show

A case whose cause is not inferable scores on abstentions and on the events the updates time. Two such items carry the score here, so the result is about restraint, not about reconstruction. A sealed case whose updates hint at the cause would test more; which case that is depends on what each provider wrote, and decision 0017 forbids choosing seals by that.

## Cost and spend

| Part | Count | Cost at list prices, USD | Source |
|---|---|---|---|
| Sealed runs on Azure | 2 runs | 0.0891 | [`attempts.json`](attempts.json), price table version 1 (`data/prices.yaml`) |
| Judge (`claude-opus-5-5`) | 2 calls | 0.17 | [`spend.json`](spend.json) |
| Reviewer (`claude-fable-5-1`) | 2 calls | 0.56 | same |

The Claude prices are version 1 of `data/claude-prices.yaml`, read on 2026-11-04 from the [pricing page](https://platform.claude.com/docs/en/about-claude/pricing). The Claude API total for the reveal is USD 0.73, with no unpriced call, priced with `python -m hindcast.evaluation.spend --sealed`.

## Dataset

| Part | Where | Frozen |
|---|---|---|
| Evidence | `build/evidence/github-2026-11-04-actions.json`, cut from the snapshot captured at 2026-11-04T17:18:12Z | SHA-256 `c88d4716…`, the value both seals record |
| Postmortem | GitHub's resolved update, captured again at 2026-11-07T10:22:42Z as `github-summary-2026-11-04-actions` ([registry](../../../data/cases.yaml)); its `updated_at` is 2026-11-07T01:04:38Z | SHA-256 `76af8617…` |
| Key | [`eval/keys/github-2026-11-04-actions.json`](../../keys/github-2026-11-04-actions.json), drafted by hand from the summary; every quote checked word for word with `python -m hindcast.keys check` | [`eval/keys/frozen.json`](../../keys/frozen.json) |
| Labels | [`eval/keys/labels/github-2026-11-04-actions.json`](../../keys/labels/github-2026-11-04-actions.json): 1 stated, 10 not inferable | [`eval/keys/labels/frozen.json`](../../keys/labels/frozen.json) |
| Library | The case's snapshot, 267 chunks, taken at 2026-11-04T17:23:39Z before the index was deleted | [`library-snapshots.json`](../../sealed/library-snapshots.json) |
| Reveal record | Publication time, hashes, and the leak check's counts | [`reveals.json`](../../sealed/reveals.json) |

## Pending cases

| Case | Provider | Sealed | State on 2026-11-07 |
|---|---|---|---|
| `cloudflare-2026-10-20` | Cloudflare | 2026-11-01 and 2026-11-02 | No cause published; resolved update reads "This incident has been resolved." |
| `github-2026-10-21` | GitHub | 2026-11-01 and 2026-11-02 | No cause published; GitHub's October report is due 2026-11-11 |
| `github-2026-10-22` | GitHub | 2026-11-01 and 2026-11-02 | No cause published; same report |
| `github-2026-11-04-pull-requests` | GitHub | 2026-11-04 | No cause published |

Each pending case is revealed by the [sealing runbook](../../../docs/runbooks/sealing.md#reveal-a-seal) when its provider publishes, or dropped on 2026-11-30.

## Limits

- One case, one seal per model, no repeats: the scores describe two runs, not a model's average.
- The key was drafted by hand, not by Content Understanding as the showcase keys were. The word-for-word quote check and the review by a person are the same.
- The evidence ends at the resolved update at 17:01. GitHub's summary describes a second period of delays from 17:20 to 17:55, which no update covers.
- The judge's system prompt was rebuilt from rubric version 2, the version its lock names; versions 2 and 3 differ in that prompt only in the title line.
- The scores are not comparable with the showcase arms' columns. A sealed case has no single-search baseline (the comparison model runs in the agent's place, decision 0017), no prior-knowledge question (it began after both model versions were released), and no per-case library picks (it searches the whole library within its date bound).

## Files

| File | What it is |
|---|---|
| [`attempts.json`](attempts.json) | The ledger: one entry per revealed seal, with its hash, usage, and cost |
| [`judgments/`](judgments/) | The judge's judgment of each run |
| [`reviewer/judgments/`](reviewer/judgments/) | The reviewer's judgment of each run |
| [`reviews/`](reviews/) | The reviewer's decisions on the queued items |
| [`scores.json`](scores.json) | Scores per run and arm, agreement, and the second opinion |
| [`spend.json`](spend.json) | The judge's and the reviewer's Claude API usage at list prices |
| [`../../investigations/github-2026-11-04-actions/`](../../investigations/github-2026-11-04-actions/) | The revealed result files, byte for byte as sealed |

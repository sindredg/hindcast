# Reconstruction evaluation, showcase v1

The scored reconstructions of the four showcase cases: each arm of [decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md) run three times per case, scored against the frozen keys and labels by the [rubric](../../rubric/rubric.md), version 3. This page holds the scores, the judge-reviewer agreement, the error analysis, and the Foundry cloud evaluation's numbers.

## Status

- **Frozen before any scored run:** the inferable-from-evidence labels on 2026-11-03, and the rubric (version 2) with the timeline tolerance of 30 minutes on 2026-11-04, with the keys frozen earlier. Version 2 replaced version 1, frozen on 2026-11-03, before any run used it. Version 3 replaced version 2 at 18:56:41Z on 2026-11-04, after the judge ran and before any review decision; it changes only who decides the review queue. [`eval/rubric/frozen.json`](../../rubric/frozen.json) records their hashes, and `tests/test_rubric.py` fails if any of them changes.
- **Runs, verified on 2026-11-04:** 60 scored runs, 03:10:48Z to 04:00:47Z, live, with `python -m hindcast.evaluation.batch run` ([runbook](../../../docs/runbooks/evaluation.md#scored-runs), steps 9 and 10). Every slot filled on its first attempt: 60 entries in `attempts.json`, all `complete`, none `no-result`.
- **Foundry cloud evaluation, verified on 2026-11-04:** repeat 1 of each arm and case, completed at 04:28:33Z ([below](#foundry-cloud-evaluation)).
- **Judge, verified on 2026-11-04:** prompt version 1 frozen ([`eval/judge/frozen.json`](../../judge/frozen.json)) before any judge call and before any run output was read. `claude-opus-5-5`, effort `high`, judged all 60 runs from 17:16:57Z to 17:23:51Z with no judge error (`python -m hindcast.evaluation.judge run`, [runbook](../../../docs/runbooks/evaluation.md#judge), step 17). The judgments were committed before any review decision.
- **Reviewer, verified on 2026-11-04:** `claude-fable-5-1` decides the review queue in place of a person ([decision 0027](../../../docs/decisions/0027-reviewer-model.md)). Its prompts were frozen at 18:57:31Z ([`eval/judge/frozen-reviewer.json`](../../judge/frozen-reviewer.json)). The test call on one run ran from 18:58:01Z to 18:59:23Z, and the full run from 19:02:48Z to 19:17:22Z: `judged 59, errors 0, kept 1`, every call `end_turn` (`python -m hindcast.evaluation.reviewer run`, [runbook](../../../docs/runbooks/evaluation.md#review-and-scores), steps 19 and 20). `reviewer apply` wrote 880 decisions over the 60 runs at 19:17:49Z to 19:17:50Z, none missing (step 21).
- **Scores, verified on 2026-11-04:** `python -m hindcast.evaluation.score` with no open review item wrote [`scores.json`](scores.json) (step 22).
- **Spend, verified on 2026-11-04:** the Claude API usage of the judge and the reviewer priced at list prices with `python -m hindcast.evaluation.spend` (step 23); the Console's token totals were compared on 2026-11-07 ([below](#cost-and-spend)); the billed amount was not read.

## Results

On the three cases the models did not know beforehand, the five arms score between 0.78 and 0.82, and each difference traces to a few items in a few runs. These scores do not separate the arms.

- **The arms do not separate.** Over 9 runs each, the means run from 0.78 to 0.82. Scoring the same runs with the judge alone or the reviewer alone moves an arm's mean by up to 0.03 and reorders all arms but the first ([judge and reviewer](#judge-and-reviewer)). Within each arm, runs range from 0.42 or 0.50 to 1.00.
- **The case decides the score.** Every run scores 1.00 on `github-2026-10-07`, and every run scores between 0.42 and 0.70 on `google-cloud-2026-07-14`. The labels largely set both ([where the credit is lost](#where-the-credit-is-lost)).
- **Neither the tool loop nor the library adds measurable score here.** `single-search`, one search and one model call, leads under every judge: 0.82 against 0.79 for `library-off` and 0.78 for `hindcast`. Its lead over `hindcast` is six items in five runs ([where the credit is lost](#where-the-credit-is-lost)). The library holds 23 documents, so this says little about retrieval in general.
- **The comparison model costs twice as much for the same score.** `gpt-6.1-sol` takes 55 seconds and USD 0.088 per run, against 31 seconds and USD 0.045 for `gpt-6-luna` with the same prompt and tools, and scores 0.79 against 0.78.
- **No guesses and no unsupported hits.** Across all 60 runs, every hit and partial rests on a supported run item. Every root cause the labels mark `not inferable` was answered with an abstention.
- **The abstention prompt changes nothing measurable.** This is decision 0006's one controlled comparison, the prompt alone changed: 0.81 against `hindcast`'s 0.78, with the same 12 justified abstentions, and 4 unsupported run items against none.
- **What the models knew stayed out of the root cause.** Both models' prior answers named the root cause of `cloudflare-2025-11-18`, yet all 15 runs on that case abstained on it ([known before evidence](#known-before-evidence)).

### Per arm

The cases not known before evidence: `github-2026-08-17`, `google-cloud-2026-07-14`, and `github-2026-10-07`, three runs each. Seconds and cost come from `attempts.json`; cost is from price table version 1 (`data/prices.yaml`).

| Arm | Runs | Mean | Min | Max | Seconds per run | Cost per run, USD |
|---|---|---|---|---|---|---|
| `hindcast` | 9 | 0.78 | 0.50 | 1.00 | 30.6 | 0.0453 |
| `comparison` | 9 | 0.79 | 0.50 | 1.00 | 55.3 | 0.0876 |
| `single-search` | 9 | 0.82 | 0.42 | 1.00 | 25.8 | 0.0409 |
| `library-off` | 9 | 0.79 | 0.50 | 1.00 | 24.8 | 0.0378 |
| `abstention` | 9 | 0.81 | 0.50 | 1.00 | 28.7 | 0.0445 |

The `library-off` arm differs from `hindcast` in its prompt as well as its tools, because the `hindcast` prompt tells the model to search ([decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md)). The `abstention` arm differs in its prompt alone.

Per arm and case, mean (min to max) over three runs:

| Arm | `github-2026-08-17` | `google-cloud-2026-07-14` | `github-2026-10-07` |
|---|---|---|---|
| `hindcast` | 0.84 (0.80 to 0.90) | 0.50 (0.50 to 0.50) | 1.00 (1.00 to 1.00) |
| `comparison` | 0.86 (0.83 to 0.90) | 0.50 (0.50 to 0.50) | 1.00 (1.00 to 1.00) |
| `single-search` | 0.90 (0.90 to 0.90) | 0.57 (0.42 to 0.70) | 1.00 (1.00 to 1.00) |
| `library-off` | 0.87 (0.80 to 0.90) | 0.50 (0.50 to 0.50) | 1.00 (1.00 to 1.00) |
| `abstention` | 0.86 (0.83 to 0.90) | 0.57 (0.50 to 0.70) | 1.00 (1.00 to 1.00) |

The full outcome table, summed over the 9 runs per arm. The three cases have 24 key items between them, so each arm has 72. A supported item outside the key is a run item scored supported that matches no key item: the reviewer's verdict where the item was in the queue, otherwise the judge's. It is counted, not scored.

| Arm | Supported hit | Partial | Unsupported hit | Unsupported partial | Abstained | Missed | Wrong | Justified abstentions | Guesses | Unsupported run items | Supported items outside the key | Contradictions | Failures |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `hindcast` | 24 | 6 | 0 | 0 | 15 | 27 | 0 | 12 | 0 | 0 | 121 | 0 | 0 |
| `comparison` | 24 | 8 | 0 | 0 | 15 | 25 | 0 | 12 | 0 | 0 | 153 | 0 | 0 |
| `single-search` | 26 | 6 | 0 | 0 | 13 | 25 | 2 | 12 | 0 | 0 | 114 | 0 | 0 |
| `library-off` | 24 | 5 | 0 | 0 | 15 | 28 | 0 | 12 | 0 | 0 | 121 | 0 | 0 |
| `abstention` | 25 | 8 | 0 | 0 | 14 | 25 | 0 | 12 | 0 | 4 | 122 | 0 | 0 |

The Abstained column includes 12 abstentions on the `google-cloud-2026-07-14` attack verdict, which the labels call `inferable`; they earn 0 and count as missed in the credit. Most misses are neutral, 22 to 24 of each arm's 25 to 28: a `not inferable` factor or timeline event that no run mentions leaves the denominator ([rubric](../../rubric/rubric.md#credit)). Per-run outcomes, credits, and item lists are in `scores.json`.

### Known before evidence

Both models' prior answers hit the root cause of `cloudflare-2025-11-18`, in both collections ([prior-knowledge check](../../prior-knowledge/v1/README.md#results)). Their runs on it are reported here, apart:

| Arm | Runs | Mean | Min | Max | Wrong | Seconds per run | Cost per run, USD |
|---|---|---|---|---|---|---|---|
| `hindcast` | 3 | 0.83 | 0.75 | 1.00 | 2 | 31.6 | 0.0470 |
| `comparison` | 3 | 0.70 | 0.61 | 0.88 | 3 | 63.3 | 0.0916 |
| `single-search` | 3 | 0.58 | 0.38 | 0.88 | 0 | 23.9 | 0.0427 |
| `library-off` | 3 | 0.58 | 0.50 | 0.75 | 2 | 25.3 | 0.0345 |
| `abstention` | 3 | 0.79 | 0.50 | 1.00 | 2 | 30.6 | 0.0449 |

The models knew the cause and did not use it. All 15 runs answered the root cause with an abstention, and the reviewer, judging blind, agreed on every one. The labels mark it `not inferable`, so each abstention earns credit.

An abstention shows that the known cause stayed out of the root-cause item. It does not show that the knowledge shaped nothing else in the run.

### Judge and reviewer

Agreement between the judge's proposals and the reviewer's verdicts, over the review queue (the rubric's measure) and over every item of every judgment:

| Items | Count | Agreement | Cohen's kappa |
|---|---|---|---|
| Queue, all | 880 | 98.9% | 0.98 |
| Queue, matches | 331 | 97.0% | 0.95 |
| Queue, support verdicts | 549 | 100.0% | 1.00 |
| Every key item | 660 | 95.2% | 0.93 |
| Every run item's support | 1,242 | 99.9% | 0.89 |

These numbers say less than they look:

- **The support kappa rests on 3 negatives.** Of the 549 support verdicts in the queue, both models called 546 supported and the same 3 unsupported.
- **The queue checks hits and leaves misses mostly unchecked.** The judge and the reviewer differ on 32 key items. 22 of them are outside the queue, and in all 22 the judge says missed where the reviewer finds a partial (11), a supported hit (7), or a wrong (4). Outside the queue the judge's proposal stands.

How far the means move with the judge that decides, from `second_opinion` in `scores.json`:

| Arm | Judge alone | Rubric score | Reviewer alone |
|---|---|---|---|
| `hindcast` | 0.78 | 0.78 | 0.78 |
| `comparison` | 0.79 | 0.79 | 0.76 |
| `single-search` | 0.84 | 0.82 | 0.81 |
| `library-off` | 0.78 | 0.79 | 0.80 |
| `abstention` | 0.81 | 0.81 | 0.80 |

`single-search` leads in all three columns, by 0.01 to 0.03 over the next arm. The order of the other four changes with the judge: `comparison` is third with the judge alone, fourth under the rubric, and last with the reviewer alone.

## Error analysis

### Unsupported verdicts on a correct root cause

None. [Decision 0006](../../../docs/decisions/0006-evaluation-design.md) lists every one here, and there is nothing to list: no run has an unsupported hit or an unsupported partial on a root cause. The 60 root causes are 45 abstentions on the three cases whose root cause is `not inferable`, and 15 partials on `google-cloud-2026-07-14`, each resting on a supported item.

One root-cause run item was found unsupported, and it is an abstention, not a cause. In `abstention/github-2026-08-17/r3/a1`, finding `f1` lists Issues and Pull Requests among the degraded services, but none of the updates it cites (`u2`, `u3`, `u4`, `u18`, `u19`) names them.

The inference `f6` rests on `f1`, and the root cause rests on `f6`, so both fail rule 2.1. The abstention still earns full credit: the rubric's abstention outcome has no support condition ([#71](https://github.com/sindredg/hindcast/issues/71)).

### Unsupported run items

Five over the 60 runs, of three kinds: a claim carrying a detail its citations do not give (two), an inference resting on such a claim (two), and a claim about a withheld text (one):

| Run | Item | What fails |
|---|---|---|
| `abstention/github-2026-08-17/r3/a1` | `findings[0]` (`f1`) | Names Issues and Pull Requests, which none of its cited updates gives |
| `abstention/github-2026-08-17/r3/a1` | `findings[5]` (`f6`), `root_cause` | Rest on `f1` |
| `abstention/github-2026-10-07/r2/a1` | `findings[5]` | Says recovery by 17:25 UTC citing `u24`, which does not give that time |
| `single-search/cloudflare-2025-11-18/r1/a1` | `timeline[11]` | Says the resolved update gave no details; that update's text is withheld. The reviewer called it supported, but it was outside the queue, so the judge's verdict stands |

The abstention arm holds four of the five, in two runs. Its prompt adds one rule to Hindcast's, the abstention rule; two runs cannot show whether that rule loosens the citations.

### Wrong items

| Key item | Runs | Cause |
|---|---|---|
| `cloudflare-2025-11-18` `timeline/10`, all services resolved at 17:06 | 9 of 15 | The runs date the end of impact by the update that reported it, `u21` at 17:44, 38 minutes later and past the 30-minute tolerance. The 3 runs that used `u20`, at 17:14, hit. The other 3 make the same 17:44 claim, and the judge called it missed; the reviewer calls two of them wrong, but they are outside the queue |
| `google-cloud-2026-07-14` `contributing_factors/1`, routing health checks stayed up | 2 `single-search` runs | The runs state BGP session flapping as a contributing factor; the postmortem says BGP and BFD stayed fully functional. Two `comparison` runs put the same BGP instability in their root cause, and the reviewer calls it wrong there too, but those items are outside the queue, so the judge's missed stands |

Both rows show a limit of the method, not only of the runs. Status updates trail the events they report, so a run that dates each event by its update is late by the posting lag. And the same claim scores differently depending on whether the seeded draw put it in the queue.

### Where the credit is lost

Most of the lost credit is set by the labels and the timeline tolerance, not by a run's error:

- **`google-cloud-2026-07-14` has a ceiling of 0.5 on its root cause.** The label is `stated`: update `u4` names a configuration update as the likely cause. The mechanism, a gap in the control plane's routing logic that dropped one private address range, is in the postmortem only. All 15 runs name the trigger without the mechanism, a partial.
- **The `google-cloud-2026-07-14` attack verdict is `inferable`, and 12 of 15 runs answer `cannot tell`.** The label reads `u4`'s configuration update as settling "not an attack". The investigator prompt says to answer `cannot tell` unless the evidence supports a verdict. The three runs that answered `not an attack` score 0.70, 0.70, and 0.58 against 0.50; the last also has a wrong factor.
- **`google-cloud-2026-07-14` `contributing_factors/2`, single-zone workloads without replication, is missed by all 15 runs.** Its label is `inferable` and marked a close call.
- **`github-2026-08-17` `contributing_factors/1` is a partial in 13 of 15 runs.** The runs say authentication retries slowed recovery; none names the latent client retry bug or the endpoint it flooded.
- **`single-search`'s lead over `hindcast`, 0.04, is six items.** On `google-cloud-2026-07-14`, its three runs score +0.20, +0.08, and −0.08 against `hindcast`'s 0.50: two answered `not an attack`, and two had the wrong factor above, a net +0.20. On `github-2026-08-17`, one `hindcast` run missed the stated factor and one found part of a `not inferable` factor (below): together 0.17 below the 0.90 every `single-search` run scored there. The 0.37 over 9 runs is the 0.04.
- **Finding part of a `not inferable` factor lowers the score.** A `not inferable` factor no run mentions leaves the denominator, but a partial on it counts 0.5 of 1. Six runs found part of one, and each scores lower than it would have by saying nothing: five on `github-2026-08-17` `contributing_factors/2`, at 0.83 instead of 0.90 ([#72](https://github.com/sindredg/hindcast/issues/72)).
- **The `cloudflare-2025-11-18` onset is hit by 2 minutes, and caution costs it.** The key puts the onset at 11:20; the first update is at 11:48:27, 28 minutes later. A run that calls 11:48 the start of the incident gets the hit (8 of 15). A run that says 11:48 is only the first public report, which is the more accurate reading, gets a miss.

### Disagreements in the queue

The judge and the reviewer differ on 10 of the 331 queue matches, and the reviewer's verdict decides each. In 5 the reviewer finds less than the judge (a hit or partial becomes missed); in 5 it finds more (a missed becomes a hit, a partial, or a wrong). Each is in `reviews/`, where a decision differs from its `proposal`.

## Cost and spend

The scored runs and their judging bill to two accounts:

| Part | Count | Cost at list prices, USD | Source |
|---|---|---|---|
| Scored runs on Azure, all 60 | 60 runs (142 model calls) | 3.0871 | `attempts.json`, price table version 1 (`data/prices.yaml`) |
| Judge, scored runs (`claude-opus-5-5`) | 60 calls | 5.54 | [`eval/judge/spend.json`](../../judge/spend.json) |
| Judge, prior answers (`claude-opus-5-5`) | 14 calls | 0.11 | same |
| Reviewer, scored runs (`claude-fable-5-1`) | 60 calls | 19.14 | same |
| Reviewer, prior answers (`claude-fable-5-1`) | 14 calls | 0.27 | same |

The Claude prices are version 1 of `data/claude-prices.yaml`, read on 2026-11-04 from the [pricing page](https://platform.claude.com/docs/en/about-claude/pricing). The Claude API total is USD 25.07, with no unpriced call. The reviewer is three quarters of it: its input and output prices are two and a half times the judge's, and it wrote more output.

The table leaves out the 16 injection runs and the Foundry evaluation's judge calls, both on Azure. Two kinds of Claude call are in no judgment file, so not in the total: the judge's test call on the development run (USD 0.12 by its logged usage) and four accepted schema probes of at most 64 output tokens each. The Anthropic Console's usage page, read on 2026-11-07 at 11:33Z for the last 30 days (every call falls on 2026-11-04 except the sealed reveal's four on 2026-11-07), shows 1,245,493 input and 491,121 output tokens across both models. The priced showcase calls in `spend.json` account for 1,226,082 input (with cache writes and reads) and 486,922 output tokens: 98.4% and 99.1%. The remainder, 19,411 input and 4,199 output tokens, is the size of the test call and the probes above; the sealed reveal's calls (29,170 input, 13,512 output, [sealed spend](../sealed-v1/spend.json)) ran about an hour before the reading and do not fit in it, so they had not reached the page yet. The billed amount in USD was not read.

## Dataset

| Part | Where | Frozen |
|---|---|---|
| Cases | `cloudflare-2025-11-18`, `github-2026-08-17`, `google-cloud-2026-07-14`, `github-2026-10-07` in [`data/cases.yaml`](../../../data/cases.yaml) | The registry pins each source by SHA-256 |
| Answer keys | [`eval/keys/`](../../keys/README.md) | SHA-256 per key in `eval/keys/frozen.json` |
| Labels | [`eval/keys/labels/`](../../keys/labels/README.md) | SHA-256 per file in `eval/keys/labels/frozen.json` |
| Rubric | [`eval/rubric/rubric.md`](../../rubric/rubric.md) | SHA-256 in `eval/rubric/frozen.json` |

Each run records the SHA-256 of the evidence file it read. Every run of a case read the same file:

| Case | Evidence SHA-256 |
|---|---|
| `cloudflare-2025-11-18` | `8b7e1ccb5bf0188613b7f7c76719ebc665d5787fcf90197ece0ae0d295f60fb6` |
| `github-2026-08-17` | `f45a778dc5a4db145f2ae8ab3c6f5100a1d5da187648531c7669ca1b07c768ee` |
| `google-cloud-2026-07-14` | `b4fa7c503cf93b309310bd6e8796a7fdaab6daa98b995f7defc863f8623e7b26` |
| `github-2026-10-07` | `9589943f72e1123ebb1c4d976ee36fe3274c851e268e7563c8776a80cc76938d` |

## Arms

The five arms of [decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md), three repeats per case, 12 runs per arm. All 60 runs ran from code commit `8d175ac` (tree `3144277a…` for `src/`) with a clean code and prompt tree, Prompt Shields and the PII check on, and, where the arm searches, the index `hindcast-library-1024` on search API version `2026-04-01`. The values below are read from `attempts.json` and each run's provenance.

| Arm | Deployment, model version | Agent, version | Prompt | Prompt blob |
|---|---|---|---|---|
| `hindcast` | `gpt-6-luna`, 2026-09-22 | `hindcast-investigator-gpt-6-luna`, 3 | `prompts/investigator.md` | `1d0911f4…` |
| `comparison` | `gpt-6.1-sol`, 2026-09-29 | `hindcast-investigator-gpt-6-1-sol`, 2 | `prompts/investigator.md` | `1d0911f4…` |
| `single-search` | `gpt-6-luna`, 2026-09-22 | none: one search, one model call | `prompts/single-search.md` | `939340e0…` |
| `library-off` | `gpt-6-luna`, 2026-09-22 | `hindcast-investigator-gpt-6-luna-library-off`, 1 | `prompts/investigator-library-off.md` | `60d84db0…` |
| `abstention` | `gpt-6-luna`, 2026-09-22 | `hindcast-investigator-gpt-6-luna-abstention`, 1 | `prompts/investigator-abstention.md` | `4fc4aed8…` |

The `hindcast` and `comparison` agents are the versions that made the sealed runs with the library search, on [2026-11-02](../../../docs/worklogs/05-sealed-reconstructions.md#second-seals-with-the-library-2026-11-02) and [2026-11-04](../../../docs/worklogs/05-sealed-reconstructions.md#third-seals-two-github-outages-of-2026-11-04) (`eval/sealed/seals.json`). A run's ID is `<arm>/<case_id>/r<repeat>/a<attempt>`; every run ID is in `attempts.json`.

The judge (`claude-opus-5-5`, prompt `prompts/judge.md` version 1) and the reviewer (`claude-fable-5-1`, prompt `prompts/reviewer.md` version 1) are named with their locks in `eval/judge/`; each judgment records its model, system prompt hash, input hash, and request ID.

## Foundry cloud evaluation

The generally available Foundry evaluators on repeat 1 of each arm and case ([decision 0006](../../../docs/decisions/0006-evaluation-design.md)): groundedness and relevance on every arm, tool call accuracy on the four agent arms (the single-search arm makes no tool calls of its own). Judge deployment `gpt-6.1-sol`, model version 2026-09-29. Live, 2026-11-04: `python -m hindcast.evaluation.foundry build`, `submit` (04:19:59Z), and `results` (04:28:33Z), runbook steps 12 to 14.

| Dataset | Rows | SHA-256 | Evaluation | Run |
|---|---|---|---|---|
| `hindcast-showcase-v1-quality` version 1 | 20 | `6aa87095…` | `eval_aec1d0f8bb7d4ae8aab749d603622dff` | `evalrun_b2062f4eff8d479ab0078f2f210cd01b` |
| `hindcast-showcase-v1-tools` version 1 | 16 | `6b9a2a92…` | `eval_1174097b41ca4f06bc3b33b3049f604c` | `evalrun_114619cbc16942faac568f78c428e37a` |

Mean score on the evaluators' 1 to 5 scale, over four rows per arm (one per case); failed rows in brackets:

| Arm | Groundedness | Relevance | Tool call accuracy |
|---|---|---|---|
| `hindcast` | 5.0 | 5.0 | 5.0 |
| `comparison` | 5.0 | 5.0 | 5.0 |
| `abstention` | 4.5 | 5.0 | 5.0 |
| `library-off` | 4.25 (1 failed) | 5.0 | 5.0 |
| `single-search` | 4.0 (1 failed) | 5.0 | not applicable |

Errored rows: 0 in both runs, counted per row as well as read from the service's own counts (quality: 18 passed, 2 failed, 0 errored; tools: 16 passed). A row with no score, no verdict, or an error would count as errored ([#7](https://github.com/sindredg/hindcast/issues/7)).

What these numbers can and cannot say:

- Groundedness compares a run's answer with the tool outputs it was shown, not with the postmortem. A grounded answer can still be wrong about the cause; the rubric's scores answer that.
- `gpt-6.1-sol` judges its own arm, `comparison`, as well as the others.
- One repeat of each arm and case: 20 runs of 60.
- A run file keeps the library refs a search returned, not the chunk text. For 10 of the 57 refs searched across all runs, the section spans more than one chunk, and the dataset's context holds the whole section: more than the run was shown.

## Limits

Written before the scores.

| Limit | What it means for the scores |
|---|---|
| A small library: 23 documents | Retrieval is close to a lookup, so the scores say little about retrieval quality ([retrieval check](../../retrieval/library-v1/README.md#limits)) |
| The keys have been public in this repository since 2026-10-27 | `gpt-6-luna` is version 2026-09-22 and `gpt-6.1-sol` version 2026-09-29, both before that day, so neither version's training data can include the keys. A later version could. The judge sees the key in every request, so its own training data does not change what it compares ([decision 0024](../../../docs/decisions/0024-judge-model.md)) |
| Training cutoffs | `cloudflare-2025-11-18` is the only showcase case that began before both models' training cutoffs. The [prior-knowledge check](../../prior-knowledge/v1/README.md) decides which model and case pairs go to the known-before-evidence table |
| Four cases, every key `not an attack` | A run that always answers "not an attack" gets every attack verdict right; no case tests an attack ([#19](https://github.com/sindredg/hindcast/issues/19)) |
| Abstention credit rests on the labels | The labels mark the root cause `not inferable` in three of the four cases (all but `google-cloud-2026-07-14`), and the attack verdict in the same three. On those items an abstention earns full credit. Each label is a judgment, approved by a person and frozen before any run ([labels](../../keys/labels/README.md#status)) |
| Two models, no person | `claude-opus-5-5` proposes every outcome; `claude-fable-5-1`, judging blind, decides every proposed hit and partial, every support verdict on an inference, and a quarter of the rest ([rubric](../../rubric/rubric.md#review)). Both come from one provider, so an error they share goes uncaught, and no person measured the reviewer's error rate. Judge-reviewer kappa measures agreement, not correctness ([decision 0027](../../../docs/decisions/0027-reviewer-model.md)) |
| A library citation resolves to the whole section | A run file keeps the refs a search returned, not the chunk text. For a section split over several chunks, the judge and the reviewer see more of it than the run was shown |
| Sealed cases | They have no single-search baseline (the comparison model runs in the agent's place) and no per-case library picks ([decision 0017](../../../docs/decisions/0017-sealed-reconstructions.md)). Their scores are on the [sealed report](../sealed-v1/README.md), one addendum per reveal ([decision 0030](../../../docs/decisions/0030-close-evaluation-with-sealed-addenda.md)) |

Found in the scores:

| Limit | What it means |
|---|---|
| 9 runs per arm on three cases | The largest difference between arms, 0.04, is close to the 0.03 that the choice of judge moves an arm's mean, and it comes from six items. A difference that size cannot be read from these runs |
| The queue samples a quarter of the misses | 22 key items where the reviewer's own judgment differs keep the judge's "missed". The same claim can score differently depending on the draw ([wrong items](#wrong-items)) |
| A label covers a key item whole | A `stated` root cause whose mechanism the updates never give caps every run at a partial ([where the credit is lost](#where-the-credit-is-lost)) |
| Status updates trail events | A run that dates an event by its update is late by the posting lag, and the 30-minute tolerance decides the outcome by minutes |
| An abstention needs no support | An abstention whose root-cause item fails support still earns full credit ([#71](https://github.com/sindredg/hindcast/issues/71)) |
| A partial on a `not inferable` item is scored | Finding part of a factor the evidence could not establish lowers a run's score ([#72](https://github.com/sindredg/hindcast/issues/72)) |
| Supported items outside the key are counted, not scored | 114 to 153 per arm over 9 runs. The count does not say whether an item is useful |

Known differences, each with no effect on these scores:

- **Abstention wording ([#65](https://github.com/sindredg/hindcast/issues/65)).** Decision 0023 defines a root-cause abstention as "a hedged claim and an open question that names what is missing". The rubric defines it as a root cause that "says the evidence does not determine it, names what is missing, and an open question asks for it", and counts a hedged statement as "a statement of what it hedges". The frozen rubric governs, and it matches the abstention prompt.
- **A stated label on a resolved update's time ([#66](https://github.com/sindredg/hindcast/issues/66)).** `github-2026-08-17` `timeline/1` is labelled `stated` on the resolved update alone, whose text the investigator never sees; its time is shown. `stated` and `inferable` earn the same credit.
- **Single-search `pii-error` keeps the model call's checks ([#64](https://github.com/sindredg/hindcast/issues/64)).** A `pii-error` attempt is not scored, and none of the 60 attempts ended that way.
- **Prior-knowledge effort ([#4](https://github.com/sindredg/hindcast/issues/4)).** The answers record the effort requested, `medium`, not the effort the service reports using.

## Files

| File | What it is |
|---|---|
| `README.md` | This page |
| `attempts.json` | One entry per attempt: run ID, arm, case, repeat, attempt, status, reason, result file and its SHA-256, usage, cost, agent, model, code commit |
| `runs/<arm>/<case_id>/r<repeat>-a<attempt>-<UTC time>.json` | One result per run, as `python -m hindcast.evaluation.batch` writes it |
| `foundry/runs.json` | The Foundry evaluation's judge deployment, datasets with their SHA-256, evaluation and run IDs, and criteria |
| `foundry/results.json` | Per arm and evaluator: rows passed, failed, and errored, and the mean score, with the service's own counts |
| `judgments/<arm>/<case_id>/r<repeat>/a<attempt>.json` | The judge's proposal for one run: an outcome per key item and a support verdict per run item, each with a reason; the run's ID, arm, and SHA-256; the code commit; the judge's model, effort, output limit, system prompt and input hashes, time, and request ID; the stop reason, usage, and any judge error |
| `reviewer/judgments/<arm>/<case_id>/r<repeat>/a<attempt>.json` | The reviewer's second judgment of the same run, in the same form, made without the judge's proposals |
| `reviews/<arm>/<case_id>/r<repeat>/a<attempt>.json` | The decision on each queue item: the judge's proposal, whether the item was sampled, the decision, its time, and the reviewer model and judgment hash it came from |
| `scores.json` | Per run: outcomes, credits, primary score, and the item lists beside it; the tables per arm and case and known before evidence; the agreement over the queue; and `second_opinion`, the agreement over every item and the means with each judge alone |

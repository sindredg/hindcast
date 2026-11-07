# Prior-knowledge check, `v1`

What each model said about each showcase outage before it saw any evidence, scored against the frozen keys on two items: the root cause and the attack verdict ([rubric](../../rubric/rubric.md#prior-knowledge), version 3; its Prior knowledge section is as version 2 froze it). A reconstruction is worth less when the model already knew the cause, so a model whose prior answer hits a case's root cause has its scores on that case reported in a separate known-before-evidence table in the [evaluation report](../../reconstruction/showcase-v1/README.md).

## Written before the judge

**Answers.** `python -m hindcast.evaluation.prior collect` asks each model about each showcase outage from its provider, its public incident title, and its date, at effort `medium` ([architecture](../../../docs/architecture/README.md#the-prior-knowledge-check)). The question names no key fact; `test_no_key_fact_in_any_question` checks that. The collector prints token counts only. The answers were committed unread; the judge and the reviewer model read them, and the review page shows them.

**Judge.** The same model and settings as the reconstruction judge: `claude-opus-5-5`, effort `high`, output limit 64,000 tokens ([decision 0024](../../../docs/decisions/0024-judge-model.md)). The system prompt is [`prompts/judge-prior.md`](../../../prompts/judge-prior.md) followed by the rubric's hedging and matching rules and its Prior knowledge section. Version 1 was frozen at 2026-11-04T15:59:40Z, before any prior judge call ([`eval/judge/frozen-prior.json`](../../judge/frozen-prior.json)). An answer cites no evidence, so there is no support verdict:

| Item | Outcomes |
|---|---|
| Root cause | hit, partial, abstained, missed, wrong |
| Attack verdict | hit, abstained, missed, wrong |

**Review.** The queue holds every proposed hit and partial, and a quarter of the other proposals, drawn with a fixed seed per answer (`hindcast.evaluation.review.prior_queue`). Since rubric version 3, the reviewer model `claude-fable-5-1` judges each answer again, blind to the judge's proposals, and its outcome on a queue item is the decision, replacing the judge's proposal ([decision 0027](../../../docs/decisions/0027-reviewer-model.md)). No person decides.

**Known before evidence.** A model and case pair is known before evidence when that model's answer in either collection is a hit on the root cause after review (`hindcast.evaluation.score.known_before_evidence`). A partial is reported, and does not move the pair.

## Dataset

| Answer file | Collected (UTC) | Deployment | Model version | Cases | SHA-256 |
|---|---|---|---|---|---|
| `eval/results/prior-2026-10-25-gpt-6-luna.json` | 2026-10-25T21:15:01Z | `gpt-6-luna` | 2026-09-22 | 3 | `c2973475…` |
| `eval/results/prior-2026-10-25-gpt-6.1-sol.json` | 2026-10-25T21:15:35Z | `gpt-6.1-sol` | 2026-09-29 | 3 | `d6345caa…` |
| `eval/results/prior-2026-11-01-gpt-6-luna.json` | 2026-11-01T08:27:36Z | `gpt-6-luna` | 2026-09-22 | 4 | `d4e1615d…` |
| `eval/results/prior-2026-11-01-gpt-6.1-sol.json` | 2026-11-01T08:28:17Z | `gpt-6.1-sol` | 2026-09-29 | 4 | `cbb584fe…` |

The 2026-10-25 collection covers `cloudflare-2025-11-18`, `github-2026-08-17`, and `google-cloud-2026-07-14` ([worklog 01](../../../docs/worklogs/01-foundations.md#prior-knowledge)). The 2026-11-01 collection adds `github-2026-10-07`, registered that day ([worklog 05, sealed reconstructions](../../../docs/worklogs/05-sealed-reconstructions.md#the-october-case)). 14 answers in all.

## Status

- **Answers, verified:** collected live on 2026-10-25 and 2026-11-01 and committed unread (dates and token counts in the worklogs above).
- **Judge, verified on 2026-11-04:** `python -m hindcast.evaluation.judge_prior run`, live, 17:24:07Z to 17:24:56Z: `judged 14, errors 0, kept 0`; every call ended `end_turn` ([runbook](../../../docs/runbooks/evaluation.md#judge), step 17). The judgments were committed before any review decision.
- **Reviewer, verified on 2026-11-04:** the prompt was frozen at 18:57:31Z ([`eval/judge/frozen-reviewer-prior.json`](../../judge/frozen-reviewer-prior.json)), before any reviewer call. `python -m hindcast.evaluation.reviewer run` judged the 14 answers again from 19:16:35Z to 19:17:19Z: `judged 14, errors 0`, every call `end_turn`. `reviewer apply` wrote the 18 queue decisions at 19:17:50Z, none missing ([runbook](../../../docs/runbooks/evaluation.md#review-and-scores), steps 20 and 21).
- **Scores, verified on 2026-11-04:** `python -m hindcast.evaluation.score` wrote [`scores.json`](scores.json) with no open review item (step 22). Results [below](#results).

## Results

Both models named the root cause of `cloudflare-2025-11-18` in every answer, and abstained on both items for the other three cases. Only the Cloudflare outage began before both models' training cutoffs.

Outcomes after review, as root cause, attack verdict:

| Case | `gpt-6-luna`, 2026-10-25 | `gpt-6-luna`, 2026-11-01 | `gpt-6.1-sol`, 2026-10-25 | `gpt-6.1-sol`, 2026-11-01 |
|---|---|---|---|---|
| `cloudflare-2025-11-18` | hit, hit | hit, hit | hit, hit | hit, hit |
| `github-2026-08-17` | abstained, abstained | abstained, abstained | abstained, abstained | abstained, abstained |
| `google-cloud-2026-07-14` | abstained, abstained | abstained, abstained | abstained, abstained | abstained, abstained |
| `github-2026-10-07` | not asked | abstained, abstained | not asked | abstained, abstained |

Known before evidence: (`gpt-6-luna`, `cloudflare-2025-11-18`) and (`gpt-6.1-sol`, `cloudflare-2025-11-18`). Every run of every arm on that case moves to the [known-before-evidence table](../../reconstruction/showcase-v1/README.md#known-before-evidence).

The judge and the reviewer agree on 17 of the 18 queue items (94.4%, Cohen's kappa 0.89). The one difference: the judge called the 2026-11-01 `gpt-6-luna` root cause on `cloudflare-2025-11-18` a partial, and the reviewer a hit. The pair is known either way, through the 2026-10-25 answer.

## Limits

- The question asks about the postmortem, not this repository. The keys have been public here since 2026-10-27, after both model versions; the [keys README](../../keys/README.md) states what that means for later versions.
- A miss shows that this question did not bring the cause out. It does not show that the model never read the postmortem.
- Four cases and two models: 14 answers. `github-2026-10-07` has one answer per model, the other cases two.
- Two models from one provider decide the outcomes, and no person checks them: the reviewer decides every proposed hit and partial, and a quarter of the rest; the judge's proposal stands on the other items.
- Each answer file records the reasoning effort that was requested (`medium`), not the effort the response reports. A live call on 2026-10-25 showed the response reports an effort (`medium` when none was sent); whether it can differ from the requested one was not checked, and both collections requested the same effort ([issue #4](https://github.com/sindredg/hindcast/issues/4)).

## Files

| File | What it is |
|---|---|
| `README.md` | This page |
| `scores.json` | Per answer: its file, deployment, model version, collection time, case, and reviewed outcomes; the known-before-evidence pairs; and the judge-reviewer agreement over the queue |
| `reviewer/judgments/prior-<date>-<deployment>/<case_id>.json` | The reviewer's second judgment of the same answer, in the same form, made without the judge's proposals |
| `reviews/prior-<date>-<deployment>/<case_id>.json` | The decision on each queue item: the judge's proposal, whether it was sampled, the decision, its time, and the reviewer model and judgment hash it came from |
| `judgments/prior-<date>-<deployment>/<case_id>.json` | The judge's proposal for one answer: an outcome and a reason for the root cause and the attack verdict; the answer file, case, deployment, model version, and collection time; the code commit; the judge's model, effort, output limit, system prompt and input hashes, time, and request ID; the stop reason, usage, and any judge error |

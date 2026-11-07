# 27. A reviewer model decides the review queue

Status: Accepted (2026-11-04).

Changes who decides the judge's proposals in [decision 0006](0006-evaluation-design.md) and [decision 0024](0024-judge-model.md). [Rubric version 3](../../eval/rubric/rubric.md#review) carries the change; queue, outcomes, support rules, and credit stay as version 2 froze them.

## Context

The judge proposed outcomes and support verdicts for the 60 scored runs and the 14 prior-knowledge answers ([worklog](../worklogs/05-evaluation.md#live-runs)). Rubric version 2 sends 898 proposals to a person: every hit and partial, every support verdict on an inference, a quarter of the rest. That is days of reading, and the sealed reveals, up to 2026-11-30, add more. No person had read a scored output, so the rule that a change after reading needs new runs does not apply.

## Options considered

| Option | Decides | The report can say | Cost |
|---|---|---|---|
| A person decides all 898 (version 2) | A person | Judge-person agreement | Days |
| A person decides a sample | The judge | The judge's error rate | Errors outside the sample stay |
| A reviewer model shown the proposal | A second model | Agreement, anchored | Leans on the proposal |
| A reviewer model judges blind; a person checks a sample | A second model | Agreement and error rate | Hours |
| A reviewer model judges blind; no person | A second model | Agreement between two models | No error rate |

## Decision

The last option.

1. **Reviewer.** `claude-fable-5-1` on the Anthropic API; per the [models overview](https://platform.claude.com/docs/en/about-claude/models/overview) and the Models API on 2026-11-04: Active, retirement not sooner than 2027-09-01, training data to June 2026.
2. **Blind second judgment.** Every judged run and prior answer, from the judge's input, never seeing its proposals. Prompts: the judge's frozen prompts less "A person reviews your verdicts.", effort `high`, output limit 64,000 tokens, same schema and checks, no fallback. Frozen before the first call (`eval/judge/frozen-reviewer.json`, `eval/judge/frozen-reviewer-prior.json`).
3. **Decisions.** On each queue item the reviewer's verdict replaces the judge's. The queue is version 2's, same rule and seed. A decision names the reviewer's model and the SHA-256 of its judgment, and is refused if that judgment used other input.
4. **Agreement.** Percent agreement and Cohen's kappa over the queue items.
5. **No person decides or checks a sample.**
6. **Locks.** The judge's locks keep version 2's hash; the score checks each judgment's recorded system-prompt hash and model against its lock. A new judge call needs the judge frozen again on version 3.

## Trade-offs

- Two models from one provider with one cutoff: a shared error goes uncaught, and no person measured the reviewer's error rate. Kappa is agreement, not correctness.
- The reviewer wins every disagreement unchecked.
- Every decision can be repeated from committed files and an API key.
- The quarter sample stays because it was frozen before the runs.
- The headline rests on a model call checked by a second model: weaker than a person, stronger than none.

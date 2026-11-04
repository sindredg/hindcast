# 27. A reviewer model decides the review queue

Status: Accepted (2026-11-04).

Changes who decides the judge's proposals in [decision 0006](0006-evaluation-design.md) and [decision 0024](0024-judge-model.md): a second model, not a person. [Rubric version 3](../../eval/rubric/rubric.md#review) carries the change; the review queue, the outcomes, the support rules, and the credit stay as version 2 froze them.

## Context

The judge proposed an outcome for every key item and a support verdict for every run item of the 60 scored runs, and an outcome on the root cause and the attack verdict for the 14 prior-knowledge answers ([worklog](../worklogs/05-evaluation.md#live-runs)). Rubric version 2 sends 898 of those proposals to a person: every proposed hit and partial, every support verdict on an inference, and a quarter of the rest.

Each item means reading a key item, a run item, and the text the run cited, side by side. 898 of them take days of reading, and the sealed reveals, up to 2026-11-30, add more.

When this was decided, no review decision existed and no person had read a scored output or a judgment's reason. The rubric's rule, that a change after a scored output is read needs a new set of runs, does not apply, so the 60 runs and their judgments stand.

## Options considered

| Option | Who decides a queue item | What the report can say | Cost |
|---|---|---|---|
| A person decides all 898 (version 2) | A person | Agreement between the judge and a person | Days of reading |
| A person decides a random sample; the judge's proposals stand | The judge | The judge's error rate with an interval | Every error outside the sample stays in the scores |
| A reviewer model shown the proposal confirms or changes it | A second model | Agreement, anchored on the proposal | The reviewer leans towards what it is shown |
| A reviewer model judges blind, and a person checks a sample | A second model | Agreement, and the reviewer's error rate | Hours of reading for the sample |
| A reviewer model judges blind, and no person checks | A second model | Agreement between two models | No measured error rate |

## Decision

The last option.

1. **Reviewer.** `claude-fable-5-1` on the Anthropic API, version and settings read from the provider's [models overview](https://platform.claude.com/docs/en/about-claude/models/overview) and the Models API on 2026-11-04: Active, retirement not sooner than 2027-09-01, training data to June 2026. A different model from the judge, positioned for demanding reasoning.
2. **Blind second judgment.** The reviewer judges every judged run and prior answer again, from the same input the judge received, and never sees the judge's proposals. Its prompts are the judge's frozen prompts less one sentence, "A person reviews your verdicts.", with the same rubric sections, effort `high`, output limit of 64,000 tokens, reply schema, and reply checks, and no fallback model. They are frozen before the first reviewer call (`eval/judge/frozen-reviewer.json`, `eval/judge/frozen-reviewer-prior.json`).
3. **Decisions.** For each item in the review queue, the reviewer's outcome or support verdict is the decision and replaces the judge's proposal. The queue is version 2's, with the same rule and seed. Items outside it keep the judge's proposal. A decision names the reviewer's model and the SHA-256 of the judgment it came from, and is refused if that judgment was made on other input.
4. **Agreement.** The report gives percent agreement and Cohen's kappa between the judge and the reviewer over the queue items.
5. **No person decides or checks a sample.**
6. **Locks.** The judge's locks keep rubric version 2's hash: they record what the judge was given. Version 3's title line is part of the judge's system prompt, so the score checks each judgment's recorded system-prompt hash and model against its lock instead of composing the prompt again. A new judge call, such as a sealed reveal's, needs the judge frozen again on version 3.

## Trade-offs

- The scores rest on two models: on their agreement, and on the reviewer where they disagree. Both come from one provider and share a training cutoff, so an error they share goes uncaught, and no person measured how often the reviewer is wrong. Kappa measures agreement, not correctness.
- The reviewer wins every disagreement on a queue item. Judging blind keeps it from leaning on the proposal; nothing checks it in turn.
- Every decision can be repeated from committed files and an API key: the input hashes, the prompts, the locks, and each verdict's reason are in the repository.
- The quarter sample of the rest was sized for a person's time. It stays because it was frozen before the runs, not because it still saves anything.
- Decision 0006 kept the headline number off "an unchecked model call". After this change it rests on a model call checked by a second model, which is weaker than a person's check and stronger than none.

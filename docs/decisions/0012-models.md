# 12. Models: gpt-6-luna investigates, gpt-6.1-sol compares

Status: Accepted (2026-10-26). Changed by [decision 0024](0024-judge-model.md).

## Context

Hindcast needs an investigator, a larger comparison model, and a judge ([decision 6](0006-evaluation-design.md)). The investigator runs on every run and has to quote evidence word for word, refuse when the evidence has no answer, call tools, and return structured output.

Candidates: GA Global Standard deployments in Sweden Central, newest stable version. Deployed: gpt-6-luna 2026-09-22, gpt-6.1-sol 2026-09-29, gpt-5-mini 2025-08-07, grok-4.7 version 1. Measurements use the development outage (`cloudflare-2026-02-20`, ten updates); rule, questions, and event table were merged first ([model selection](../../eval/model-selection/dev-outage-v1/README.md)).

**Timeline, one call per model (2026-10-25).** Every event with its UTC time, nothing else; scored by hand against nine events.

| Deployment | Effort | Events of 9 | Not in the updates | Output tokens |
|---|---|---|---|---|
| gpt-6-luna 2026-09-22 | low | 9 | 0 | 473 |
| gpt-6-luna 2026-09-22 | medium | 9 | 0 | 662 |
| gpt-6.1-sol 2026-09-29 | medium | 9 | 0 | 409 |

Ten short updates do not separate the models.

**Foundry evaluation, one question per call (2026-10-26).** One portal run per model, committed in the [model selection](../../eval/model-selection/dev-outage-v1/README.md) folder. Dataset `dataset-dev-outage-v1` version 1: five questions with the updates as context; four are answered by the updates, the fifth asks for a cause they do not state, so the right answer is a refusal. Prompt: answer only from the text, quote the sentence, say when the text lacks the answer. Default effort. Judge gpt-6.1-sol 2026-09-29, pass threshold 3. Evaluator versions: Groundedness 18, Response completeness 13, Relevance 14, Coherence 13, Similarity 10.

Rule, written first: luna passes if groundedness and completeness are within 1 point of sol's and it answers question 5 with a refusal.

| Result, mean of 5 | gpt-6-luna | gpt-6.1-sol |
|---|---|---|
| Groundedness | 5.0 | 5.0 |
| Response completeness | missing (4.25 over the 4 scored) | 4.4 |
| Relevance | 3.6 | 4.0 |
| Coherence | missing (4.75 over the 4 scored) | 4.6 |
| Similarity | 4.4 | 4.4 |
| Quotes word for word | 6 of 6 | 6 of 6 |
| Answer cost, 5 questions | USD 0.0007 | USD 0.0103 |
| Judge cost, 5 questions | USD 0.090 | USD 0.100 |

Scores and tokens from `summarise_runs.py`; quotes from `check_quotes.py`, after normalising quote marks, whitespace, and trailing punctuation. Costs from token counts and the prices below.

Two of the 25 judge calls in luna's run failed with 401 ([troubleshooting](../troubleshooting.md)): no completeness on question 4, no coherence on question 2. With any score from 1 to 5 on question 4, luna's completeness mean lies between 3.6 and 4.4; the rule needs 3.4. That bound was worked out after the run.

Question 5: both refused. Relevance scored both refusals 2, a fail ([finding](../findings/evaluation.md)). Both scored 3 for completeness on question 3: each named the 20:35 problem and missed the 22:16 update.

Prices per 1M tokens, input / output, Global Standard, short context: gpt-6-luna USD 0.10 / 0.50, gpt-6.1-sol USD 2.00 / 10.00, gpt-5-mini USD 0.25 / 2.00, grok-4.7 USD 2.00 / 6.00. Long context: luna USD 0.20 / 0.75, sol USD 4.00 / 15.00; the list does not say where it starts.

Sources, read 2026-10-26: [retail prices](https://prices.azure.com/api/retail/prices) (`serviceName eq 'Foundry Models'`, `armRegionName eq 'swedencentral'`); `az cognitiveservices model list -l swedencentral`; `az cognitiveservices account deployment list`; [built-in evaluators](https://learn.microsoft.com/azure/foundry/concepts/built-in-evaluators); [model versioning](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/model-versions).

## Options considered

| Option | Investigator | Comparison | Trade-off |
|---|---|---|---|
| A | gpt-6-luna | gpt-6.1-sol | Cheapest; met the rule |
| B | gpt-6.1-sol | gpt-6-luna | Twenty times luna's price |
| C | gpt-6-luna | grok-4.7 | Another vendor at sol's input price; not measured; retires 2027-10-05 |
| D | gpt-5-mini | gpt-6.1-sol | Older; two and a half times luna's input price, four times its output; retires 2027-02-09; not measured |

## Decision

Option A. Luna met the rule at about a sixteenth of sol's answer cost; sol as comparison turns luna's gaps into a measured result. The judge is the comparison deployment until the evaluation milestone confirms it, with every match reviewed by a person; grok-4.7 stays deployed as the other-vendor candidate. Both deployments are pinned with automatic upgrade off (`NoAutoUpgrade`); both versions retire on 2028-03-11.

## Trade-offs

- A smoke test: one row moves a mean by up to 0.8.
- Luna's completeness mean is missing one score; the bound is an argument made after the run.
- Whether luna keeps up on a whole investigation is measured by the comparison runs.
- Sol judged its own answers and shares a vendor with luna.
- Grading cost more than answering: 9 to 11 judge tokens per answer token, USD 0.090 and USD 0.100 against USD 0.0007 and USD 0.0103. The portal showed only luna's answer cost.
- The portal used chat completions after the Responses API refused its `top_p` ([finding](../findings/evaluation.md)); Hindcast calls the Responses API.
- Luna used 605 output tokens for 1,210 characters of answers, sol 320 for 1,371, most likely reasoning ([models](../findings/models.md)). Cost comparisons use measured tokens.
- Global Standard may process a request in any region; the inputs are public.
- With upgrade off, a deployment stops at retirement.

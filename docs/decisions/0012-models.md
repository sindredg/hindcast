# 12. Models: gpt-6-luna investigates, gpt-6.1-sol compares

Status: Accepted (2026-10-26).

## Context

Hindcast needs a chat model for the investigator, a larger model to compare it with, and a judge that proposes finding matches for review ([decision 6](0006-evaluation-design.md)). The investigator runs on every investigation, every baseline run, and every evaluation run, so its token price is paid many times over. It has to quote the evidence word for word, refuse when the evidence has no answer, call function tools, and return structured output.

Candidates had to be generally available as Global Standard deployments in Sweden Central, in the newest stable version. Four are deployed: gpt-6-luna 2026-09-22, gpt-6.1-sol 2026-09-29, gpt-5-mini 2025-08-07, and grok-4.7 version 1. The measurements below use the development outage (`cloudflare-2026-02-20`, ten status updates). The rule, the questions, and the event table were merged before any run ([model selection](../../eval/model-selection/dev-outage-v1/README.md)).

**Timeline, one call per model (2026-10-25).** Task: list every event in the updates with its UTC time, and nothing that is not in them. Scored by hand against nine events counted from the updates.

| Deployment | Effort | Events of 9 | Not in the updates | Output tokens |
|---|---|---|---|---|
| gpt-6-luna 2026-09-22 | low | 9 | 0 | 473 |
| gpt-6-luna 2026-09-22 | medium | 9 | 0 | 662 |
| gpt-6.1-sol 2026-09-29 | medium | 9 | 0 | 409 |

Ten short updates do not separate the models. The difference has to come from the questions and, later, from whole investigations.

**Foundry evaluation, one question per call (2026-10-26).** One portal run per model; the run records, answers, scores, and log excerpts are committed in the [model selection](../../eval/model-selection/dev-outage-v1/README.md) folder. Dataset `dataset-dev-outage-v1` version 1: five questions with the updates as context. Four are answered by the updates. The fifth asks for the cause of the withdrawal, which the updates do not state, so the right answer is a refusal. Prompt: answer only from the text, quote the sentence, say so when the text does not contain the answer. Reasoning effort at the deployment default. Judge gpt-6.1-sol 2026-09-29, pass threshold 3. Evaluators, with the versions the run log names: Groundedness 18, Response completeness 13, Relevance 14, Coherence 13, Similarity 10.

The rule was written before the runs: luna is good enough if its groundedness and completeness scores are within 1 point of sol's and it answers question 5 by saying the updates do not contain the cause, without inventing one.

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

Scores and tokens are from `summarise_runs.py` on the committed results; quotes from `check_quotes.py`. A quote counts as word for word when it appears in the updates after quote marks, whitespace, and trailing punctuation are normalised. Costs are computed from the runs' token counts and the prices below.

Two of the 25 judge calls in luna's run failed with 401 ([troubleshooting](../troubleshooting.md)), so luna has no completeness score on question 4 and no coherence score on question 2. The rule is decided anyway: with any completeness score from 1 to 5 on question 4, luna's mean lies between 3.6 and 4.4, and the rule needs 3.4 or more. This bound was worked out after the run; the rule's text did not cover a missing score.

Question 5, read by hand: both models said the text does not say what change caused the withdrawal and named no cause. Relevance scored both refusals 2, a fail, because the answer does not name a change ([finding](../findings/evaluation.md)). Both scored 3 for completeness on question 3: each named the 20:35 problem and left out the 22:16 update.

Prices per 1M tokens, input / output, Global Standard, short context: gpt-6-luna USD 0.10 / 0.50, gpt-6.1-sol USD 2.00 / 10.00, gpt-5-mini USD 0.25 / 2.00, grok-4.7 USD 2.00 / 6.00. The price list has a separate long-context rate for luna (USD 0.20 / 0.75) and sol (USD 4.00 / 15.00). It does not say where long context starts.

Sources, read 2026-10-26: [Azure retail prices API](https://prices.azure.com/api/retail/prices) (`serviceName eq 'Foundry Models'`, `armRegionName eq 'swedencentral'`); lifecycle and retirement from `az cognitiveservices model list -l swedencentral`; versions, SKU, capacity, and upgrade setting from `az cognitiveservices account deployment list`; [Built-in evaluators](https://learn.microsoft.com/azure/foundry/concepts/built-in-evaluators); [Model versioning in Foundry Models](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/model-versions).

## Options considered

| Option | Investigator | Comparison | Trade-off |
|---|---|---|---|
| A | gpt-6-luna | gpt-6.1-sol | Cheapest investigator; met the rule against sol on the questions |
| B | gpt-6.1-sol | gpt-6-luna | Twenty times luna's input and output price on every run |
| C | gpt-6-luna | grok-4.7 | A comparison from another vendor at sol's input price; not measured on the development outage; retires 2027-10-05 |
| D | gpt-5-mini | gpt-6.1-sol | An older version, two and a half times luna's input price and four times its output price; retires 2027-02-09; not measured on the development outage |

## Decision

Option A. Luna met the rule written before the evaluation, at about a sixteenth of sol's answer cost on the five questions. Sol, as the comparison, shows what a larger model finds on the same cases, which turns luna's gaps into a measured result instead of an assumption.

The judge is the comparison deployment until the evaluation milestone confirms it. A person reviews every match it proposes, so a judge that is also a run subject biases the proposals, not the reported counts. grok-4.7 stays deployed as the candidate for a judge from another vendor.

Both deployments are pinned to their versions with automatic version upgrade turned off (`NoAutoUpgrade`), so every result stays tied to the version that produced it. Both versions retire on 2028-03-11. The embedding model and the model Content Understanding uses are chosen with the retrieval and extraction milestones.

## Trade-offs

- The evaluation is a smoke test: five questions on one outage. One row moves a mean by up to 0.8.
- Luna's completeness mean is missing one score. The rule holds for every value that score could take, but the bound is an argument made after the run, not the check the rule described.
- The timeline task did not separate the models on ten updates. Whether luna keeps up on a whole investigation, where it reads more evidence through tools, is not shown yet. The comparison runs measure it.
- Sol judged both runs, including its own answers. Self-preference would favour sol. Sol and luna also come from the same vendor, which can make sol a lenient grader of luna. A judge from another vendor would test that.
- Grading cost more than answering: 9 to 11 judge tokens per answer token, USD 0.090 and USD 0.100 per run against USD 0.0007 and USD 0.0103 for the answers. The portal's cost estimate showed only luna's answers, and nothing for sol's run. Evaluation budgets count the judge.
- The portal reached both models through chat completions, after the Responses API refused the `top_p` the portal sends ([finding](../findings/evaluation.md)). Hindcast calls the Responses API, so these scores measure the models, not Hindcast's client.
- Luna used more output tokens than sol for shorter answers: 605 tokens for 1,210 characters of answers, against 320 for 1,371. The difference is most likely reasoning, which the run does not report separately. Its price advantage per run is smaller than its price per token suggests ([models](../findings/models.md)). Cost comparisons use measured tokens.
- Both are Global Standard deployments, which may process a request in any Azure region. The inputs are published status updates and postmortems, so no data residency limit applies.
- With automatic upgrade off, a deployment stops working when its version retires instead of moving to a newer one.

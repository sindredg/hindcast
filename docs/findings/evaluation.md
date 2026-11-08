# Evaluation runs

Findings about Foundry evaluation runs in the portal, seen on the [model re-check](../../eval/model-selection/dev-outage-v1/README.md), where the run records, results, and log excerpts are committed.

## What these findings mean

These findings concern the earlier portal-based model check, rather than the final reconstruction comparison. The main lesson is that a platform's headline score needs context:

- **Missing scores can disappear from pass counts.** A successful-looking summary can conceal failed grading calls.
- **The portal uses a different API path and settings.** Its result does not directly measure Hindcast's own execution path.
- **A metric can penalise the desired answer.** Relevance marked a correct refusal as a failure because it could not see that the evidence lacked the answer.
- **Grading has its own cost.** The portal's answer-cost estimate omits the judge's usage.

Hindcast therefore checks individual evaluation records, reports errors explicitly, and evaluates actual application runs. The final [reconstruction comparison](../../eval/reconstruction/showcase-v1/README.md#reading-the-results) explains its separate scoring method and findings. The dated entries below preserve the observations and supporting records.

## An evaluator call that fails drops out of the pass counts (2026-10-26)

**Seen:** in luna's run, two judge calls failed with 401 and returned no score. The run still reports `errored: 0`, four rows passed and one failed. The run page showed "4/4" on the affected rows; the downloaded rows carry no such count.

**Evidence:** tested live, 2026-10-26, `run-luna-dev-outage-v1.json`: `result_counts` `{"total": 5, "passed": 4, "failed": 1, "errored": 0}`, while `per_testing_criteria_results` lists `errored: 1` for Coherence and for ResponseCompleteness. In `results-luna-dev-outage-v1.jsonl`, those two results have `status` `error`, `score` null, and an error message in `sample`. The log excerpt has the two failed calls ("Error during evaluation ... Principal does not have access to API/Operation") and `EVALUATOR_ROW_SUMMARY ... errored_items=2 graded_items=25`.

**For Hindcast:** a headline pass count can hide a missing score. `summarise_runs.py` lists failed calls and reports a mean as missing when a score is; `hindcast.evaluation.foundry` reads scores from the rows and counts a row with a missing score as errored.

**Read more:** [Run evaluations from the portal](https://learn.microsoft.com/azure/foundry/how-to/evaluate-generative-ai-app).

## The portal sends `top_p`, so every answer comes through chat completions (2026-10-26)

**Seen:** a portal run with a model target sends `top_p: 1` and `max_completion_tokens: 16384`. The gpt-6 models refuse `top_p` on the Responses API, so the service retries each question on chat completions. All five questions in both runs.

**Evidence:** tested live, 2026-10-26. Each run record has `data_source.target.sampling_params` `{"top_p": 1, "max_completion_tokens": 16384}`. Each log excerpt has five lines "Responses API call failed, falling back to chat completions", four or five with HTTP 400 "Unsupported parameter: 'top_p' is not supported with this model." (sol's first failed with 401 instead). Also seen on 2026-10-25 (not committed). The portal's model target has no reasoning effort setting.

**For Hindcast:** a portal score measures the model through chat completions with the portal's parameters, not Hindcast's client, which calls the Responses API, sends no `top_p`, and sets the effort. Scores that judge Hindcast come from runs that call Hindcast's code.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning).

## Each evaluator sees only the fields its schema declares (2026-10-26)

**Seen:** the run maps query, context, expected answer, and response to every evaluator, and each drops the fields it does not declare. Relevance sees only the question and the answer.

**Evidence:** tested live, 2026-10-26, both log excerpts: "Removed ['context', 'ground_truth'] from evaluator_configurations for 'Relevance'", and likewise context for Similarity, query and context for Response completeness, the expected answer for Groundedness, and context and expected answer for Coherence.

**For Hindcast:** Relevance cannot know that the evidence lacks an answer, which explains the next finding.

**Read more:** [Retrieval-augmented generation (RAG) evaluators](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/rag-evaluators).

## Relevance fails a correct refusal (2026-10-26)

**Seen:** question 5 asks for a cause the updates do not state. Both models said so. Relevance scored both answers 2, a fail, because they "do not identify the change"; Groundedness, Response completeness, and Similarity scored them 5.

**Evidence:** tested live, 2026-10-26, row 4 of both result files. Also seen on 2026-10-25 (not committed), where correct refusals scored 2 and 3.

**For Hindcast:** Relevance penalises the behaviour Hindcast wants when the evidence has no answer. The model rule does not use it, and the evaluation in milestone 5 does not score refusals with it.

**Read more:** [Retrieval-augmented generation (RAG) evaluators](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/rag-evaluators).

## Similarity sometimes returns no reason, or a reason about its own instructions (2026-10-26)

**Seen:** in sol's run, Similarity returned only a score on question 2, and on question 3 its reason discussed a conflict in its own output instructions. Both rows still have a score.

**Evidence:** tested live, 2026-10-26, `results-sol-dev-outage-v1.jsonl`. Question 2: `{"score":5}`. Question 3: the reason starts "The output used a bare rating token instead of the user-requested JSON schema". Luna's run, same evaluator version, gave a reason about the answers on all five rows. Hypothesis, not checked: the evaluator's prompt asks for a bare number and the service asks for JSON.

**For Hindcast:** Similarity scores can be read; its reasons cannot be cited as the basis of a score.

**Read more:** [Textual similarity evaluators](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/textual-similarity-evaluators).

## Grading costs more than answering (2026-10-26)

**Seen:** the judge used 9 to 11 tokens per token of the answers it graded; on luna's run it cost over a hundred times the answers. The portal's cost estimate covers the answers only, and sol's run shows none.

**Evidence:** tested live, 2026-10-26, token counts from `summarise_runs.py` and the run records, prices from [decision 0012](../decisions/0012-models.md):

| Run | Answers | Judge (gpt-6.1-sol) | Portal estimate |
|---|---|---|---|
| luna | 3,538 / 605 tokens, USD 0.0007 | 35,702 / 1,857 tokens, USD 0.090 | USD 0.000656, target only |
| sol | 3,538 / 320 tokens, USD 0.0103 | 38,759 / 2,216 tokens, USD 0.100 | none |

**For Hindcast:** the evaluation budget is driven by the judge, not the investigator. Costs come from each run's token usage, not the portal's estimate.

**Read more:** [Plan and manage costs for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/manage-costs).

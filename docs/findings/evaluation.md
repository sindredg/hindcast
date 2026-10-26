# Evaluation runs

Findings about Foundry evaluation runs in the portal: what a run sends, what its evaluators see, and what its counts mean. Seen on the [model re-check](../../eval/model-selection/dev-outage-v1/README.md), where the run records, results, and log excerpts are committed.

## An evaluator call that fails drops out of the pass counts (2026-10-26)

**Seen:** in luna's run, two judge calls failed with 401 and returned no score. The run still reports `errored: 0`, four rows passed and one failed. On the run page, each affected row showed a pass over four evaluators instead of five ("4/4"); the downloaded rows carry no such count. Only the per-evaluator counts and the row's results show the failure.

**Evidence:** tested live, 2026-10-26, in `run-luna-dev-outage-v1.json`: `result_counts` `{"total": 5, "passed": 4, "failed": 1, "errored": 0}`, while `per_testing_criteria_results` lists `errored: 1` for Coherence and for ResponseCompleteness. In `results-luna-dev-outage-v1.jsonl`, those two results have `status` `error`, `score` null, and an error message in `sample`. The log excerpt has the two failed calls ("Error during evaluation ... Principal does not have access to API/Operation") and the service's own count: `EVALUATOR_ROW_SUMMARY ... errored_items=2 graded_items=25`.

**For Hindcast:** a headline pass count can hide a missing score. `summarise_runs.py` lists the failed calls and reports a mean as missing when one of its scores is. The evaluation in milestone 5 reads scores from the rows and treats a run with a missing score on a gated metric as incomplete.

**Read more:** [Run evaluations from the portal](https://learn.microsoft.com/azure/foundry/how-to/evaluate-generative-ai-app).

## The portal sends `top_p`, so every answer comes through chat completions (2026-10-26)

**Seen:** a portal run with a model target sends `top_p: 1` and `max_completion_tokens: 16384`. The gpt-6 models refuse `top_p` on the Responses API, so the service retries each question on chat completions, which answers. This happened on all five questions in both runs.

**Evidence:** tested live, 2026-10-26. Each run record has `data_source.target.sampling_params` `{"top_p": 1, "max_completion_tokens": 16384}`. Each log excerpt has five lines "Responses API call failed, falling back to chat completions", four or five of them with HTTP 400 "Unsupported parameter: 'top_p' is not supported with this model." (sol's first one failed with 401 instead). Also seen on an earlier evaluation run on 2026-10-25 (not committed). The portal's model target has no reasoning effort setting, so the deployment default applies.

**For Hindcast:** a portal score measures the model through chat completions with the portal's parameters, not Hindcast's client: `hindcast.models` calls the Responses API, sends no `top_p`, and always sets the effort. Scores that judge Hindcast itself come from runs that call Hindcast's code.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning).

## Each evaluator sees only the fields its schema declares (2026-10-26)

**Seen:** the run maps the query, context, expected answer, and response to every evaluator, and each evaluator drops the fields it does not declare. Relevance sees only the question and the answer: not the context, not the expected answer.

**Evidence:** tested live, 2026-10-26, in both log excerpts: "Removed ['context', 'ground_truth'] from evaluator_configurations for 'Relevance'", and likewise context for Similarity, query and context for Response completeness, the expected answer for Groundedness, and context and expected answer for Coherence.

**For Hindcast:** an evaluator can only judge what it receives. Relevance cannot know that the evidence lacks an answer, which explains the next finding.

**Read more:** [Retrieval-augmented generation (RAG) evaluators](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/rag-evaluators).

## Relevance fails a correct refusal (2026-10-26)

**Seen:** question 5 asks for a cause the updates do not state. Both models said so and named no cause. Relevance scored both answers 2, a fail, because they "do not identify the change". Groundedness, Response completeness, and Similarity scored the same answers 5.

**Evidence:** tested live, 2026-10-26, row 4 of both result files. Also seen on an earlier evaluation run on 2026-10-25 (not committed), where correct refusals scored 2 and 3.

**For Hindcast:** Relevance penalises the behaviour Hindcast wants when the evidence has no answer. The model rule does not use it, and the evaluation in milestone 5 does not score refusals with it.

**Read more:** [Retrieval-augmented generation (RAG) evaluators](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/rag-evaluators).

## Similarity sometimes returns no reason, or a reason about its own instructions (2026-10-26)

**Seen:** in sol's run, the Similarity judge returned only a score on question 2. On question 3 its reason discussed a conflict in its own output instructions instead of comparing the two answers. Both rows still have a score.

**Evidence:** tested live, 2026-10-26, `results-sol-dev-outage-v1.jsonl`. Question 2, judge output `{"score":5}`. Question 3, the reason starts "The output used a bare rating token instead of the user-requested JSON schema". Luna's run, same evaluator version, gave a reason about the answers on all five rows. Hypothesis, not checked: the evaluator's prompt asks for a bare number and the service asks for JSON.

**For Hindcast:** Similarity scores can be read; its reasons cannot be cited as the basis of a score.

**Read more:** [Textual similarity evaluators](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/textual-similarity-evaluators).

## Grading costs more than answering (2026-10-26)

**Seen:** the judge used 9 to 11 tokens for every token of the answers it graded. On luna's run the judge cost over a hundred times the answers. The portal's cost estimate covers the answers only, and sol's run shows no estimate at all.

**Evidence:** tested live, 2026-10-26, token counts from `summarise_runs.py` and the run records, prices from [decision 0012](../decisions/0012-models.md):

| Run | Answers | Judge (gpt-6.1-sol) | Portal estimate |
|---|---|---|---|
| luna | 3,538 / 605 tokens, USD 0.0007 | 35,702 / 1,857 tokens, USD 0.090 | USD 0.000656, target only |
| sol | 3,538 / 320 tokens, USD 0.0103 | 38,759 / 2,216 tokens, USD 0.100 | none |

**For Hindcast:** the evaluation budget in milestone 5 is driven by the judge, not the investigator. The portal's estimate is not a budget figure; costs come from each run's token usage.

**Read more:** [Plan and manage costs for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/manage-costs).

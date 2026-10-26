# Model selection on the development outage, dataset `dev-outage-v1`

The evidence behind [decision 0012](../../../docs/decisions/0012-models.md): whether gpt-6-luna is good enough to investigate, measured against gpt-6.1-sol on the development case `cloudflare-2026-02-20` (Cloudflare status incident `kwy3dt82bwbt`, 10 updates).

## Written before the runs

**Rule:** luna is good enough if its groundedness and completeness scores are within 1 point of sol's and it answers question 5 by saying the updates do not contain the cause, without inventing one.

**Questions:** `questions-v1.jsonl`, five questions with the expected answer. Four are answered by the updates. The fifth asks for the cause of the withdrawal, which the updates do not state, so the right answer is a refusal.

**Evidence given to the models:** every status update before the one marked resolved, plus the resolved update's time and status with its text withheld (`build_dataset.py`). The text is the same for every model and every question.

**Timeline events, counted by hand from the updates:** an event is an update that reports something new: a status change, a finding, an action, a workaround, or a new problem. Repeats are not events.

| # | Time (UTC, 2026-02-20) | Event |
|---|---|---|
| 1 | 18:45 | Investigation opened: errors or timeouts reaching Cloudflare's network or services |
| 2 | 19:09 | Impact identified on a subset of BYOIP prefixes |
| 3 | 19:09 | Underlying issue identified and mitigated; advertisements being restored |
| 4 | 19:20 | Customers can restore service themselves by readvertising prefixes from the dashboard |
| 5 | 20:35 | Some customers cannot reload their IPs through the dashboard; fix in progress |
| 6 | 20:50 | Customers who withdrew their IPs will see them withdrawn once mitigation completes |
| 7 | 22:16 | The last subset of prefixes cannot be mitigated by toggling advertisement on the dashboard |
| 8 | 23:38 | Remaining prefixes restored to their previous state; monitoring |
| 9 | 23:50 | Incident resolved |

A model's timeline is scored by hand against this table: events found, events missed, and events that are not in the updates.

## Results

### Timeline, one call per model (API, 2026-10-25)

`compare_timeline.py` sent the evidence above with the instruction to list every event with its UTC time and nothing that is not in the updates. Scored by hand against the event table. Answers are kept locally, not committed (they repeat Cloudflare's text).

| Deployment | Effort | Events found (of 9) | Not in the updates | Input tokens | Output tokens |
|---|---|---|---|---|---|
| gpt-6-luna 2026-09-22 | low | 9 | 0 | 693 | 473 |
| gpt-6-luna 2026-09-22 | medium | 9 | 0 | 693 | 662 |
| gpt-6.1-sol 2026-09-29 | medium | 9 | 0 | 693 | 409 |

All three listed every update in order, including the two that repeat earlier ones, and none added a cause. On ten short updates the task does not separate the models: the difference has to come from the five questions and, later, from whole investigations.

### Foundry evaluation, five questions (portal, 2026-10-26)

One evaluation run per model in the Foundry portal: luna at 18:11 UTC (41 seconds), sol at 18:13 UTC (44 seconds). The run records, answers, scores, and log lines are committed here, sanitized (see Files).

- **Dataset:** `dataset-dev-outage-v1` version 1, uploaded from the file `build_dataset.py` writes (SHA-256 starting `b76a883bd24595a5`). The queries and expected answers in both result files equal `questions-v1.jsonl`.
- **Models:** gpt-6-luna 2026-09-22 and gpt-6.1-sol 2026-09-29, read from each row's `sample.model`. Reasoning effort not set, so the deployment default applies.
- **Prompt:** in each run record under `data_source.input_messages`: answer only from the text, quote the sentence, say so when the text does not contain the answer.
- **Judge and evaluators:** gpt-6.1-sol 2026-09-29 for every evaluator, pass threshold 3. Versions from the log excerpts: Groundedness 18, Response completeness 13, Relevance 14, Coherence 13, Similarity 10 (registry `azureml`).

Scores per question, luna / sol, on a scale of 1 to 5. "Error" means the judge call failed and returned no score.

| Question | Groundedness | Completeness | Relevance | Coherence | Similarity |
|---|---|---|---|---|---|
| 1. First affected customers | 5 / 5 | 5 / 5 | 4 / 4 | 5 / 4 | 5 / 5 |
| 2. What customers could do | 5 / 5 | 4 / 5 | 4 / 5 | error / 5 | 4 / 5 |
| 3. Problem with that fix | 5 / 5 | 3 / 3 | 4 / 4 | 5 / 5 | 3 / 3 |
| 4. Restored and resolved | 5 / 5 | error / 4 | 4 / 5 | 5 / 5 | 5 / 4 |
| 5. Cause, not in the updates | 5 / 5 | 5 / 5 | 2 / 2 | 4 / 4 | 5 / 5 |
| Mean | 5.0 / 5.0 | missing / 4.4 | 3.6 / 4.0 | missing / 4.6 | 4.4 / 4.4 |

**Rule: met.**

- Groundedness: 5.0 against 5.0.
- Completeness: luna's score on question 4 is missing, so `summarise_runs.py` reports its mean as missing and exits 1. The rule is still decided: with any score from 1 to 5 on question 4, luna's mean lies between 3.6 and 4.4, and the rule needs 3.4 or more (sol's 4.4 minus 1). The rule's text did not say how to treat a missing score; this bound was worked out after the run, and it holds for every value the score could take.
- Question 5: both answers say the text does not say what change caused the withdrawal, and name no cause.

**Quotes:** `check_quotes.py --no-quote-ok 4` found 6 of 6 quotes word for word in each run, exit code 0. With `--break-row 0` it reports 5 of 6 and exits 1, for each run.

**Tokens and cost**, from `summarise_runs.py`, at the prices in [decision 0012](../../../docs/decisions/0012-models.md):

| | luna run | sol run |
|---|---|---|
| Answers: input / output tokens | 3,538 / 605 | 3,538 / 320 |
| Answers: cost | USD 0.0007 | USD 0.0103 |
| Judge calls | 25, of which 2 failed | 25 |
| Judge: input / output tokens | 35,702 / 1,857 | 38,759 / 2,216 |
| Judge: cost | USD 0.090 | USD 0.100 |

Luna's answers cost about a sixteenth of sol's: a twentieth of the price per token, but 1.9 times the output tokens. Grading cost more than answering in both runs.

### What the runs showed

- Both models answered every question from the updates, quoted word for word, and refused question 5. Where both have a completeness score, they differ by at most one point per question.
- Both missed the second half of question 3: they named the 20:35 problem (customers could not reload their IPs) and left out the 22:16 update (the last prefixes could not be mitigated from the dashboard). The question asks for one problem and the expected answer has two; the question could be clearer.
- Relevance gave both correct refusals a 2, a fail. The rule does not use Relevance.
- The first attempt failed on every row with 401, and three calls in these runs failed with 401 after the fix: [troubleshooting](../../../docs/troubleshooting.md).
- What the platform did during the runs (the `top_p` fallback, dropped fields, pass counts that skip errors, Similarity reasons) is recorded in [findings: evaluation](../../../docs/findings/evaluation.md).

## Files

| File | What it is |
|---|---|
| `questions-v1.jsonl` | The five questions and expected answers. Frozen before the runs. |
| `compare_timeline.py` | One timeline call per deployment and effort; prints token usage. |
| `build_dataset.py` | Builds the upload file `data/sources/model-selection/dataset-dev-outage-v1.jsonl` (ignored by Git) by adding the status text as `context`. The status text is Cloudflare's and is not committed. |
| `run-<model>-dev-outage-v1.json` | The run record from the run page's "Raw JSON": status, prompt, target, sampling parameters, result counts, and token usage per model. Without the person who ran it and the portal link. |
| `results-<model>-dev-outage-v1.jsonl` | One row per question: the answer, each evaluator's score and reason, and the judge's tokens. Every copy of the status text is `<context withheld>`. |
| `log-excerpt-<model>-dev-outage-v1.txt` | The log lines the findings cite: evaluator versions, dropped fields, the chat completions fallback, and failed judge calls with the service's count of them. |
| `sanitize_results.py` | Turns one run's downloads into the three files above. Every copy of the status text becomes `<context withheld>`, at every level of JSON encoding. Run and evaluation IDs and resource names become placeholders. Writes nothing if a copy of the status text or an identifier is left. |
| `check_quotes.py` | Checks that every quote in a run's answers appears word for word in the updates. A quote that is empty after normalising counts as not found. |
| `summarise_runs.py` | Prints each run's score per question and evaluator, the means, the evaluator calls that failed, the answer and judge tokens, and the score part of the rule. With two runs, exit code 1 when the score part is not met or a score is missing. |

The procedure to run it again is in the [runbook](../../../docs/runbooks/foundations.md#re-check-the-model-choice).

## Status

Tested live on 2026-10-26: both runs above, read with the scripts in this folder. The rule, the questions, and the event table were merged to `main` before the runs, in `15a6d3f` (2026-10-25); none has changed since. The decision is [0012](../../../docs/decisions/0012-models.md).

## Licence

The questions and expected answers are this project's. They paraphrase Cloudflare's status updates for incident `kwy3dt82bwbt` (Cloudflare status page), which are not redistributed here. The committed answers quote single sentences from those updates, as the prompt asked; the updates themselves are withheld in every file.

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

## Files

| File | What it is |
|---|---|
| `questions-v1.jsonl` | The five questions and expected answers. Frozen before the runs. |
| `compare_timeline.py` | One timeline call per deployment and effort; prints token usage. |
| `check_quotes.py` | Checks that every quote in a run's answers appears word for word in the updates. Tested on hand-made rows in the portal's result format, not on a real run yet. |
| `build_dataset.py` | Builds the upload file `data/sources/model-selection/dataset-dev-outage-v1.jsonl` (ignored by Git) by adding the status text as `context`. The status text is Cloudflare's and is not committed. |
| `sanitize_results.py` | Turns one run's downloads into the files committed here. Every copy of the status text becomes `<context withheld>`, at every level of JSON encoding. Run and evaluation IDs and resource names become placeholders. The log keeps only the lines the findings cite. Writes nothing if a copy of the status text or an identifier is left. Tested on hand-made rows and on the downloads of an earlier evaluation run, not on these runs yet. |
| `summarise_runs.py` | Prints each run's score per question and evaluator, the means, the answer and judge tokens, and the score part of the rule. Exit code 1 when the score part is not met or a score is missing. |

## Status

The rule, the questions, and the event table were committed before the Foundry evaluation runs. The runs on the five questions are open; their results, the quote check, and the decision follow in this folder and in [decision 0012](../../../docs/decisions/0012-models.md).

## Licence

The questions and expected answers are this project's. They paraphrase Cloudflare's status updates for incident `kwy3dt82bwbt` (Cloudflare status page), which are not redistributed here.

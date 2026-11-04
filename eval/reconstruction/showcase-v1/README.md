# Reconstruction evaluation, showcase v1

The scored reconstructions of the four showcase cases: each arm of [decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md) run three times per case, scored against the frozen keys and labels by the [rubric](../../rubric/rubric.md). The rubric's scores, with their error analysis, come here once the runs are judged and reviewed; the Foundry cloud evaluation's numbers are below.

## Status

- **Frozen before any scored run:** the inferable-from-evidence labels on 2026-11-03, and the rubric (version 2) with the timeline tolerance of 30 minutes on 2026-11-04, with the keys frozen earlier. Version 2 replaced version 1, frozen on 2026-11-03, before any run used it. [`eval/rubric/frozen.json`](../../rubric/frozen.json) records their hashes, and `tests/test_rubric.py` fails if any of them changes.
- **Runs, verified on 2026-11-04:** 60 scored runs, 03:10:48Z to 04:00:47Z, live, with `python -m hindcast.evaluation.batch run` ([runbook](../../../docs/runbooks/evaluation.md#scored-runs), steps 9 and 10). Every slot filled on its first attempt: 60 entries in `attempts.json`, all `complete`, none `no-result`.
- **Foundry cloud evaluation, verified on 2026-11-04:** repeat 1 of each arm and case, completed at 04:28:33Z ([below](#foundry-cloud-evaluation)).
- **Judge:** prompt version 1 frozen on 2026-11-04 ([`eval/judge/frozen.json`](../../judge/frozen.json)), before any judge call and before any run output was read. Not run yet.
- **Review and scores:** open.

## Dataset

| Part | Where | Frozen |
|---|---|---|
| Cases | `cloudflare-2025-11-18`, `github-2026-08-17`, `google-cloud-2026-07-14`, `github-2026-10-07` in [`data/cases.yaml`](../../../data/cases.yaml) | The registry pins each source by SHA-256 |
| Answer keys | [`eval/keys/`](../../keys/README.md) | SHA-256 per key in `eval/keys/frozen.json` |
| Labels | [`eval/keys/labels/`](../../keys/labels/README.md) | SHA-256 per file in `eval/keys/labels/frozen.json` |
| Rubric | [`eval/rubric/rubric.md`](../../rubric/rubric.md) | SHA-256 in `eval/rubric/frozen.json` |

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

## Files

| File | What it is |
|---|---|
| `README.md` | This page |
| `attempts.json` | One entry per attempt: run ID, arm, case, repeat, attempt, status, reason, result file and its SHA-256, usage, cost, agent, model, code commit |
| `runs/<arm>/<case_id>/r<repeat>-a<attempt>-<UTC time>.json` | One result per run, as `python -m hindcast.evaluation.batch` writes it |
| `foundry/runs.json` | The Foundry evaluation's judge deployment, datasets with their SHA-256, evaluation and run IDs, and criteria |
| `foundry/results.json` | Per arm and evaluator: rows passed, failed, and errored, and the mean score, with the service's own counts |

# Reconstruction evaluation, showcase v1

The scored reconstructions of the four showcase cases: each arm of [decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md) run three times per case, scored against the frozen keys and labels by the [rubric](../../rubric/rubric.md). The report, with its results and error analysis, comes here once the runs are judged and reviewed.

## Status

Frozen before any scored run: the inferable-from-evidence labels on 2026-11-03, and the rubric (version 2) with the timeline tolerance of 30 minutes on 2026-11-04, with the keys frozen earlier. Version 2 replaced version 1, frozen on 2026-11-03, before any run used it. [`eval/rubric/frozen.json`](../../rubric/frozen.json) records their hashes, and `tests/test_rubric.py` fails if any of them changes. No scored run has been made.

## Dataset

| Part | Where | Frozen |
|---|---|---|
| Cases | `cloudflare-2025-11-18`, `github-2026-08-17`, `google-cloud-2026-07-14`, `github-2026-10-07` in [`data/cases.yaml`](../../../data/cases.yaml) | The registry pins each source by SHA-256 |
| Answer keys | [`eval/keys/`](../../keys/README.md) | SHA-256 per key in `eval/keys/frozen.json` |
| Labels | [`eval/keys/labels/`](../../keys/labels/README.md) | SHA-256 per file in `eval/keys/labels/frozen.json` |
| Rubric | [`eval/rubric/rubric.md`](../../rubric/rubric.md) | SHA-256 in `eval/rubric/frozen.json` |

## Files

| File | What it is |
|---|---|
| `README.md` | This page |

The batch adds `attempts.json`, one entry per attempt, and `runs/<arm>/<case_id>/r<repeat>-a<attempt>-<UTC time>.json`, one result per run (`python -m hindcast.evaluation.batch`).

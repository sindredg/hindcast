# Inferable-from-evidence labels

One label file per scored case: for each scored key item, whether the case's evidence states it, supports reaching it through a written step, or cannot reach it ([decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md)). An abstention earns credit only on an item labelled `not inferable`. The keys stay as frozen; the labels sit next to them.

## Status

Four label files frozen on 2026-11-03, before any scored run, and one at a reveal; each label approved by a person, from the keys and the evidence, never from a run's output. A sealed case is labelled at its reveal, before its sealed file is opened ([decision 0022](../../../docs/decisions/0022-sealed-drop-date-and-offline-reveal.md)): `github-2026-11-04-actions` on 2026-11-07, approved and frozen before `python -m hindcast.reveal` read its seals.

[`frozen.json`](frozen.json) records each file's SHA-256; `tests/test_labels.py` fails if a label file changes or is not frozen. A changed label is a new approval, not an edit.

| Case | Stated | Inferable | Not inferable |
|---|---|---|---|
| `cloudflare-2025-11-18` | 6 | 0 | 14 |
| `github-2026-08-17` | 3 | 0 | 4 |
| `google-cloud-2026-07-14` | 3 | 2 | 3 |
| `github-2026-10-07` | 4 | 0 | 5 |
| `github-2026-11-04-actions` | 1 | 0 | 10 |

The attack verdict is `inferable` where an update names a cause that settles it, `not inferable` where none does.

## Fields

| Field | Meaning |
|---|---|
| `case_id` | The case, matching its key and its evidence |
| `items[].item` | `attack`, `root_cause`, `contributing_factors/<i>`, or `timeline/<i>`: every scored key item exactly once. Fixes are not scored and have no label |
| `items[].label` | `stated` (an update before the resolved one says it, or the resolved update's time and status, which the investigator sees without its text; issue #66), `inferable` (reachable through a written step), or `not inferable` (needs information the evidence does not hold) |
| `items[].reason` | One line on why |
| `items[].evidence` | The update and chart IDs the reason rests on; `stated` and `inferable` need at least one |

"Evidence" is the case's status updates and charts. A library document is a lead, never evidence, so a label never cites it. A step to an `inferable` item may use general engineering knowledge.

## Checks

`hindcast.labels` refuses a label file that:

- misses a scored item, names an unknown one, or names one twice
- uses a label outside the three, or an empty reason
- cites an ID not in the case's evidence, or cites nothing for `stated` or `inferable`
- labels `stated` an item the key marks not stated during the incident, or labels anything else an item the key marks stated

The attack verdict has no `stated_during_incident` flag in the key, so its label is not checked against one.

## Files

| File | What it is |
|---|---|
| [`cloudflare-2025-11-18.json`](cloudflare-2025-11-18.json) | Scored case |
| [`github-2026-08-17.json`](github-2026-08-17.json) | Scored case |
| [`google-cloud-2026-07-14.json`](google-cloud-2026-07-14.json) | Scored case |
| [`github-2026-10-07.json`](github-2026-10-07.json) | Scored case |
| [`github-2026-11-04-actions.json`](github-2026-11-04-actions.json) | Revealed sealed case |
| [`frozen.json`](frozen.json) | SHA-256 of each label file |

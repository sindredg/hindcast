# Inferable-from-evidence labels

One label file per scored case: for each scored key item, whether the case's evidence states it, supports reaching it through a written step, or cannot reach it ([decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md)). The evaluation credits an abstention only on an item labelled `not inferable`. The keys stay as they were frozen; the labels sit next to them.

## Status

Written: `hindcast.labels` and its checks. No label is frozen yet. Each label is approved by a person and frozen before the first scored run.

`frozen.json`, once written, records each file's SHA-256, and `tests/test_labels.py` fails if a label file changes or is not frozen. A changed label is a new approval, not an edit.

## Fields

| Field | Meaning |
|---|---|
| `case_id` | The case, matching its key and its evidence |
| `items[].item` | `attack`, `root_cause`, `contributing_factors/<i>`, or `timeline/<i>`: every scored key item exactly once. Fixes are not scored, so they have no label |
| `items[].label` | `stated` (an update before the resolved one says it), `inferable` (the evidence supports reaching it through a written step), or `not inferable` (it needs information the evidence does not hold) |
| `items[].reason` | One line on why |
| `items[].evidence` | The update and chart IDs the reason rests on; `stated` and `inferable` need at least one |

"Evidence" is the case's status updates and charts. A library document is a lead, never evidence, so a label never cites it. A step to an `inferable` item may use general engineering knowledge.

## Checks

`hindcast.labels` refuses a label file that:

- misses a scored item, names an unknown one, or names one twice
- uses a label outside the three, or an empty reason
- cites an ID that is not in the case's evidence, or cites nothing for `stated` or `inferable`
- labels `stated` an item the key marks not stated during the incident, or labels anything else an item the key marks stated

The attack verdict has no `stated_during_incident` flag in the key, so its label is not checked against one.

## Files

| File | What it is |
|---|---|
| `README.md` | This page |

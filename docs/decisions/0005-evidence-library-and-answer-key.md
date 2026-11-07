# 5. Evidence, library, and answer key: fixed cut rules that fail closed

Status: Accepted (2026-10-25).

## Context

An investigator that reads the postmortem or the provider's cause summary is scored on summarising. The answer leaks elsewhere too: the resolved update often states the cause (GitHub, Google Cloud), Google Cloud appends incident reports to the incident record, and the library could hold the case's postmortem or a later one that refers to it. The cut has to be deterministic, testable, and safe for an unseen format.

## Options considered

| Option | How | Risk |
|---|---|---|
| A. Fixed rules, fail closed | Evidence is every update before the resolved one, plus the resolved update's time and status with its text withheld. Report entries and unknown entry types are dropped and listed. The library returns only documents published before the outage and none about the case. A leak check compares key, evidence, and filtered library before any scored run | Facts stated only in the resolved update are lost |
| B. Keep the resolved update | The whole status page | The cause is stated there |
| C. A model labels revealing updates | A model decides | Not deterministic; one wrong label leaks |
| D. A plus a sentence filter | Removes sentences close to a key statement | Removes true facts the provider stated |

## Decision

Option A: deterministic, testable, and wrong only toward withholding. A fact the provider stated during the incident is evidence; the key marks such facts so the report can say what the public already knew.

## Trade-offs

- Scores are a lower bound.
- Entry rules are per provider; a new format needs review before scoring.
- The leak check catches near-copies, not an update that implies the cause. Each report names that risk.
- A case where the provider named the cause is easier; the report says so per case.
- Prior knowledge is the prior-knowledge check's job, not the cut's.

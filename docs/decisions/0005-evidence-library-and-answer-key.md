# 5. Evidence, library, and answer key: fixed cut rules that fail closed

Status: Accepted (2026-10-25).

## Context

Hindcast scores its reconstruction against the provider's postmortem. If the investigator can read the postmortem, or the provider's own summary of the cause, the score measures how well it summarises the answer, not how well it investigates.

The answer leaks in more places than the postmortem itself:

- The update that marks an incident resolved often carries a root-cause summary. GitHub's and Google Cloud's do.
- Google Cloud appends a preliminary and a full incident report to the same incident record as its live updates.
- The library could hold the case's own postmortem, or a later one that refers back to it.

So the evidence and the library are cut before the investigator sees them. The cut has to be deterministic, testable, and safe for a provider format it has not seen before.

## Options considered

| Option | How it works | Risk |
|---|---|---|
| A. Fixed cut rules, fail closed | Case evidence is every update before the resolved one, plus the resolved update's time and status with its text withheld. Any entry that is itself a report is dropped; an entry type the rules do not know is dropped and listed for review. The library returns only documents published before the outage began and none about the case. A leak check compares the answer key with the evidence and the filtered library before any scored run | Facts stated only in the resolved update are lost, so scores lean pessimistic |
| B. Keep the resolved update in full | Everything the status page showed is evidence | GitHub and Google Cloud state the cause there, so scores are inflated |
| C. A model decides which updates reveal the cause | A language model labels each update | Not deterministic; one wrong label leaks the answer, and every label still needs review |
| D. Option A plus a sentence filter | Also removes evidence sentences that closely match an answer-key statement | Removes true facts the provider stated during the incident, hiding real evidence from the investigator |

## Decision

Option A. It is deterministic, it can be tested with fixed inputs, and when it is wrong it errs toward withholding evidence, which lowers scores instead of inflating them.

A fact the provider stated publicly during the incident is legitimate evidence. The answer key marks such facts, so the evaluation report can say which parts of a reconstruction the provider had already told the public.

## Trade-offs

- Scores are a lower bound on what the investigator could do with everything the status page showed.
- The report-entry rules are per provider. A new provider, or a new entry format from a known one, needs its entries reviewed before its cases can be scored.
- The leak check catches near-copies of answer-key text. It does not catch an update that implies the cause without stating it; that residual risk is named in each evaluation report.
- A case where the provider named the cause during the incident is easier than one where it did not, and the evaluation report says so per case.
- What the model already knew about a case is a separate risk, handled by the prior-knowledge check, not by the cut.

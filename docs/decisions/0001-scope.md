# 1. Scope: an investigator over public outage records

Status: Accepted (2026-10-25).

## Context

Scoring needs a reference answer not written by the model. Providers publish two records of an outage: the status page, what an outsider saw at the time, and the postmortem, days later, with the root cause. Status updates rarely say whether it was an attack. Fixed budget, short schedule, nothing deployed after the demo, no cases with harm to people or leaked personal data.

## Options considered

| Option | Reference | Cost |
|---|---|---|
| A. Investigator over provider outages: status updates as evidence, earlier postmortems as a library, the postmortem as the key | The postmortem | Pay-per-use only |
| B. Simulated intrusions in a fictional company | The scenario | Public sets publish answers; a self-built scenario grades data the project wrote |
| C. A without the library | As in A | Search and extraction have nothing to do |
| D. Live monitoring of status pages | None until a postmortem, often weeks later | Always-on polling |

## Decision

Option A. Every reconstruction starts with an attack assessment (attack, not an attack, cannot tell), then the timeline, root cause, contributing factors, and open questions.

A case qualifies when:

- nobody was hurt and no personal data leaked
- the postmortem names no attacker beyond what the provider states
- at least eight timestamped updates came before the incident was resolved
- the postmortem states a root cause
- for a scored recent case, the outage began after the training cutoff of every model scored on it

## Trade-offs

- Finished incidents only; Hindcast detects nothing.
- The key is the provider's account, not an independent one.
- Most outages are not attacks, so "not an attack" always scores well. The attack assessment is reported per case with its reasoning, not as an accuracy rate.
- The pages are copyrighted: the repository holds URLs, retrieval times, hashes, and a capture command; the pages stay private.
- Google Cloud's feed keeps recent incidents only, so its cases are captured early.

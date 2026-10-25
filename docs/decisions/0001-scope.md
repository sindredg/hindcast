# 1. Scope: an investigator over public outage records

Status: Accepted (2026-10-25).

## Context

Hindcast has to show that its reconstructions are right, not only that they read well. That needs a reference answer for each case, written by someone other than the model, to score the output against.

Large providers publish two records of an outage. The status page shows what they said while it was happening. The postmortem, published days later, gives the root cause. The first is what an outside engineer could see at the time; the second is the answer key. The question an outside engineer asks first is whether it was an attack, and the status updates rarely say.

The project runs on a fixed budget and a short schedule, with no quota increases. Nothing stays deployed after the demo is recorded. Cases must not involve people who were hurt or whose personal data leaked.

## Options considered

| Option | Reference to score against | Cost and effort |
|---|---|---|
| A. Investigator over provider outages: the live status updates as case evidence, earlier public postmortems as a reference library, the provider's own postmortem as the answer key | The provider's postmortem | Pay-per-use services only; nothing runs between investigations |
| B. Simulated intrusions in a fictional company, from a public security-operations training set or a self-built scenario | The scenario's ground truth | Public sets publish their answers or need their own platform to read; a self-built scenario means grading data the project wrote |
| C. Option A without the library | As in A | Least work, but a case has tens of short updates: search and document extraction have nothing to do, and an agent-versus-single-prompt comparison measures tool overhead |
| D. Live monitoring of status pages, investigating outages as they happen | None until a postmortem appears, often weeks later | Always-on polling for an answer that arrives after the project ends |

## Decision

Option A. Each case has an answer key written by the provider, and the library gives retrieval real work: an engineer reading an outage looks for similar failures in earlier postmortems.

Every reconstruction starts with an attack assessment (attack, not an attack, cannot tell), then the timeline, the most likely root cause, contributing factors, and open questions.

A case qualifies when:

- nobody was hurt and no personal data leaked
- the postmortem names no attacker beyond what the provider states
- at least eight timestamped updates came before the incident was resolved
- the postmortem states a root cause
- for a scored recent case, the outage began after the training cutoff of every model that is scored on it

## Trade-offs

- Hindcast works on finished incidents. It does not detect anything, and its value is in making a reconstruction checkable, not in early warning.
- The answer key is the provider's own account. It is the best available reference, not an independent one.
- Most outages are not attacks. A model that always answers "not an attack" scores well on that item, so the attack assessment is reported per case with its reasoning, not as an accuracy rate.
- Status pages and postmortems are copyrighted. The repository holds their URLs, retrieval times, and hashes, and a capture command; the pages stay in private storage.
- Archives differ by provider. Google Cloud's status feed keeps recent incidents only, so its cases are captured early.

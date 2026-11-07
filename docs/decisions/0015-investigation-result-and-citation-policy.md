# 15. Investigation result: keep and mark unsupported items, lock scored cases in code

Status: Accepted (2026-10-30). Changed by [decision 0021](0021-screens-pii-and-challenge.md).

Sealed cases: [decision 0017](0017-sealed-reconstructions.md). Library citations: [decision 0020](0020-library-citations.md).

## Context

Every item cites what it rests on, and [decision 0006](0006-evaluation-design.md) scores an item as supported only when its evidence states it. The roadmap requires that a bad citation is rejected with a reason and the rest survives. Open: what happens to an item whose citations are all rejected, and what stops a scored case from running before the rubric exists, which would let the rubric drift towards the output, the risk the [prior-knowledge check](../architecture/README.md#the-prior-knowledge-check) guards against.

## Options considered

| Question | Option | Cost |
|---|---|---|
| An item without support | Drop it | Hides the claim the evaluation needs to count |
| | Keep it, list it in `checks.unsupported` | The checks have to be read next to the items |
| | Refuse the whole result | One bad citation loses a run |
| The scored-case lock | By convention | Nothing checks it |
| | In code: refuse until `eval/rubric/frozen.json` exists | One file to write; a test covers both directions |

## Decision

Keep and mark. A rejected citation is removed from its item and listed in `checks.rejected_citations` with where and why: `malformed`, `unknown`, `other-case`, or `unknown-finding`. An item with no valid citation and no valid `rests_on` stays and is listed in `checks.unsupported`. The attack verdict is never dropped. `checks` is written by the app.

Lock in code. `python -m hindcast.investigate` refuses a case whose role is not `development` or `injection` until `eval/rubric/frozen.json` exists, before any model call.

The result follows `hindcast.result`: the investigation under a strict JSON schema, with the case, agent name and version, model name and version read from the deployment, provenance (prompt blob hash or SHA-256 with a dirty flag, code commit with a dirty flag, evidence SHA-256), status and reason, checks, and usage. Findings carry `kind` (`observation` or `inference`) and `rests_on`; timeline events carry `time_kind` (`stated` or `inferred`).

## Trade-offs

- A citation check proves a reference resolves, not that the evidence says what the item claims. That is milestone 5's support rule.
- An unsupported item reaches the file and the interface, which has to show the mark.
- Writing `eval/rubric/frozen.json` by hand unlocks the cases; an early one shows in the history.
- A dirty tree is recorded, not refused. Milestone 5 decides whether scored runs refuse it.

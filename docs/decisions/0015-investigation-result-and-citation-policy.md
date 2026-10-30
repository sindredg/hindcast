# 15. Investigation result: keep and mark unsupported items, lock scored cases in code

Status: Accepted (2026-10-30).

## Context

The investigator returns a structured reconstruction: an attack verdict, findings, a timeline, a root cause, contributing factors, and open questions. Every item cites what it rests on. [Decision 0006](0006-evaluation-design.md) scores an item as supported only when its evidence states it, or, for an inference, when the findings it rests on are supported. The roadmap requires that a bad citation is rejected with a reason and the rest of the investigation survives.

Two questions follow that the schema alone does not settle:

1. What happens to an item whose citations are all rejected?
2. What stops an investigation of a scored case from being read before the scoring rubric exists? Reading showcase output first would let the rubric drift towards what the model produced, the same risk the [prior-knowledge check](../architecture/README.md#the-prior-knowledge-check) guards against.

## Options considered

For an item left without support:

| Option | What the evaluation sees | Cost |
|---|---|---|
| Drop the item | Only supported items; the claim the model made is gone | Hides a wrong or unbacked claim, which is exactly what the evaluation needs to count |
| Keep the item and list it as unsupported | Every claim, with the unbacked ones named in `checks.unsupported` | A reader of the result file has to read the checks next to the items |
| Refuse the whole result | Nothing | One bad citation throws away a whole run, against the roadmap's "the rest survives" |

For the scored-case lock:

| Option | Holds when | Cost |
|---|---|---|
| By convention: do not run the showcase cases yet | Everyone remembers | Nothing checks it |
| In code: refuse a showcase case until `eval/rubric/frozen.json` exists | Always; a test covers both directions | One file the evaluation milestone has to write |

## Decision

Keep and mark. A rejected citation is removed from its item and listed in `checks.rejected_citations` with where it was and why: `malformed`, `unknown`, `other-case`, or `unknown-finding`. An item left with no valid citation and no valid `rests_on` stays in the investigation and is listed in `checks.unsupported`. The attack verdict is never dropped. `checks` is written by the app, never by the model.

Lock in code. `python -m hindcast.investigate` refuses a case whose role is not `development` or `injection` until `eval/rubric/frozen.json` exists, before any model call.

The result file follows the schema in `hindcast.result`: the investigation the model fills under a strict JSON schema, wrapped with the case, the agent name and version, the model name and version read from the deployment, the provenance (prompt blob hash or SHA-256 with a dirty flag, code commit with a dirty flag, evidence SHA-256), the status and its reason, the checks, and the usage. Findings carry `kind` (`observation` or `inference`) and `rests_on`, and timeline events carry `time_kind` (`stated` or `inferred`), from the first run, so that no result has to be relabelled when milestone 5's support rules read them.

## Trade-offs

- A citation check proves that a reference resolves to this case's evidence, not that the evidence says what the item claims. Whether a cited update supports its item is milestone 5's support rule.
- An unsupported item still reaches the result file and, later, the interface. The interface has to show the mark, or a reader takes the claim as backed.
- The lock is a file check. Writing `eval/rubric/frozen.json` by hand unlocks the showcase cases. The file is meant to be committed with the rubric, so an early one shows in the history.
- A dirty prompt or code tree is recorded, not refused, so iterating on the development case does not need a commit per try. Milestone 5 decides whether scored runs refuse a dirty tree, as the prior-knowledge check does.

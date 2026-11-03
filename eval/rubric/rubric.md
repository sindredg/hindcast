# Reconstruction rubric, version 1

How a reconstruction of a scored case is scored against its frozen key ([decisions 0006](../../docs/decisions/0006-evaluation-design.md) and [0023](../../docs/decisions/0023-abstention-and-inferable-labels.md)). Frozen with the labels and the timeline tolerance before the first scored run; [`frozen.json`](frozen.json) records the hashes. A change after a scored output is read is a new version and a new set of runs, never an edit.

## What is scored

Each run of each arm on each showcase case. The scored key items are the attack verdict, the root cause, each contributing factor, and each timeline event. Fixes are not scored. The run's items are its attack assessment, findings, timeline events, root cause, and contributing factors.

Each scored key item carries a frozen label from [`eval/keys/labels/`](../keys/labels/README.md): `stated`, `inferable`, or `not inferable` from the case's status updates and charts.

## Outcomes

The judge proposes one outcome per key item per run; the review decides where the review rule below says so.

| Outcome | Meaning |
|---|---|
| supported hit | The run states the key item, and the run's item that states it is supported |
| partial | The run's supported item states part of the key item: the right mechanism without its trigger, or the trigger without the mechanism. Root cause and contributing factors only |
| unsupported hit | The run states the key item, but no supported item does |
| abstained | Root cause: the run's root cause says the evidence does not determine it, names what is missing, and an open question asks for it. Attack verdict: `cannot tell` |
| missed | No run item states it |
| wrong | A run item contradicts it: another root cause stated as the cause, the opposite attack verdict, or a timeline time more than the tolerance away for the same event |

A hedged statement ("likely", "probably") counts as a statement of what it hedges. When one run item states a key item and another contradicts it, the outcome is wrong.

**Matching.** A root cause or factor matches when it names the same mechanism, in any words; a different component with the same symptom does not match. A timeline event matches when it is the same event and its time is within **30 minutes** of the key's time; where the key's event names a second time, either counts. An attack verdict matches when it is the same verdict.

## Support

An item is supported only by the case's evidence: its status updates and charts.

1. **Observation.** Supported when a cited update or chart states it. A value or a time that rests only on a chart description is a lead, not support: a description is model output about an image.
2. **Inference.** Supported when all four hold:
   1. it rests on observations (in `rests_on` or its citations), and each of them is supported;
   2. the step from them uses only those observations and general engineering knowledge, such as how a kind of system usually fails, never a library document and never knowledge of this outage from elsewhere;
   3. it adds no fact about this outage that the cited items do not give: no component, time, number, or cause of its own;
   4. the conclusion follows: a reader with the cited items and general engineering knowledge would reach it, not merely find it consistent with them.
3. **Library.** A claim about this outage that rests only on a library document is unsupported. A library hit shows how another outage went; it is a lead.
4. **Structural checks.** Citations and `rests_on` entries that the code rejects (`hindcast.result.check_citations`: unknown, other case, not shown, withheld, not retrieved, an observation's `rests_on`, self-support, an ambiguous finding ID, a cycle) are removed before the judge reads the run. An item the code lists as unsupported is unsupported.

## Credit

| Outcome on a key item | Label | Credit |
|---|---|---|
| supported hit | any | 1 |
| partial | any | 0.5 |
| abstained | `not inferable` (root cause, attack verdict) | 1, a justified abstention |
| abstained | `stated`, `inferable` | 0, counted as missed |
| unsupported hit | any | 0; reported as a guess when the label is `not inferable` |
| missed | `stated`, `inferable` | 0 |
| missed | `not inferable` factor or timeline event | neutral: not scorable for that run, listed |
| missed | `not inferable` root cause or attack verdict | 0 |
| wrong | any | 0 |

**Primary score per run:** credited ÷ scorable, where scorable is every scored key item except the neutral ones. Next to it, never folded in, the report gives per run: unsupported items, wrong items, guesses, supported items that match no key item (counted and listed, not scored), failures, seconds, and cost. Per arm and case it gives the mean, the minimum, and the maximum of the primary score over the runs, and the summed outcome counts. The full outcome table is always shown, not only the score.

## Review

The judge proposes; a person decides:

- every proposed supported hit, partial, and unsupported hit;
- every support verdict on an inference;
- a sample of a quarter of the remaining verdicts (missed, abstained, wrong, and support verdicts on observations), drawn per run with the seed 20261104.

A reviewed decision replaces the judge's proposal. The agreement between the judge and the reviewer is reported as percent agreement and Cohen's kappa over the reviewed items.

## Failures

Every attempt is in the attempts ledger. An attempt with no result (no output, or a failed model call) is reported as a failure and is not scored; a slot with three such attempts is closed and reported. A run that ended incomplete after the model produced output is scored as it stands: an item it does not hold is missed.

## Prior knowledge

Each model's prior-knowledge answer for a case is scored on the root cause and the attack verdict with the same outcomes, by the same judge and review. When a model's prior answer matches a case's root cause, that model's scores on that case are reported in a separate known-before-evidence row. `cloudflare-2025-11-18` is the only scored case that began before both models' training cutoffs.

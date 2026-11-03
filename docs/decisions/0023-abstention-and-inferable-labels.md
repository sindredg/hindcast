# 23. Abstention: inferable-from-evidence labels, and a score that tells a miss from an unknowable item

Status: Accepted (2026-11-03).

Extends the scoring of [decision 0006](0006-evaluation-design.md) and names the arms it compares.

## Context

Decision 0006 scores the root cause as match, partial, or none, counts the contributing factors and timeline events recovered, and counts a correct claim without support as unsupported, not as a hit. It does not ask whether the item could be found at all.

Some key items cannot be reached from public evidence. A postmortem can name an internal change that no status update mentions. A run that says "the updates do not show what changed" then scores the same as a run that missed an obvious cause, and a reader of the scores cannot tell the two apart.

## Options considered

| Option | Result | Cost |
|---|---|---|
| Report it as a limit | Nothing to build | The headline mixes "missed what the evidence showed" with "declined to guess what it could not show" |
| Change every arm's prompt to invite abstention | Every arm can abstain | The arms no longer run the prompt the sealed cases ran, and a sealed run cannot be repeated, so the sealed scores stop comparing with the showcase ones |
| Label each key item, score abstention against the label, and test the prompt change in one arm | A justified abstention scores above a miss and a guess; the prompt's effect is measured, not assumed | Labels are judgements to write, review, and freeze; one more arm to run |

## Decision

Label each key item, score abstention against the label, and test the prompt change in one arm.

1. **Labels.** Every scored key item (the attack verdict, the root cause, each contributing factor, each timeline event) gets one label, with a one-line reason that names the update IDs it rests on:

   | Label | Meaning |
   |---|---|
   | `stated` | A status update before the resolved one says it. Matches the key's `stated_during_incident: true`. |
   | `inferable` | The evidence supports reaching it through a written step. |
   | `not inferable` | Reaching it needs information the evidence does not hold. |

   "Evidence" means the case's status updates and charts. The library is a lead, never evidence. The inference step may use general engineering knowledge, never a library document; the support rules of decision 0006 say the same.
2. **Freeze.** Labels live in `eval/keys/labels/<case_id>.json`, apart from the frozen keys, which stay unchanged. A person approves each label, and the files are frozen by SHA-256 before the first scored run. A sealed case is labelled and frozen at its reveal, before its sealed file is opened ([decision 0022](0022-sealed-drop-date-and-offline-reveal.md)).
3. **Outcomes.** The judge proposes one outcome per key item per run; a person decides where decision 0006's review rule says so.

   | Outcome | Meaning |
   |---|---|
   | supported hit | Matches the key item and is supported by its citations |
   | partial | Partly matches (decision 0006's root-cause scale) |
   | unsupported hit | Matches but has no support: unsupported, never a hit |
   | abstained | The run says the evidence does not settle it: for the root cause, a hedged claim and an open question that names what is missing; for the attack verdict, `cannot tell` |
   | missed | Not mentioned |
   | wrong | Contradicts the key |

4. **Credit.**
   - An abstention on a `not inferable` root cause or attack verdict is justified and credited. On a `stated` or `inferable` item it counts as missed.
   - Factors and events have no abstention form; silence is their abstention. A `not inferable` factor or event the run does not mention is neutral: it leaves that run's recall denominator and is listed. Mentioned without support, it is a guess.
   - An unsupported hit on a `not inferable` item is reported as a guess.
   - The rubric, frozen before the first scored run, turns the outcomes into the primary score. The report always shows the whole outcome table next to it.
5. **Arms.** Each showcase case runs on five arms, three times each:

   | Arm | Model | Library search | Prompt |
   |---|---|---|---|
   | Hindcast | gpt-6-luna agent | On | Investigator v3 |
   | Comparison model (decision 0006) | gpt-6.1-sol agent | On | Investigator v3 |
   | Single search (decision 0006) | gpt-6-luna, one search, one call | One search | Single-search prompt |
   | Library off | gpt-6-luna agent | Off | Investigator v3 without its library parts |
   | Abstention | gpt-6-luna agent | On | Investigator v3 plus one rule: when the evidence does not determine the root cause, the claim says so, names what is missing, and an open question asks for it |

   The abstention arm is decision 0006's one controlled comparison: it differs from Hindcast by the prompt alone. The other arms keep their prompts, so they compare with the sealed runs, which used investigator v3. The library-off arm differs in prompt as well as tool, because v3 tells the model to search; the report says so.

## Trade-offs

- A label is a judgement made with the key open. A wrong `not inferable` credits an abstention that should have been a miss. Labels are frozen before any run output is read, and each reason names its updates so a reader can check it.
- A neutral item leaves the denominator, so recall reads higher on a case with many `not inferable` factors. The outcome table shows the count next to the score.
- The arms that keep investigator v3 are never told they may abstain, so the credit mostly matters for the abstention arm. That is the comparison: it measures what the permission changes.
- Three runs per arm show spread, not a confidence interval.

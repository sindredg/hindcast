# 23. Abstention: inferable-from-evidence labels, and a score that tells a miss from an unknowable item

Status: Accepted (2026-11-03). Changed by [decision 0027](0027-reviewer-model.md).

Extends the scoring of [decision 0006](0006-evaluation-design.md) and names the arms.

## Context

Decision 0006 does not ask whether a key item could be found at all. A run that says the updates do not show the cause scores like one that missed an obvious cause.

## Options considered

| Option | Result | Cost |
|---|---|---|
| Report it as a limit | Nothing to build | Misses and justified refusals mixed |
| Invite abstention in every arm | Every arm can abstain | Sealed runs cannot be repeated, so sealed and showcase scores stop comparing |
| Label each key item, score against it, test the prompt in one arm | A justified abstention beats a miss and a guess; the prompt's effect is measured | Labels to freeze; one more arm |

## Decision

The third option.

1. **Labels.** Every scored key item gets one label and a one-line reason naming update IDs:

   | Label | Meaning |
   |---|---|
   | `stated` | A status update before the resolved one says it. Matches the key's `stated_during_incident: true`. |
   | `inferable` | The evidence supports reaching it through a written step. |
   | `not inferable` | Reaching it needs information the evidence does not hold. |

   Evidence means the case's updates and charts; the library is a lead. The step may use general engineering knowledge, never a library document.
2. **Freeze.** `eval/keys/labels/<case_id>.json`, apart from the keys. A person approves each; frozen by SHA-256 before the first scored run. A sealed case is labelled at its reveal, before its file is opened ([decision 0022](0022-sealed-drop-date-and-offline-reveal.md)).
3. **Outcomes.** The judge proposes one per key item per run; a person decides where decision 0006 says so.

   | Outcome | Meaning |
   |---|---|
   | supported hit | Matches and is supported by its citations |
   | partial | Partly matches (decision 0006's root-cause scale) |
   | unsupported hit | Matches without support: never a hit |
   | abstained | The run says the evidence does not settle it: a hedged root-cause claim with an open question naming what is missing, or `cannot tell` for the attack verdict |
   | missed | Not mentioned |
   | wrong | Contradicts the key |

4. **Credit.**
   - An abstention on a `not inferable` root cause or attack verdict is credited; on a `stated` or `inferable` item it is missed.
   - Factors and events abstain by silence. A `not inferable` one the run omits is neutral: out of the recall denominator, and listed. Mentioned without support, it is a guess.
   - An unsupported hit on a `not inferable` item is a guess.
   - The rubric, frozen before the first scored run, turns outcomes into the primary score, shown next to the whole outcome table.
5. **Arms.** Each showcase case runs five arms, three times each:

   | Arm | Model | Library search | Prompt |
   |---|---|---|---|
   | Hindcast | gpt-6-luna agent | On | Investigator v3 |
   | Comparison model (decision 0006) | gpt-6.1-sol agent | On | Investigator v3 |
   | Single search (decision 0006) | gpt-6-luna, one search, one call | One search | Single-search prompt |
   | Library off | gpt-6-luna agent | Off | Investigator v3 without its library parts |
   | Abstention | gpt-6-luna agent | On | Investigator v3 plus one rule: when the evidence does not determine the root cause, say so, name what is missing, and ask for it in an open question |

   The abstention arm is decision 0006's controlled comparison: prompt only. The others keep v3, as the sealed runs did. The library-off arm also differs in prompt, because v3 tells the model to search.

## Trade-offs

- A label is made with the key open; a wrong `not inferable` credits what should be a miss. Labels are frozen before any output is read, each reason naming its updates.
- Neutral items leave the denominator, so recall reads higher with many `not inferable` factors; the table shows the count.
- Only the abstention arm is told it may abstain. That is the comparison.
- Three runs per arm show spread, not a confidence interval.

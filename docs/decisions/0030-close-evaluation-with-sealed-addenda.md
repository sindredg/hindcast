# 30. Close the evaluation with sealed reveals as addenda, and give a revealed case its own role

Status: Accepted (2026-11-07).

Changes how [decision 0017](0017-sealed-reconstructions.md)'s reveals relate to milestone 5's close and replaces its showcase-role rule. Sealing, revealing, dropping, and [decision 0022](0022-sealed-drop-date-and-offline-reveal.md)'s drop date of 2026-11-30 are unchanged.

## Context

On 2026-11-07 one of five sealed cases had a published cause: GitHub's summary of `github-2026-11-04-actions` in the resolved update at 2026-11-07T01:04:38Z. GitHub's October report, covering two more, is due 2026-11-11. Read as a gate, the criterion holds milestone 5 open three weeks with nothing else left. The `showcase` role would put a revealed case under the prior-knowledge and baseline rules 0017 exempts it from (issue #34) and mix single seals into tables of three repeats per arm.

## Options considered

| Option | Result | Cost |
|---|---|---|
| Keep milestone 5 open until every sealed case is settled | The gate as written | Open until 2026-11-30 |
| Drop the four unrevealed cases now | One sealed result | Selection after seeing who published, which 0017 and 0022 rule out |
| Close once published causes are revealed; later reveals are addenda | Closes on what exists | An accepted gap on the sealed gate row until the last case is settled |

| Revealed role | Result | Cost |
|---|---|---|
| `showcase`, as 0017 says | One role fewer | Prior-knowledge and baseline rules apply; mixed tables |
| Exempt former sealed cases by name | No new role | Exception lists in every check |
| `revealed` | Each rule reads the role once | One more role |

## Decision

1. **Close with addenda.** Milestone 5 closes when every sealed case with a published cause on the closing day is revealed and scored and the independent review has run. Each later reveal follows decision 0022's order as an addendum in its own change. No cause by 2026-11-30: dropped. Until then the sealed gate row is tested for the revealed cases and an accepted gap for the rest.
2. **Role `revealed`.** Has its postmortem, keeps the whole library, is refused by `hindcast.investigate`, and is scored from its seals only: no prior-knowledge question, no baselines, no new runs.
3. **A tree of its own.** `eval/reconstruction/sealed-v1/`, with the frozen judge, the reviewer, the labels, and rubric version 3, reported apart from the showcase runs. The judge uses the exact system prompt its lock pins.
4. **Order in code.** `python -m hindcast.reveal` refuses a sealed file until the key and labels are frozen, the evidence is the file the seals name, the cause was published after every seal, and the leak check passes against the snapshot.

## Trade-offs

- Part of one criterion stays open; the gap names the cases and dates.
- One seal per model per case: a score says what one run did.
- One more role value for every role check; the checks are tested.

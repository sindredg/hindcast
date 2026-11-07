# 30. Close the evaluation with sealed reveals as addenda, and give a revealed case its own role

Status: Accepted (2026-11-07).

Changes how [decision 0017](0017-sealed-reconstructions.md)'s reveals relate to milestone 5's close, and replaces 0017's rule that a revealed case becomes a showcase case. The rules for sealing, revealing, and dropping, and [decision 0022](0022-sealed-drop-date-and-offline-reveal.md)'s drop date of 2026-11-30, are unchanged.

## Context

On 2026-11-07 one of the five sealed cases had a published cause: GitHub wrote its summary of `github-2026-11-04-actions` into the incident's resolved update at 2026-11-07T01:04:38Z. The other four had none. GitHub's monthly report for October, which covers two of them, is due on 2026-11-11.

Milestone 5's criterion says each sealed case is revealed and scored, or dropped on 2026-11-30. Read as a gate, it holds the milestone open for three more weeks, although everything else in it is scored and reviewed and nothing in the remaining reveals changes how the others were scored.

Decision 0017 also says a revealed case changes its role from `sealed` to `showcase`. A showcase case falls under two rules that 0017 exempts sealed cases from: the prior-knowledge question and the baselines (issue #34). Folding a revealed case into the showcase tables would also mix two kinds of run: three repeats per arm on a case whose postmortem was public, and one seal per model on a case whose cause did not exist yet.

## Options considered

| Option | Result | Cost |
|---|---|---|
| Keep milestone 5 open until every sealed case is revealed or dropped | The gate reads as written | The milestone stays open until 2026-11-30 with no other work left in it |
| Drop the four unrevealed cases now | The milestone closes with one sealed result | Moving the drop date after seeing which providers published is the selection 0017 and 0022 rule out, and it likely loses the two cases GitHub's October report covers |
| Close the milestone once the cases with a published cause are revealed; reveal the rest later as addenda under the same rules | The milestone closes on what exists; the sealed result grows as providers publish | The gate row for sealed cases carries an accepted gap until the last case is revealed or dropped |

| Option for the revealed role | Result | Cost |
|---|---|---|
| `showcase`, as 0017 says | One role fewer | The case falls under the prior-knowledge and baseline rules, and its seals mix into the showcase tables |
| Exempt former sealed cases by name | No new role | Every rule that reads the role needs a list of exceptions |
| A role of its own, `revealed` | Each rule reads the role once | One more role in the registry and the code |

## Decision

1. **Close with addenda.** Milestone 5 closes when every sealed case with a published cause on the closing day is revealed and scored and the milestone's independent review has run. Each later reveal follows decision 0022's order and is an addendum to the sealed report in its own change. A case with no published cause by 2026-11-30 is dropped, as decision 0022 says. Until then the gate row for sealed cases is tested for the revealed cases and an accepted gap for the rest.
2. **Role `revealed`.** A revealed case has its postmortem, keeps the whole library like a sealed case, is refused by `hindcast.investigate`, and is scored from its seals only: no prior-knowledge question, no baselines, no new runs.
3. **A tree of its own.** The revealed seals are scored under `eval/reconstruction/sealed-v1/` with the frozen judge, the reviewer, the labels, and rubric version 3, and reported apart from the showcase runs. The judge uses the exact system prompt its lock pins, so the revealed runs get the same instructions as the showcase runs.
4. **Order in code.** `python -m hindcast.reveal` refuses to read a sealed file until the key and the labels are frozen, the evidence is the file the seals name, the cause was published after every seal, and the leak check passes against the library snapshot.

## Trade-offs

- The milestone is called done with part of one criterion still open. The accepted gap names the open cases and the date that settles each one.
- The sealed result is small: one seal per model per case, with no repeats, so a score says what one run did, not how a model behaves on average.
- A new role means one more value every role check has to handle. The checks that read it are tested.

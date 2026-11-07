# 22. Sealed cases: a later drop date and a reveal that works offline

Status: Accepted (2026-11-03). Reveals after milestone 5 closes are addenda, per [decision 0030](0030-close-evaluation-with-sealed-addenda.md).

Changes [decision 0017](0017-sealed-reconstructions.md)'s drop date and says how its reveal runs after the Azure environment is gone.

## Context

Decision 0017 drops a sealed case whose provider has published no cause by 2026-11-09. On 2026-11-03 at 20:36 UTC none of the three sealed cases had one: each incident is resolved, and none carries a postmortem on its status page.

Two facts make 2026-11-09 a poor date:

1. GitHub publishes a monthly availability report on its incidents. The three in the library came out on 2023-10-11, 2023-12-13, and 2026-07-08 ([`data/library.yaml`](../../data/library.yaml)), each the second Wednesday of the month after. The report for October 2026, the month of both sealed GitHub outages, is then due on 2026-11-11, two days after the drop date.
2. The Azure environment is torn down on 2026-11-09. A reveal today needs Content Understanding to draft the key and the live index for the leak check, so a cause published after teardown could not be revealed even with a later date.

## Options considered

| Option | Result | Cost |
|---|---|---|
| Keep 2026-11-09 | The rule stays exactly as fixed in advance | The GitHub cases are likely dropped two days before their cause is due; the headline result is likely empty |
| Move the date per case as causes appear | Each case waits as long as it needs | Choosing per case after seeing which providers publish is the selection decision 0017 rules out |
| Move it to 2026-11-30 for every sealed case alike, decided before any cause is known | Covers GitHub's October report with time to spare | A date fixed in advance moves once, and the report stays open three weeks longer |
| No date | Nothing is dropped | The report never closes |

## Decision

Move the date to 2026-11-30 for every sealed case alike, and make the reveal work offline.

1. **Drop date.** A sealed case whose provider has published no cause by 2026-11-30 is dropped, with its records kept and marked `dropped`, as decision 0017 rule 2 says. The date applies to the three sealed cases and to any case sealed later. It is decided on 2026-11-03, before any sealed case's provider has published a cause.
2. **Library snapshot.** Before teardown, `python -m hindcast.seal snapshot <case_id>` writes every chunk the case's search filter returns from the live index to a local file, and records the index, the filter, the chunk count, the file's SHA-256, and the time in `eval/sealed/library-snapshots.json`. The file stays local; the record is committed.
3. **Leak check.** After teardown, the leak check reads the library side from the snapshot, and refuses a snapshot whose SHA-256 differs from its record.
4. **Key.** The key of a revealed case is drafted by hand from the captured postmortem, not by Content Understanding. Every quote is still checked word for word against the captured file in code, a person reviews the key, and it is frozen by hash like the others.
5. **Order.** For each revealed case: capture the postmortem, freeze the key, freeze the case's labels ([decision 0023](0023-abstention-and-inferable-labels.md)), pass the leak check against the snapshot, then open the sealed file, check it against its hash, and score it.

## Trade-offs

- Decision 0017 fixed the date before the first seal. Moving it once, for all cases, before any cause is known keeps what the seals prove: each result was made before its cause existed, and the file is unchanged.
- A reader still has to accept that the move was not informed by the results. Nothing has read them: the files are in private storage, and every command that touches them prints counts and hashes only.
- The report stays open until 2026-11-30 at the latest.
- A hand-drafted key is made differently from the showcase keys, which Content Understanding drafted. The word-for-word quote check and the human review are the same for both.
- A snapshot holds what the filter returned when it was taken, not what each sealed run retrieved. Each run's own tool calls record the refs it was shown.

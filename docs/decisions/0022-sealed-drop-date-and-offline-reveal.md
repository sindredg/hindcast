# 22. Sealed cases: a later drop date and a reveal that works offline

Status: Accepted (2026-11-03). Changed by [decision 0030](0030-close-evaluation-with-sealed-addenda.md).

Changes [decision 0017](0017-sealed-reconstructions.md)'s drop date and makes its reveal run after teardown.

## Context

Decision 0017 drops a sealed case with no cause by 2026-11-09. On 2026-11-03 at 20:36 UTC none of the three had one. GitHub's monthly reports in the library came out on 2023-10-11, 2023-12-13, and 2026-07-08 ([`data/library.yaml`](../../data/library.yaml)), the second Wednesday of the next month, so the October 2026 report, covering both sealed GitHub outages, is due 2026-11-11. The Azure environment goes on 2026-11-09, and a reveal needs Content Understanding and the live index.

## Options considered

| Option | Result | Cost |
|---|---|---|
| Keep 2026-11-09 | The rule as fixed | The GitHub cases likely drop two days early |
| Move per case | Each waits | Selection after seeing who publishes |
| 2026-11-30 for every case, before any cause is known | Covers GitHub's report | Three weeks longer |
| No date | Nothing dropped | Never closes |

## Decision

2026-11-30 for every sealed case, and an offline reveal.

1. **Drop date.** No cause by 2026-11-30: dropped, records kept and marked `dropped`. Applies to the three sealed cases and any sealed later. Decided 2026-11-03, before any cause was published.
2. **Library snapshot.** Before teardown, `python -m hindcast.seal snapshot <case_id>` writes every chunk the case's filter returns to a local file and records index, filter, chunk count, SHA-256, and time in `eval/sealed/library-snapshots.json`.
3. **Leak check.** Reads the library side from the snapshot and refuses one whose SHA-256 differs.
4. **Key.** Drafted by hand from the captured postmortem; quotes checked in code, reviewed, frozen by hash.
5. **Order.** Capture the postmortem, freeze the key, freeze the labels ([decision 0023](0023-abstention-and-inferable-labels.md)), pass the leak check, then open the sealed file, check its hash, score it.

## Trade-offs

- One move, for all cases, before any cause is known keeps what the seals prove.
- Nothing has read the files; every command that touches them prints counts and hashes only.
- The report stays open until 2026-11-30 at the latest.
- A hand-drafted key differs in origin from the showcase keys; the checks are the same.
- A snapshot holds what the filter returned when taken; each run's tool calls record its own refs.

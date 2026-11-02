# Investigations of the development case `cloudflare-2026-02-20`

Two development runs, read against the evidence and not scored. The answer key stays closed until the milestone 5 rubric is frozen. The page shows the second run.

## The runs

| Field | Slice 1: case tools | Slice 2: case tools and library search |
|---|---|---|
| Evidence for | gate row 1 of [milestone 4, slice 1](../../../docs/worklogs/04-investigator.md#gate) | the [slice 2 pass bar](../../../docs/worklogs/04-investigator.md#pass-bar-for-the-slice-2-live-runs) |
| Case | `cloudflare-2026-02-20` (Cloudflare status incident `kwy3dt82bwbt`, 10 updates, 2 charts) | same |
| Agent | `hindcast-investigator-gpt-6-luna`, version 1 | `hindcast-investigator-gpt-6-luna`, version 3 |
| Model | deployment `gpt-6-luna`, model gpt-6-luna version 2026-09-22 | same |
| Prompt | `prompts/investigator.md` v2, blob `fb660e15cf20654c2d05696c89a63a313cc2ffe4`, clean | `prompts/investigator.md` v3, blob `1d0911f407e73fd3d4def4f4e14ab8763c6cfbbc`, clean |
| Code | commit `7c27d84`, clean | commit `764b37e`, clean |
| Evidence | `build/evidence/cloudflare-2026-02-20.json`, SHA-256 `ee6be350c1f4d19b393e12b13f87dfa97a0ba6341aed57e58fd9c2285381e074` | same |
| Library | none | `data/library.yaml` blob `ca5fb507e65dab71001a76adb9ae2258aae261b4`; index `hindcast-library-1024`; search API `2026-04-01`; text-embedding-3-large version 1, 1,024 dimensions |
| Outcome | `complete`; 10 findings, 8 timeline events, 2 factors, 4 open questions; 0 rejected citations, 0 unsupported | `complete`; 6 findings, 9 timeline events, 1 factor, 3 open questions; 0 rejected citations, 0 unsupported; 1 search, 1 library citation kept |
| Usage | 2 model calls, 2 tool calls, 31.353 s; 3,776 input tokens (1,034 cached), 3,395 output tokens | 3 model calls, 3 tool calls, 39.258 s; 10,151 input tokens (5,525 cached), 3,340 output tokens |

The reading of each result against the evidence is in the [worklog](../../../docs/worklogs/04-investigator.md).

## Files

| File | Purpose |
|---|---|
| `20261030T040215Z-v1.json` | The slice 1 result file the command wrote, unchanged. |
| `20261102T181721Z-v3.json` | The slice 2 result file the command wrote, unchanged: as above, plus the tool calls with each search's query and returned refs, and the library provenance. |

`tests/test_committed_investigation.py` checks the files:

- Each run is complete and parses against the schema.
- Where the evidence file is present, every item except the open questions keeps at least one case citation that resolves. The evidence is not in the repository, so CI skips this test.
- In the slice 2 run, every library citation names a ref that a search in the run returned. This runs in CI.
- Where the library extracts are present, the slice 2 run repeats no library section it retrieved in a fragment longer than 120 characters. The extracts are not in the repository, so CI skips this test.

## Status

- Slice 1, tested live on 2026-10-30: the run above. Tested locally on 2026-10-30: both tests pass, and each failed once on a broken copy of the file (an inference with its citations removed, a status changed to `incomplete`).
- Slice 2, tested live on 2026-11-02: the run above. Tested locally on 2026-11-02: every test passes, and each new or changed test failed once on a broken copy of the file. A library citation changed to a ref the run did not retrieve failed the retrieved test and the case-citation test. A 150-character fragment of a retrieved section added to a finding failed the library-text test.

## Licence

The investigations are model output about Cloudflare's status updates for incident `kwy3dt82bwbt`, which are not redistributed here. They paraphrase them. Measured with `difflib` against the evidence file, counting matches of 25 characters or more:

- Slice 1 (measured 2026-10-30): about a fifth of its text repeats the updates word for word, in fragments of at most 61 characters.
- Slice 2 (measured 2026-11-02): 17.6% of its text repeats the updates, in fragments of at most 56 characters.

The slice 2 run also read five sections of earlier Cloudflare postmortems from the library, which are not redistributed here either. None of its text repeats them in a match of 25 characters or more. The longest shared fragment is 22 characters.

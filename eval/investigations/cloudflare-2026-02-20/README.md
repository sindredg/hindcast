# Investigations of the development case `cloudflare-2026-02-20`

Four development runs and nine challenges, read against the evidence and not scored. The answer key was frozen on 2026-10-27 and is not used on these runs. The page lists the runs and opens on the newest `gpt-6-luna` run.

## The runs

| Field | Slice 1: case tools | Slice 2: case tools and library search |
|---|---|---|
| Evidence for | gate row 1 of [milestone 4, slice 1](../../../docs/worklogs/04-investigator.md#gate) | the [slice 2 pass bar](../../../docs/worklogs/04-investigator.md#pass-bar-for-the-slice-2-live-runs) |
| Case | `cloudflare-2026-02-20` (Cloudflare status incident `kwy3dt82bwbt`, 10 updates, 2 charts) | same |
| Agent | `hindcast-investigator-gpt-6-luna`, version 1 | `hindcast-investigator-gpt-6-luna`, version 3 |
| Model | deployment `gpt-6-luna`, model gpt-6-luna version 2026-09-22 | same |
| Prompt | `prompts/investigator.md` v1, blob `fb660e15cf20654c2d05696c89a63a313cc2ffe4`, clean | `prompts/investigator.md` v3, blob `1d0911f407e73fd3d4def4f4e14ab8763c6cfbbc`, clean |
| Code | commit `7c27d84`, clean | commit `764b37e`, clean |
| Evidence | `build/evidence/cloudflare-2026-02-20.json`, SHA-256 `ee6be350c1f4d19b393e12b13f87dfa97a0ba6341aed57e58fd9c2285381e074` | same |
| Library | none | `data/library.yaml` blob `ca5fb507e65dab71001a76adb9ae2258aae261b4`; index `hindcast-library-1024`; search API `2026-04-01`; text-embedding-3-large version 1, 1,024 dimensions |
| Outcome | `complete`; 10 findings, 8 timeline events, 2 factors, 4 open questions; 0 rejected citations, 0 unsupported | `complete`; 6 findings, 9 timeline events, 1 factor, 3 open questions; 0 rejected citations, 0 unsupported; 1 search, 1 library citation kept |
| Usage | 2 model calls, 2 tool calls, 31.353 s; 3,776 input tokens (1,034 cached), 3,395 output tokens | 3 model calls, 3 tool calls, 39.258 s; 10,151 input tokens (5,525 cached), 3,340 output tokens |

Slice 3 ran each model once with Prompt Shields on every tool item and PII detection on the answer:

| Field | Slice 3, gpt-6-luna | Slice 3, gpt-6.1-sol |
|---|---|---|
| Evidence for | the [slice 3 gate](../../../docs/worklogs/04-investigator.md#slice-3-gate) | same |
| Agent | `hindcast-investigator-gpt-6-luna`, version 3 | `hindcast-investigator-gpt-6-1-sol`, version 2 |
| Model | deployment `gpt-6-luna`, model gpt-6-luna version 2026-09-22 | deployment `gpt-6.1-sol`, model gpt-6.1-sol version 2026-09-29 |
| Prompt | `prompts/investigator.md` v3, blob `1d0911f407e73fd3d4def4f4e14ab8763c6cfbbc`, clean | same |
| Code | commit `81e01a7`, clean | same |
| Evidence and library | as slice 2 | same |
| Outcome | `complete`; 6 findings, 8 timeline events, 2 factors, 4 open questions; 0 rejected citations, 0 unsupported; 1 search, no library citation kept | `complete`; 9 findings, 9 timeline events, 2 factors, 3 open questions; 0 rejected citations, 0 unsupported; 1 search, 1 library citation kept |
| Screens | 5 Prompt Shields calls, 25 text records; 0 items withheld | 5 calls, 27 records; 0 withheld |
| PII | 6 calls, 26 text records; 0 hits | 6 calls, 28 records; 0 hits |
| Usage | 3 model calls, 3 tool calls, 42.195 s; 10,648 input tokens (4,251 cached), 3,039 output tokens | 3 model calls, 3 tool calls, 56.597 s; 10,552 input tokens (4,251 cached), 2,940 output tokens |
| Cost (price table v1) | USD 0.037583 | USD 0.080555 |

Each challenge checks one observation finding of a slice 3 run with the question "Which status update shows this, and does any later update contradict it?":

| File | Challenges | Agent | Outcome | Cost |
|---|---|---|---|---|
| `challenges/20261103T171441Z-F1.json` | F1 of the gpt-6-luna run | `hindcast-challenger-gpt-6-luna`, version 1 | `complete`, `stands`; 2 case citations kept, 0 rejected; 2 model calls, 1 tool call | USD 0.006129 |
| `challenges/20261103T171511Z-F1.json` | F1 of the gpt-6.1-sol run | `hindcast-challenger-gpt-6-1-sol`, version 1 | `complete`, `stands`; 10 case citations kept, 0 rejected; 2 model calls, 1 tool call | USD 0.014526 |
| `challenges/20261103T171932Z-F2.json` | F2 of the gpt-6-luna run, to check the traces after the sampler fix | `hindcast-challenger-gpt-6-luna`, version 1 | `complete`, `stands`; 8 case citations kept, 0 rejected; 2 model calls, 3 tool calls | USD 0.011807 |
| `challenges/20261103T174229Z-F3.json` | F3 of the gpt-6-luna run, to check that traces arrive with the workspace's shared keys off | same | `complete`, `stands`; 6 case citations kept, 0 rejected; 2 model calls, 2 tool calls | USD 0.007431 |
| `challenges/20261103T174623Z-F4.json` | F4 of the gpt-6-luna run, to check the traces after Application Insights was disconnected from the Foundry account | same | `complete`, `stands`; 5 case citations kept, 0 rejected; 2 model calls, 1 tool call | USD 0.006193 |

Four more challenge F5 of the gpt-6-luna run, started from the page's box in a browser ([screenshots](../../../docs/screenshots/README.md)): `20261103T192648Z-F5.json`, `20261103T192857Z-F5.json`, `20261103T193005Z-F5.json`, and `20261103T193159Z-F5.json`. All `complete` and `stands`, 2 to 4 case citations each (one cites chart1), none rejected, no PII hit.

The reading of each result against the evidence: [worklog](../../../docs/worklogs/04-investigator.md).

## Files

| File | Purpose |
|---|---|
| `20261030T040215Z-v1.json` | The slice 1 result file, unchanged. |
| `20261102T181721Z-v3.json` | The slice 2 result file, unchanged: as above, plus the tool calls with each search's query and returned refs, and the library provenance. |
| `20261103T171237Z-v3.json`, `20261103T171355Z-v2.json` | The slice 3 result files, unchanged: as above, plus each tool call's withheld refs and screen calls, `checks.pii`, the screen and PII counts in the usage, and the cost. |
| `challenges/*.json` | The challenge files `hindcast.challenge` wrote, from the command or the page, unchanged: the result file and finding challenged, the PII-masked question, the answer, its checks, tool calls, usage, and cost. |

`tests/test_committed_investigation.py` checks:

- Each run is complete and parses against the schema.
- Where the evidence file is present, every item except the open questions keeps at least one case citation that resolves. The evidence is not in the repository, so CI skips this.
- In each run that kept a library citation, every library citation names a ref that a search in the run returned. Runs in CI.
- Where the library extracts are present, no run that searched repeats a retrieved library section in a fragment longer than 120 characters. CI skips this.
- Each challenge is complete, parses against the challenge schema, names a committed run, and has no rejected or unsupported citation. Runs in CI.
- Where the evidence and the extracts are present, each challenge's case citations resolve, and its answer repeats no library section that it or its run retrieved in a fragment longer than 120 characters.

## Status

- Slice 1, tested live on 2026-10-30: the run above. Tested locally on 2026-10-30: both tests pass, and each failed once on a broken copy of the file (an inference with its citations removed, a status changed to `incomplete`).
- Slice 2, tested live on 2026-11-02: the run above. Tested locally on 2026-11-02: every test passes, and each new or changed test failed once on a broken copy. A library citation changed to a ref the run did not retrieve failed the retrieved test and the case-citation test; a 150-character fragment of a retrieved section added to a finding failed the library-text test.
- Slice 3, tested live on 2026-11-03: the runs and challenges above. Tested locally on 2026-11-03: all 41 tests pass with the evidence and extracts present. A challenge citation changed to `cloudflare-2026-02-20/u99` failed the challenge citation test; a 150-character fragment of a retrieved section added to a finding of the gpt-6.1-sol run failed the library-text test.

## Licence

The investigations are model output about Cloudflare's status updates for incident `kwy3dt82bwbt`, which are not redistributed here. Measured with `difflib` against the evidence file, counting matches of 25 characters or more:

- Slice 1 (measured 2026-10-30): about a fifth of its text repeats the updates word for word, in fragments of at most 61 characters.
- Slice 2 (measured 2026-11-02): 17.6% of its text repeats the updates, in fragments of at most 56 characters.

- Slice 3 (measured 2026-11-03): the gpt-6-luna run repeats 17.0% of its text from the updates, in fragments of at most 49 characters; the gpt-6.1-sol run 6.3%, at most 44. The five challenges from the command repeat 11.8%, 20.9%, 35.3%, 20.6%, and 15.6% of their answers, and the four from the page 35.2%, 10.2%, 6.6%, and 15.3%, in fragments of at most 81 characters.

The slice 2 and slice 3 runs also read sections of earlier Cloudflare postmortems from the library, not redistributed here either. None of their text, nor any challenge's, repeats them in a match of 25 characters or more; the longest shared fragment is 22 characters in a run and 20 in a challenge.

# Investigation of the development case `cloudflare-2026-02-20`

The first investigation Hindcast ran: the live run behind gate row 1 of [milestone 4, slice 1](../../../docs/worklogs/04-investigator.md#gate). It is a development run, read against the evidence and not scored. The answer key stays closed until the milestone 5 rubric is frozen.

## The run

| Field | Value |
|---|---|
| Case | `cloudflare-2026-02-20` (Cloudflare status incident `kwy3dt82bwbt`, 10 updates, 2 charts) |
| Agent | `hindcast-investigator-gpt-6-luna`, version 1 |
| Model | deployment `gpt-6-luna`, model gpt-6-luna version 2026-09-22 |
| Prompt | `prompts/investigator.md`, blob `fb660e15cf20654c2d05696c89a63a313cc2ffe4`, clean |
| Code | commit `7c27d84`, clean |
| Evidence | `build/evidence/cloudflare-2026-02-20.json`, SHA-256 `ee6be350c1f4d19b393e12b13f87dfa97a0ba6341aed57e58fd9c2285381e074` |
| Outcome | `complete`; 10 findings, 8 timeline events, 2 factors, 4 open questions; 0 rejected citations, 0 unsupported |
| Usage | 2 model calls, 2 tool calls, 31.353 s; 3,776 input tokens (1,034 cached), 3,395 output tokens |

The reading of the result against the evidence is in the [worklog](../../../docs/worklogs/04-investigator.md#live-run).

## Files

| File | Purpose |
|---|---|
| `20261030T040215Z-v1.json` | The result file the command wrote, unchanged: the investigation, the agent, the model, the provenance, the checks, and the usage. |

`tests/test_committed_investigation.py` checks the file: it is complete and parses against the schema, and, where the evidence file is present, every item except the open questions keeps at least one case citation that resolves. The evidence is not in the repository, so CI skips the second test.

## Status

Tested live on 2026-10-30: the run above. Tested locally on 2026-10-30: both tests pass, and each failed once on a broken copy of the file (an inference with its citations removed, a status changed to `incomplete`).

## Licence

The investigation is model output about Cloudflare's status updates for incident `kwy3dt82bwbt`, which are not redistributed here. It paraphrases them: about a fifth of its text repeats the updates word for word, in fragments of at most 61 characters (measured with `difflib` against the evidence file on 2026-10-30, counting matches of 25 characters or more).

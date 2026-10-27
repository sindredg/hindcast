# Answer keys

One frozen key per case: what the provider's own postmortem says happened. Milestone 5 scores each scored case's reconstruction against its key; the development case's key is for iterating on the investigator in milestone 4 and is never scored. The investigator never sees a key or the postmortem it comes from ([decision 0005](../../docs/decisions/0005-evidence-library-and-answer-key.md)).

## Status

Frozen on 2026-10-27, before any scored run, with the prior-knowledge answers still unread. [`frozen.json`](frozen.json) records each key's SHA-256, and `tests/test_keys.py` fails if a key file changes or a frozen key has no file. A changed key is a new review, not an edit.

## Files

| File | What it is |
|---|---|
| [`cloudflare-2025-11-18.json`](cloudflare-2025-11-18.json) | Scored case |
| [`github-2026-08-17.json`](github-2026-08-17.json) | Scored case |
| [`google-cloud-2026-07-14.json`](google-cloud-2026-07-14.json) | Scored case |
| [`cloudflare-2026-02-20.json`](cloudflare-2026-02-20.json) | Development case, not scored |
| [`frozen.json`](frozen.json) | SHA-256 of each key |

## Fields

| Field | Meaning |
|---|---|
| `attack` | `attack` or `not an attack`. An attack is deliberate hostile action, such as a DDoS attack, an intrusion, or a route hijack, that caused the outage in whole or in part, as the postmortem states it. Heavy but legitimate traffic is not an attack unless the postmortem calls it one. |
| `attack_basis` | `stated` (the postmortem says it outright), `implied` (the cause it gives settles it, for example an internal configuration change), or `not stated` |
| `attack_quote` | The sentence the verdict rests on |
| `root_cause` | The root cause, close to the postmortem's wording |
| `contributing_factors` | Conditions the postmortem names as making the outage happen, spread, or last longer |
| `timeline` | Events the postmortem gives a time for, in UTC (`time`) and as written (`time_as_written`) |
| `fixes` | Changes the provider made or committed to after the outage; mitigation during the outage is in the timeline |
| `source_quote` | On every item: a sentence from the postmortem that states it. A table row's cells count as one sentence |
| `stated_during_incident` | On every item: true when a status update before the resolved one already said it, though not necessarily its exact time or detail |

`stated_during_incident` lets the evaluation report separate what a reconstruction could take from the evidence as written from what it had to work out. For example, the Google Cloud status page named "a recent configuration update" as the likely cause hours before the outage ended, so that key marks its root cause as stated.

## How the keys were made

Each postmortem was cut to its article (and, for GitHub's monthly report, to the case's incident) and extracted with the `hindcast_answer_key` analyzer ([`analyzers/answer-key.json`](../../analyzers/answer-key.json)). Each draft was then checked field by field against its postmortem: wrong values corrected, missing factors and events added, steps taken during the outage moved out of the fixes, and every time converted to UTC. Every quote, including those added in review, appears word for word in the captured postmortem: `tests/test_keys.py::test_every_frozen_quote_appears_in_its_postmortem` checks it where the captured pages are present. The corrections were approved before freezing. The procedure is in the [extraction runbook](../../docs/runbooks/extraction.md).

## Limits

- All four keys say `not an attack`. A reconstruction that always answers "not an attack" gets every verdict right, so the evaluation reports the attack verdict together with its reasoning and citations, never as accuracy alone.
- A postmortem can disagree with itself. Where it gives two times for the same event, both are kept with their own quotes (Cloudflare 2025-11-18 gives 11:20 and 11:28 for the start). The GitHub key's end time is 13:40 UTC plus the duration in the report's heading; the report's impact summary gives a shorter duration.
- `stated_during_incident` is a judgment about meaning, not a string match.

## Sources and attribution

Each key quotes short passages from the provider's postmortem, under the copyright of the provider. The pages themselves are not in the repository; their URLs, retrieval times, and SHA-256 hashes are in [`data/cases.yaml`](../../data/cases.yaml).

| Key | Postmortem |
|---|---|
| `cloudflare-2025-11-18` | Cloudflare blog, [Cloudflare outage on November 18, 2025](https://blog.cloudflare.com/18-november-2025-outage/) |
| `github-2026-08-17` | GitHub blog, [GitHub availability report: August 2026](https://github.blog/news-insights/company-news/github-availability-report-august-2026/), incident of August 17 |
| `google-cloud-2026-07-14` | Google Cloud Service Health, [incident T8gmtofFSTGT5tbhyciF](https://status.cloud.google.com/incidents/T8gmtofFSTGT5tbhyciF) |
| `cloudflare-2026-02-20` | Cloudflare blog, [Cloudflare outage on February 20, 2026](https://blog.cloudflare.com/cloudflare-outage-february-20-2026/) |

# Case sources

Findings about the providers' status pages and postmortems: what they keep, in what form, and where the answer leaks into the evidence.

## Google Cloud's status feed holds recent incidents only, and there is no per-incident JSON (2026-10-25)

**Seen:** `https://status.cloud.google.com/incidents.json` returned 8 incidents, the oldest from 2026-02-27. A single incident's page is served as HTML, but the same path with `.json` returns HTTP 404.

**Evidence:** tested live, 2026-10-25, with `curl`: the feed's earliest `begin` was 2026-02-27; `incidents/<id>` returned 200 and `incidents/<id>.json` returned 404 for the newest incident in the feed.

**For Hindcast:** a Google Cloud case is captured while it is still in the feed. `python -m hindcast.capture status --provider "Google Cloud"` takes the incident's entry from the feed; `--feed-file` with `--retrieved-at` reads a saved copy when the live feed has dropped it.

**Read more:** [Google Cloud Service Health](https://status.cloud.google.com/).

## Statuspage feeds hold the last 50 incidents, but the per-incident API returns older ones (2026-10-25)

**Seen:** Cloudflare's and GitHub's status pages run on Atlassian Statuspage. Their `api/v2/incidents.json` feeds held 50 incidents each, reaching back only to 2026-10-12 for Cloudflare and 2026-08-12 for GitHub. The per-incident endpoint `api/v2/incidents/<id>.json` still returned an incident from 2025-11-18 with all 22 updates.

**Evidence:** tested live, 2026-10-25. Incident IDs older than the feed were found in the Internet Archive's index of the status pages, then read from the providers' API.

**For Hindcast:** older cases are captured by incident ID. Finding an old ID takes a search outside the provider's own feed.

**Read more:** [Statuspage API](https://developer.statuspage.io/).

## A status response hashes differently when anything else on the page changes (2026-10-25)

**Seen:** a Statuspage incident response carries a `page` block next to the `incident`. Its `updated_at` follows the status page, not the incident, so the hash of the raw response can change for an incident that has not changed.

**Evidence:** tested live, 2026-10-25: the response for GitHub's incident of 2026-08-17 had `page.updated_at` 2026-10-25T17:24:46Z; Cloudflare's had 2026-08-27. A snapshot of the `incident` object alone, as canonical JSON, was captured twice for Cloudflare's 2025-11-18 incident and gave the same SHA-256 both times (`95e7a2ef…`).

**For Hindcast:** `hindcast.capture` keeps the incident object only, so a registry hash pins the incident, not the page around it.

**Read more:** [Statuspage API](https://developer.statuspage.io/).

## The resolved update often carries the provider's summary of the cause (2026-10-25)

**Seen:** GitHub's update that marked its 2026-08-17 incident resolved is a full summary: duration, impact, the cause, and follow-up actions. Google Cloud's update that marked its 2026-07-14 incident available has a summary and a description of what failed. Cloudflare's resolved updates for its 2025-11-18 and 2026-02-20 incidents say only that the incident was resolved.

**Evidence:** read from the captured snapshots in the [case registry](../../data/cases.yaml), 2026-10-25.

**For Hindcast:** the case evidence ends before the resolved update; its time and status stay and its text is withheld ([decision 5](../decisions/0005-evidence-library-and-answer-key.md)).

**Read more:** [GitHub status](https://www.githubstatus.com/), [Google Cloud Service Health](https://status.cloud.google.com/).

## Google Cloud adds its incident reports to the live incident record (2026-10-25)

**Seen:** the 2026-07-14 incident record holds, after its live updates, a "Preliminary Incident Report" posted on 2026-07-20 and an "Incident Report" with the root cause posted on 2026-07-24. Both are entries in the same `updates` list as the live updates.

**Evidence:** read from the captured snapshot of incident `T8gmtofFSTGT5tbhyciF`, 2026-10-25.

**For Hindcast:** the evidence cut drops report entries by type, and an entry type the rules do not know is dropped and listed ([decision 5](../decisions/0005-evidence-library-and-answer-key.md)). The incident page, which shows the report, is registered as the answer key.

**Read more:** [Google Cloud Service Health](https://status.cloud.google.com/).

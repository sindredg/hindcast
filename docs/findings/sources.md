# Case sources

Findings about the providers' status pages, postmortems, and charts: what they keep, in what form, and where the answer leaks into the evidence.

## A GitHub blog post's body ends with its author's bio and photo (2026-10-27)

**Seen:** on github.blog the element that holds a post's text also holds, after the last paragraph, the post's tags, a "Written by" heading, and an author bio with name and photo.

**Evidence:** tested live, 2026-10-27, on the six captured github.blog pages in the library. The first extraction kept those blocks: the six extracts ended with "Tags", "Written by", and a section headed with the author's name, each listing the photo as a figure. After the GitHub rule dropped the blocks, the six extracts had one figure fewer each and none contains "Written by".

**For Hindcast:** `hindcast.library_extract` drops the tags, the "Written by" block, and the author bio from GitHub posts. A new site gets its own rule, and its first extracts are checked for names and portraits ([troubleshooting](../troubleshooting.md)).

**Read more:** none; the page layout is not documented.

## Cloudflare Radar serves whole UTC days, and only to a browser (2026-10-27)

**Seen:** Radar's chart downloads cover whole UTC days from 00:00 to 23:45, whatever times the page address asks for. The site refuses scripted requests and the API needs an account token, so charts are downloaded by hand in a browser. A chart can carry a shaded band and a bar under the axis, Radar's marking of an event, without text.

**Evidence:** tested live, 2026-10-27. `curl` on `radar.cloudflare.com/traffic`: HTTP 403; the API: code 9106, "Missing X-Auth-Key, X-Auth-Email or Authorization headers". In a browser, `traffic?dateStart=2025-11-18T10:48:00Z&dateEnd=2025-11-18T19:28:00Z` produced charts labelled "Nov 18, 2025, 00:00 UTC → Nov 18, 2025, 23:45 UTC", with a shaded band from about 11:48 to 14:42.

**For Hindcast:** a case's chart can show the hours after its resolved update. The development case's views end before it; the 2025-11-18 view runs about four hours past it, recorded with the chart ([`data/charts/`](../../data/charts/README.md)). Radar's graphs are CC BY 4.0, so the images are committed with attribution.

**Read more:** [Cloudflare Radar](https://developers.cloudflare.com/radar/).

## AWS post-event summaries and Azure post-incident reviews state no publish date (2026-10-27)

**Seen:** most AWS post-event summaries carry no publish date, and Azure's post-incident reviews have neither a date nor a page of their own: each is a collapsed entry on a status history page. Cloudflare's blog, the GitHub blog, and Google Cloud's incident pages state their dates.

**Evidence:** read live, 2026-10-27. Seven AWS summaries (including `aws.amazon.com/message/101925/`) show no date; `aws.amazon.com/message/12721/` states "December 10th, 2021". The Azure reviews are entries on `azure.status.microsoft/en-us/status/history/`, and their short links lead to a feedback form.

**For Hindcast:** a library document has to state its publish date ([decision 13](../decisions/0013-library-selection.md)). The library has one AWS document and no Azure document.

**Read more:** [AWS post-event summaries](https://aws.amazon.com/premiumsupport/technology/pes/), [Azure status history](https://azure.status.microsoft/en-us/status/history/).

## Google Cloud's status feed holds recent incidents only, and there is no per-incident JSON (2026-10-25)

**Seen:** `https://status.cloud.google.com/incidents.json` returned 8 incidents, the oldest from 2026-02-27. An incident's page is HTML; the same path with `.json` returns HTTP 404.

**Evidence:** tested live, 2026-10-25, with `curl`: the feed's earliest `begin` was 2026-02-27; `incidents/<id>` returned 200 and `incidents/<id>.json` returned 404 for the newest incident.

**For Hindcast:** a Google Cloud case is captured while it is in the feed. `python -m hindcast.capture status --provider "Google Cloud"` takes the entry from the feed; `--feed-file` with `--retrieved-at` reads a saved copy.

**Read more:** [Google Cloud Service Health](https://status.cloud.google.com/).

## Statuspage feeds hold the last 50 incidents, but the per-incident API returns older ones (2026-10-25)

**Seen:** Cloudflare's and GitHub's `api/v2/incidents.json` feeds held 50 incidents each, back to 2026-10-12 for Cloudflare and 2026-08-12 for GitHub. `api/v2/incidents/<id>.json` still returned an incident from 2025-11-18 with all 22 updates.

**Evidence:** tested live, 2026-10-25. Older incident IDs were found in the Internet Archive's index of the status pages, then read from the providers' API.

**For Hindcast:** older cases are captured by incident ID, found outside the provider's feed.

**Read more:** [Statuspage API](https://developer.statuspage.io/).

## A status response hashes differently when anything else on the page changes (2026-10-25)

**Seen:** a Statuspage incident response carries a `page` block whose `updated_at` follows the status page, not the incident, so the hash of the raw response changes for an unchanged incident.

**Evidence:** tested live, 2026-10-25: GitHub's incident of 2026-08-17 had `page.updated_at` 2026-10-25T17:24:46Z; Cloudflare's had 2026-08-27. The `incident` object alone, as canonical JSON, captured twice for Cloudflare's 2025-11-18 incident, gave the same SHA-256 both times (`95e7a2ef…`).

**For Hindcast:** `hindcast.capture` keeps the incident object only, so a registry hash pins the incident.

**Read more:** [Statuspage API](https://developer.statuspage.io/).

## The resolved update often carries the provider's summary of the cause (2026-10-25)

**Seen:** GitHub's resolving update for its 2026-08-17 incident is a full summary: duration, impact, cause, and follow-up. Google Cloud's for its 2026-07-14 incident has a summary and what failed. Cloudflare's for 2025-11-18 and 2026-02-20 say only that the incident was resolved.

**Evidence:** read from the captured snapshots in the [case registry](../../data/cases.yaml), 2026-10-25.

**For Hindcast:** the evidence ends before the resolved update, keeping its time and status and withholding its text ([decision 5](../decisions/0005-evidence-library-and-answer-key.md)); `hindcast.evidence` cuts every case this way and drops Google Cloud's report entries ([worklog](../worklogs/02-extraction.md#evidence-cut)).

**Read more:** [GitHub status](https://www.githubstatus.com/), [Google Cloud Service Health](https://status.cloud.google.com/).

## Google Cloud adds its incident reports to the live incident record (2026-10-25)

**Seen:** the 2026-07-14 incident record holds, after its live updates, a "Preliminary Incident Report" posted 2026-07-20 and an "Incident Report" with the root cause posted 2026-07-24, both in the same `updates` list.

**Evidence:** read from the captured snapshot of incident `T8gmtofFSTGT5tbhyciF`, 2026-10-25.

**For Hindcast:** `hindcast.evidence` drops report entries by type, and drops and lists any unknown entry type ([decision 5](../decisions/0005-evidence-library-and-answer-key.md)); for this case it drops two. The incident page, which shows the report, is the answer key.

**Read more:** [Google Cloud Service Health](https://status.cloud.google.com/).

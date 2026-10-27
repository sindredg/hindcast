# Case sources

Findings about the providers' status pages, postmortems, and charts: what they keep, in what form, and where the answer leaks into the evidence.

## A GitHub blog post's body ends with its author's bio and photo (2026-10-27)

**Seen:** on github.blog the element that holds a post's text also holds, after the last paragraph, the post's tags, a "Written by" heading, and an author bio with the author's name and photo. Cutting the page to that element is not enough to keep a person out of the extract.

**Evidence:** tested live, 2026-10-27, on the six captured github.blog pages in the library. The first library extraction kept those blocks: the six extracts ended with "Tags", "Written by", and a section headed with the author's name, and each listed the author's photo as a figure. After the GitHub rule dropped the blocks, the six pages were extracted again with one figure fewer each, and no extract contains "Written by".

**For Hindcast:** `hindcast.library_extract` drops the tags, the "Written by" block, and the author bio from GitHub posts. A new site gets its own rule, and its first extracts are checked for names and portraits before use ([troubleshooting](../troubleshooting.md)).

**Read more:** none; the page layout is not documented.

## Cloudflare Radar serves whole UTC days, and only to a browser (2026-10-27)

**Seen:** Radar's chart downloads cover whole UTC days from 00:00 to 23:45, even when the page address asks for exact times. The site refuses scripted requests, and the Radar API needs an account token, so charts are downloaded by hand in a browser. A chart can carry a shaded band and a bar under the axis, Radar's own marking of an event, without text.

**Evidence:** tested live, 2026-10-27. `curl` on `radar.cloudflare.com/traffic` returned HTTP 403; the API returned code 9106, "Missing X-Auth-Key, X-Auth-Email or Authorization headers". In a browser, `traffic?dateStart=2025-11-18T10:48:00Z&dateEnd=2025-11-18T19:28:00Z` produced charts labelled "Nov 18, 2025, 00:00 UTC → Nov 18, 2025, 23:45 UTC", with a shaded band from about 11:48 to 14:42.

**For Hindcast:** a case's chart can show the hours after its resolved update. The development case's views end before its resolved update; the 2025-11-18 view runs about four hours past it, which is recorded with the chart ([`data/charts/`](../../data/charts/README.md)). Radar's downloadable graphs and images are licensed CC BY 4.0, so the images are committed with their attribution.

**Read more:** [Cloudflare Radar](https://developers.cloudflare.com/radar/).

## AWS post-event summaries and Azure post-incident reviews state no publish date (2026-10-27)

**Seen:** most AWS post-event summaries carry no publish date on the page, and Azure's post-incident reviews have neither a publish date nor a page of their own: each is a collapsed entry on a status history page that also lists later reviews. Cloudflare's blog, the GitHub blog, and Google Cloud's incident pages state their dates.

**Evidence:** read live, 2026-10-27, while searching for library candidates. Seven AWS summaries checked (including `aws.amazon.com/message/101925/`) show no date; one, `aws.amazon.com/message/12721/`, states "December 10th, 2021" under its title. The Azure reviews are entries on `azure.status.microsoft/en-us/status/history/`, and their short links lead to a feedback form.

**For Hindcast:** a library document has to state its publish date, so a served case can be shown only documents published before it began ([decision 13](../decisions/0013-library-selection.md)). The library has one AWS document and no Azure document.

**Read more:** [AWS post-event summaries](https://aws.amazon.com/premiumsupport/technology/pes/), [Azure status history](https://azure.status.microsoft/en-us/status/history/).

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

**For Hindcast:** the case evidence ends before the resolved update, keeping its time and status and withholding its text ([decision 5](../decisions/0005-evidence-library-and-answer-key.md)). `hindcast.evidence` cuts every case this way, and Google Cloud's report entries are dropped ([worklog](../worklogs/02-extraction.md#evidence-cut)).

**Read more:** [GitHub status](https://www.githubstatus.com/), [Google Cloud Service Health](https://status.cloud.google.com/).

## Google Cloud adds its incident reports to the live incident record (2026-10-25)

**Seen:** the 2026-07-14 incident record holds, after its live updates, a "Preliminary Incident Report" posted on 2026-07-20 and an "Incident Report" with the root cause posted on 2026-07-24. Both are entries in the same `updates` list as the live updates.

**Evidence:** read from the captured snapshot of incident `T8gmtofFSTGT5tbhyciF`, 2026-10-25.

**For Hindcast:** `hindcast.evidence` drops report entries by type, and drops and lists any entry type the rules do not know ([decision 5](../decisions/0005-evidence-library-and-answer-key.md)); for this case it drops two report entries. The incident page, which shows the report, is registered as the answer key.

**Read more:** [Google Cloud Service Health](https://status.cloud.google.com/).

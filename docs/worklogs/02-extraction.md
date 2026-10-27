# Milestone 2: Extraction

Status: Open. Everything the milestone builds was built and run on 2026-10-27: the evidence cut, ingestion from Blob Storage, the library and its extraction, the charts, and the frozen answer keys. The independent review is open. The milestone state is in the [roadmap](../roadmap.md).

## Scope

Cut each case's status updates into evidence, extract the postmortem library and the answer keys, and describe the charts ([roadmap](../roadmap.md#2-extraction)). The procedure to rebuild it is the [runbook](../runbooks/extraction.md).

## Work completed

### Settings per component

`hindcast.config` loads one section per component (models, storage, extraction, search) instead of every variable at once, so the `.env` the foundations runbook writes, with search and embedding still empty, loads for everything milestone 2 runs. `hindcast.models` now reads its endpoint through the model section. This closes [#3](https://github.com/sindredg/hindcast/issues/3). Tested locally: `tests/test_config.py`, 9 tests, which failed on the missing names before the code existed. Live, 2026-10-27: one `ask_model` call on gpt-6-luna through the project answered after the change.

### Evidence cut

`hindcast.evidence` applies [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) per status format:

| Format | Kept | Resolved mark | Report entries | Unknown |
|---|---|---|---|---|
| Statuspage (Cloudflare, GitHub) | `investigating`, `identified`, `monitoring`, `update` | first `resolved`: time and status, text withheld | `postmortem` | any other status |
| Google Cloud feed entry | `SERVICE_DISRUPTION`, `SERVICE_OUTAGE`, `SERVICE_INFORMATION` | first `AVAILABLE` | any update that opens with a Markdown heading | any other status |

Everything after the resolved mark is dropped as well. Dropped entries are listed with time, status, and reason, never with their text. Times are normalised to UTC and sorted.

Tested locally: `tests/test_evidence.py`, 14 tests. The first 11 ran first against a missing module; the 3 added after the code review below failed on the code before its fix. They include a planted report entry for each format (a `postmortem` update on a Statuspage incident and a `## Mini Incident Report` update before Google's `AVAILABLE`), an unknown status, updates after the first resolved one, mixed time formats out of order, updates in the same second given newest first, an update tied with the resolved mark, a time without a zone, and an incident that never resolved.

The model re-check's dataset builder now calls the same cut. Rebuilt on 2026-10-27, the dataset file is byte for byte the one the evaluation runs used (`cmp` equal, SHA-256 starting `b76a883bd24595a5`), and `check_quotes.py` still finds 6 of 6 quotes in each committed run.

### Blob access from code

`hindcast.storage` reads and writes Blob Storage with `DefaultAzureCredential`. A download is refused unless its SHA-256 matches the registry; an upload never overwrites unless asked. `azure-storage-blob` 12.31.0, the newest stable release on PyPI (released 2026-09-30), is now a direct dependency; it was already in the locked tree through `azure-ai-projects`, so the lock gained no package. `pip-audit --strict --disable-pip --require-hashes` on the exported lock: no known vulnerabilities.

Tested locally: `tests/test_storage.py`, 5 tests with a fake container. Live, 2026-10-27: the development case's status snapshot downloaded from Blob Storage with the Azure CLI sign-in (12,241 bytes, the size of the local copy); the same call with one character of the pinned hash changed raised `SourceMismatch: cloudflare-status-2026-02-20: downloaded bytes do not match the registry`.

### Ingestion

`python -m hindcast.ingest evidence` downloads each case's snapshot, cuts it, and writes the evidence to `build/evidence/` and Blob `extracted/evidence/`. Tested locally: `tests/test_ingest.py`, 6 tests, including that a source failing its hash writes nothing anywhere, that identical evidence already in Blob Storage only writes the local copy, that different evidence is kept and reported, and that one failing case does not stop the others. Live, 2026-10-27, first run:

```
cloudflare-2025-11-18: 22 updates (resolved 2025-11-18T19:28:36Z), dropped 0
cloudflare-2026-02-20: 10 updates (resolved 2026-02-20T23:50:58Z), dropped 0
github-2026-08-17: 36 updates (resolved 2026-08-17T21:15:46Z), dropped 0
google-cloud-2026-07-14: 9 updates (resolved 2026-07-15T05:34:26Z), dropped 2
  report: 2
```

These were the counts expected from the snapshots' structure before the run (update statuses and times, no text). A second run without `--replace` refused all four uploads and exited 1. Each Blob copy equals its local file, every resolved update's text is `null`, and the Google evidence contains no "Incident Report" heading.

After the code review, existing evidence is compared instead of refused. Live, 2026-10-27, with `build/evidence/` moved away: each case reported the same counts and `blob: unchanged`, exit 0, and the four local files were rebuilt byte for byte as before. The cut fix left the four cases' evidence and the dataset hash unchanged.

### Library pick rule

[Decision 0013](../decisions/0013-library-selection.md) picks the library by what an outside engineer could see during each case, with decoys, instead of by the known cause. The symptom tags each case is picked by are in [`data/library.yaml`](../../data/library.yaml): `product`, `symptom`, or `scale`, each quoting its update word for word. They were committed in commit `85b4561`, before the search for library documents began; that commit is the proof of order. Each case's start time joined the registry in commit `ac98004` (`Case.started_at`, refused unless it is a UTC timestamp).

Tested locally: `tests/test_library.py` checks every tag's form and that each quote appears in the update it names. The quote check runs where the captured snapshots are present, so CI skips it; locally it failed on a changed quote, a wrong update ID, and an empty quote.

### Library registry and picks

`hindcast.library` loads the registry and refuses a document dated on or after the start day of any case it serves, a missing or non-ISO date, a URL that is a case's own source, a document ID used twice across cases and library, an unknown served case, and a reason that quotes none of the served case's tagged symptoms. Tested locally: `tests/test_library.py`, each check shown failing once with the check switched off.

Candidates were searched in the providers' archives from the symptom tags alone; the cases' causes were not part of the search. Two search-result summaries showed a line of the GitHub case's report and a summary of the development case's post; the picks for those two cases had been made before those searches. Of 29 candidates, 23 were kept:

| Kind | Documents |
|---|---|
| Same provider | 8 |
| Attack suspected | 6 |
| Decoy | 5 |
| Other provider | 4 |

By provider: Cloudflare 11, GitHub 6, Google Cloud 5, AWS 1. The decoys are the one place a case's cause was used: each decoy's cause was compared with its case's to make sure they differ. Six candidates were dropped: one whose only date may be the event day (fails closed), three whose causes were too close to the Google case's to serve as decoys, and two for size.

Gaps: no Azure document (post-incident reviews state no publish date and have no page of their own) and one AWS document ([sources](../findings/sources.md#aws-post-event-summaries-and-azure-post-incident-reviews-state-no-publish-date-2026-10-27)). Nothing matches GitHub's download errors, SCIM, or Copilot sign-in, nothing at any provider covers VMware stretched clusters, and nothing covers BYOIP. Some picks share a case's cause class, such as a bad change pushed to the whole network; they were picked on symptoms and stay under the rule.

### Library capture

Each page was captured once over HTTPS on 2026-10-27 between 15:59:14 and 15:59:27 UTC, its SHA-256 and retrieval time pinned in the registry, and uploaded to Blob `sources/library/` (`hindcast.storage.upload_source`, which never overwrites). Tested live: all 23 blobs downloaded into an empty directory match their hashes, and a copy with one flipped byte is refused by `download_source` with `SourceMismatch` naming the document. `tests/test_library.py` loads the registry strictly, so a missing hash or time fails it.

### Content Understanding setup

Three analyzers are defined in [`analyzers/`](../../analyzers/): `hindcast_postmortem` (article markdown, title, publish date), `hindcast_chart` (description, text in the image, alt text), and `hindcast_answer_key` (attack verdict and basis, root cause, contributing factors, timeline, fixes, each with a quote). They use gpt-5-mini 2025-08-07 for completion; the two on the document base also name `text-embedding-3-large` ([decision 0014](../decisions/0014-extraction-and-embedding-models.md)). `hindcast.extract` creates missing analyzers, refuses one whose service copy differs from its file, and replaces one from its file on request.

Live, 2026-10-27:

- Cognitive Services Content Understanding Contributor was assigned to the developer on the Foundry resource at 15:38 UTC.
- `supportedModels` lists gpt-5-mini; no defaults were set (`DefaultsNotSet`).
- The document analyzers could not be created without an embedding deployment. A `text-embedding-3-large` deployment (version 1, Global Standard, 50K tokens per minute, automatic upgrade off) was added and set as a default with gpt-5-mini ([troubleshooting](../troubleshooting.md)).
- All three analyzers reported `ready`; a second run created none, and a locally changed definition raised `AnalyzerDiffers`.
- Smoke test on the development case's postmortem: 18 minimal pages, 18,000 contextualization tokens, gpt-5-mini 18,999 input and 132 output tokens, 9.5 seconds; `published_date` 2026-02-21, the date in the page's metadata.

Tested locally: `tests/test_extract.py`, including a check of every key in the analyzer files against the field names the SDK defines, which failed on a misspelt field key and a misspelt setting. What the service did that the documentation does not say is in the [extraction findings](../findings/extraction.md).

### Library extraction

`python -m hindcast.ingest library` downloads each page (hash-checked), cuts out the article by a fixed rule per site, checks that the page's own date equals the registry's, extracts the article with `hindcast_postmortem`, splits it into sections by heading, drops text dated after the earliest served case and undated update notes, and describes each image in the article with `hindcast_chart`. Library figures are never displayable. A page whose title, date, or body its site's rule cannot find is refused. An extract already in Blob Storage is reused unless `--replace` is given.

Tested locally: `tests/test_library_extract.py` and `tests/test_ingest.py`, each rule shown failing once with the rule switched off. Live, 2026-10-27, 16:10:12 to 16:21:17 UTC: 23 of 23 documents extracted and uploaded, exit 0; usage 118 minimal pages, 189,000 contextualization tokens, gpt-5-mini 130,915 input (34,944 more cached) and 22,752 output tokens. A check of the extracts found the GitHub author bios and photos ([troubleshooting](../troubleshooting.md)); after the fix, six documents were extracted again (19 pages, 26,000 contextualization tokens, gpt-5-mini 22,555 input and 2,493 output), and two monthly reports again so that each incident is its own section (6 pages, 6,000 contextualization tokens). Final library: 23 extracts, 176 sections, 65 described figures, no text dropped for its date. No extract mentions a case's report or a case's date. The one Google page whose newest update postdates its report counts as published on that newest update (2020-12-22).

### Charts

Radar refuses scripted downloads, so the charts were downloaded in a browser ([sources](../findings/sources.md#cloudflare-radar-serves-whole-utc-days-and-only-to-a-browser-2026-10-27)) and committed under [`data/charts/`](../../data/charts/README.md) with their source, licence, and attribution. The registry refuses a chart whose licence is not CC BY 4.0. `python -m hindcast.ingest charts` describes each chart once and stores the description; evidence ingestion attaches it with a stable ID.

| Case | Views | Window |
|---|---|---|
| `cloudflare-2026-02-20` | Announced IPv4 space and BGP announcements for AS13335 | Whole UTC day, ending at 23:45, before the resolved update |
| `cloudflare-2025-11-18` | HTTP traffic worldwide | Whole UTC day, about four hours past the resolved update |

Views left out: announced IPv6 space (its only change is about six hours before the outage), two traffic views that repeat the HTTP chart, and a map without a time axis. Live, 2026-10-27: three descriptions (3,000 contextualization tokens, gpt-5-mini 1,132 input and 1,261 output); then all four cases' evidence replaced, each Blob copy equal to its local file, every resolved update's text `null`, and the model re-check dataset still the same bytes (SHA-256 starting `b76a883bd24595a5`). A description gave a value no label in the image shows ([extraction findings](../findings/extraction.md#a-chart-description-gets-times-roughly-right-and-can-invent-a-value-2026-10-27)).

### Answer keys

`python -m hindcast.keys draft` cuts each case's postmortem to its article (and the GitHub report to the case's incident), runs `hindcast_answer_key`, and writes a draft and a review sheet. Content Understanding returns no source locations for HTML, so each item carries a quote, checked word for word against the extracted text. Live, 2026-10-27: four drafts, together 24 minimal pages and about 23,000 gpt-5-mini input and 5,000 output tokens.

Each draft was then checked field by field against its postmortem. The corrections: the Google Cloud end time converted to UTC; the attack basis of the GitHub and Google Cloud keys changed to `implied`, since the cause each postmortem gives settles the question; missing contributing factors and timeline events added; steps taken during an outage moved out of the fixes; and every item a status update had already stated marked `stated_during_incident`. The corrections were approved, and the keys frozen with `python -m hindcast.keys freeze <case_id>` in commit `c2133df`. The keys, the attack definition, and the rules are described in the [keys README](../../eval/keys/README.md).

| Key | Attack | Basis | Factors | Timeline | Fixes | Stated during the incident |
|---|---|---|---|---|---|---|
| `cloudflare-2025-11-18` | not an attack | stated | 7 | 11 | 4 | 6 |
| `github-2026-08-17` | not an attack | implied | 3 | 2 | 5 | 3 |
| `google-cloud-2026-07-14` | not an attack | implied | 3 | 3 | 5 | 3 |
| `cloudflare-2026-02-20` | not an attack | stated | 6 | 13 | 3 | 6 |

Tested locally: `tests/test_keys.py` refuses a key with a missing field, an attack value outside the definition, or a time that is not UTC in form, and checks every frozen key against its hash in `eval/keys/frozen.json`; one changed byte in a frozen key failed it, and freezing a frozen case is refused.

### Role removal

Live, 2026-10-27: the Content Understanding role was removed at 18:23:46 UTC, leaving Owner, Foundry User at project scope, and Storage Blob Data Contributor. Content Understanding reads kept succeeding until 18:34:23 and were refused from 18:35:09 with `PermissionDenied` naming `analyzers/read` ([identity findings](../findings/identity-and-access.md#a-removed-role-kept-working-on-content-understanding-for-about-11-minutes-2026-10-27)). A model call through the project endpoint still answered on the project-scope role ("Blue", 24 input and 18 output tokens).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Ingestion reads the sources from Blob Storage with an Entra token | Tested live | The ingestion run above read all four snapshots, and the library extraction all 23 pages, from Blob Storage with the Azure CLI sign-in's token; a changed hash is refused (`SourceMismatch`, live) |
| The evidence cut, tested per provider with fixed inputs including a planted report entry | Tested locally and live | `tests/test_evidence.py` (14 tests; 11 run first against a missing module, 3 failing on the code before the review fix); live counts above |
| Library postmortems extracted into sections with publish dates; charts described with their source | Tested live | Library extraction above: 23 documents, 176 sections, 65 described figures with source URL and SHA-256; each page's date equals the registry's or the page is refused (`tests/test_library_extract.py`) |
| Answer keys extracted, reviewed by a person, and frozen by hash | Tested | Answer keys above: each field checked against its postmortem, every quote verified in code, corrections approved before freezing; `tests/test_keys.py` checks each key against `eval/keys/frozen.json` and failed on one changed byte |
| A third-party chart is shown only under a licence that allows it | Tested locally | `tests/test_cases.py::test_chart_sources_need_a_display_licence` and `tests/test_library_extract.py::test_library_figures_are_never_displayable`; the three Radar charts are CC BY 4.0 with their attribution in [`data/charts/`](../../data/charts/README.md) |

## Independent review

Open for the milestone.

### Code review of the first pull request

A separate agent reviewed the first pull request read-only on 2026-10-27, against the plan, decision 0005, and the project rules. Each finding was checked again before it was acted on; none was rejected. Fixed in that pull request:

- The cut sorted on times truncated to the second, and providers list updates newest first, so an update posted after the resolved one in the same second was kept with its text. Updates now sort at full precision, and on an exact tie the resolved mark goes first.
- A time without a zone was read as the machine's local time; it is now refused.
- A second workstation with an empty `build/` could not get the evidence without overwriting Blob Storage; identical evidence now writes the local copy.
- A refused cut or a missing blob stopped the whole run; each case now fails on its own.
- A test that matched the case ID too loosely, and two test counts in this worklog.

## Deviations from the plan

- The model re-check scripts that import the dataset builder now import `hindcast`, which is not installed as a package, so their commands in the [foundations runbook](../runbooks/foundations.md#re-check-the-model-choice) gained `PYTHONPATH=src`.
- The analyzer IDs use underscores, since the service refuses hyphens.
- The project gained an embedding deployment, which the document analyzers require; retrieval reuses it.
- The answer-key analyzer gained a quote per item and a timeline time as written next to the UTC time, because HTML results carry no source locations. It was replaced in place, which the Contributor role allows although it cannot delete.
- The article is cut out of each page in code before extraction, by a rule per site; the plan cut it after extraction. Extraction bills fewer pages, and a page the rule cannot read is refused.
- Text dropped for its date would be listed in each extract's `dropped` field, not in the registry entry that decision 0013 names; none was found.
- Chart descriptions are stored once and attached during evidence ingestion, so evidence ingestion stays deterministic.
- The 2025-11-18 chart runs past the resolved update; Radar offers whole days only.
- A document has one kind; where it serves a second case in another relation, its reason says so.

## Follow-up

- [#12](https://github.com/sindredg/hindcast/issues/12): the answer-key draft check accepts a time that was not converted to UTC.
- [#13](https://github.com/sindredg/hindcast/issues/13): the extraction model upgrades automatically, and extracts do not record its version.

## Not verified

- A Statuspage incident with an `update` or `postmortem` status in a real capture: none of the four cases has one, so those rules are tested only on hand-made input.
- The extracts and figure descriptions were checked by sample: the section headings of two documents, one figure, and a search of all extracts for case reports, case dates, and bylines. The 65 library figure descriptions were not each compared with their images.
- `stated_during_incident` is a judgment about meaning, made per item.
- The cost of extraction in currency: the usage is recorded above; Cost Management was not read for it.
- The prior-knowledge risk in library selection: the rule, the quoted symptom on every pick, and the decoys reduce it; nothing measures it.

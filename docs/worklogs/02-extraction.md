# Milestone 2: Extraction

Status: Verified on 2026-10-27, built and run the same day ([gate](#gate), [independent review](#independent-review)). Milestone state: [roadmap](../roadmap.md#status).

On this page: [Scope](#scope) · [Work completed](#work-completed) · [Gate](#gate) · [Independent review](#independent-review) · [Deviations from the plan](#deviations-from-the-plan) · [Follow-up](#follow-up) · [Not verified](#not-verified)

## Scope

Evidence cut per case, postmortem library, answer keys, chart descriptions ([roadmap](../roadmap.md#2-extraction)). Rebuild: [runbook](../runbooks/extraction.md).

## Work completed

### Settings per component

`hindcast.config` loads one section per component (models, storage, extraction, search), so a `.env` without search values loads. Closes [#3](https://github.com/sindredg/hindcast/issues/3). Tested locally: `tests/test_config.py`, 9 tests, failed before the code. Live, 2026-10-27: one `ask_model` call on gpt-6-luna answered.

### Evidence cut

`hindcast.evidence` applies [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) per status format:

| Format | Kept | Resolved mark | Report entries | Unknown |
|---|---|---|---|---|
| Statuspage (Cloudflare, GitHub) | `investigating`, `identified`, `monitoring`, `update` | first `resolved`: time and status, text withheld | `postmortem` | any other status |
| Google Cloud feed entry | `SERVICE_DISRUPTION`, `SERVICE_OUTAGE`, `SERVICE_INFORMATION` | first `AVAILABLE` | any update opening with a Markdown heading | any other status |

Everything after the resolved mark is dropped; dropped entries are listed with time, status, and reason, never text. Times are UTC, sorted.

Tested locally: `tests/test_evidence.py`, 14 tests (11 first against a missing module, 3 added after the code review, failing before its fix), with a planted report entry per format, an unknown status, same-second and tied updates, a time without a zone, an unresolved incident.

The model re-check's dataset builder calls the same cut. Rebuilt on 2026-10-27: `cmp` equal to the file the evaluation runs used (SHA-256 starting `b76a883bd24595a5`); `check_quotes.py` still 6 of 6 per run.

### Blob access from code

`hindcast.storage` uses `DefaultAzureCredential`; a download must match the registry's SHA-256, an upload never overwrites unless asked. `azure-storage-blob` 12.31.0 (newest stable on PyPI, 2026-09-30) is a direct dependency; already in the lock through `azure-ai-projects`, so no new package. `pip-audit --strict --disable-pip --require-hashes`: no known vulnerabilities.

Tested locally: `tests/test_storage.py`, 5 tests, fake container. Live, 2026-10-27: the development snapshot downloaded (12,241 bytes, the local size); with one hash character changed: `SourceMismatch: cloudflare-status-2026-02-20: downloaded bytes do not match the registry`.

### Ingestion

`python -m hindcast.ingest evidence` downloads, cuts, and writes to `build/evidence/` and Blob `extracted/evidence/`. Tested locally: `tests/test_ingest.py`, 6 tests (failed hash writes nothing; identical Blob evidence writes locally only; one failing case does not stop the others). Live, 2026-10-27, first run:

```
cloudflare-2025-11-18: 22 updates (resolved 2025-11-18T19:28:36Z), dropped 0
cloudflare-2026-02-20: 10 updates (resolved 2026-02-20T23:50:58Z), dropped 0
github-2026-08-17: 36 updates (resolved 2026-08-17T21:15:46Z), dropped 0
google-cloud-2026-07-14: 9 updates (resolved 2026-07-15T05:34:26Z), dropped 2
  report: 2
```

Counts as expected from the snapshots before the run. A second run without `--replace`: all four uploads refused, exit 1. Blob copies equal local files, every resolved text `null`, no "Incident Report" heading in the Google evidence.

After the code review, existing evidence is compared, not refused. Live, 2026-10-27, `build/evidence/` moved away: same counts, `blob: unchanged`, exit 0, files rebuilt byte for byte. The cut fix left evidence and dataset hash unchanged.

### Library pick rule

[Decision 0013](../decisions/0013-library-selection.md): picks by what an outside engineer could see during each case, with decoys. Symptom tags (`product`, `symptom`, `scale`, each quoting its update) in [`data/library.yaml`](../../data/library.yaml), committed in `85b4561` before the search began. `Case.started_at` (UTC only) joined the registry in `ac98004`.

Tested locally: `tests/test_library.py` checks each tag's form and quote. The quote check needs the snapshots, so CI skips it; locally it failed on a changed quote, a wrong update ID, an empty quote.

### Library registry and picks

`hindcast.library` refuses a document dated on or after a served case's start day, a missing or non-ISO date, a case's own source URL, a duplicate ID, an unknown case, or a reason quoting no tagged symptom. Tested locally: `tests/test_library.py`, each check shown failing once.

Candidates searched from the symptom tags alone. The 2025-11-18 cause was widely reported, so its picks rest on the rule and the decoys. Two search summaries showed GitHub report and development post text; those picks predate them. 29 candidates, 23 kept:

| Kind | Documents |
|---|---|
| Same provider | 8 |
| Attack suspected | 6 |
| Decoy | 5 |
| Other provider | 4 |

By provider: Cloudflare 11, GitHub 6, Google Cloud 5, AWS 1. Each decoy's cause was checked to differ, the one use of a cause. Six dropped: one possibly dated on the event day, three too close to the Google cause, two for size.

Gaps: no Azure document, one AWS ([sources](../findings/sources.md#aws-post-event-summaries-and-azure-post-incident-reviews-state-no-publish-date-2026-10-27)); nothing on GitHub's download errors, SCIM, Copilot sign-in, VMware stretched clusters, or BYOIP. Some picks share a case's cause class; picked on symptoms, they stay.

### Library capture

Captured once over HTTPS on 2026-10-27, 15:59:14 to 15:59:27 UTC, hash and time pinned, uploaded to Blob `sources/library/` (`hindcast.storage.upload_source`). Tested live: all 23 blobs match their hashes; one flipped byte is refused by `download_source` with `SourceMismatch`. `tests/test_library.py` fails on a missing hash or time.

### Content Understanding setup

Analyzers in [`analyzers/`](../../analyzers/): `hindcast_postmortem` (markdown, title, publish date), `hindcast_chart` (description, text in image, alt text), `hindcast_answer_key` (attack verdict and basis, root cause, factors, timeline, fixes, each with a quote). Completion gpt-5-mini 2025-08-07; the document analyzers also name `text-embedding-3-large` ([decision 0014](../decisions/0014-extraction-and-embedding-models.md)). `hindcast.extract` creates, refuses a differing service copy, replaces on request.

Live, 2026-10-27:

- Cognitive Services Content Understanding Contributor assigned on the Foundry resource at 15:38 UTC.
- `supportedModels` lists gpt-5-mini; no defaults (`DefaultsNotSet`).
- Document analyzers need an embedding deployment: `text-embedding-3-large` (version 1, Global Standard, 50K tokens per minute, automatic upgrade off) added and set as default with gpt-5-mini ([troubleshooting](../troubleshooting.md)).
- All three `ready`; a second run created none; a changed definition raised `AnalyzerDiffers`.
- Smoke test, development postmortem: 18 minimal pages, 18,000 contextualization tokens, gpt-5-mini 18,999 input and 132 output, 9.5 seconds; `published_date` 2026-02-21.

`azure-ai-contentunderstanding` 1.1.0, new direct dependency (typed GA API calls with `DefaultAzureCredential`, instead of hand-written REST); newest stable on PyPI when adopted (2026-04-20; 1.2.0 releases are betas); the lock gained only it. `pip-audit --strict --disable-pip --require-hashes`: no known vulnerabilities.

Tested locally: `tests/test_extract.py`, including every analyzer key against the SDK's field names (failed on a misspelt key and setting). Undocumented service behaviour: [extraction findings](../findings/extraction.md).

### Library extraction

`python -m hindcast.ingest library`: download (hash-checked), cut the article by a rule per site, check the page date against the registry, extract with `hindcast_postmortem`, split by heading, drop text dated after the earliest served case, describe each image with `hindcast_chart`. All library figures are `display: false` (provider copyright). An unreadable page is refused; a stored extract is reused unless `--replace`.

Tested locally: `tests/test_library_extract.py`, `tests/test_ingest.py`, each rule shown failing once. Live, 2026-10-27, 16:10:12 to 16:21:17 UTC: 23 of 23, exit 0; 118 minimal pages, 189,000 contextualization tokens, gpt-5-mini 130,915 input (34,944 more cached), 22,752 output. GitHub author bios found ([troubleshooting](../troubleshooting.md)): six documents redone (19 pages, 26,000 contextualization tokens, 22,555 input, 2,493 output), two monthly reports split per incident (6 pages, 6,000 contextualization tokens). Final: 23 extracts, 176 sections, 65 figures, nothing dropped for its date, no case report or date mentioned. One Google page counts as published on its newest update (2020-12-22).

### Charts

Radar refuses scripted downloads; charts downloaded in a browser ([sources](../findings/sources.md#cloudflare-radar-serves-whole-utc-days-and-only-to-a-browser-2026-10-27)) and committed under [`data/charts/`](../../data/charts/README.md) with source, licence, attribution. The registry refuses a chart not CC BY 4.0. `python -m hindcast.ingest charts` describes each once; evidence ingestion attaches the description with a stable ID.

| Case | Views | Window |
|---|---|---|
| `cloudflare-2026-02-20` | Announced IPv4 space and BGP announcements for AS13335 | Whole UTC day, ending at 23:45, before the resolved update |
| `cloudflare-2025-11-18` | HTTP traffic worldwide | Whole UTC day, about four hours past the resolved update |

Left out: IPv6 space (only change about six hours before the outage), two repeats of the HTTP chart, a map without a time axis. Live, 2026-10-27: three descriptions (3,000 contextualization tokens, gpt-5-mini 1,132 input, 1,261 output); evidence replaced, Blob equal to local, resolved texts `null`, dataset hash `b76a883bd24595a5` unchanged. One description invented a value ([extraction findings](../findings/extraction.md#a-chart-description-gets-times-roughly-right-and-can-invent-a-value-2026-10-27)).

### Answer keys

`python -m hindcast.keys draft` cuts each postmortem to its article, runs `hindcast_answer_key`, writes a draft and a review sheet; each item carries a quote checked word for word (HTML results have no source locations). Live, 2026-10-27: four drafts, 24 minimal pages, about 23,000 gpt-5-mini input and 5,000 output tokens.

Checked field by field. Corrections: Google Cloud end time to UTC; GitHub and Google Cloud basis to `implied`; factors and timeline events added; mid-outage steps moved out of fixes; items a status update stated marked `stated_during_incident`. Approved and frozen with `python -m hindcast.keys freeze <case_id>` in `c2133df`. Rules: [keys README](../../eval/keys/README.md).

| Key | Attack | Basis | Factors | Timeline | Fixes | Stated during the incident |
|---|---|---|---|---|---|---|
| `cloudflare-2025-11-18` | not an attack | stated | 7 | 11 | 4 | 6 |
| `github-2026-08-17` | not an attack | implied | 3 | 2 | 5 | 3 |
| `google-cloud-2026-07-14` | not an attack | implied | 3 | 3 | 5 | 3 |
| `cloudflare-2026-02-20` | not an attack | stated | 6 | 13 | 3 | 6 |

Tested locally: `tests/test_keys.py` refuses a missing field, an attack value outside the definition, a non-UTC time; checks each frozen key against `eval/keys/frozen.json` (one changed byte failed); freezing a frozen case is refused.

### Role removal

Live, 2026-10-27: Content Understanding role removed at 18:23:46 UTC (left: Owner, Foundry User at project scope, Storage Blob Data Contributor). Reads succeeded until 18:34:23, refused from 18:35:09 with `PermissionDenied` naming `analyzers/read` ([identity findings](../findings/identity-and-access.md#a-removed-role-kept-working-on-content-understanding-for-about-11-minutes-2026-10-27)). A model call through the project still answered ("Blue", 24 input, 18 output tokens).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Ingestion reads the sources from Blob Storage with an Entra token | Tested live | All four snapshots and all 23 library pages read with the Azure CLI sign-in's token; a changed hash refused (`SourceMismatch`, live) |
| The evidence cut, tested per provider with fixed inputs including a planted report entry | Tested locally and live | `tests/test_evidence.py` (15 tests; 11 first against a missing module, 3 failing before the review fix, 1 for chart evidence); live counts above |
| Library postmortems extracted into sections with publish dates; charts described with their source | Tested live; accepted gap | 23 documents, 176 sections, 65 figures with source URL and SHA-256; a date differing from the registry is refused (`tests/test_library_extract.py`). Accepted gap: the 2025-11-18 chart runs about four hours past the resolved update (Radar serves whole days); those hours show recovery only (reason in `data/cases.yaml`) |
| Answer keys extracted, reviewed by a person, and frozen by hash | Tested locally; accepted gap | `tests/test_keys.py`: each key against `eval/keys/frozen.json` (failed on one changed byte), every quote against the captured postmortem (73 quotes; failed on one changed quote). Fields checked against the postmortem, corrections approved before freezing. Accepted gap: the approval covered the corrections, not a re-read of every field |
| A third-party chart is shown only under a licence that allows it | Tested locally | `tests/test_cases.py::test_chart_sources_need_a_display_licence`, `tests/test_library_extract.py::test_only_cc_by_4_0_is_displayable`, `test_extract_document_describes_each_figure_and_never_displays_it`; all 65 library figures `display: false`; the three Radar charts CC BY 4.0 with attribution in [`data/charts/`](../../data/charts/README.md) |

## Independent review

Read-only, fresh context, 2026-10-27: every claim against the code, stored outputs, Blob Storage, and live Azure (pick order, dates and hashes, extracts, key hashes and quotes, charts, settings). None of its findings was rejected. Fixed in this pull request:

- Quote check missed HTML-entity apostrophes and quotes split by inline tags; a committed test now checks every frozen key's quotes against the captured postmortem.
- Frozen-key hash test passed with no keys; now requires one per scored and development case.
- Library text dated on a case's start day was kept; now dropped. No extract contains a case date.
- Keys row claimed a review of every field; now records the approval as covering the corrections.
- Statements beyond the code: figures shown by licence, not never; the diagram said every step refuses; the as-built diagram said capture reads Radar and key drafts go to Blob Storage; decision 0014 said no default decides the model.
- Decision 0013's rule 6 says what the code does; a dependency entry and a test count added; the runbook's leak search covers every case date; chart images lost their executable bit.

Recorded as issues: [#14](https://github.com/sindredg/hindcast/issues/14) to [#17](https://github.com/sindredg/hindcast/issues/17). Left as is: the 2025-11-18 chart's extra hours (accepted gap); the GitHub key's attack basis, settled by the milestone 5 rubric.

### Code review of the first pull request

Read-only, fresh context, 2026-10-27, against the plan and decision 0005; no finding rejected. Fixed in that pull request:

- Times truncated to the second let a same-second update after the resolved one keep its text; now full precision, resolved mark first on a tie.
- A time without a zone was read as local time; now refused.
- An empty `build/` could not get the evidence without overwriting Blob Storage; identical evidence now writes locally.
- A refused cut or missing blob stopped the run; each case fails on its own.
- A loose case ID match, and two test counts in this worklog.

## Deviations from the plan

- The re-check scripts import `hindcast`, not installed as a package: their commands in the [foundations runbook](../runbooks/foundations.md#re-check-the-model-choice) gained `PYTHONPATH=src`.
- Analyzer IDs use underscores; the service refuses hyphens.
- An embedding deployment, required by the document analyzers; retrieval reuses it.
- The answer-key analyzer gained a quote per item and the time as written next to the UTC time (no source locations for HTML). Replaced in place; the Contributor role allows that but cannot delete.
- The article is cut out in code before extraction, by a rule per site, not after: fewer pages billed, unreadable pages refused.
- Decision 0013's rule 6 corrected before merge: each extract lists text dropped for its date (none); each site's rule leaves out related posts, tags, bylines.
- Text dated on a case's start day is dropped; the first version kept it. Nothing re-extracted: no extract contains a case date.
- Chart descriptions stored once, attached during evidence ingestion, which stays deterministic.
- The 2025-11-18 chart runs past the resolved update; Radar offers whole days only.
- A document has one kind; a second relation is stated in its reason.

## Follow-up

- [#12](https://github.com/sindredg/hindcast/issues/12): the draft check accepts a time not converted to UTC.
- [#13](https://github.com/sindredg/hindcast/issues/13): the extraction model upgrades automatically; extracts do not record its version.
- [#14](https://github.com/sindredg/hindcast/issues/14): a reused extract or chart description is not checked against the registry.
- [#15](https://github.com/sindredg/hindcast/issues/15): analyzers are not checked against their files before each run.
- [#16](https://github.com/sindredg/hindcast/issues/16): the support rules have to treat a chart description as a lead.
- [#17](https://github.com/sindredg/hindcast/issues/17): chart evidence carries no attribution for display.

## Not verified

- A real Statuspage `update` or `postmortem` status: none of the four cases has one; tested on hand-made input.
- Extracts and figures checked by sample: two documents' headings, one figure, a search for case reports, dates, bylines. The 65 figure descriptions were not compared with their images.
- `stated_during_incident` is a judgment per item.
- Extraction cost in currency: usage recorded above; Cost Management not read.
- The prior-knowledge risk in library selection: reduced by the rule, the quotes, and the decoys; not measured.

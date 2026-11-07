# 18. Extraction model: gpt-5.4-mini, pinned, checked before each analysis

Status: Accepted (2026-11-01).

## Context

[Decision 0014](0014-extraction-and-embedding-models.md) used gpt-5-mini, auto-upgrading, with no version recorded per extract, and promised a pinned newer model before extraction ran again ([#13](https://github.com/sindredg/hindcast/issues/13)). Also, `analyze` never called `ensure_analyzers`, so a changed analyzer in the service would run unnoticed ([#15](https://github.com/sindredg/hindcast/issues/15)).

Read 2026-11-01: `az cognitiveservices model list -l swedencentral` lists gpt-5.4-mini 2026-03-17 as GA, retiring 2027-09-21; `GET analyzers/prebuilt-document` lists it under `supportedModels.completion` ([extraction findings](../findings/extraction.md#gpt-54-mini-runs-under-content-understanding-2026-11-01)).

## Options considered

| Option | For | Against |
|---|---|---|
| A. Keep gpt-5-mini 2025-08-07, upgrade off | No new deployment | Not the newest; retires 2027-02-09 |
| B. gpt-5.4-mini 2026-03-17, new, upgrade off | Newest supported mini; retires 2027-09-21 | One more deployment |
| C. gpt-5.5 2026-04-24, new | Strongest supported | Large, for reviewed drafts |

## Decision

Option B. Deployment `gpt-5.4-mini`, version 2026-03-17, upgrade off; the analyzer files and resource defaults name it; gpt-5-mini is deleted.

Before an analyzer's first analysis in a process, `hindcast.extract.analyze` reads the service's copy and refuses it if it differs from the committed file or names a completion model other than the extraction deployment's (`HINDCAST_EXTRACTION_DEPLOYMENT`). Every result carries that deployment's model name and version under `model`.

## Trade-offs

- The extracts, chart descriptions, and key drafts of 2026-10-27 and 2026-11-01 ran on gpt-5-mini 2025-08-07, not recorded with them. They stay: re-extracting would change reviewed and frozen work, and gpt-5-mini is deleted.
- One analyzer read per analyzer and process; only the fields the file sets are compared.
- A pinned version gets fixes only by a new decision. It retires on 2027-09-21, after the live phase.

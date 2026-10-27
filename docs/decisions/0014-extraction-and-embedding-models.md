# 14. Extraction and embedding models: gpt-5-mini and text-embedding-3-large

Status: Accepted (2026-10-27).

## Context

[Decision 12](0012-models.md) chose the investigator and comparison models and left two choices for later: the model Content Understanding uses for extraction, and the embedding model. Milestone 2 had to make both.

Content Understanding's generally available API (`2025-11-01`) does not accept the GPT-6 deployments the investigator uses ([findings](../findings/models.md#content-understandings-ga-api-does-not-accept-the-gpt-6-models-2026-10-25)). Its supported list, read on 2026-10-27, runs from gpt-4o to gpt-5.5 for completion and offers three embedding models ([extraction findings](../findings/extraction.md#gpt-5-mini-is-on-the-supported-list-of-the-ga-api-2026-10-27)). An analyzer on the document base will not even be created without an embedding model, although Hindcast's analyzers use no labeled samples.

Extraction runs once and its output is stored and reused, so the model is called a few hundred times in all. The answer keys it drafts are corrected and frozen after review, so a weaker draft costs review time, not accuracy.

## Options considered

| Option | For | Against |
|---|---|---|
| A. gpt-5-mini 2025-08-07, already deployed | No new chat deployment; cheap; on the supported list | Not the newest supported mini model; its deployment upgrades automatically; retires on 2027-02-09 |
| B. gpt-5.4-mini 2026-03-17, a new deployment | The newest supported mini model; retires on 2027-09-21 | One more deployment and its quota, for a model called a few hundred times |
| C. gpt-5.5 2026-04-24, a new deployment | The strongest supported model | A larger model and a new deployment, for drafts that are reviewed anyway |
| Embedding: text-embedding-3-large | The model the documentation maps the prebuilt analyzers' embedding alias to; one deployment serves extraction and retrieval | USD 0.13 per million tokens, six and a half times the small model |
| Embedding: text-embedding-3-small | USD 0.02 per million tokens | Weaker retrieval in milestone 3 |

Prices: the Azure retail price list for Sweden Central, Global Standard, read 2026-10-27 (gpt-5-mini USD 0.25 input and 2.00 output per million tokens; the list has no entry for gpt-5.4-mini or gpt-5.5 there). Retirement dates: `az cognitiveservices model list`, same day.

## Decision

Option A for extraction, with text-embedding-3-large as the embedding model.

gpt-5-mini was deployed already, and a second chat deployment for a step that runs once is not worth its quota. Extraction is stored and its drafts are reviewed, so a newer model buys little here. text-embedding-3-large is deployed once, version 1, with automatic upgrade off, and the same deployment embeds the library for retrieval in milestone 3. Each analyzer names its models in its committed definition ([`analyzers/`](../../analyzers/)), so no alias decides which model runs; the resource defaults map those names to the deployments.

## Trade-offs

- gpt-5-mini is not the newest supported mini model; gpt-5.4-mini is. The older model is accepted for the stored extracts only. Before extraction runs again, the extraction model moves to the newest supported mini model, pinned, and each extract records the version that produced it ([#13](https://github.com/sindredg/hindcast/issues/13)).
- The gpt-5-mini deployment upgrades its model version automatically, and Content Understanding's usage does not name the version. The extracts made on 2026-10-27 ran on version 2025-08-07, read from the deployment that day, not recorded with them.
- gpt-5-mini retires on 2027-02-09, after the project's live phase.
- text-embedding-3-large costs nothing while idle. Retrieval is set up to shorten its vectors to 1,024 dimensions (the settings default); milestone 3 checks that against search quality.

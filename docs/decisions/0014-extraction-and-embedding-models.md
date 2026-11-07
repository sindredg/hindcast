# 14. Extraction and embedding models: gpt-5-mini and text-embedding-3-large

Status: Accepted (2026-10-27). Changed by [decision 0018](0018-extraction-model.md).

## Context

[Decision 12](0012-models.md) left the extraction and embedding models to milestone 2. Content Understanding's GA API (`2025-11-01`) rejects the GPT-6 deployments ([findings](../findings/models.md#content-understandings-ga-api-does-not-accept-the-gpt-6-models-2026-10-25)); its supported list, read 2026-10-27, runs from gpt-4o to gpt-5.5 with three embedding models ([extraction findings](../findings/extraction.md#gpt-5-mini-is-on-the-supported-list-of-the-ga-api-2026-10-27)). An analyzer needs an embedding model to be created. Extraction runs once, a few hundred calls, and its drafts are reviewed.

## Options considered

| Option | For | Against |
|---|---|---|
| A. gpt-5-mini 2025-08-07, deployed | No new deployment; cheap | Not the newest mini; auto-upgrades; retires 2027-02-09 |
| B. gpt-5.4-mini 2026-03-17, new | Newest supported mini; retires 2027-09-21 | One more deployment |
| C. gpt-5.5 2026-04-24, new | Strongest supported | Large, for reviewed drafts |
| text-embedding-3-large | The documented alias target; serves extraction and retrieval | USD 0.13 per million tokens, six and a half times the small model |
| text-embedding-3-small | USD 0.02 per million tokens | Weaker retrieval |

Prices: Azure retail list, Sweden Central, Global Standard, 2026-10-27 (gpt-5-mini USD 0.25 input, 2.00 output per million tokens; no entry for gpt-5.4-mini or gpt-5.5). Retirement dates: `az cognitiveservices model list`, same day.

## Decision

Option A for extraction, text-embedding-3-large for embeddings, deployed once, version 1, upgrade off, serving retrieval in milestone 3. Each analyzer names its models in its committed definition ([`analyzers/`](../../analyzers/)); the resource defaults map them to deployments.

## Trade-offs

- gpt-5-mini is accepted for the stored extracts only. Before extraction runs again the model moves to the newest supported mini, pinned, with the version recorded per extract ([#13](https://github.com/sindredg/hindcast/issues/13)).
- The extracts of 2026-10-27 ran on 2025-08-07, read from the deployment that day, not recorded with them.
- gpt-5-mini retires on 2027-02-09, after the live phase.
- Retrieval shortens the vectors to 1,024 dimensions (the settings default); milestone 3 checks that.

# 18. Extraction model: gpt-5.4-mini, pinned, checked before each analysis

Status: Accepted (2026-11-01).

## Context

[Decision 0014](0014-extraction-and-embedding-models.md) ran Content Understanding on the gpt-5-mini deployment that already existed, and named the cost: it was not the newest supported mini model, its deployment upgraded its model version automatically, and nothing recorded which version produced an extract. That decision moved extraction to a newer model, pinned, before extraction ran again ([#13](https://github.com/sindredg/hindcast/issues/13)).

A second gap sat next to it. Content Understanding runs whatever analyzer the service holds under an ID. `ensure_analyzers` compared the service's copy with the committed file only when it was called, and `analyze` did not call it, so an analyzer changed in the service would have run unnoticed ([#15](https://github.com/sindredg/hindcast/issues/15)).

Facts read on 2026-11-01: `az cognitiveservices model list -l swedencentral` lists gpt-5.4-mini 2026-03-17 as generally available, retiring on 2027-09-21. `GET analyzers/prebuilt-document` on the live resource lists gpt-5.4-mini under `supportedModels.completion` ([extraction findings](../findings/extraction.md#gpt-54-mini-runs-under-content-understanding-2026-11-01)).

## Options considered

| Option | For | Against |
|---|---|---|
| A. Keep gpt-5-mini 2025-08-07, set automatic upgrade off | No new deployment | Not the newest supported mini model; retires on 2027-02-09 |
| B. gpt-5.4-mini 2026-03-17, a new deployment with automatic upgrade off | The newest supported mini model; retires on 2027-09-21 | One more deployment; the extracts already stored stay on the older model |
| C. gpt-5.5 2026-04-24, a new deployment | The strongest supported model | A larger model for drafts and descriptions that are reviewed or sampled anyway |

## Decision

Option B. The deployment `gpt-5.4-mini` runs model version 2026-03-17 with automatic upgrade off. The three analyzer files name it as their completion model, the resource defaults map it, and gpt-5-mini is removed from the defaults and deleted.

Each analysis is checked first. Before an analyzer's first analysis in a process, `hindcast.extract.analyze` reads the service's copy and refuses it if it differs from the committed file or names a completion model other than the model of the extraction deployment (`HINDCAST_EXTRACTION_DEPLOYMENT`). Every result carries that deployment's model name and version, read from the deployment, under `model`; library extracts, chart descriptions, and answer-key analyzer results store it.

## Trade-offs

- The outputs made before the switch stay as they are: the library extracts, the chart descriptions, and the answer-key drafts of 2026-10-27 and 2026-11-01 ran on gpt-5-mini 2025-08-07, read from the deployment on those days, not recorded with them. Re-extracting them would change reviewed and frozen work for a model change alone. gpt-5-mini is deleted, so those outputs cannot be reproduced on the same model.
- The check costs one analyzer read per analyzer and process, and it compares only the fields the file sets; the service adds defaults of its own, which are not compared.
- A pinned version does not upgrade, so a fix in a later version arrives only by a new decision. The version retires on 2027-09-21, after the project's live phase.

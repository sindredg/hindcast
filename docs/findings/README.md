# Findings

What building Hindcast showed about the platform and the sources: behaviour the documentation does not state, states differently, or that changed a design choice.

One file per topic, one entry per finding, newest first. Each entry says what was seen, the evidence and how it was obtained (live on Azure, locally, or read from the documentation), and what it changes for Hindcast. An entry says what was true on its date and is not rewritten; a later finding that changes it gets its own entry and links back.

| Topic | File |
|---|---|
| Models, tokens, and rate limits | [models.md](models.md) |
| Identity and access | [identity-and-access.md](identity-and-access.md) |
| Quota and deployments | [quota-and-deployments.md](quota-and-deployments.md) |
| Case sources | [sources.md](sources.md) |
| Evaluation runs | [evaluation.md](evaluation.md) |
| Extraction with Content Understanding | [extraction.md](extraction.md) |

The model comparison and its results are in [decision 0012](../decisions/0012-models.md). A failure with its symptom, cause, and fix is in [troubleshooting](../troubleshooting.md), which links back to the finding behind it. Defects and open questions found along the way are GitHub issues; entries link to them.

# Safety services

Findings about Prompt Shields and PII detection on the Foundry resource. The design is [decision 0021](../decisions/0021-screens-pii-and-challenge.md).

## Prompt Shields and PII detection need a data role the OpenAI role does not include (2026-11-03)

**Seen:** with Cognitive Services OpenAI User on the Foundry resource, both services answered 401 `PermissionDenied`, each naming its missing data action. No built-in role holds just these two: Cognitive Services User grants every data action on the resource and `listkeys`.

**Evidence:** tested live, 2026-11-03: Prompt Shields named `Microsoft.CognitiveServices/accounts/ContentSafety/text:shieldprompt/action`, PII detection `Microsoft.CognitiveServices/accounts/Language/analyze-text/action`. Built-in roles read with `az role definition list`. A custom role with only those two data actions, assigned on the resource at 17:05:54Z, let Prompt Shields answer at 17:08:28Z.

**For Hindcast:** the developer holds the custom role "Hindcast Safety Caller" on the Foundry resource until teardown. The [investigator runbook](../runbooks/investigator.md) creates it.

## Prompt Shields leaves out the prompt analysis when the prompt is empty (2026-11-03)

**Seen:** a call with `"userPrompt": ""` and one document returned `documentsAnalysis` and no `userPromptAnalysis` key.

**Evidence:** tested live, 2026-11-03, API version 2024-09-01: the response was `{"documentsAnalysis": [{"attackDetected": false}]}`.

**For Hindcast:** a missing flag counts as a pass only for an empty prompt. For a challenge question, a missing flag is a screen error.

## PII detection flags roles and IP addresses, not company names or times (2026-11-03)

**Seen:** on "The on-call engineer paged Jane Doe at 09:14 UTC about Cloudflare's 1.1.1.1 resolver.", the default categories returned `PersonType` for "engineer", `Person` for "Jane Doe", and `IPAddress` for "1.1.1.1". "Cloudflare" and "09:14 UTC" were not flagged.

**Evidence:** tested live, 2026-11-03, API version 2026-05-01, model version 2026-05-01, `stringIndexType` `UnicodeCodePoint`.

**For Hindcast:** `PersonType`, `Organization`, `DateTime`, `URL`, and `IPAddress` are dropped before masking; in an outage report they name roles, providers, times, and service addresses. Both slice 3 development runs and their five challenges had no hit left after that. Since 2026-11-05 a hit whose text is a provider's name is dropped too, whatever its category: a live run on 2026-11-05 tagged "Cloudflare" as a `Person` in "Cloudflare began investigating; ..." ([#79](https://github.com/sindredg/hindcast/issues/79)).

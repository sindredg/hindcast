# 7. Safety and injection: Prompt Shields called by the app on every tool result

Status: Accepted (2026-10-25). Changed by [decision 0021](0021-screens-pii-and-challenge.md) and [decision 0025](0025-injection-test-layers.md).

## Context

Everything the investigator reads is third-party text that can carry instructions aimed at the model. Telling the model to ignore it is not a defence. Already in the design: the case and date bound in tool code (decision 2), schema validation, rejected citations, planted-instruction tests with canaries. Open: where Prompt Shields runs, and the personal-data check on outputs.

## Options considered

| Option | How | Limit |
|---|---|---|
| A. Default Foundry guardrails | On the deployment | First 1,000 characters only |
| B. A, plus the app calling Prompt Shields on every tool result and challenge text | GA API: five documents, 10,000 characters per call | One call per result; long results split |
| C. A, plus an agent guardrail at the tool-response point | On the agent | Preview; not stated for app-run tools |
| D. Spotlighting | Documents encoded as less trusted | Preview, Chat Completions only |

Sources, read 2026-10-24: [Prompt Shields](https://learn.microsoft.com/azure/ai-services/content-safety/concepts/jailbreak-detection), [guardrails](https://learn.microsoft.com/azure/foundry/guardrails/guardrails-overview), [intervention points](https://learn.microsoft.com/azure/foundry/guardrails/intervention-points), [regions and limits](https://learn.microsoft.com/azure/ai-services/content-safety/region-availability).

## Decision

Option B: whole text, GA API, testable code. Default guardrails stay on.

Injection tests plant instructions in three copies of the development case: a status update, a library postmortem's text, and a chart image in a library postmortem. A pass: nothing follows the instruction and the result is valid.

Every output is checked with Azure Language PII detection before display, so "no personal data in outputs" can fail.

## Trade-offs

- Prompt Shields misses some attacks and flags benign text; both are reported per variant, false positives from a clean run.
- A flagged result is withheld and shown in the trace; a false positive removes evidence.
- One call and some latency per result and output.
- PII detection finds names it recognises; "the on-call engineer" passes, as intended.

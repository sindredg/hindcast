# 7. Safety and injection: Prompt Shields called by the app on every tool result

Status: Accepted (2026-10-25).

## Context

Everything the investigator reads comes from pages Hindcast did not write: status updates, earlier postmortems in the library, and the text inside charts. Any of it can carry instructions aimed at the model, an indirect prompt injection. A poisoned document in a search index is the realistic version of this attack on an agent that searches. Instructions to the model to ignore such text are not counted as a defence.

These defences are already part of the design:

- the case and the library's date bound are set in the app's tool code (decision 2)
- outputs are validated against a JSON schema, and claims with citations that do not resolve are rejected
- planted-instruction test cases with canary values measure what gets through

The open question was where Prompt Shields, Azure's classifier for prompt and document attacks, runs. Outputs also need a check that they carry no personal data, since postmortems and status pages occasionally name people.

## Options considered

| Option | How | Limits found |
|---|---|---|
| A. Default Foundry guardrails on the model deployments, Prompt Shields where available | Configured on the deployment | Foundry guardrails moderate the first 1,000 characters of text, so most of a long tool result is never scanned |
| B. Option A, plus the app calling the Prompt Shields API on every tool result and on challenge text, before the model reads it | GA Content Safety API: up to five documents and 10,000 characters per call; the app blocks or flags | One extra call per tool result; long results are split across calls |
| C. Option A, plus a Foundry agent guardrail at the tool-response intervention point | Configured on the agent | Preview, and documented for supported tools only; support for function tools run by the app is not stated |
| D. Spotlighting | The service encodes documents so the model treats them as less trusted | Preview, and Chat Completions only |

Sources, read 2026-10-24: [Prompt Shields](https://learn.microsoft.com/azure/ai-services/content-safety/concepts/jailbreak-detection), [Guardrails overview](https://learn.microsoft.com/azure/foundry/guardrails/guardrails-overview), [Intervention points](https://learn.microsoft.com/azure/foundry/guardrails/intervention-points), [Region availability and limits](https://learn.microsoft.com/azure/ai-services/content-safety/region-availability).

## Decision

Option B. The app sends every tool result to Prompt Shields before the model reads it, so the check covers the whole text, runs on a GA API, and sits in code that tests can drive. The default guardrails stay on the deployments.

The injection tests plant instructions in three places, each in a copy of the development case: a status update, the text of a library postmortem, and a chart image inside a library postmortem. A test passes when no tool call or output follows the instruction and the run still produces a valid result.

Every investigation output is also checked with Azure Language PII detection before display, so "no personal data in outputs" is a check that can fail.

## Trade-offs

- Prompt Shields is a classifier. It misses some attacks and flags some benign text. The injection tests report both for each variant, and a run on the development case's clean evidence measures false positives.
- A flagged tool result is withheld from the model and shown in the trace. A false positive therefore removes real evidence from an investigation.
- Each tool result and each output costs an extra service call and adds latency. Library sections are long, so they take more calls than status updates.
- PII detection finds names it recognises. A role description, such as "the on-call engineer", passes, as intended.

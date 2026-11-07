# 2. Agent approach: a Foundry prompt agent with function tools run by the app

Status: Accepted (2026-10-25).

## Context

Three rules keep the investigator blind: it sees only the open case, never its postmortem or the provider's cause summary, and the library returns only documents published before the outage and none about the case. An instruction to the model is a request, not a control, so the rules hold in testable code that sees each tool result first.

## Options considered

| Option | Rules enforced in | Cost |
|---|---|---|
| A. Foundry prompt agent, versioned in Foundry; app-run function tools with the case bound in code; app-run loop with call and time caps | App tool code | None |
| B. Prompt agent with the built-in Azure AI Search tool | A `filter` in the tool definition, one agent version per case; no app check before the model reads | Two write roles on Search |
| C. Responses API, no stored agent | App tool code | No versioned agent or playground |
| D. Microsoft Agent Framework in the app | App tool code | One more dependency |
| E. Foundry hosted agent (agent code as a container) | The container | A registry, a second hosting surface, more roles; about two days |

Sources, read 2026-10-24: [Agents](https://learn.microsoft.com/azure/foundry/agents/overview), [AI Search tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search), [Agent Framework](https://learn.microsoft.com/agent-framework/integrations/by-component/model-providers/microsoft-foundry).

## Decision

Option A. Scoping, the answer-key exclusion, the date bound, and validation of what the model reads and returns run in Hindcast's code; the agent stays a versioned Foundry object that can be inspected, traced, and tested in the playground. Two tool groups: case tools over the open case, and a library search whose date bound comes from the case. Every citation records its group.

## Trade-offs

- Hindcast maintains the loop, caps, and error handling itself.
- The tools only work through the app.
- Option D stays open: Agent Framework's `FoundryAgent` drives the same stored agent.
- Built-in features such as automatic search citations are rebuilt in the app.

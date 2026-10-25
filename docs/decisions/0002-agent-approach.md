# 2. Agent approach: a Foundry prompt agent with function tools run by the app

Status: Accepted (2026-10-25).

## Context

The investigator reads one case's status updates and charts, and searches a library of earlier postmortems. Three rules keep its output honest and its evaluation blind:

- It sees only the open case.
- It never sees the case's postmortem or the provider's summary of the cause, which are the answer key.
- Its library search returns only documents published before the outage began, and none about the case.

A rule written in the agent's instructions is a request, not a control. A document can contain text that argues the model out of it. All three rules have to hold in code that can be tested. The same code has to see each tool result before the model does, so the citation, schema, and leak checks run on everything the model reads.

## Options considered

| Option | Where case scoping and the answer-key exclusion are enforced | Cost and effort |
|---|---|---|
| A. Foundry prompt agent (instructions, model, and tool definitions stored and versioned in Foundry); function tools executed by the app with the case bound in code; the app runs the tool loop with call and time caps | In the app's tool code, before results reach the model | No extra services |
| B. Prompt agent with the built-in Azure AI Search tool | A `filter` fixed in the tool definition, so one agent version per case and its date bound. The model reads results before any app check runs | The project identity needs Search Service Contributor and Search Index Data Contributor, which are write roles |
| C. Responses API with no stored agent | In the app's tool code, as in A | Least code; no versioned agent definition, no playground |
| D. Microsoft Agent Framework in the app | In the app's tool code, as in A | One more dependency and its abstractions; middleware fits the caps |
| E. Foundry hosted agent (the app's agent code as a container run by Foundry) | In the container's code | A container registry, a second hosting surface next to the web app, and more roles; about two days of work |

Sources, read 2026-10-24: [Agents in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/agents/overview), [Connect an Azure AI Search index to Foundry agents](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search), [Microsoft Foundry model provider for Agent Framework](https://learn.microsoft.com/agent-framework/integrations/by-component/model-providers/microsoft-foundry).

## Decision

Option A. The checks have to run in Hindcast's own code: case scoping, the answer-key exclusion, the library's date bound, and validation of what the model reads and returns. A does that and keeps the agent as a versioned Foundry object that can be inspected, traced, and tested in the playground.

The tools fall into two groups: case tools that read the open case's evidence (status updates, charts), and a library search whose date bound comes from the case, never from the model. Every citation records which group it came from.

## Trade-offs

- Hindcast writes and maintains the tool loop, the caps, and the error handling that a built-in tool or a framework would provide.
- The agent's tools are only useful through the app. Another client calling the stored agent gets tool calls it cannot execute.
- Option D stays open. Agent Framework's `FoundryAgent` drives the same stored prompt agent, so moving the loop into the framework later does not change the agent or its tools.
- No built-in Foundry tools are used, so built-in features such as automatic search citations are rebuilt in the app.

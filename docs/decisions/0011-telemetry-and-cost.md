# 11. Telemetry and cost: Foundry tracing to Application Insights, cost from a versioned price table

Status: Accepted (2026-10-24).

## Context

Every investigation produces a trace (tool calls, tokens, time) shown in the app's trace panel. Every evaluation result names its cost. Both have to be available per run, immediately, and traceable to their source.

## Options considered

| Option | Tracing | Cost per run | Catch |
|---|---|---|---|
| A. Foundry tracing to Application Insights; cost computed from token counts and a versioned price table in the repository | Spans appear in the Foundry portal's Traces view and in Application Insights | Exact and immediate; the table records its source and retrieval date | Foundry's client-side agent tracing is a preview feature |
| B. Plain OpenTelemetry to Application Insights with `azure-monitor-opentelemetry`, without Foundry's instrumentation | Spans in Application Insights only | Same price table | No Foundry Traces view |
| C. Foundry portal and Azure Cost Management as the cost source | Not applicable | The model Monitor tab shows estimates; Cost Management shows billed cost about five hours later, aggregated per deployment; the agent cost tile excludes prompt agents | No per-run cost |

Sources, read 2026-10-24: [Client-side tracing for Foundry agents](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-client-side), [Plan and manage costs for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/manage-costs), [Monitor model deployments](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/monitor-models).

## Decision

Option A. Foundry tracing gives the trace view where agent runs are inspected. The preview is accepted for observability only: the app's trace panel, the scores, and the costs come from Hindcast's own records, so no result depends on the preview. Cost per run is computed from the token counts the model returns and the price table. The table total is checked once against billed cost in Cost Management.

## Trade-offs

- A preview feature can change or be withdrawn. If the Foundry instrumentation breaks, tracing falls back to plain OpenTelemetry (option B) without touching the app's own records.
- The price table is a copy of public prices on a date. It goes stale when prices change, and it does not reflect discounts. Each result names the table version it used.
- Traces can contain prompt and document text. Content recording stays off outside development, and Application Insights is deleted at teardown.
- The Application Insights connection string lets anyone who has it write telemetry. It is configuration, not a credential for reading data, and it stays out of the repository.

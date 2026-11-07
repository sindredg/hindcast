# 11. Telemetry and cost: Foundry tracing to Application Insights, cost from a versioned price table

Status: Accepted (2026-10-24). Changed by [decision 0021](0021-screens-pii-and-challenge.md).

## Context

Every investigation produces a trace (tool calls, tokens, time), and every evaluation result names its cost. Both per run, immediate, and traceable.

## Options considered

| Option | Tracing | Cost per run | Catch |
|---|---|---|---|
| A. Foundry tracing to Application Insights; cost from token counts and a versioned price table | Foundry Traces view and Application Insights | Exact; the table records source and date | Client-side agent tracing is preview |
| B. Plain OpenTelemetry with `azure-monitor-opentelemetry` | Application Insights only | Same table | No Foundry Traces view |
| C. Foundry portal and Azure Cost Management | None | Estimates; billed cost about five hours later, per deployment; the agent tile excludes prompt agents | No per-run cost |

Sources, read 2026-10-24: [client-side tracing](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-client-side), [costs](https://learn.microsoft.com/azure/foundry/concepts/manage-costs), [monitor models](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/monitor-models).

## Decision

Option A. The preview serves observability only; the trace panel, scores, and costs come from Hindcast's own records. Cost per run comes from returned token counts and the price table, checked once against Cost Management.

## Trade-offs

- If the Foundry instrumentation breaks, tracing falls back to option B.
- The price table is a dated copy, no discounts; each result names its version.
- Traces can hold prompt text. Content recording stays off outside development; Application Insights is deleted at teardown.
- The connection string lets anyone write telemetry; it is configuration, kept out of the repository.

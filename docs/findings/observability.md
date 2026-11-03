# Observability

Findings about traces in Application Insights. The tracing choice is [decision 0021](../decisions/0021-screens-pii-and-challenge.md), which replaces part of [decision 0011](../decisions/0011-telemetry-and-cost.md).

## Foundry's server-side traces store every prompt and answer, whatever the client sets (2026-11-03)

**Seen:** with Application Insights connected to the Foundry account, each agent call adds server-side spans under the role `responsesapi` (`invoke_agent <agent>:<version>`, `chat <model>`, `execute_tool`). Their attributes hold the full input and output messages, the tool-call arguments, and a `user.id`. The client's content-recording setting was off. So the evidence, the library sections, and the model's answer before the PII check masks it were all stored.

**Evidence:** tested live, 2026-11-03, on the runs of [milestone 4, slice 3](../worklogs/04-investigator.md#slice-3-live-runs): a query over the spans' attribute keys listed `gen_ai.input.messages` (longest value 23,918 characters) and `gen_ai.output.messages` (10,858 characters) on the `invoke_agent` and `chat` spans. `HINDCAST_ENV` was unset, so `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` was `false`. Foundry's trace data page (updated 2026-10-19) names one control: disconnect Application Insights. After the `AppInsights` connection was deleted at 17:45:50Z, a challenge's own spans arrived and no `responsesapi` span did (read 17:50Z).

**For Hindcast:** the connection is deleted; traces come from Hindcast's own spans, which carry counts and times only. The runs before 2026-11-03 left their prompts and answers in Application Insights until its retention ends or it is deleted at teardown. No PII hit was found in any committed run.

**Read more:** [Microsoft Foundry tracing and data handling](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data).

## The Azure Monitor exporter samples five traces per second by default (2026-11-03)

**Seen:** `configure_azure_monitor` with no sampler set uses a rate-limited sampler at five traces per second. The first traced runs lost spans in their burst of calls: both investigations' root spans, one of the gpt-6-luna run's three model calls, all three of the gpt-6.1-sol run's, and both challenges' question screens.

**Evidence:** tested live, 2026-11-03: of 10 `model_call` spans expected from the first four runs, 6 arrived, and no `investigation` span. Read locally in `azure-monitor-opentelemetry` 1.8.11 (`_utils/configurations.py`, `_default_sampling_ratio`): without `OTEL_TRACES_SAMPLER`, it sets `traces_per_second` to 5.0. With `OTEL_TRACES_SAMPLER=parentbased_always_on`, a challenge's trace arrived whole, each span with `itemCount` 1.

**For Hindcast:** `hindcast.telemetry` sets the sampler to `parentbased_always_on`; a run makes a few dozen spans.

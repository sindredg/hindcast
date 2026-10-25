# Models, tokens, and rate limits

Findings about the deployed models: [gpt-6-luna](../decisions/0012-models.md) 2026-09-22 and gpt-6.1-sol 2026-09-29, Global Standard, Sweden Central.

## The smaller model reasoned longer, so its price advantage shrank (2026-10-25)

**Seen:** on the three prior-knowledge questions at medium effort, gpt-6-luna wrote shorter answers than gpt-6.1-sol but used 1.5 times its output tokens. Luna's tokens cost a twentieth of sol's; the run cost about a thirteenth. The same pattern showed on the timeline task: 662 output tokens for luna against 409 for sol, for the same nine events.

**Evidence:** tested live, 2026-10-25, from the usage in the prior-knowledge result files (prompt and code at commit `30c180e`). Output tokens: luna 3,526 (2,805, 368, 353 per question), sol 2,315 (1,802, 198, 315); input tokens 466 each. Answers: luna 2,087 characters in total, sol 5,896. Cost at the retail prices in [decision 0012](../decisions/0012-models.md) (USD per 1M tokens, input / output: luna 0.10 / 0.50, sol 2.00 / 10.00): luna USD 0.0018, sol USD 0.0241. Timeline task: [model selection](../../eval/model-selection/dev-outage-v1/README.md). That the difference is reasoning is inferred from answer length; the result files do not record reasoning tokens separately.

**For Hindcast:** cost comparisons use measured tokens, not price ratios. The evaluation compares cost per investigation from the run's own usage.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning).

## Reasoning effort defaults to medium when the request does not set it (2026-10-25)

**Seen:** a Responses API call that sends no `reasoning` parameter runs gpt-6-luna at effort `medium`. The response says so in its `reasoning` field.

**Evidence:** tested live, 2026-10-25. `responses.create(model="gpt-6-luna", input="Name three primary colours, comma-separated.")` returned `reasoning.effort == "medium"`.

**For Hindcast:** effort changes cost, and on longer evidence it can change coverage. On the development outage's timeline, luna used 473 output tokens at low effort and 662 at medium for the same nine events ([model selection](../../eval/model-selection/dev-outage-v1/README.md)). A result that does not record its effort cannot be compared with another run, and a service-side change of the default would change results silently. So `hindcast.models.ask_model` always sends an effort (medium unless the caller sets another), and result files record it.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning), [Use the Azure OpenAI Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses).

## Reasoning tokens are billed as output, even for a three-word answer (2026-10-25)

**Seen:** a three-word answer cost 45 output tokens, 34 of them reasoning tokens the caller never sees.

**Evidence:** tested live, 2026-10-25, same call as above. Answer `'Red, yellow, blue'`; `usage.input_tokens` 14, `usage.output_tokens` 45, `usage.output_tokens_details.reasoning_tokens` 34. An earlier call with the same input returned 52 output tokens: the reasoning length varies between identical calls.

**For Hindcast:** cost estimates use `output_tokens` as billed, not the length of the visible answer. Luna's output price is five times its input price, so reasoning dominates the cost of short answers.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning).

## The response names the model but not its version (2026-10-25)

**Seen:** the `model` field of a Responses API result is the model name only, `gpt-6-luna`. The version comes from the deployment.

**Evidence:** tested live, 2026-10-25. `response.model` was `gpt-6-luna`; `project.deployments.get("gpt-6-luna")` returned `model_name` `gpt-6-luna` and `model_version` `2026-09-22`.

**For Hindcast:** results read the version from the deployment (`hindcast.models.deployment_model`). Both deployments are pinned with automatic upgrade off, so the version read at collection time is the one that answered.

**Read more:** [Model versioning in Microsoft Foundry Models](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/model-versions).

## Every deployment here gets 1 request per minute per 1,000 tokens per minute (2026-10-25)

**Seen:** each deployment's request limit is its token limit divided by 1,000: gpt-6-luna and gpt-6.1-sol at capacity 50 allow 50 requests per minute, gpt-5-mini at 237 allows 237, and grok-4.7 at 50 allows 50. The quota documentation's table gives 6 requests per minute per 1,000 tokens for older chat models; the ratio differs per model, and the portal's Quota page shows only tokens per minute.

**Evidence:** tested live, 2026-10-25. `az cognitiveservices account deployment list` and `deployment show` read `properties.rateLimits`: `request` 50 and `token` 50000 for gpt-6-luna, gpt-6.1-sol, and grok-4.7, `request` 237 and `token` 237000 for gpt-5-mini, each with `renewalPeriod` 60.

**For Hindcast:** every agent turn and every tool round trip is one request. A batch run such as the evaluation paces itself to 50 requests per minute per deployment and backs off on 429.

**Read more:** [Manage Azure OpenAI quota](https://learn.microsoft.com/azure/foundry/openai/how-to/quota).

## Content Understanding's GA API does not accept the GPT-6 models (2026-10-25)

**Seen:** the generally available Content Understanding API (`2025-11-01`) uses GPT-5.x, GPT-4.1, and GPT-4o family deployments. GPT-5.6, GPT-6, and GPT-6.1 are supported only in the `2026-06-01-preview` API.

**Evidence:** read from the documentation, not tested here: "What's new in Content Understanding", October 2026 entry. The analyzer's `supportedModels` could not be read yet (see [identity and access](identity-and-access.md)).

**For Hindcast:** extraction needs a GPT-5.x deployment next to the investigator's model. The extraction milestone chooses it and reads `supportedModels` first.

**Read more:** [What's new in Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/whats-new), [Model deployment options for Content Understanding analyzers](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/models-deployments), [Content Understanding service limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits).

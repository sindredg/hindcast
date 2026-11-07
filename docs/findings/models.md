# Models, tokens, and rate limits

Findings about the deployed models, [gpt-6-luna](../decisions/0012-models.md) 2026-09-22 and gpt-6.1-sol 2026-09-29, Global Standard, Sweden Central, and the judge, `claude-opus-5-5` on the Anthropic API ([decision 0024](../decisions/0024-judge-model.md)).

## Structured output refuses a schema with one array per key item (2026-11-04)

**Seen:** the Anthropic API refused the judge's first reply schema with HTTP 400 `invalid_request_error`, "The compiled grammar is too large, which would cause performance issues. Simplify your tool schemas or reduce the number of strict tools." The request had no tools. The schema was built per run: one required object per run item (reason and support flag) and one per key item (an array of run-item names, a reason, and an outcome enum). The [structured outputs documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) sets limits on strict tools, optional parameters, and union types, none used here, and names further internal limits on grammar size without numbers, with the error "Schema is too complex for compilation", not the message seen.

**Evidence:** tested live, 2026-11-04, 16:40 to 17:10 UTC, with the development run's schema: 21 key items, 18 run items. The first two rows are judge calls; the rest are probes with a one-line message and `max_tokens` 64. A refused schema gets its 400 before any output.

| Schema | Result |
|---|---|
| Built per run, each array limited to the run's item names (enum) | 400 |
| The same, without the enum | 400 |
| The same, without the outcome enums | 400 |
| Key items only | 400 |
| Key items only, without the array | accepted |
| Key items only, without the reason | 400 |
| The first 10 key items only | accepted |
| The first 15 key items only | 400 |
| Run items only | accepted |
| Two lists of objects, the same for every run | accepted |

**For Hindcast:** the judge sends one fixed schema with two lists and checks in code what the per-run schema enforced ([worklog](../worklogs/05-evaluation.md#the-judge)). The keys hold 7 to 21 key items.

## The project endpoint serves no embeddings (2026-11-01)

**Seen:** through the Foundry project's OpenAI-compatible endpoint (`<project endpoint>/openai/v1`), an embeddings call for `text-embedding-3-large` returned 404 with an empty body, while Responses API calls on the same client worked. With API version `2024-10-21`, 400, "API version not supported". The resource endpoint (`https://<resource>.services.ai.azure.com/openai/v1`) serves embeddings, to a role at resource scope.

**Evidence:** tested live, 2026-11-01, 12:01 to 12:20 UTC. With Foundry User on the project only, the resource endpoint answered 401 `PermissionDenied`, naming `Microsoft.CognitiveServices/accounts/OpenAI/deployments/embeddings/action`. Cognitive Services OpenAI User assigned on the resource at 12:45:56 UTC; a build at 12:51:06 still got 401, a one-text call at 12:51:19 succeeded, and both index builds embedded all 267 chunks ([worklog](../worklogs/03-retrieval.md#live-run)).

**For Hindcast:** embeddings go to the resource endpoint (`HINDCAST_EMBEDDING_ENDPOINT`), and the developer holds Cognitive Services OpenAI User on the resource until teardown ([decision 0019](../decisions/0019-library-index.md)). The app's identity holds the same role (`appOpenAi` in `infra/modules/roles.bicep`).

## The smaller model reasoned longer, so its price advantage shrank (2026-10-25)

**Seen:** on the three prior-knowledge questions at medium effort, gpt-6-luna wrote shorter answers than gpt-6.1-sol but used 1.5 times its output tokens. Luna's tokens cost a twentieth of sol's; the run cost about a thirteenth. The timeline task showed the same: 662 output tokens for luna against 409 for sol, for the same nine events.

**Evidence:** tested live, 2026-10-25, from the prior-knowledge result files (prompt and code at PR #5 commit `30c180e`). Output tokens: luna 3,526 (2,805, 368, 353 per question), sol 2,315 (1,802, 198, 315); input tokens 466 each. Answers: luna 2,087 characters, sol 5,896. Cost at the retail prices in [decision 0012](../decisions/0012-models.md) (USD per 1M tokens, input / output: luna 0.10 / 0.50, sol 2.00 / 10.00): luna USD 0.0018, sol USD 0.0241. Timeline task: [model selection](../../eval/model-selection/dev-outage-v1/README.md). That the difference is reasoning is inferred from answer length; the result files do not record reasoning tokens.

**For Hindcast:** cost comparisons use measured tokens, not price ratios.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning).

## Reasoning effort defaults to medium when the request does not set it (2026-10-25)

**Seen:** a Responses API call with no `reasoning` parameter runs gpt-6-luna at effort `medium`, as the response's `reasoning` field says.

**Evidence:** tested live, 2026-10-25. `responses.create(model="gpt-6-luna", input="Name three primary colours, comma-separated.")` returned `reasoning.effort == "medium"`.

**For Hindcast:** effort changes cost and can change coverage: on the development outage's timeline, luna used 473 output tokens at low effort and 662 at medium for the same nine events ([model selection](../../eval/model-selection/dev-outage-v1/README.md)). `hindcast.models.ask_model` always sends an effort (medium unless the caller sets another), and result files record it, so a service-side change of the default cannot change results silently.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning), [Use the Azure OpenAI Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses).

## Reasoning tokens are billed as output, even for a three-word answer (2026-10-25)

**Seen:** a three-word answer cost 45 output tokens, 34 of them reasoning tokens the caller never sees.

**Evidence:** tested live, 2026-10-25, same call as above. Answer `'Red, yellow, blue'`; `usage.input_tokens` 14, `usage.output_tokens` 45, `usage.output_tokens_details.reasoning_tokens` 34. An earlier identical call returned 52 output tokens: reasoning length varies between identical calls.

**For Hindcast:** cost estimates use `output_tokens` as billed. Luna's output price is five times its input price, so reasoning dominates the cost of short answers.

**Read more:** [Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning).

## The response names the model but not its version (2026-10-25)

**Seen:** the `model` field of a Responses API result is the model name only, `gpt-6-luna`. The version comes from the deployment.

**Evidence:** tested live, 2026-10-25. `response.model` was `gpt-6-luna`; `project.deployments.get("gpt-6-luna")` returned `model_name` `gpt-6-luna` and `model_version` `2026-09-22`.

**For Hindcast:** results read the version from the deployment (`hindcast.models.deployment_model`). Both deployments are pinned with automatic upgrade off, so the version read at collection time is the one that answered.

**Read more:** [Model versioning in Microsoft Foundry Models](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/model-versions).

## Every deployment here gets 1 request per minute per 1,000 tokens per minute (2026-10-25)

**Seen:** each deployment's request limit is its token limit divided by 1,000: gpt-6-luna and gpt-6.1-sol at capacity 50 allow 50 requests per minute, gpt-5-mini at 237 allows 237, grok-4.7 at 50 allows 50. The quota documentation gives 6 requests per minute per 1,000 tokens for older chat models; the portal's Quota page shows only tokens per minute.

**Evidence:** tested live, 2026-10-25. `az cognitiveservices account deployment list` and `deployment show` read `properties.rateLimits`: `request` 50 and `token` 50000 for gpt-6-luna, gpt-6.1-sol, and grok-4.7, `request` 237 and `token` 237000 for gpt-5-mini, each with `renewalPeriod` 60.

**For Hindcast:** every agent turn and tool round trip is one request. The code makes one call at a time; `ask_model` keeps the `openai` client's two retries with backoff, and the investigator's agent calls make none, so a 429 fails the run. The evaluation runner stays under 50 requests per minute per deployment.

**Read more:** [Manage Azure OpenAI quota](https://learn.microsoft.com/azure/foundry/openai/how-to/quota).

## Content Understanding's GA API does not accept the GPT-6 models (2026-10-25)

**Seen:** the generally available Content Understanding API (`2025-11-01`) uses GPT-5.x, GPT-4.1, and GPT-4o family deployments. GPT-5.6, GPT-6, and GPT-6.1 are supported only in the `2026-06-01-preview` API.

**Evidence:** read from the documentation, not tested: "What's new in Content Understanding", October 2026 entry. The analyzer's `supportedModels` could not be read yet (see [identity and access](identity-and-access.md)).

**For Hindcast:** extraction needs a GPT-5.x deployment next to the investigator's model. It used gpt-5-mini, read from `supportedModels` on 2026-10-27 ([extraction findings](extraction.md#gpt-5-mini-is-on-the-supported-list-of-the-ga-api-2026-10-27)), and runs on gpt-5.4-mini since 2026-11-01 ([decision 0018](../decisions/0018-extraction-model.md)).

**Read more:** [What's new in Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/whats-new), [Model deployment options for Content Understanding analyzers](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/models-deployments), [Content Understanding service limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits).

## A prompt agent drives app-run function tools under a strict output schema (2026-10-30)

**Seen:** a Foundry prompt agent on gpt-6-luna with a strict function tool and a strict JSON schema output format returned a `function_call` item on the first call and, with the function's output sent back, text that parsed against the schema. The agent is referenced from the project's OpenAI client with `extra_body={"agent_reference": {"type": "agent_reference", "name": ..., "version": ...}}`, and the second call chains with `previous_response_id`. `agents.list_versions(name, limit=1, order="desc")` returns the version's metadata, where Hindcast stores the definition's fingerprint. Foundry User on the project was enough to create, call, and delete the agent. Both calls reported 0 reasoning tokens at effort medium.

**Evidence:** tested live, 2026-10-30, with a throwaway agent (one `echo` tool, a one-field schema), created as version 1 and deleted after. Usage: 83 input and 17 output tokens on the first call, 117 and 14 on the second. The same call shape then ran the investigator on the development case ([worklog](../worklogs/04-investigator.md#live-run)). Whether the definition's effort is applied is not shown: the task was too small to need reasoning.

**For Hindcast:** [decision 0002](../decisions/0002-agent-approach.md) option A works as decided, with no fallback and no extra role. Each result records the effort each response applied, next to the one requested, and the reasoning tokens ([#26](https://github.com/sindredg/hindcast/issues/26)); the milestone 5 runs of 2026-11-04 were the first live read, and every response applied the requested `medium` ([showcase report](../../eval/reconstruction/showcase-v1/README.md)). The prior-knowledge results keep the requested effort only ([#4](https://github.com/sindredg/hindcast/issues/4)).

**Read more:** [Agents in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/agents/overview).

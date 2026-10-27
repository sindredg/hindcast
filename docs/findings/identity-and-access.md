# Identity and access

Findings about Entra ID roles, scopes, and keyless access. Hindcast uses no keys: every call carries an Entra token ([decision 0009](../decisions/0009-hosting-and-identity.md)).

## A removed role kept working on Content Understanding for about 11 minutes (2026-10-27)

**Seen:** after the Content Understanding Contributor role was removed, reads on the Content Understanding endpoint kept succeeding for about 11 minutes before they were refused. Azure documents up to 10 minutes for a role change to take effect. Model calls through the project endpoint kept working on the project-scope role throughout, as expected.

**Evidence:** tested live, 2026-10-27, from the developer's sign-in. `az role assignment delete` at 18:23:46 UTC; afterwards the user held Owner, Foundry User at project scope, and Storage Blob Data Contributor. `get_analyzer("hindcast_chart")`, polled about every 32 seconds, succeeded up to 18:34:23 and returned `PermissionDenied` at 18:35:09, naming `MultiModalIntelligence/analyzers/read`. `ask_model("gpt-6-luna", ...)` through the project endpoint answered "Blue" (24 input, 18 output tokens).

**For Hindcast:** removing a role is not instant revocation. A teardown or a role removal is checked by retrying the refused call until it is refused, not by reading the assignment list. The extraction runbook does so.

**Read more:** [Troubleshoot Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/troubleshooting).

## A few calls failed with 401 an hour after the role assignment (2026-10-26)

**Seen:** after the role in the next entry was assigned, two portal evaluation runs mostly worked, but three model calls still failed with 401 `PermissionDenied`, "Principal does not have access to API/Operation." The calls around them, with the same identity, deployment, and operation, succeeded. Azure documents up to 10 minutes for a role change to take effect; these failures came about an hour after it. The cause is not known.

**Evidence:** tested live, 2026-10-26. Role assigned 17:12 UTC, runs at 18:11 and 18:13 UTC. In the [log excerpts](../../eval/model-selection/dev-outage-v1/README.md): 2 of 25 judge calls in luna's run, and 1 of 5 Responses API calls for sol's answers (the service then answered through chat completions). Tracked in [#7](https://github.com/sindredg/hindcast/issues/7).

**For Hindcast:** a run that finishes as "completed" can still be missing scores. `summarise_runs.py` lists failed calls, and the model re-check was read with it; the evaluation in milestone 5 will check every result the same way before using it ([evaluation findings](evaluation.md)).

**Read more:** [Troubleshoot Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/troubleshooting).

## With key access off, a portal evaluation calls the models as the user, on the resource endpoint (2026-10-26)

**Seen:** a Foundry portal evaluation with a model target failed on every row with 401. The service called `POST /openai/deployments/{deployment-id}/chat/completions` on the resource endpoint with the signed-in user's identity, and the user's only Foundry role was at project scope, which does not reach that path. The day before, with key access on, a run of the same kind worked. In between, key access was turned off and the user's wider Foundry User assignments were removed.

**Evidence:** tested live, 2026-10-26.

- Every row: `Error code: 401 - PermissionDenied`, "The principal `<user>` lacks the required data action `Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action`".
- Activity log: the portal's key requests (`accounts/listkeys/action`) failed 39 times between 16:18 and 16:46 UTC; they had succeeded the day before. That the earlier run used a key is inferred from those requests, not observed.
- `GET <project endpoint>/openai/evals?api-version=v1` as the same user: HTTP 400 naming the missing data action `Microsoft.CognitiveServices/accounts/OpenAI/evals/read`. About 3 minutes after Cognitive Services OpenAI User was assigned on the Foundry resource: HTTP 200 with the evaluation list. The runs that followed answered all ten questions; see the entry above for three calls that still failed.
- `az role definition list`: Cognitive Services OpenAI User grants OpenAI chat completions, Responses, and reads (`OpenAI/*/read`), and nothing outside `OpenAI/`. Foundry User grants `Microsoft.CognitiveServices/*`.

**For Hindcast:** whoever runs portal evaluations needs an OpenAI data role on the Foundry resource; Foundry User at project scope is enough for Hindcast's own calls, not for the portal's. Cognitive Services OpenAI User worked, and grants less than Foundry User at the same scope; no narrower role was tried. While it is assigned it also covers the project, so the project-scope claim cannot fail ([#9](https://github.com/sindredg/hindcast/issues/9)). The [runbook](../runbooks/foundations.md#re-check-the-model-choice) assigns it before the runs and removes it after. Removed 2026-10-26 at 19:26 UTC, then checked: the evals read returned 400 again and `ask_model` on gpt-6-luna through the project answered. Milestone 5 decides the identity for evaluation runs.

**Read more:** [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry), [Run evaluations from the portal](https://learn.microsoft.com/azure/foundry/how-to/evaluate-generative-ai-app).

## With key access off, a valid key gets the same 401 as a wrong one (2026-10-25)

**Seen:** after key access was turned off on the Foundry resource (`disableLocalAuth` true), a request with a valid API key fails with 401 and the message for a wrong key: "Access denied due to invalid subscription key or wrong API endpoint." Nothing in the response says that key access is disabled. Entra calls through the project keep working.

**Evidence:** tested live, 2026-10-25. `GET https://<resource>.services.ai.azure.com/openai/v1/models` with header `api-key: <key1>`: HTTP 200 before the change, HTTP 401 after `az resource update --ids <resource-id> --set properties.disableLocalAuth=true`. Read back: `disableLocalAuth` `true`. The same day, `ask_model` on gpt-6-luna through the project endpoint answered.

**For Hindcast:** the resource accepts Entra tokens only. A 401 on a key-based call after this change means key access is off, not that the key is wrong; regenerating keys does not help.

**Read more:** [Disable local authentication in Foundry Tools](https://learn.microsoft.com/azure/ai-services/disable-local-auth), [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry).

## A project-scope role reaches the models but not the resource endpoint (2026-10-25)

**Seen:** with Foundry User assigned only at project scope, a model call through the project endpoint succeeds, and a Content Understanding call on the resource endpoint is refused. Foundry User grants the needed data actions (`Microsoft.CognitiveServices/*`), so the scope of the assignment decides, not the role.

**Evidence:** tested live, 2026-10-25, signed in as a user whose only Foundry User assignment is on the project.

- `responses.create` through `https://<resource>.services.ai.azure.com/api/projects/<project>` with gpt-6-luna: answered.
- `GET https://<resource>.services.ai.azure.com/contentunderstanding/analyzers/prebuilt-documentSearch?api-version=2025-11-01` with a token for `https://cognitiveservices.azure.com/.default`: HTTP 401, `PermissionDenied`, "lacks the required data action `Microsoft.CognitiveServices/accounts/MultiModalIntelligence/analyzers/read`". The same for `GET .../contentunderstanding/defaults`. Later the same day, after key access was turned off, the same GET returned 401 `PermissionDenied` with "Principal does not have access to API/Operation." and no action named (read 19:30 UTC).
- `az role definition list`: Foundry User and Cognitive Services User grant `Microsoft.CognitiveServices/*`; Cognitive Services Content Understanding Reader grants analyzer reads and the analyze actions, but no writes; Content Understanding Contributor and Owner grant `MultiModalIntelligence/*`.

**For Hindcast:** extraction needs a second assignment at resource scope. Reader is enough to analyze; setting the resource's model defaults needs Contributor. Milestone 2 assigned Contributor to the developer on 2026-10-27 to build and run the analyzers, to be removed when extraction is done; Contributor cannot delete analyzers ([extraction findings](extraction.md#content-understanding-contributor-cannot-delete-an-analyzer-but-can-replace-one-2026-10-27)). The app's identity is decided with deployment.

**Read more:** [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry), [Secure your Content Understanding analyzers and data](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/secure-communications).

## A wider copy of a role hides a least-privilege test (2026-10-25)

**Seen:** an older Foundry User assignment at subscription scope made the project-scope assignment untestable: every scope below the subscription inherits the role, so no call can fail for lack of it.

**Evidence:** tested live, 2026-10-25. `az role assignment list --assignee <user> --all` listed Foundry User at subscription scope, on two resource groups, and on the project. After all but the project assignment were deleted, the Content Understanding call above returned 401. That the call would have passed with the subscription assignment in place is reasoned from inheritance, not observed: it was not run before the deletion.

**For Hindcast:** a least-privilege claim starts with the assignment list. Checks of access run against an identity that holds only the intended assignments.

**Read more:** [Understand scope for Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/scope-overview), [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry).

## No token and a missing role both return 401 (2026-10-25)

**Seen:** the Content Understanding endpoint answers 401 both without a token and with a valid token that lacks the data action. Only the response body tells them apart.

**Evidence:** tested live, 2026-10-25, on the analyzer GET above: without an `Authorization` header, 401; with a token and no role at resource scope, 401 with `PermissionDenied` and the missing action named.

**For Hindcast:** an access check asserts on the error code in the body (`PermissionDenied`), not on the status code alone, and not on the message: the message changed within the day.

**Read more:** [Secure your Content Understanding analyzers and data](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/secure-communications).

## Blob Storage with shared keys off refuses keys and anonymous reads (2026-10-25)

**Seen:** with shared key access and public blob access both off, a key-based request and an anonymous request both fail, each with a specific error code. Entra sign-in with Storage Blob Data Contributor works.

**Evidence:** tested live, 2026-10-25, on the case source account.

- `az storage container list --auth-mode key`: `KeyBasedAuthenticationNotPermitted`.
- `curl` on `https://<account>.blob.core.windows.net/sources?restype=container&comp=list` without a token: HTTP 409, `PublicAccessNotPermitted`.
- `az storage container list --auth-mode login`: `extracted`, `sources`.

**For Hindcast:** the source files are reachable only with an Entra token and a data role.

**Read more:** [Prevent Shared Key authorization](https://learn.microsoft.com/azure/storage/common/shared-key-authorization-prevent), [Remediate anonymous read access to blob data](https://learn.microsoft.com/azure/storage/blobs/anonymous-read-access-prevent).

## Foundry tracing stores a connection string, not an Entra identity (2026-10-25)

**Seen:** connecting Application Insights to the Foundry project creates a project connection of category `AppInsights` with authentication type `ApiKey`: it holds the Application Insights connection string. Entra-authenticated trace ingestion for Foundry agents is in preview.

**Evidence:** tested live, 2026-10-25: the project's connections, read from Azure Resource Manager, list one `AppInsights` connection with `authType` `ApiKey`. Preview status read from "Set up tracing for AI agents in Microsoft Foundry" (updated 2026-10-21).

**For Hindcast:** the connection string can write telemetry but not read it; [decision 0011](../decisions/0011-telemetry-and-cost.md) treats it as configuration that stays out of the repository. Application Insights keeps accepting it, because the generally available tracing path needs it. Previews are not used, so this stays until Entra ingestion is generally available.

**Read more:** [Set up tracing for AI agents in Foundry](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup), [Entra authentication for trace ingestion (preview)](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-ingestion-entra-authentication).

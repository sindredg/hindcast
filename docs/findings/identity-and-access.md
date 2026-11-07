# Identity and access

Findings about Entra ID roles, scopes, and keyless access. Hindcast uses no keys: every call carries an Entra token ([decision 0009](../decisions/0009-hosting-and-identity.md)).

## Content Understanding kept answering for more than 85 minutes after its role was removed (2026-11-01)

**Seen:** after Content Understanding Contributor was removed from the Foundry resource, Content Understanding kept accepting the developer's analyzer reads, a defaults read, and a defaults write that changed nothing, while RBAC listed no Content Understanding permission. The [earlier removal](#a-removed-role-kept-working-on-content-understanding-for-about-11-minutes-2026-10-27) was refused after about 11 minutes, and one the same morning after about 2. Cause unknown.

**Evidence:** tested live, 2026-11-01. `az role assignment delete` at 13:18:02 UTC; by 13:18:13 the resource held only Cognitive Services OpenAI User, and Foundry User stayed on the project. `get_analyzer("hindcast_chart")`, polled every 30 seconds and then every 2 minutes, succeeded up to 14:45:33; `update_defaults` with the current mapping succeeded at 14:13:10. `GET .../providers/Microsoft.Authorization/permissions` on the resource at about 13:58 listed only the OpenAI User data actions. Hypotheses:

- A cached token: refuted. The token in use until 14:43:48 was issued at 13:16:30, before the removal, but a token issued at 14:34:26 kept working.
- Authorization on Cognitive Services OpenAI User at resource scope, which the earlier removals lacked: refuted. On 2026-11-04 the calls were refused while OpenAI User was still assigned.

**Refused, 2026-11-04:** a defaults read at 03:05:34 UTC (`PermissionDenied`, data action `Microsoft.CognitiveServices/accounts/MultiModalIntelligence/defaults/read`) and `get_analyzer("hindcast_chart")` at 03:06:01. No call is recorded between 14:45:33 on 2026-11-01 and then, so when access ended is not known.

**Assigned and removed again, 2026-11-04:** Content Understanding Contributor assigned at 03:34:12 UTC. A defaults read was accepted at 03:40:07; `get_analyzer` was refused at 03:40:12 and 03:40:29 and accepted at 03:42:11, so the grant reached the two operations about 6 and 8 minutes after the assignment. Removed at 05:49:42; `get_analyzer`, polled every 60 seconds, was refused at 05:50:09, 27 seconds later. Tested live.

**For Hindcast:** neither the assignment list nor the permissions API shows what an identity can do on Content Understanding. A removal is checked by retrying a refused call ([retrieval runbook](../runbooks/retrieval.md), step 17). The 2026-11-01 removal was seen refused on 2026-11-04.

## An admin key gets 401, not 403, when local authentication is off (2026-11-01)

**Seen:** an Azure AI Search service with `disableLocalAuth: true` refused its real admin key with 401, the same status as no credential. The gate's expected value was 403, reasoned, not read from the documentation.

**Evidence:** tested live, 2026-11-01, 12:01 UTC. `az search service show` read `disableLocalAuth: true`. `GET` on the indexes without a credential: 401. With the admin key from `az search admin-key show` in the `api-key` header (never printed): 401. With a bearer token for `https://search.azure.com`: 200.

**For Hindcast:** the status alone cannot tell a refused key from a missing credential, so the gate pairs the key request with the setting read from the service and a token request that succeeds ([worklog](../worklogs/03-retrieval.md#gate)).

## Container Apps sign-in works with a managed identity through a federated credential (2026-10-31)

**Seen:** Container Apps' built-in authentication signed a user in with no client secret: the app registration's client credential is the container app's user-assigned identity, through a federated credential on the registration. Documented for App Service; for Container Apps asked for in [microsoft/azure-container-apps#1693](https://github.com/microsoft/azure-container-apps/issues/1693) and not documented.

**Evidence:** tested live, 2026-10-31. The auth config's `clientSecretSettingName` is `override-use-mi-fic-assertion-client-id`, the only container secret, whose value is the identity's client ID (`az containerapp auth show`, `az containerapp secret list`). The registration holds the redirect URI and one federated credential, issuer `https://login.microsoftonline.com/<tenant>/v2.0`, subject the identity's principal ID, audience `api://AzureADTokenExchange`. In a browser, the deploying account signed in and reached the page.

**For Hindcast:** no client secret is stored or rotated ([decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md)). The behaviour is undocumented; the fallback is the `authClientSecret` parameter of `infra/main.bicep` and a provision.

## A GitHub job's OIDC subject names its environment, and this repository's subject carries IDs (2026-10-31)

**Seen:** a job that references a deployment environment presents the environment in its OIDC subject, not the branch, and a repository created after 2026-07-15 uses immutable subjects with the owner and repository IDs: `repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:<name>`. A credential for `repo:sindredg/hindcast:ref:refs/heads/main` or `repo:sindredg/hindcast:environment:azure` would refuse the push job.

**Evidence:** read from the [OpenID Connect reference](https://docs.github.com/en/actions/reference/security/oidc), 2026-10-31: "The subject claim includes the branch name of the workflow, but only if the job doesn't reference an environment", and "repositories created after July 15, 2026 now use an immutable default subject format". Read live, 2026-10-31: `gh api repos/sindredg/hindcast/actions/oidc/customization/sub` → `use_default: true`, `use_immutable_subject: true`, and a `sub_claim_prefix` with both IDs. Not yet observed in a token.

**For Hindcast:** the pre-provision hook reads the prefix from GitHub, and the CI identity's federated credential trusts `<prefix>:environment:azure`. The environment's branch policy admits only `main`; only the subject is in the template.

## A removed role kept working on Content Understanding for about 11 minutes (2026-10-27)

**Seen:** after Content Understanding Contributor was removed, reads on the Content Understanding endpoint succeeded for about 11 minutes. Azure documents up to 10 minutes. Model calls through the project endpoint kept working on the project-scope role.

**Evidence:** tested live, 2026-10-27. `az role assignment delete` at 18:23:46 UTC; the user then held Owner, Foundry User at project scope, and Storage Blob Data Contributor. `get_analyzer("hindcast_chart")`, polled about every 32 seconds, succeeded up to 18:34:23 and returned `PermissionDenied` at 18:35:09, naming `MultiModalIntelligence/analyzers/read`. `ask_model("gpt-6-luna", ...)` through the project answered "Blue" (24 input, 18 output tokens).

**For Hindcast:** a role removal is checked by retrying the refused call, not by reading the assignment list. The extraction runbook does so.

**Read more:** [Troubleshoot Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/troubleshooting).

## A few calls failed with 401 an hour after the role assignment (2026-10-26)

**Seen:** after the role in the next entry was assigned, three model calls in two portal evaluation runs failed with 401 `PermissionDenied`, "Principal does not have access to API/Operation.", while the calls around them succeeded. About an hour after the assignment; Azure documents up to 10 minutes. Cause unknown.

**Evidence:** tested live, 2026-10-26. Role assigned 17:12 UTC, runs at 18:11 and 18:13 UTC. In the [log excerpts](../../eval/model-selection/dev-outage-v1/README.md): 2 of 25 judge calls in luna's run, and 1 of 5 Responses API calls for sol's answers. Tracked in [#7](https://github.com/sindredg/hindcast/issues/7).

**For Hindcast:** a "completed" run can be missing scores. `summarise_runs.py` lists failed calls; `hindcast.evaluation.foundry` counts a row with no score, no verdict, or an error as errored (0 errored rows in its two runs, [report](../../eval/reconstruction/showcase-v1/README.md#foundry-cloud-evaluation)). See also the [evaluation findings](evaluation.md).

**Read more:** [Troubleshoot Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/troubleshooting).

## With key access off, a portal evaluation calls the models as the user, on the resource endpoint (2026-10-26)

**Seen:** a portal evaluation with a model target failed on every row with 401. The service called `POST /openai/deployments/{deployment-id}/chat/completions` on the resource endpoint as the signed-in user, whose only Foundry role was at project scope. The day before, with key access on, the same kind of run worked.

**Evidence:** tested live, 2026-10-26.

- Every row: `Error code: 401 - PermissionDenied`, "The principal `<user>` lacks the required data action `Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action`".
- Activity log: the portal's key requests (`accounts/listkeys/action`) failed 39 times between 16:18 and 16:46 UTC; they had succeeded the day before. That the earlier run used a key is inferred from those requests.
- `GET <project endpoint>/openai/evals?api-version=v1` as the user: HTTP 400 naming `Microsoft.CognitiveServices/accounts/OpenAI/evals/read`. About 3 minutes after Cognitive Services OpenAI User was assigned on the resource: HTTP 200. The runs that followed answered all ten questions; three calls still failed (entry above).
- `az role definition list`: Cognitive Services OpenAI User grants OpenAI chat completions, Responses, and reads (`OpenAI/*/read`), nothing outside `OpenAI/`. Foundry User grants `Microsoft.CognitiveServices/*`.

**For Hindcast:** portal evaluations need an OpenAI data role on the resource; Foundry User at project scope is enough for Hindcast's own calls. Cognitive Services OpenAI User worked and grants less than Foundry User at the same scope; no narrower role was tried. While assigned it also covers the project, so the project-scope claim cannot fail ([#9](https://github.com/sindredg/hindcast/issues/9)). The [runbook](../runbooks/foundations.md#re-check-the-model-choice) assigns it before the runs and removes it after; removed 2026-10-26 at 19:26 UTC, then checked: the evals read returned 400 again and `ask_model` through the project answered.

**Read more:** [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry), [Run evaluations from the portal](https://learn.microsoft.com/azure/foundry/how-to/evaluate-generative-ai-app).

## With key access off, a valid key gets the same 401 as a wrong one (2026-10-25)

**Seen:** with `disableLocalAuth` true on the Foundry resource, a request with a valid API key fails with 401 and the wrong-key message: "Access denied due to invalid subscription key or wrong API endpoint." Entra calls through the project keep working.

**Evidence:** tested live, 2026-10-25. `GET https://<resource>.services.ai.azure.com/openai/v1/models` with header `api-key: <key1>`: HTTP 200 before, HTTP 401 after `az resource update --ids <resource-id> --set properties.disableLocalAuth=true`. Read back: `disableLocalAuth` `true`. `ask_model` on gpt-6-luna through the project answered the same day.

**For Hindcast:** a 401 on a key-based call means key access is off, not that the key is wrong; regenerating keys does not help.

**Read more:** [Disable local authentication in Foundry Tools](https://learn.microsoft.com/azure/ai-services/disable-local-auth), [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry).

## A project-scope role reaches the models but not the resource endpoint (2026-10-25)

**Seen:** with Foundry User only at project scope, a model call through the project endpoint succeeds and a Content Understanding call on the resource endpoint is refused. Foundry User grants `Microsoft.CognitiveServices/*`, so the scope decides, not the role.

**Evidence:** tested live, 2026-10-25, as a user whose only Foundry User assignment is on the project.

- `responses.create` through `https://<resource>.services.ai.azure.com/api/projects/<project>` with gpt-6-luna: answered.
- `GET https://<resource>.services.ai.azure.com/contentunderstanding/analyzers/prebuilt-documentSearch?api-version=2025-11-01` with a token for `https://cognitiveservices.azure.com/.default`: HTTP 401, `PermissionDenied`, "lacks the required data action `Microsoft.CognitiveServices/accounts/MultiModalIntelligence/analyzers/read`". The same for `GET .../contentunderstanding/defaults`. Later that day, after key access was turned off, the same GET returned 401 `PermissionDenied` with "Principal does not have access to API/Operation." and no action named (read 19:30 UTC).
- `az role definition list`: Foundry User and Cognitive Services User grant `Microsoft.CognitiveServices/*`; Cognitive Services Content Understanding Reader grants analyzer reads and the analyze actions, no writes; Content Understanding Contributor and Owner grant `MultiModalIntelligence/*`.

**For Hindcast:** extraction needs a second assignment at resource scope: Reader to analyze, Contributor to set the resource's model defaults. Contributor was assigned to the developer on 2026-10-27 and removed the same day ([entry above](#a-removed-role-kept-working-on-content-understanding-for-about-11-minutes-2026-10-27)); it cannot delete analyzers ([extraction findings](extraction.md#content-understanding-contributor-cannot-delete-an-analyzer-but-can-replace-one-2026-10-27)). The app's identity gets no Content Understanding role (`infra/modules/roles.bicep`).

**Read more:** [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry), [Secure your Content Understanding analyzers and data](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/secure-communications).

## A wider copy of a role hides a least-privilege test (2026-10-25)

**Seen:** an older Foundry User assignment at subscription scope made the project-scope assignment untestable: every scope below inherits it, so no call can fail for lack of it.

**Evidence:** tested live, 2026-10-25. `az role assignment list --assignee <user> --all` listed Foundry User at subscription scope, on two resource groups, and on the project. After all but the project assignment were deleted, the Content Understanding call above returned 401. That it would have passed before is reasoned from inheritance, not observed.

**For Hindcast:** a least-privilege claim starts with the assignment list; access checks run against an identity that holds only the intended assignments.

**Read more:** [Understand scope for Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/scope-overview), [Role-based access control for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry).

## No token and a missing role both return 401 (2026-10-25)

**Seen:** the Content Understanding endpoint answers 401 without a token and with a valid token that lacks the data action. Only the body tells them apart.

**Evidence:** tested live, 2026-10-25, on the analyzer GET above: without an `Authorization` header, 401; with a token and no role at resource scope, 401 with `PermissionDenied` and the missing action named.

**For Hindcast:** an access check asserts on the error code in the body (`PermissionDenied`), not on the status alone or the message, which changed within the day.

**Read more:** [Secure your Content Understanding analyzers and data](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/secure-communications).

## Blob Storage with shared keys off refuses keys and anonymous reads (2026-10-25)

**Seen:** with shared key access and public blob access off, a key-based request and an anonymous request both fail with a specific error code. Entra sign-in with Storage Blob Data Contributor works.

**Evidence:** tested live, 2026-10-25, on the case source account.

- `az storage container list --auth-mode key`: `KeyBasedAuthenticationNotPermitted`.
- `curl` on `https://<account>.blob.core.windows.net/sources?restype=container&comp=list` without a token: HTTP 409, `PublicAccessNotPermitted`.
- `az storage container list --auth-mode login`: `extracted`, `sources`.

**For Hindcast:** the source files are reachable only with an Entra token and a data role.

**Read more:** [Prevent Shared Key authorization](https://learn.microsoft.com/azure/storage/common/shared-key-authorization-prevent), [Remediate anonymous read access to blob data](https://learn.microsoft.com/azure/storage/blobs/anonymous-read-access-prevent).

## Foundry tracing stores a connection string, not an Entra identity (2026-10-25)

**Seen:** connecting Application Insights to the Foundry project creates a connection of category `AppInsights` with authentication type `ApiKey`, holding the connection string. Entra-authenticated trace ingestion is in preview.

**Evidence:** tested live, 2026-10-25: the project's connections, read from Azure Resource Manager, list one `AppInsights` connection with `authType` `ApiKey`. Preview status from "Set up tracing for AI agents in Microsoft Foundry" (updated 2026-10-21).

**For Hindcast:** the connection string can write telemetry but not read it; [decision 0011](../decisions/0011-telemetry-and-cost.md) treats it as configuration kept out of the repository. Previews are not used. The `AppInsights` connection was deleted on 2026-11-03 for the content its traces store ([observability](observability.md#foundrys-server-side-traces-store-every-prompt-and-answer-whatever-the-client-sets-2026-11-03)); the commands and the page still send their own spans with the connection string.

**Read more:** [Set up tracing for AI agents in Foundry](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup), [Entra authentication for trace ingestion (preview)](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-ingestion-entra-authentication).

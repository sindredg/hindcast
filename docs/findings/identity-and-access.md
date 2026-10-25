# Identity and access

Findings about Entra ID roles, scopes, and keyless access. Hindcast uses no keys: every call carries an Entra token ([decision 0009](../decisions/0009-hosting-and-identity.md)).

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

**For Hindcast:** extraction needs a second assignment at resource scope. Reader is enough to analyze; setting the resource's model defaults needs Contributor. The extraction milestone decides, for the developer and for the app's identity.

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

# Deployment

Findings about the Azure Developer CLI, Bicep, and Azure Container Apps. Design: [architecture](../architecture/README.md#the-deployment); procedure: [deployment runbook](../runbooks/deployment.md).

## `azd down --purge` leaves the Log Analytics workspace recoverable (2026-11-06)

**Seen:** `azd down --purge --force` purged the Foundry resource but left the Log Analytics workspace soft-deleted. The next `azd up` under the same names recovered it, old spans included. Neither command says so.

**Evidence:** tested live, 2026-11-06, azd 1.37.2. After the removal at 19:23Z, `az group exists` printed `false`. After the rebuild, `az monitor log-analytics workspace show` reported `createdDate` 19:28:45Z, and the trace query on the new Application Insights resource returned the three runs made from 18:25Z to 18:36Z on the removed environment. Documented in [delete and recover a workspace](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/delete-workspace): a deleted workspace is recoverable for 14 days, the same subscription, resource group, name, and region recover it with its data, and only `--force` is permanent.

**For Hindcast:** the [runbook](../runbooks/deployment.md#remove) deletes the workspace with `--force true` before `azd down` and lists deleted workspaces afterwards. The forced delete ran at the final removal on 2026-11-06 and left none ([worklog](../worklogs/06-deployment.md#slice-2-final-removal)).

## A Bicep compiler warning exits 0 (2026-11-01)

**Seen:** `az bicep build` reports a property of the wrong type (`BCP036`) as a warning and exits 0. `infra/bicepconfig.json` raises the linter's rules to errors, but compiler diagnostics are not linter rules.

**Evidence:** tested locally, 2026-11-01, Bicep CLI 0.48.1 through Azure CLI 2.88.0. A copy of `infra/search.bicep` with `replicaCount: '1'`: `az bicep build` exit 0, `Warning BCP036` on standard error; `az bicep lint` printed it again. The committed template printed nothing.

**For Hindcast:** the CI step fails when build or lint prints anything. It passed the committed template and failed the copy.

## Built-in authentication answers 401 to a client that does not look like a browser (2026-10-31)

**Seen:** with `unauthenticatedClientAction: RedirectToLoginPage`, a request without a session is redirected only when it carries a browser `User-Agent`. `curl` gets `401`, with or without `Accept: text/html`, for `GET` and `HEAD`.

**Evidence:** tested live, 2026-10-31, against `ca-hindcast`. With `User-Agent: Mozilla/5.0`: `302` to `https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize`. Without it: `401`. `/_stcore/health`, an excluded path: `404` from the placeholder image, never `302`.

**For Hindcast:** the redirect check sends a browser user agent ([runbook](../runbooks/deployment.md#the-page), step 11).

## Reading the container app that the same template deploys is a circular dependency (2026-10-31)

**Seen:** azd's convention reads the container app as an `existing` resource to keep its image on re-provision. In the template that also deploys the app, validation rejects that with `Circular dependency detected on resource`. On the first provision the condition is false, so neither the first run nor a what-if before it shows it.

**Evidence:** tested live, 2026-10-31. `az deployment sub validate` with `webExists=true` on the template at `ccec94d`: `Circular dependency detected on resource`, exit 1. With the read in a module (`infra/fetch-image.bicep`): `Succeeded` for both values, and `azd provision` succeeded.

**For Hindcast:** the template does not read the existing app: every provision takes the image from `HINDCAST_IMAGE` ([worklog](../worklogs/06-deployment.md#live-run)). `az deployment sub validate` runs before a provision; it catches template errors, not parameter values.

## `azd provision --preview` does not run the provision hooks (2026-10-31)

**Seen:** `azd provision --preview` skipped the pre-provision hook and prompted for a Bicep parameter the hook sets. `azd provision` runs the hooks.

**Evidence:** tested live, 2026-10-31, azd 1.37.2: the preview prompted `Enter a value for the 'allowedUserObjectId' infrastructure parameter`. After `azd hooks run preprovision`, which printed `app registration: hindcast-app (created)`, it ran without a prompt.

**For Hindcast:** the runbook runs the hook by name before the preview ([runbook](../runbooks/deployment.md#preview), step 3).

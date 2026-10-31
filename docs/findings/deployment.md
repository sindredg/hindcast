# Deployment

Findings about the Azure Developer CLI, Bicep, and Azure Container Apps. The deployment is described in the [architecture](../architecture/README.md#the-deployment), and the procedure in the [deployment runbook](../runbooks/deployment.md).

## Built-in authentication answers 401 to a client that does not look like a browser (2026-10-31)

**Seen:** with `unauthenticatedClientAction: RedirectToLoginPage`, a request without a session is redirected to Entra sign-in only when it carries a browser `User-Agent`. `curl` with its own user agent gets `401`, with or without `Accept: text/html`, for `GET` and `HEAD`.

**Evidence:** tested live, 2026-10-31, against `ca-hindcast`. With `User-Agent: Mozilla/5.0`: `302` to `https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize`. Without it: `401`. `/_stcore/health`, an excluded path: `404` from the placeholder image, never `302`.

**For Hindcast:** a check of the sign-in redirect sends a browser user agent; a `401` without one is not a fault ([runbook](../runbooks/deployment.md#sign-in), step 6).

## Reading the container app that the same template deploys is a circular dependency (2026-10-31)

**Seen:** azd's convention keeps a container app's current image on re-provision by reading the app as an `existing` resource. In the template that also deploys the app, deployment validation rejects that with `Circular dependency detected on resource`. On the first provision the condition is false and the template passes, so neither the first run nor a what-if before it shows the problem.

**Evidence:** tested live, 2026-10-31. `az deployment sub validate` with `webExists=true` on the template at `ccec94d`: `Circular dependency detected on resource`, exit 1. With the read moved into a module (`infra/fetch-image.bicep`): `Succeeded` for `webExists=true` and `false`, and `azd provision` succeeded.

**For Hindcast:** the existing image is read in a module of its own, and both values of `webExists` are validated before a provision ([worklog](../worklogs/06-deployment.md#checks)).

## `azd provision --preview` does not run the provision hooks (2026-10-31)

**Seen:** `azd provision --preview` skipped the pre-provision hook and prompted for a Bicep parameter that the hook sets. `azd provision` runs the hooks.

**Evidence:** tested live, 2026-10-31, azd 1.37.2: the preview prompted `Enter a value for the 'allowedUserObjectId' infrastructure parameter`. After `azd hooks run preprovision`, which printed `app registration: hindcast-app (created)`, the preview ran without a prompt.

**For Hindcast:** the runbook runs the hook by name before the preview ([runbook](../runbooks/deployment.md#preview), step 3).

# 9. Hosting and identity: Azure Container Apps with a user-assigned managed identity

Status: Accepted (2026-10-24).

## Context

Hindcast is one Python web app (decision 8) that calls Foundry, AI Search, Content Safety, Language, and Blob Storage. It is used by one person at a time, mostly idle, and deleted after the demo is recorded. It runs behind Microsoft Entra sign-in and reaches every service without keys.

The workstation it is built from cannot run Docker, so a container image has to be built in the cloud, or the app has to deploy without an image.

## Options considered

| Option | Fit | Cost | Catch |
|---|---|---|---|
| A. Azure Container Apps, consumption plan, one replica, built-in Entra authentication | Scales to zero. One replica keeps a Streamlit session on one container without sticky routing | A monthly free grant of 180,000 vCPU-seconds and 2 million requests per subscription, plus a container registry for the image | A cold start after idle |
| B. Azure App Service, Linux, B1 | Deploys code without an image or a registry; same built-in authentication; WebSockets on by default for Linux | Billed while it exists, whether used or not | Never scales to zero |
| C. A Foundry hosted agent plus a thin front end | Moves the agent loop into Foundry | Two hosting surfaces | Ruled out in decision 2 |

Identity type for the app:

| Option | Fit |
|---|---|
| User-assigned managed identity | Exists before the app, so its roles (registry pull, data access) are in place for the first revision. Can be reused across a redeploy |
| System-assigned managed identity | Created with the app and deleted with it. Its roles can only be granted after the app exists, which complicates the first deployment |

Sources, read 2026-10-24: [Authentication in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/authentication), [Billing in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/billing), [App Service on Linux FAQ](https://learn.microsoft.com/troubleshoot/azure/app-service/faqs-app-service-linux-new).

## Decision

Option A with a user-assigned managed identity. Container Apps costs nothing while idle, the image builds in the registry without a local Docker engine, and the identity's roles exist before the first revision starts.

## Trade-offs

- A container registry is one more resource to create, secure, and delete.
- The first request after idle waits for a container to start. The demo is recorded with one replica kept warm.
- Built-in authentication with Entra ID needs an app registration. The documented setup uses a client secret, stored as a Container Apps secret, which is the one secret in an otherwise keyless design. Whether a managed identity can replace it as a federated credential is not checked yet; that check comes before the deployment.
- A user-assigned identity outlives the app unless it is deleted with the resource group.
- Container Apps passes WebSocket connections through its ingress per its documentation; Streamlit depends on that, and it is not tested yet.

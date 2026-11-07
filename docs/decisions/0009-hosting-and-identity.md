# 9. Hosting and identity: Azure Container Apps with a user-assigned managed identity

Status: Accepted (2026-10-24). Changed by [decision 0016](0016-sign-in-credential-image-build-and-resource-group.md).

## Context

One Python web app (decision 8) calling Foundry, AI Search, Content Safety, Language, and Blob Storage; one user at a time, mostly idle, deleted after the demo, Entra sign-in, no keys. The workstation cannot run Docker.

## Options considered

| Option | Fit | Cost | Catch |
|---|---|---|---|
| A. Azure Container Apps, consumption, one replica, built-in Entra authentication | Scales to zero; one replica keeps a Streamlit session on one container | Monthly free grant of 180,000 vCPU-seconds and 2 million requests, plus a registry | Cold start |
| B. Azure App Service, Linux, B1 | No image needed; same authentication; WebSockets on | Billed while it exists | Never scales to zero |
| C. Foundry hosted agent plus a front end | | Two hosting surfaces | Ruled out in decision 2 |

| Identity | Fit |
|---|---|
| User-assigned | Exists before the app; roles in place for the first revision; reusable |
| System-assigned | Roles only after the app exists |

Sources, read 2026-10-24: [authentication](https://learn.microsoft.com/azure/container-apps/authentication), [billing](https://learn.microsoft.com/azure/container-apps/billing), [App Service Linux FAQ](https://learn.microsoft.com/troubleshoot/azure/app-service/faqs-app-service-linux-new).

## Decision

Option A with a user-assigned identity: free while idle, image built in the registry, roles before the first revision.

## Trade-offs

- A registry to create, secure, and delete.
- The first request after idle waits; the demo keeps one replica warm.
- Entra authentication's documented setup stores a client secret, the one secret in a keyless design. Whether a managed identity can replace it as a federated credential is checked before deployment.
- The identity outlives the app unless deleted with the resource group.
- WebSocket pass-through is documented, not yet tested.

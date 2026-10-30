# 16. Deployment: a federated sign-in credential, an image built in CI, and a resource group of the app's own

Status: Accepted (2026-10-30).

## Context

Decision [0009](0009-hosting-and-identity.md) chose Azure Container Apps with built-in Entra authentication and left two checks open: whether a managed identity can replace the client secret the documentation uses, and whether the ingress passes Streamlit's WebSocket. Decision [0010](0010-infrastructure-as-code.md) chose `azd` with Bicep. Writing the first template surfaced three facts, read on 2026-10-30:

1. The [Container Apps Entra page](https://learn.microsoft.com/azure/container-apps/authentication-entra) documents a client secret, stored as a container secret, or an ID-token-only flow. App Service documents a managed identity as a federated credential for the same feature; for Container Apps the only evidence is an open issue ([microsoft/azure-container-apps#1693](https://github.com/microsoft/azure-container-apps/issues/1693)) with two community reports that the App Service setting works when the secret is named in lowercase.
2. The registry's remote build, which `azd` uses to build without a local Docker engine, runs as a registry task, and [registry task runs](https://learn.microsoft.com/azure/container-registry/container-registry-tasks-overview) are not available to this subscription. The workstation has no Docker engine either.
3. `azd down` deletes the resource group it provisioned. Foundry, the model deployments, the sources, and the extracts live in a resource group built by hand before any template existed.

The [ingress overview](https://learn.microsoft.com/azure/container-apps/ingress-overview) answers the WebSocket check: HTTP ingress supports WebSocket, with a 240 second request timeout. Streamlit reconnects its socket on its own.

## Options considered

Sign-in credential:

| Option | Fit | Catch |
|---|---|---|
| A. The app's managed identity as a federated credential on the app registration, through the lowercase override secret name | No secret anywhere; the one "secret" the container holds is the identity's client ID | Undocumented for Container Apps; may stop working |
| B. A client secret with a short expiry, stored as a container secret | Documented and predictable | The one secret in an otherwise keyless design; it expires and has to be rotated |

Image build:

| Option | Fit | Catch |
|---|---|---|
| C. GitHub Actions builds the image and pushes it to the registry, signed in with the workflow's OIDC token against a CI identity | No stored credential; the federated credential accepts only this repository's `main` branch; the pull stays the app identity's `AcrPull` | One more identity, a deployment environment with four secrets that hold IDs, and a first-run order: provision, set the secrets, push, deploy |
| D. GitHub Actions pushes to the GitHub container registry; the app pulls the public image | No Azure credential in GitHub, no registry in Bicep | A public image; the app pulls anonymously instead of with its identity |
| E. A workstation with Docker | None of the above | Not available here |

Resource group:

| Option | Fit | Catch |
|---|---|---|
| F. The app in its own resource group; the existing resources read by name | `azd down` cannot reach Foundry or storage | Two resource groups until the full template owns both |
| G. The app in the existing resource group | One group | One `azd down` would delete everything built so far |

## Decision

A with B as the fallback, C, and F. The template carries both credential paths: an empty client-secret parameter selects the federated credential; a value selects the secret. If sign-in fails on the federated path, the fallback is one environment value and a redeploy, and the result is recorded in the deployment worklog. The image is built in GitHub Actions on every pull request, which proves the Dockerfile, and pushed from `main` only, from a job in a deployment environment that holds the identity and registry IDs. The app's resources live in `rg-hindcast-app`.

## Trade-offs

- The federated path rests on undocumented behaviour. The trigger to revisit: Microsoft documents it, or sign-in fails. Until then the fallback stays in the template, tested as a parameter path, not live.
- GitHub to Entra is one more federated trust. Its subject is pinned to `refs/heads/main` of one repository, so a pull request or a fork cannot push an image.
- The image is built twice per push to `main`: once as the pull-request proof, once in the push job. Both builds are deterministic from digest-pinned bases.
- Two resource groups mean two places to look at and two to delete. The full template, written when milestone 6 closes, decides whether it owns both.
- Role assignments the app identity later gets on Foundry and storage live in the other resource group and are not removed by `azd down`; they are orphaned when the identity goes and cleaned up at teardown.

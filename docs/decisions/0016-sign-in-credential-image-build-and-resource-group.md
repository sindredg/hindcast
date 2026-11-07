# 16. Deployment: a federated sign-in credential, an image built in CI, and a resource group of the app's own

Status: Accepted (2026-10-30). Changed by [decision 0028](0028-full-environment-and-live-page.md) and [decision 0029](0029-push-the-tested-image.md).

## Context

Decision [0009](0009-hosting-and-identity.md) left the sign-in credential and the WebSocket open; decision [0010](0010-infrastructure-as-code.md) chose `azd` with Bicep. Read on 2026-10-30:

1. The [Container Apps Entra page](https://learn.microsoft.com/azure/container-apps/authentication-entra) documents a client secret or an ID-token-only flow. A managed identity as federated credential is documented for App Service only; for Container Apps the evidence is [microsoft/azure-container-apps#1693](https://github.com/microsoft/azure-container-apps/issues/1693), two community reports that it works when the secret is named in lowercase.
2. [Registry task runs](https://learn.microsoft.com/azure/container-registry/container-registry-tasks-overview), which `azd` uses to build without local Docker, are not available to this subscription.
3. `azd down` deletes the group it provisioned; Foundry, the deployments, sources, and extracts live in a hand-built group.

The [ingress overview](https://learn.microsoft.com/azure/container-apps/ingress-overview) settles the WebSocket: supported, 240 second request timeout; Streamlit reconnects on its own.

## Options considered

| Question | Option | Fit | Catch |
|---|---|---|---|
| Credential | A. The managed identity as federated credential, via the lowercase override name | No secret | Undocumented for Container Apps |
| | B. A short-lived client secret | Documented | The one secret; rotation |
| Image build | C. GitHub Actions builds and pushes with its OIDC token against a CI identity | No stored credential; the trust accepts only this repository's `azure` environment, which admits only `main`; pull stays the app's `AcrPull` | One more identity, four ID secrets, a first-run order: provision, secrets, push, deploy |
| | D. Push to the GitHub container registry; the app pulls the public image | No Azure credential in GitHub | A public image, pulled anonymously |
| | E. A workstation with Docker | | Not available |
| Resource group | F. The app in its own group | `azd down` cannot reach Foundry or storage | Two groups |
| | G. The existing group | One group | One `azd down` deletes everything |

## Decision

A with B as fallback, C, and F. The template carries both credential paths: an empty client-secret parameter selects the federated credential, a value selects the secret; the fallback is one environment value and a redeploy, recorded in the deployment worklog. The image is built on every pull request and pushed from `main` only, from a job in a deployment environment holding the identity and registry IDs. The app lives in `rg-hindcast-app`.

## Trade-offs

- The federated path is undocumented; revisit when Microsoft documents it or sign-in fails. `az deployment sub validate` with a client-secret value succeeds; the fallback has not run live.
- GitHub to Entra is one more federated trust, scoped to the `azure` environment of one repository. The guard is the subject in Bicep plus a branch policy on GitHub that is not in the template.
- The image is built twice per push to `main`, both from digest-pinned bases.
- Two groups until milestone 6's template decides whether it owns both.
- Roles the app gets on Foundry and storage survive `azd down` and are cleaned up at teardown.

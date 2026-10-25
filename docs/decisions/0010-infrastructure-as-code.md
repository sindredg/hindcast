# 10. Infrastructure as code: Azure Developer CLI with Bicep

Status: Accepted (2026-10-24).

## Context

Every Azure resource Hindcast uses is first created by hand, to see each setting. The whole system then has to be rebuilt from an empty resource group by someone else following the runbooks, and deleted after the demo. That rebuild needs the infrastructure and the app deployment as code, run by one command.

## Options considered

| Option | Fit | Catch |
|---|---|---|
| A. Azure Developer CLI (`azd`) 1.37.1 with Bicep 0.48.1 | `azd up` provisions the infrastructure, builds the image in the cloud, and deploys the app. Microsoft's Foundry templates use it. Bicep uses the Azure Resource Manager API versions directly, so new Foundry resource types are available when their API ships | One more tool on the workstation, and a Bicep linter in CI |
| B. Terraform 1.17.0 with the azurerm provider 5.11.0 | Widely used; one language across clouds | New Foundry resource types tend to need the AzAPI provider until azurerm covers them. Building and deploying the app is scripted outside Terraform |
| C. Azure portal only | Fastest for a single build | Not reproducible; no rebuild from scratch |

Versions are the latest releases on 2026-10-24 (GitHub releases and the Terraform registry).

## Decision

Option A. One command rebuilds both the infrastructure and the app, and Bicep reaches new Foundry resource types without a second provider.

## Trade-offs

- Bicep is Azure-only. Nothing in Hindcast runs elsewhere, so that costs nothing here.
- `azd` adds its own conventions (`azure.yaml`, environments under `.azure/`) and keeps environment values in local files that contain real resource names. Those stay out of the repository.
- `azd` deploys what the templates describe. Settings changed by hand after a deployment drift from the code until they are written back into Bicep.

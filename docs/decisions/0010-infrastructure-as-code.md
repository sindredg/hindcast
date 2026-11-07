# 10. Infrastructure as code: Azure Developer CLI with Bicep

Status: Accepted (2026-10-24).

## Context

Resources are first created by hand, then rebuilt from an empty resource group by someone following the runbooks, with one command, and deleted after the demo.

## Options considered

| Option | Fit | Catch |
|---|---|---|
| A. Azure Developer CLI (`azd`) 1.37.1 with Bicep 0.48.1 | `azd up` provisions, builds in the cloud, deploys; Bicep uses Resource Manager API versions directly, so new Foundry types arrive with their API | One more tool; a Bicep linter in CI |
| B. Terraform 1.17.0 with azurerm 5.11.0 | One language across clouds | New Foundry types need AzAPI; build and deploy scripted outside |
| C. Portal only | Fastest once | Not reproducible |

Versions: latest releases on 2026-10-24.

## Decision

Option A. One command rebuilds infrastructure and app; Bicep reaches new Foundry types without a second provider.

## Trade-offs

- Bicep is Azure-only; nothing here runs elsewhere.
- `azd` adds `azure.yaml` and `.azure/` environments with real resource names, kept out of the repository.
- Hand-changed settings drift until written back into Bicep.

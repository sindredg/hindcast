# Reproduce the project

Status: Not tested from a fork. The project was built once, in one subscription and one GitHub repository, and every Azure resource was removed by 2026-11-07. This page lists what those runs depended on and the order of the runbooks, so that a second build knows what to prepare and what to change. Expect gaps: each runbook was validated on the date in its status line, against the service versions of that day.

## What you need

| Requirement | Used for |
| --- | --- |
| An Azure subscription where you hold Owner, or Contributor plus User Access Administrator | The resource group, the Foundry resource, storage, search, the custom role, and the role assignments |
| Global Standard quota in Sweden Central of at least 50,000 tokens per minute for each chat model, plus the extraction and embedding models | The deployments ([foundations](runbooks/foundations.md#prerequisites), [deployment](runbooks/deployment.md#inputs-and-access)) |
| A GitHub repository you own, with a `main` ruleset, secret scanning, and an `azure` deployment environment limited to `main` (the foundations runbook sets the ruleset; the environment is created in the repository settings, as [worklog 06](worklogs/06-deployment.md) records) | CI and the image push over OIDC |
| An Anthropic API key | The judge and the reviewer model ([evaluation](runbooks/evaluation.md#inputs-and-access)) |
| An operator machine with Git, uv, the Azure CLI, the Azure Developer CLI, Bicep, the GitHub CLI, `openssl`, and a browser | Every command; a browser for the Cloudflare Radar charts and the Entra sign-in |
| A signing key for commits | The ruleset requires signed commits |

Costs: the search service and the container app bill per hour while they exist; the model deployments bill per token. The [price table](../data/prices.yaml) holds the rates each run's cost used.

## The order

Each runbook starts with an "Inputs and access" section that names what the earlier ones must have produced. Run them in this order:

| Step | Runbook | What it leaves behind |
| --- | --- | --- |
| 1 | [Foundations](runbooks/foundations.md) | The repository protection, the resource group with the Foundry resource and project, the model deployments, the storage account, `.env`, the case sources in Blob Storage, and the prior-knowledge answers |
| 2 | [Extraction](runbooks/extraction.md) | The case evidence, the chart descriptions, the library extracts, and the frozen answer keys |
| 3 | [Investigator](runbooks/investigator.md), steps 1 to 3 | The evidence check, the safety role, and its check |
| 4 | [Retrieval](runbooks/retrieval.md) | The search service, the library index, and the gate |
| 5 | [Investigator](runbooks/investigator.md), from step 4 | Investigations with the library search, challenges, traces, and costs |
| 6 | [Sealing](runbooks/sealing.md) | Sealed reconstructions by hash, their library snapshots, and later their reveals |
| 7 | [Evaluation](runbooks/evaluation.md) | The frozen rubric and labels, the scored runs, the injection runs, the judge and reviewer decisions, and the report |
| 8 | [Deployment](runbooks/deployment.md) | The full environment from one template, the signed-in page, its live runs and traces, and its removal |
| 9 | [Teardown](runbooks/teardown.md) | Nothing: the hand-built resources removed, with the sealed copies checked first |

The [development runbook](runbooks/development.md) covers the local checks that CI runs.

## What to change

| Change | Where |
| --- | --- |
| The resource group, Foundry resource, storage account, and search service names | The `export` lines at the top of each runbook; `.env` from `.env.example` |
| The repository | `GH_REPO` in the foundations runbook; the `azure` environment's secrets and the `HINDCAST_PUSH_IMAGE` variable ([deployment](runbooks/deployment.md#image)) |
| The azd environment name | `hindcast-full` in the deployment runbook; `azd down` deletes `rg-<environment>` |
| The allowed sign-in account | The `AUTH_ALLOWED_OBJECT_ID` the deployment runbook sets |

## What a second build cannot repeat

- **The sealed reconstructions.** Each was run before its provider published a cause and is pinned by hash in [`seals.json`](../eval/sealed/seals.json). A new run of the same case is a new reconstruction, not a seal: the cause is public by then.
- **The prior-knowledge answers and the scored runs.** They name the model deployments and versions of their day ([showcase v1](../eval/reconstruction/showcase-v1/README.md), [prior knowledge](../eval/prior-knowledge/v1/README.md)). A later version answers differently, and the answer keys have been public in this repository since 2026-10-27.
- **The captures.** Each source is pinned by SHA-256 in the [case registry](../data/cases.yaml) and the [library registry](../data/library.yaml). The capture commands fetch by URL and refuse a hash mismatch, so a page the provider edited since needs a new registry entry, not a silent replacement.
- **The Foundry IQ comparison** ran once in the full environment ([foundry-iq-v1](../eval/retrieval/foundry-iq-v1/README.md)) and needs it again.

The local data tree (`data/sources/`, `build/`) is not in the repository. The registries say what each file is and how to fetch it; the extraction and sealing runbooks say how each derived file was made.

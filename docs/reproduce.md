# Reproduce the project

Status: Not tested from a fork. Built once, in one subscription and one GitHub repository; every Azure resource removed by 2026-11-07. Each runbook was validated on its status line's date against that day's services, so expect gaps.

## What you need

| Requirement | Used for |
| --- | --- |
| An Azure subscription with Owner, or Contributor plus User Access Administrator | Resource group, Foundry resource, storage, search, the custom role, role assignments |
| Global Standard quota in Sweden Central of at least 50,000 tokens per minute per chat model, plus the extraction and embedding models | The deployments ([foundations](runbooks/foundations.md#prerequisites), [deployment](runbooks/deployment.md#inputs-and-access)) |
| A GitHub repository you own, with a `main` ruleset, secret scanning, and an `azure` deployment environment limited to `main` (the foundations runbook sets the ruleset; the environment is created in the repository settings, [worklog 06](worklogs/06-deployment.md)) | CI and the image push over OIDC |
| An Anthropic API key | The judge and the reviewer model ([evaluation](runbooks/evaluation.md#inputs-and-access)) |
| An operator machine with Git, uv, the Azure CLI, the Azure Developer CLI, Bicep, the GitHub CLI, `openssl`, and a browser | Every command; the browser for the Cloudflare Radar charts and the Entra sign-in |
| A signing key for commits | The ruleset requires signed commits |

The search service and the container app bill per hour, the model deployments per token ([price table](../data/prices.yaml)).

## The order

| Step | Runbook | What it leaves behind |
| --- | --- | --- |
| 1 | [Foundations](runbooks/foundations.md) | Repository protection, the resource group with Foundry resource and project, model deployments, storage account, `.env`, case sources in Blob Storage, prior-knowledge answers |
| 2 | [Extraction](runbooks/extraction.md) | Case evidence, chart descriptions, library extracts, frozen answer keys |
| 3 | [Investigator](runbooks/investigator.md), steps 1 to 3 | The evidence check, the safety role, its check |
| 4 | [Retrieval](runbooks/retrieval.md) | The search service, the library index, the gate |
| 5 | [Investigator](runbooks/investigator.md), from step 4 | Investigations with the library search, challenges, traces, costs |
| 6 | [Sealing](runbooks/sealing.md) | Sealed reconstructions by hash, their library snapshots, later their reveals |
| 7 | [Evaluation](runbooks/evaluation.md) | Frozen rubric and labels, scored runs, injection runs, judge and reviewer decisions, the report |
| 8 | [Deployment](runbooks/deployment.md) | The full environment from one template, the signed-in page, its runs and traces, its removal |
| 9 | [Teardown](runbooks/teardown.md) | Nothing: the hand-built resources removed, the sealed copies checked first |

The [development runbook](runbooks/development.md) covers the local checks CI runs.

## What to change

| Change | Where |
| --- | --- |
| Resource group, Foundry resource, storage account, and search service names | The `export` lines at the top of each runbook; `.env` from `.env.example` |
| The repository | `GH_REPO` in the foundations runbook; the `azure` environment's secrets and `HINDCAST_PUSH_IMAGE` ([deployment](runbooks/deployment.md#image)) |
| The azd environment name | `hindcast-full` in the deployment runbook; `azd down` deletes `rg-<environment>` |
| The allowed sign-in account | `AUTH_ALLOWED_OBJECT_ID` in the deployment runbook |

## What a second build cannot repeat

- **The sealed reconstructions.** Each ran before its provider published a cause and is pinned by hash in [`seals.json`](../eval/sealed/seals.json). A new run of the same case is a reconstruction, not a seal.
- **The prior-knowledge answers and the scored runs.** They name the deployments and versions of their day ([showcase v1](../eval/reconstruction/showcase-v1/README.md), [prior knowledge](../eval/prior-knowledge/v1/README.md)). A later version answers differently, and the answer keys have been public here since 2026-10-27.
- **The captures.** Each source is pinned by SHA-256 in the [case registry](../data/cases.yaml) and the [library registry](../data/library.yaml). The capture commands refuse a hash mismatch; a page edited since needs a new registry entry.
- **The Foundry IQ comparison** ran once in the full environment ([foundry-iq-v1](../eval/retrieval/foundry-iq-v1/README.md)) and needs it again.

`data/sources/` and `build/` are not in the repository; the registries say how to fetch each file, the extraction and sealing runbooks how each derived file was made.

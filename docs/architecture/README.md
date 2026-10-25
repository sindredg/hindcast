# Architecture

How Hindcast is built now. What is planned is in the [target architecture](../../README.md#target-architecture) and the [roadmap](../roadmap.md); the decisions behind both are in [decisions](../decisions/). Last compared with the code and the live resources on 2026-10-25, at the end of [milestone 1](../worklogs/01-foundations.md).

## What exists

Milestone 1 built the foundation, not the investigator yet: a capture command for status updates and postmortems, a case registry, a model client, and the prior-knowledge check that runs before any evidence reaches a model.

![Hindcast as built in milestone 1: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status APIs and postmortem pages, the Azure CLI uploads the captured files to Blob Storage, Hindcast's code calls the two pinned model deployments through the Foundry project with the Responses API, and git reaches GitHub through pull requests. The project is connected to Application Insights, which the code does not use yet. The Foundry resource and the storage account accept no keys; traces use the Application Insights connection string](../diagrams/current-architecture.svg)

| Part | Where | What it does |
|---|---|---|
| Settings | `hindcast.config` | Reads endpoints and deployment names from `HINDCAST_*` variables and names every missing one at once. No keys. Not used by the code yet: `hindcast.models` reads its endpoint from the environment directly. |
| Capture | `hindcast.capture` | `status` takes one incident from a provider's status API as canonical JSON (Cloudflare and GitHub by incident ID; Google Cloud from its feed or a saved copy of it). `page` saves a postmortem page as served. Both refuse to overwrite a file, fetch only `https` URLs, and print the registry lines: URL, retrieval time, SHA-256. |
| Case registry | `data/cases.yaml`, `hindcast.cases` | Four outages: three scored showcase cases and one development case. Each has its status updates (evidence) and its postmortem (answer key), each with URL, licence, attribution, retrieval time, and SHA-256. The files stay out of Git. |
| Model client | `hindcast.models` | One Responses API call through the Foundry project, signed in with `DefaultAzureCredential`. Sends the reasoning effort on every call, never `temperature` or `top_p`, and raises on an incomplete or empty answer. Reads model versions from the deployment. |
| Prior-knowledge check | `prompts/prior_knowledge.md`, `hindcast.evaluation.prior` | Asks each model about each showcase outage from its provider, public title, and date only, and writes `eval/results/prior-<date>-<deployment>.json`. |
| Token usage | `hindcast.costs` | `TokenUsage` per call. Cost per run follows with the investigator. |

### The prior-knowledge check

Every refusal happens before a model is called, so a refused run costs nothing and every result points at a prompt, a registry, and code that are in the history. A test also checks that no key fact from a postmortem appears in any question, the incident's title included, or in the system prompt.

![The prior-knowledge check: the collector refuses to run when the prompt, the case registry, the code, or its lock file differs from the last commit, or when today's result file exists. Otherwise it reads the model version from the deployment, asks about each showcase outage from its provider, title, and date at effort medium, writes one result file with the version, effort, hashes, and commit, and prints token counts but never the answers](../diagrams/prior-knowledge-check.svg)

## Azure

One resource group in Sweden Central, created by hand with the [runbook](../runbooks/foundations.md). Bicep replaces the manual steps in milestone 6.

| Resource | Role in Hindcast | Access |
|---|---|---|
| Foundry resource and project | Hosts the model deployments; the project is the endpoint Hindcast calls | Entra ID only: key access is off |
| gpt-6-luna 2026-09-22 | Investigator model | Global Standard, 50,000 tokens and 50 requests per minute, automatic version upgrade off |
| gpt-6.1-sol 2026-09-29 | Comparison model and interim judge | Same as gpt-6-luna |
| gpt-5-mini, grok-4.7 | Candidates kept for the extraction model and the judge; not called by the code | Global Standard, automatic version upgrade on |
| Storage account | `sources` holds the captured status snapshots and postmortem pages under `<case_id>/`; `extracted` is for milestone 2 | Entra ID only: shared keys and anonymous access are off |
| Application Insights and Log Analytics | Connected to the project for tracing | The project connection holds the Application Insights connection string ([decision 0011](../decisions/0011-telemetry-and-cost.md)) |

| Caller | Target | Credential | Role and scope |
|---|---|---|---|
| Developer, `hindcast.models` | Foundry project endpoint | Entra token from the Azure CLI sign-in | Foundry User on the project |
| Developer, Azure CLI | Blob Storage | Entra token | Storage Blob Data Contributor on the account |

The setup ran as subscription Owner, which manages resources and roles but grants no data actions: without the two data roles above, neither call works.

The Foundry User role at project scope does not reach the resource endpoint, where Content Understanding runs; milestone 2 adds a role there ([finding](../findings/identity-and-access.md)).

## Pipeline

GitHub Actions runs three jobs on every pull request: lint and tests (ruff, pytest), YAML and workflow checks (yamllint, zizmor, actionlint), and a dependency audit (pip-audit on the locked tree). `main` accepts changes only through a pull request with those checks passing and signed commits. The workflow is `.github/workflows/ci.yml`.

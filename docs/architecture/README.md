# Architecture

How Hindcast is built now. What is planned is in the [target architecture](../../README.md#target-architecture) and the [roadmap](../roadmap.md); the decisions behind both are in [decisions](../decisions/). Last compared with the code and the live resources on 2026-10-27, during [milestone 2](../worklogs/02-extraction.md).

## What exists

Milestone 1 built the foundation, not the investigator yet: a capture command for status updates and postmortems, a case registry, a model client, and the prior-knowledge check that runs before any evidence reaches a model. Milestone 2 adds the evidence cut and ingestion from Blob Storage; the library, its extraction, and the answer keys follow.

![Hindcast as built: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status pages and postmortems, the Azure CLI uploads the captured files to Blob Storage and Hindcast's ingestion reads them back and writes the cut evidence there with its own Entra token, Hindcast's code calls the two pinned model deployments through the Foundry project with the Responses API, and git reaches GitHub through pull requests. During a portal evaluation run, the Foundry evaluation calls the same deployments as the signed-in user. The project is connected to Application Insights, which the code does not use yet. The Foundry resource and the storage account accept no keys; traces use the Application Insights connection string](../diagrams/current-architecture.svg)

| Part | Where | What it does |
|---|---|---|
| Settings | `hindcast.config` | Reads endpoints and deployment names from `HINDCAST_*` variables, one section per component (models, storage, extraction, search), and names every missing variable of that section at once. No keys. `hindcast.models` loads the model section, so the search values can stay empty until milestone 3. |
| Capture | `hindcast.capture` | `status` takes one incident from a provider's status API as canonical JSON (Cloudflare and GitHub by incident ID; Google Cloud from its feed or a saved copy of it). `page` saves a postmortem page as served. Both refuse to overwrite a file, fetch only `https` URLs, and print the registry lines: URL, retrieval time, SHA-256. |
| Case registry | `data/cases.yaml`, `hindcast.cases` | Four outages: three scored showcase cases and one development case. Each has its status updates (evidence) and its postmortem (answer key), each with URL, licence, attribution, retrieval time, and SHA-256. The files stay out of Git. |
| Model client | `hindcast.models` | One Responses API call through the Foundry project, signed in with `DefaultAzureCredential`. Sends the reasoning effort on every call, never `temperature` or `top_p`, and raises on an incomplete or empty answer. Reads model versions from the deployment. |
| Prior-knowledge check | `prompts/prior_knowledge.md`, `hindcast.evaluation.prior` | Asks each model about each showcase outage from its provider, public title, and date only, and writes `eval/results/prior-<date>-<deployment>.json`. |
| Evidence cut | `hindcast.evidence` | Applies [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) per status format (Statuspage for Cloudflare and GitHub, Google Cloud's feed entry): keeps every update before the resolved one and only the resolved update's time and status, and drops report entries, unknown statuses, and anything after the resolved mark into a list without their text. Times are normalised to UTC. |
| Blob access | `hindcast.storage` | Reads and writes Blob Storage with `DefaultAzureCredential`. A source is returned only if its SHA-256 matches the registry; an upload never overwrites unless asked. |
| Ingestion | `hindcast.ingest` | `evidence` downloads each case's status snapshot, cuts it, and writes the evidence to `build/evidence/` and Blob `extracted/evidence/`, printing counts only. |
| Token usage | `hindcast.costs` | `TokenUsage` per call. Cost per run follows with the investigator. |

### The prior-knowledge check

Every refusal happens before a model is called, so a refused run costs nothing and every result points at a prompt, a registry, and code that are in the history. A test also checks that no key fact from a postmortem appears in any question, the incident's title included, or in the system prompt.

![The prior-knowledge check: the collector refuses to run, before any model call, when the prompt, the case registry, the code, the project file, or the lock file differs from the last commit, when today's result file exists, or when a showcase case has no date in the prompt. Otherwise it reads the model version from the deployment, asks about each showcase outage from its provider, title, and date at effort medium, writes one result file with the version, effort, hashes, and commit, and prints token counts but never the answers](../diagrams/prior-knowledge-check.svg)

## Azure

One resource group in Sweden Central, created by hand with the [runbook](../runbooks/foundations.md). Bicep replaces the manual steps in milestone 6.

| Resource | Role in Hindcast | Access |
|---|---|---|
| Foundry resource and project | Hosts the model deployments; the project is the endpoint Hindcast calls | Entra ID only: key access is off |
| gpt-6-luna 2026-09-22 | Investigator model | Global Standard, 50,000 tokens and 50 requests per minute, automatic version upgrade off |
| gpt-6.1-sol 2026-09-29 | Comparison model and interim judge | Same as gpt-6-luna |
| gpt-5-mini, grok-4.7 | Candidates kept for the extraction model and the judge; not called by the code | Global Standard, automatic version upgrade on |
| Storage account | `sources` holds the captured status snapshots and postmortem pages under `<case_id>/`; `extracted` holds the cut case evidence under `evidence/<case_id>.json` (milestone 2) | Entra ID only: shared keys and anonymous access are off |
| Application Insights and Log Analytics | Connected to the project for tracing. Creating Application Insights also created its "Application Insights Smart Detection" action group, which Hindcast does not use | The project connection holds the Application Insights connection string ([decision 0011](../decisions/0011-telemetry-and-cost.md)) |

| Caller | Target | Credential | Role and scope |
|---|---|---|---|
| Developer, `hindcast.models` | Foundry project endpoint | Entra token from the Azure CLI sign-in | Foundry User on the project |
| Developer, Azure CLI | Blob Storage | Entra token | Storage Blob Data Contributor on the account |
| Developer, `hindcast.ingest` and `hindcast.storage` | Blob Storage | Entra token from the Azure CLI sign-in | Storage Blob Data Contributor on the account |
| Developer, Foundry portal evaluation | Model deployments on the Foundry resource endpoint | The developer's portal sign-in | Cognitive Services OpenAI User on the Foundry resource, assigned for a run and removed after it ([runbook](../runbooks/foundations.md#re-check-the-model-choice)) |

The setup ran as subscription Owner, which manages resources and roles but grants no data actions: without the data roles above, none of these calls works.

The Foundry User role at project scope does not reach the resource endpoint, where Content Understanding runs and where portal evaluations call the models. Portal evaluations need their own role there, held only while they run, so that the project-scope claim stays testable; milestone 2 adds one for Content Understanding ([findings](../findings/identity-and-access.md)).

## Pipeline

GitHub Actions runs three jobs on every pull request and every push to `main`: lint and tests (ruff, pytest), YAML and workflow checks (yamllint, zizmor, actionlint), and a dependency audit (pip-audit on the locked tree). `main` accepts changes only through a pull request with those checks passing and signed commits. The workflow is `.github/workflows/ci.yml`.

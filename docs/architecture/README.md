# Architecture

How Hindcast is built now. What is planned is in the [roadmap](../roadmap.md) with the target architecture; the decisions behind both are in [decisions](../decisions/). Last compared with the code, the pipeline, the repository settings, and the live resources on 2026-10-30, before milestone 4 started.

## What exists

Milestone 1 built the foundation, not the investigator yet: a capture command for status updates and postmortems, a case registry, a model client, and the prior-knowledge check that runs before any evidence reaches a model. Milestone 2 built what the investigator and the evaluation will read: the cut case evidence with its charts, a library of earlier postmortems extracted into sections and described figures, and the frozen answer keys.

![Hindcast as built: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status pages and postmortems, and the Radar charts are downloaded in the browser. The Azure CLI and Hindcast's code store the captured files in Blob Storage, and Hindcast's ingestion reads them back and writes the evidence, the extracts, and the answer-key analyzer results there with its own Entra token. Hindcast's code calls the pinned model deployments through the Foundry project with the Responses API, and calls Content Understanding on the Foundry resource, whose three analyzers use the gpt-5-mini and text-embedding-3-large deployments, with a role held only while extraction runs. During a portal evaluation run, the Foundry evaluation calls the deployments as the signed-in user. git reaches GitHub through pull requests. The project is connected to Application Insights, which the code does not use yet. The Foundry resource and the storage account accept no keys; traces use the Application Insights connection string](../diagrams/current-architecture.svg)

### What reaches the investigator

Three cuts decide what the investigator can read. The evidence cut follows [decision 0005](../decisions/0005-evidence-library-and-answer-key.md), the library follows [decision 0013](../decisions/0013-library-selection.md), and the answer keys stay with the evaluation.

![What the investigator can read: Three lanes. Case evidence: each case's status snapshot, read from Blob Storage and checked against its SHA-256, goes through the evidence cut, which keeps the updates before the resolved one and drops the resolved update's text and any report entries, and becomes the case evidence with its Radar chart descriptions. Library: each library page, picked by the case's symptoms, is cut to its article and extracted; a page must be dated before every case it serves, and later text and bylines are dropped; the result is the library extract, whose figures are not shown. Answer keys: each case's postmortem, which is never in the library, is drafted into a key, reviewed with every quote checked word for word and facts already stated during the incident marked, and frozen with its SHA-256. The investigator reads the case evidence and the library extract; the frozen keys are for the evaluation only. Every step fails closed: an unknown entry is dropped and listed, and a page without its date or a key with a missing field is refused.](../diagrams/extraction-flow.svg)

### Components

| Part | Where | What it does |
|---|---|---|
| Settings | `hindcast.config` | Reads endpoints and deployment names from `HINDCAST_*` variables, one section per component (models, storage, extraction, search), and names every missing variable of that section at once. No keys. `hindcast.models` loads the model section, so the search values can stay empty until milestone 3. |
| Capture | `hindcast.capture` | `status` takes one incident from a provider's status API as canonical JSON (Cloudflare and GitHub by incident ID; Google Cloud from its feed or a saved copy of it). `page` saves a postmortem page as served. Both refuse to overwrite a file, fetch only `https` URLs, and print the registry lines: URL, retrieval time, SHA-256. |
| Case registry | `data/cases.yaml`, `hindcast.cases` | Four outages: three scored showcase cases and one development case, each with its start time. Each has its status updates (evidence) and its postmortem (answer key), each with URL, licence, attribution, retrieval time, and SHA-256; those files stay out of Git. The two Cloudflare cases also have Radar charts, committed under `data/charts/` because their licence (CC BY 4.0) allows it; the registry refuses a chart under any other licence. |
| Model client | `hindcast.models` | One Responses API call through the Foundry project, signed in with `DefaultAzureCredential`. Sends the reasoning effort on every call and the image detail with every image, so a changed service default cannot change results; never sends `temperature` or `top_p`. Raises on an incomplete or empty answer and on a response without token usage. Reads model versions from the deployment. |
| Prior-knowledge check | `prompts/prior_knowledge.md`, `hindcast.evaluation.prior` | Asks each model about each showcase outage from its provider, public title, and date only, and writes `eval/results/prior-<date>-<deployment>.json`. |
| Evidence cut | `hindcast.evidence` | Applies [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) per status format (Statuspage for Cloudflare and GitHub, Google Cloud's feed entry): keeps every update before the resolved one and only the resolved update's time and status, and drops report entries, unknown statuses, and anything after the resolved mark into a list without their text. Times are normalised to UTC. |
| Blob access | `hindcast.storage` | Reads and writes Blob Storage with `DefaultAzureCredential`. A source is returned only if its SHA-256 matches the registry; an upload never overwrites unless asked. |
| Ingestion | `hindcast.ingest` | `evidence` downloads each case's status snapshot, cuts it, attaches its charts' stored descriptions, and writes the evidence to `build/evidence/` and Blob `extracted/evidence/`, printing counts only. `charts` describes each chart once. `library` extracts each library page once. Extracts already in Blob Storage are reused unless `--replace` is given. |
| Library registry | `data/library.yaml`, `hindcast.library` | The symptom tags each case is picked by, quoted from its evidence, and 23 earlier postmortems picked by them ([decision 0013](../decisions/0013-library-selection.md)). Refuses a document dated on or after a case it serves, a case's own postmortem, and a reason that quotes no tagged symptom. The pages stay out of Git, in Blob `sources/library/`. |
| Content Understanding analyzers | `analyzers/*.json`, `hindcast.extract` | Three analyzer definitions (postmortem pages, chart images, answer keys) on gpt-5-mini; the two on the document base also name `text-embedding-3-large`. Creates missing analyzers and refuses one whose service copy differs from its file. |
| Library extraction | `hindcast.library_extract` | Cuts each page to its article by a rule per site, refuses a page whose title, date, or body the rule cannot find or whose date differs from the registry, splits the extracted markdown into sections, drops text dated after the earliest served case, and describes each figure. A library figure is shown only under a licence that allows it, which no library page has. Extracts go to `build/extracted/library/` and Blob `extracted/library/`. |
| Answer keys | `hindcast.keys`, `eval/keys/` | Drafts a key per case from its postmortem, with a quote per item checked word for word, and a review sheet; freezes a reviewed key and records its SHA-256 in `eval/keys/frozen.json`, which a test checks ([keys](../../eval/keys/README.md)). |
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
| gpt-5-mini 2025-08-07 | Content Understanding's completion model ([decision 0014](../decisions/0014-extraction-and-embedding-models.md)) | Global Standard, automatic version upgrade on ([#13](https://github.com/sindredg/hindcast/issues/13)) |
| text-embedding-3-large 1 | Named by the document analyzers, which require an embedding model; retrieval reuses it in milestone 3 ([decision 0014](../decisions/0014-extraction-and-embedding-models.md)) | Global Standard, 50,000 tokens per minute, automatic version upgrade off |
| grok-4.7 | Candidate judge; not called by the code | Global Standard, automatic version upgrade on |
| Storage account | `sources` holds the captured status snapshots and postmortem pages under `<case_id>/` and the library pages under `library/`; `extracted` holds the case evidence (`evidence/`), the chart descriptions (`charts/`), the library extracts (`library/`), and the answer-key analyzer results (`keys/`) | Entra ID only: shared keys and anonymous access are off |
| Application Insights and Log Analytics | Connected to the project for tracing. Creating Application Insights also created its "Application Insights Smart Detection" action group, which Hindcast does not use | The project connection holds the Application Insights connection string ([decision 0011](../decisions/0011-telemetry-and-cost.md)) |

| Caller | Target | Credential | Role and scope |
|---|---|---|---|
| Developer, `hindcast.models` | Foundry project endpoint | Entra token from the Azure CLI sign-in | Foundry User on the project |
| Developer, Azure CLI | Blob Storage | Entra token | Storage Blob Data Contributor on the account |
| Developer, `hindcast.ingest` and `hindcast.storage` | Blob Storage | Entra token from the Azure CLI sign-in | Storage Blob Data Contributor on the account |
| Developer, `hindcast.extract`, `hindcast.ingest`, `hindcast.keys` | Content Understanding on the Foundry resource endpoint | Entra token from the Azure CLI sign-in | Cognitive Services Content Understanding Contributor on the Foundry resource, held only while extraction ran (2026-10-27, then removed; [runbook](../runbooks/extraction.md#remove-the-content-understanding-role)) |
| Developer, Foundry portal evaluation | Model deployments on the Foundry resource endpoint | The developer's portal sign-in | Cognitive Services OpenAI User on the Foundry resource, assigned for a run and removed after it ([runbook](../runbooks/foundations.md#re-check-the-model-choice)) |

The setup ran as subscription Owner, which manages resources and roles but grants no data actions: without the data roles above, none of these calls works.

The Foundry User role at project scope does not reach the resource endpoint, where Content Understanding runs and where portal evaluations call the models. Portal evaluations and Content Understanding each need their own role there, held only while they run, so that the project-scope claim stays testable. A removed role kept working on Content Understanding for about 11 minutes, so a removal is checked by retrying a refused call ([findings](../findings/identity-and-access.md)).

## Pipeline

GitHub Actions runs three jobs on every pull request and every push to `main`: lint, type checks, and tests (ruff, ruff format, pyright, pytest), YAML and workflow checks (yamllint, zizmor, actionlint), and a dependency audit (pip-audit on the locked tree). `main` accepts changes only through a pull request with those checks passing and signed commits. The workflow is `.github/workflows/ci.yml`.

Dependabot proposes weekly updates for the actions and the Python dependencies ([`.github/dependabot.yml`](../../.github/dependabot.yml)); nothing merges automatically. Python stays on 3.14 because Dependabot supports no newer version ([#8](https://github.com/sindredg/hindcast/issues/8)). The uv version, the Python version, actionlint, and the runner image move by hand.

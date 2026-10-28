# Roadmap

Each milestone has completion criteria: things shown to work, not things built. A milestone is done when every criterion has evidence in its worklog and an independent review has checked the claims against the code and the running system. An independent review is a read-only pass from a fresh context, with no part in the milestone's work, whose findings are each checked again before they are acted on. Decisions behind the design are in [decisions](decisions/).

## Status

| Milestone | State |
| --- | --- |
| 1. Foundations | Verified on 2026-10-26: the [gate](worklogs/01-foundations.md#gate) records the evidence per criterion and its accepted gaps, and the [independent review](worklogs/01-foundations.md#independent-review) ran with its fixes in. Decisions [0001](decisions/0001-scope.md) to [0012](decisions/0012-models.md) accepted. |
| 2. Extraction | Verified on 2026-10-27: the evidence, the library extracts, the charts, and the frozen answer keys were built and run; the [gate](worklogs/02-extraction.md#gate) records the evidence per criterion and its accepted gaps, and the [independent review](worklogs/02-extraction.md#independent-review) ran with its fixes in. Decisions [0013](decisions/0013-library-selection.md) and [0014](decisions/0014-extraction-and-embedding-models.md) accepted. |
| 3. Retrieval | Planned |
| 4. Investigator | Planned |
| 5. Evaluation | Planned |
| 6. Deployment and release | Planned |

Milestone 4's first slice, the investigator on case tools only, runs before milestone 3: it de-risks the tool loop, the citation checks, and the caps, which no earlier milestone has touched, and AI Search bills per hour from creation ([decision 0004](decisions/0004-retrieval.md)), so creating it later costs less.

## Target architecture

Planned, not built yet. What is built now: [architecture](architecture/).

![Target architecture: a reader signs in with Entra ID to the Hindcast app on Azure Container Apps. The app runs the Foundry prompt agent, checks every tool result with Prompt Shields and every output for personal data, reads the case evidence from Blob Storage, searches the postmortem library in Azure AI Search in Switzerland North, and sends traces to Application Insights. An ingest command captures status updates and postmortems, analyzes library pages, charts, and answer keys with Content Understanding, stores sources and extracts in Blob Storage, and indexes only library documents, so answer keys never reach the index. Service calls use Entra tokens, no keys; traces use the Application Insights connection string](diagrams/target-architecture.svg)

## 1. Foundations

Set up the repository, the pipeline, the Azure foundation, and the case sources, record what the models know about the cases before they read anything, and check the model choice on the development outage.

**Completion criteria:**

- CI runs on every pull request and fails on a lint error, an unpinned action, a workflow error, a YAML error, or a dependency with a known vulnerability. Each check is shown failing once on a broken input.
- `main` takes changes only through a pull request with passing checks and signed commits. Secret scanning and push protection are on.
- The Foundry project, the model deployments, and Blob Storage exist, and the code reaches each of them with an Entra token. Key access is off where the service allows it. (AI Search is created in milestone 3: [decision 0004](decisions/0004-retrieval.md) creates it when ingestion needs it, because it bills per hour.)
- Every source file is in the case registry with its URL, licence, attribution, retrieval time, and a SHA-256 that matches the file, locally and in Blob Storage.
- The prior-knowledge answers are recorded for each showcase case before any evidence reaches a model. The development case is not scored, so it is not asked.
- The investigator model meets a rule written before the run, measured against the comparison model on the development outage ([decision 0012](decisions/0012-models.md)).

## 2. Extraction

Cut each case's status updates into evidence, extract the postmortem library and the answer keys, and describe the charts.

**Completion criteria:**

- Ingestion reads the sources from Blob Storage with an Entra token.
- The evidence keeps every update before the resolved one and only the time and status of the resolved one. Report entries, and entry types the rules do not know, are dropped and listed. Tested per provider with fixed inputs, including a planted report entry ([decision 0005](decisions/0005-evidence-library-and-answer-key.md)).
- Each library postmortem is extracted into sections with its publish date; each chart in it is fetched and described as an image, with its source recorded.
- Each case's answer key (attack or not, root cause, contributing factors, timeline events, fixes) is extracted, reviewed by a person, and frozen by hash.
- A chart from a third party is shown only under a licence that allows it, with its attribution.

## 3. Retrieval

Index the postmortem library in Azure AI Search with section- and figure-bounded chunks and resolvable citations. Runs after the first slice of milestone 4.

**Completion criteria:**

- The AI Search service exists and the code reaches it with an Entra token. A request without a token is refused, and key access is off.
- A library search for a case returns only documents published before its outage began and none about the case, including for a query that contains quotes or a filter expression.
- Every chunk in the index resolves to a section or a chart of a library document.
- The leak check finds no answer-key fact in a case's evidence or its filtered library, except facts the key marks as stated during the incident.

## 4. Investigator

Run an investigation with a Foundry prompt agent that calls case-bound tools and the date-bound library search, and show it in the interface. Built in two slices: first the investigator on the development case with case tools only, before milestone 3; then the library search tool and its citations once milestone 3 has landed. The first bullet is met in full only after the second slice.

**Completion criteria:**

- An investigation of the development case returns an attack assessment, a timeline, findings, contributing factors, and open questions, each item with a citation that resolves, and library citations marked as such.
- A citation that is empty, malformed, unknown, or from another case is rejected with a reason, and the rest of the investigation survives.
- A tool error, an empty result, or a run past 12 tool calls or 120 seconds ends the run as incomplete with a reason.
- A finding can be challenged from the interface, and the answer cites its evidence.
- Every investigation has a trace in Application Insights and a cost.

## 5. Evaluation

Score blind reconstructions against the postmortems, compare them with the baselines and with what the models knew beforehand, and test prompt injection.

**Completion criteria:**

- The answer keys, the rubric, the criteria for a supported inference, and the timeline tolerance are frozen before the first scored run, and the leak check passes.
- Each case is scored for Hindcast and both baselines ([decision 0006](decisions/0006-evaluation-design.md)), with the dataset, model deployment and version, prompt version, and run named for every result.
- Unsupported claims are counted by the support rules; a claim about the outage that rests only on a library document counts as unsupported.
- Planted instructions in a status update, in a library page, and in a chart image are not followed.
- The evaluation report states the results and the error analysis, and two limits: the library is small enough that retrieval is close to a lookup, so the scores say little about retrieval quality; and the answer keys have been public in this repository since 2026-10-27, so for each scored model the report gives its version date against that day and says whether its training data could include the keys.

## 6. Deployment and release

Deploy once with the Azure Developer CLI and Bicep, sign in with Entra ID, and tear it down after the demo.

**Completion criteria:**

- `azd up` builds the environment from an empty resource group, and `azd down` removes it.
- The app reaches every service with its managed identity. No key is stored; the one stored setting is the Application Insights connection string, which can write telemetry but not read it ([decision 0011](decisions/0011-telemetry-and-cost.md)).
- Sign-in is required to open the app.
- A recorded demo shows a full investigation, a challenge, a refused injection, and its trace.

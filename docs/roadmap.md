# Roadmap

A milestone is done when every completion criterion has evidence in its worklog and an independent review, a read-only pass from a fresh context, has checked the claims against the code and the running system. The reasons behind the design are in [decisions](decisions/README.md).

On this page: [Status](#status) · [Architecture as built](#architecture-as-built) · [1. Foundations](#1-foundations) · [2. Extraction](#2-extraction) · [3. Retrieval](#3-retrieval) · [4. Investigator](#4-investigator) · [5. Evaluation](#5-evaluation) · [6. Deployment and release](#6-deployment-and-release) · [7. Close](#7-close)

## Status

| Milestone | State | Date | Evidence | Decisions |
| --- | --- | --- | --- | --- |
| 1. Foundations | Verified | 2026-10-26 | [gate](worklogs/01-foundations.md#gate), [review](worklogs/01-foundations.md#independent-review) | [0001](decisions/0001-scope.md) to [0012](decisions/0012-models.md) |
| 2. Extraction | Verified | 2026-10-27 | [gate](worklogs/02-extraction.md#gate), [review](worklogs/02-extraction.md#independent-review) | [0013](decisions/0013-library-selection.md), [0014](decisions/0014-extraction-and-embedding-models.md) |
| 3. Retrieval | Verified | 2026-11-01 | [gate](worklogs/03-retrieval.md#gate), [review](worklogs/03-retrieval.md#independent-review), [quality check](../eval/retrieval/library-v1/README.md#status), [Foundry IQ comparison](../eval/retrieval/foundry-iq-v1/README.md#status) | [0018](decisions/0018-extraction-model.md), [0019](decisions/0019-library-index.md) |
| 4. Investigator | Verified | 2026-11-07 | gates [1](worklogs/04-investigator.md#gate), [2](worklogs/04-investigator.md#slice-2-gate), [3](worklogs/04-investigator.md#slice-3-gate), [4](worklogs/04-investigator.md#slice-4-gate); reviews [1](worklogs/04-investigator.md#independent-review), [2](worklogs/04-investigator.md#slice-2-independent-review), [3](worklogs/04-investigator.md#slice-3-independent-review), [4](worklogs/04-investigator.md#slice-4-independent-review) | [0015](decisions/0015-investigation-result-and-citation-policy.md), [0020](decisions/0020-library-citations.md), [0021](decisions/0021-screens-pii-and-challenge.md) |
| 5. Evaluation | Verified | 2026-11-07 | [gate](worklogs/05-evaluation.md#gate), [close review](worklogs/05-evaluation.md#milestone-close-review), [report](../eval/reconstruction/showcase-v1/README.md), [sealed report](../eval/reconstruction/sealed-v1/README.md) | [0017](decisions/0017-sealed-reconstructions.md), [0022](decisions/0022-sealed-drop-date-and-offline-reveal.md) to [0027](decisions/0027-reviewer-model.md), [0030](decisions/0030-close-evaluation-with-sealed-addenda.md) |
| 6. Deployment and release | Verified | 2026-11-06 | [gate](worklogs/06-deployment.md#slice-2-gate), [review](worklogs/06-deployment.md#slice-2-independent-review), [live run](worklogs/06-deployment.md#slice-2-live-run), [final removal](worklogs/06-deployment.md#slice-2-final-removal) | [0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md), [0028](decisions/0028-full-environment-and-live-page.md), [0029](decisions/0029-push-the-tested-image.md) |
| 7. Close | Verified | 2026-11-07 | [gate](worklogs/07-close.md#gate), [review](worklogs/07-close.md#independent-review), [teardown](worklogs/07-close.md#teardown) | |

Accepted gap: four sealed cases without a published cause, each revealed as an addendum to the [sealed report](../eval/reconstruction/sealed-v1/README.md) or dropped on 2026-11-30 ([decision 0030](decisions/0030-close-evaluation-with-sealed-addenda.md)).

Milestone 4's first slice ran before milestone 3 to de-risk the tool loop before AI Search started billing ([decision 0004](decisions/0004-retrieval.md)). Milestone 6's first slice deployed a page that renders one stored result, to prove sign-in, the image path, and telemetry before the app called a model ([decision 0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md)).

## Architecture as built

Built in full on 2026-11-05 and removed on 2026-11-06 ([worklog 06](worklogs/06-deployment.md#slice-2-final-removal)); the hand-built foundation followed on 2026-11-07 ([worklog 07](worklogs/07-close.md)). Each part: [architecture](architecture/README.md).

![Architecture as built: a reader signs in with Entra ID to the Hindcast app on Azure Container Apps. The app runs the Foundry prompt agent, checks every tool result with Prompt Shields and every output for personal data, reads the case evidence from Blob Storage, searches the postmortem library in Azure AI Search in Switzerland North, and sends traces to Application Insights. Operator commands capture status updates and postmortems, analyze library pages, charts, and answer keys with Content Understanding, store sources, evidence, and extracts in Blob Storage, and the index build embeds the library chunks with the embedding deployment and indexes only library documents, so answer keys never reach the index. Service calls use Entra tokens, no keys; traces use the Application Insights connection string](diagrams/target-architecture.svg)

## 1. Foundations

The repository, the pipeline, the Azure foundation, the case sources, the prior-knowledge record, and the model choice.

- CI runs on every pull request and fails on a lint error, an unpinned action, a workflow error, a YAML error, or a vulnerable dependency; each check shown failing once.
- `main` takes changes only through a pull request with passing checks and signed commits; secret scanning and push protection on.
- The Foundry project, the model deployments, and Blob Storage exist and are reached with an Entra token; key access off where the service allows. AI Search comes in milestone 3 ([decision 0004](decisions/0004-retrieval.md)).
- Every source file is in the case registry with URL, licence, attribution, retrieval time, and a SHA-256 that matches locally and in Blob Storage.
- Prior-knowledge answers recorded per showcase case before any evidence reaches a model.
- The investigator model meets a rule written before the run, against the comparison model on the development outage ([decision 0012](decisions/0012-models.md)).

## 2. Extraction

Cut the status updates into evidence, extract the library and the answer keys, describe the charts.

- Ingestion reads the sources from Blob Storage with an Entra token.
- The evidence keeps every update before the resolved one and only the time and status of the resolved one; report entries and unknown entry types are dropped and listed. Tested per provider with fixed inputs ([decision 0005](decisions/0005-evidence-library-and-answer-key.md)).
- Each library postmortem is extracted into sections with its publish date; each chart is fetched and described, with its source.
- Each answer key is extracted, reviewed by a person, and frozen by hash.
- A third-party chart is shown only under a licence that allows it, with attribution.

## 3. Retrieval

Index the library in Azure AI Search with section- and figure-bounded chunks and resolvable citations.

- The service exists and is reached with an Entra token; a request without one is refused; key access off.
- A search for a case returns only documents published before its outage and none about the case, including for a query with quotes or a filter expression.
- Every chunk resolves to a section or a chart of a library document.
- The leak check finds no answer-key fact in a case's evidence or filtered library, except facts the key marks as stated during the incident.

## 4. Investigator

A Foundry prompt agent with case-bound tools and the date-bound library search, shown in the interface. Four slices: case tools only; the library search and its citations; Prompt Shields, the PII check, the challenge, traces, and cost; the view parts of [decision 0008](decisions/0008-user-interface.md).

- An investigation of the development case returns an attack assessment, a timeline, findings, contributing factors, and open questions, each with a resolving citation; library citations marked as such.
- An empty, malformed, unknown, or other-case citation is rejected with a reason; the rest of the investigation survives.
- A tool error, an empty result, or a run past 12 tool calls or 120 seconds ends the run as incomplete with a reason.
- A finding can be challenged from the interface; the answer cites its evidence.
- Every investigation has a trace in Application Insights and a cost.

## 5. Evaluation

Score blind reconstructions against the postmortems, compare them with the baselines and with prior knowledge, and test prompt injection.

- The keys, the inferable-from-evidence labels ([decision 0023](decisions/0023-abstention-and-inferable-labels.md)), the rubric, the support criteria, and the timeline tolerance are frozen before the first scored run; the leak check passes.
- Each showcase case is scored for Hindcast, both baselines ([decision 0006](decisions/0006-evaluation-design.md)), and the other arms with repeats; every result names its dataset, deployment and model version, prompt version, and run.
- A sealed case ([decision 0017](decisions/0017-sealed-reconstructions.md)) is revealed and scored only after its provider publishes a cause; the revealed file matches its committed hash. No cause by 2026-11-30 drops the case ([decision 0022](decisions/0022-sealed-drop-date-and-offline-reveal.md)); reveals after the close are addenda ([decision 0030](decisions/0030-close-evaluation-with-sealed-addenda.md)).
- Unsupported claims are counted by the support rules; a claim resting only on a library document is unsupported.
- Planted instructions in an update, a library page, and a chart image are not followed, with Prompt Shields on and off ([decisions 0025](decisions/0025-injection-test-layers.md), [0026](decisions/0026-case-chart-injection.md)).
- The report states the results, the error analysis, and the limits: a small library, keys public since 2026-10-27 against each model's version date, and sealed cases without a single-search baseline or per-case picks.

## 6. Deployment and release

Deploy with the Azure Developer CLI and Bicep behind Entra sign-in, and tear down.

- `azd up` builds the environment from an empty resource group; `azd down` removes it.
- The app reaches every service with its managed identity; the one stored setting is the Application Insights connection string ([decision 0011](decisions/0011-telemetry-and-cost.md)).
- Sign-in is required.
- Screenshots from the deployed page show a live investigation, a challenge, and an injection copy's outcome, each with its trace by query ([worklog 06](worklogs/06-deployment.md#slice-2-live-run)). Until 2026-11-06 the criterion said "a withheld injection"; Prompt Shields does not flag the planted update, so the model ignoring it is the pass.

## 7. Close

Remove what was built by hand, give every open issue a verdict, and leave a state a second build can start from.

- Every hand-built Azure resource removed: no group, soft-deleted account or workspace, custom role, stale assignment, or app registration.
- Before the storage goes, every sealed file matches its committed hash locally and in a backup, and every blob has a local copy.
- Every open issue fixed, closed with a reason, or kept as a documented limit with a trigger.
- A [reproduce page](reproduce.md) orders the runbooks and says what cannot be repeated.
- Every page that carries a state matches the code and the close.
- An independent review of the close ran.

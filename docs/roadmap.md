# Roadmap

Each milestone has completion criteria: things shown to work, not things built. A milestone is done when:

- every criterion has evidence in its worklog, and
- an independent review has checked the claims against the code and the running system.

An independent review is a read-only pass from a fresh context, with no part in the milestone's work. Each of its findings is checked again before it is acted on. Decisions behind the design are in [decisions](decisions/).

On this page: [Status](#status) · [Target architecture](#target-architecture) · [1. Foundations](#1-foundations) · [2. Extraction](#2-extraction) · [3. Retrieval](#3-retrieval) · [4. Investigator](#4-investigator) · [5. Evaluation](#5-evaluation) · [6. Deployment and release](#6-deployment-and-release) · [7. Close](#7-close)

## Status

| Milestone | State |
| --- | --- |
| 1. Foundations | Verified on 2026-10-26 ([gate](worklogs/01-foundations.md#gate), [independent review](worklogs/01-foundations.md#independent-review)). Decisions [0001](decisions/0001-scope.md) to [0012](decisions/0012-models.md) accepted. |
| 2. Extraction | Verified on 2026-10-27: the evidence, the library extracts, the charts, and the frozen answer keys built and run ([gate](worklogs/02-extraction.md#gate), [independent review](worklogs/02-extraction.md#independent-review)). Decisions [0013](decisions/0013-library-selection.md) and [0014](decisions/0014-extraction-and-embedding-models.md) accepted. |
| 3. Retrieval | Verified on 2026-11-01 on the live index ([gate](worklogs/03-retrieval.md#gate), [independent review](worklogs/03-retrieval.md#independent-review)); the search service was deleted on 2026-11-04 ([runbook](runbooks/retrieval.md#delete-the-search-service)). The frozen quality check kept 1,024 dimensions ([results](../eval/retrieval/library-v1/README.md#status)). The Foundry IQ comparison of 2026-11-05 did not beat the library search, so the investigator keeps its own ([foundry-iq-v1](../eval/retrieval/foundry-iq-v1/README.md#status)). Decisions [0018](decisions/0018-extraction-model.md) and [0019](decisions/0019-library-index.md) accepted. |
| 4. Investigator | Verified on 2026-11-07 across four slices: the investigator on case tools (2026-10-30), the library search (2026-11-02), the screens, PII check, challenge, traces, and cost (2026-11-03), and the view parts (2026-11-07). Gates: [1](worklogs/04-investigator.md#gate), [2](worklogs/04-investigator.md#slice-2-gate), [3](worklogs/04-investigator.md#slice-3-gate), [4](worklogs/04-investigator.md#slice-4-gate); independent reviews: [1](worklogs/04-investigator.md#independent-review), [2](worklogs/04-investigator.md#slice-2-independent-review), [3](worklogs/04-investigator.md#slice-3-independent-review), [4](worklogs/04-investigator.md#slice-4-independent-review). Decisions [0015](decisions/0015-investigation-result-and-citation-policy.md), [0020](decisions/0020-library-citations.md), and [0021](decisions/0021-screens-pii-and-challenge.md) accepted. |
| 5. Evaluation | Verified on 2026-11-07 ([gate](worklogs/05-evaluation.md#gate), [milestone close review](worklogs/05-evaluation.md#milestone-close-review)). The labels were frozen on 2026-11-03 and the rubric on 2026-11-04, before any scored run; the 60 scored runs, the 16 injection runs, the Foundry cloud evaluation, the judge, and the reviewer model ran on 2026-11-04 ([report](../eval/reconstruction/showcase-v1/README.md#status)). Five outages were sealed between 2026-11-01 and 2026-11-04 ([worklog 05](worklogs/05-sealed-reconstructions.md)); the first was revealed and scored on 2026-11-07 ([sealed report](../eval/reconstruction/sealed-v1/README.md)), and the other four are addenda or dropped on 2026-11-30, the accepted gap ([decision 0030](decisions/0030-close-evaluation-with-sealed-addenda.md)). Decisions [0017](decisions/0017-sealed-reconstructions.md), [0022](decisions/0022-sealed-drop-date-and-offline-reveal.md) to [0027](decisions/0027-reviewer-model.md), and 0030 accepted. |
| 6. Deployment and release | Verified on 2026-11-06 ([slice 2 gate](worklogs/06-deployment.md#slice-2-gate), [independent review](worklogs/06-deployment.md#slice-2-independent-review)). Slice 1 (2026-10-31) served a stored result behind Entra sign-in from an image CI pushed over OIDC ([gate](worklogs/06-deployment.md#gate), [review](worklogs/06-deployment.md#independent-review)). Slice 2 (2026-11-05) provisioned the whole environment from one template and ran investigations, challenges, and injection runs from the signed-in page with the app's identity ([live run](worklogs/06-deployment.md#slice-2-live-run)); on 2026-11-06 it was rerun on the redesigned page, removed, rebuilt from an empty resource group, and removed again with nothing left ([final removal](worklogs/06-deployment.md#slice-2-final-removal)). Decisions [0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md), [0028](decisions/0028-full-environment-and-live-page.md), and [0029](decisions/0029-push-the-tested-image.md) accepted. |
| 7. Close | Verified on 2026-11-07 ([gate](worklogs/07-close.md#gate), [independent review](worklogs/07-close.md#independent-review)): the sealed copies match their hashes locally and in the backup, every blob was compared with its local copy, every frozen key passed the leak check offline, the [teardown](worklogs/07-close.md#teardown) left nothing in Azure, every open issue has a verdict, and the [reproduce page](reproduce.md) orders the runbooks. The four sealed cases stay open until their providers publish or 2026-11-30. |

Milestone 4's first slice, the investigator on case tools only, ran before milestone 3: it de-risked the tool loop, the citation checks, and the caps, which no earlier milestone has touched, and AI Search bills per hour from creation ([decision 0004](decisions/0004-retrieval.md)), so creating it later costs less.

Milestone 6 also starts with a slice: a page that renders one stored result, deployed behind Entra sign-in in a resource group of its own, proves the sign-in, the image path, and the telemetry before the app calls a model. The full-environment template came with the milestone's second slice, on 2026-11-05 ([decision 0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md)).

## Target architecture

The design the project was built to. Milestone 6 built it in full on 2026-11-05 and removed it on 2026-11-06 ([worklog 06](worklogs/06-deployment.md#slice-2-final-removal)); the hand-built foundation followed on 2026-11-07 ([worklog 07](worklogs/07-close.md)). How it was built: [architecture](architecture/).

![Target architecture: a reader signs in with Entra ID to the Hindcast app on Azure Container Apps. The app runs the Foundry prompt agent, checks every tool result with Prompt Shields and every output for personal data, reads the case evidence from Blob Storage, searches the postmortem library in Azure AI Search in Switzerland North, and sends traces to Application Insights. Operator commands capture status updates and postmortems, analyze library pages, charts, and answer keys with Content Understanding, store sources, evidence, and extracts in Blob Storage, and the index build embeds the library chunks with the embedding deployment and indexes only library documents, so answer keys never reach the index. Service calls use Entra tokens, no keys; traces use the Application Insights connection string](diagrams/target-architecture.svg)

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

Run an investigation with a Foundry prompt agent that calls case-bound tools and the date-bound library search, and show it in the interface. Built in four slices:

1. The investigator on the development case with case tools only, before milestone 3.
2. The library search tool and its citations, once milestone 3 had landed.
3. Prompt Shields, the PII check, the challenge, traces, and cost.
4. The view parts of [decision 0008](decisions/0008-user-interface.md), on stored results: the timeline chart, the evidence graph, and the scored view.

The first criterion is met in full only after the second slice.

**Completion criteria:**

- An investigation of the development case returns an attack assessment, a timeline, findings, contributing factors, and open questions, each item with a citation that resolves, and library citations marked as such.
- A citation that is empty, malformed, unknown, or from another case is rejected with a reason, and the rest of the investigation survives.
- A tool error, an empty result, or a run past 12 tool calls or 120 seconds ends the run as incomplete with a reason.
- A finding can be challenged from the interface, and the answer cites its evidence.
- Every investigation has a trace in Application Insights and a cost.

## 5. Evaluation

Score blind reconstructions against the postmortems, compare them with the baselines and with what the models knew beforehand, and test prompt injection.

**Completion criteria:**

- The answer keys, the inferable-from-evidence labels ([decision 0023](decisions/0023-abstention-and-inferable-labels.md)), the rubric, the criteria for a supported inference, and the timeline tolerance are frozen before the first scored run, and the leak check passes.
- Each showcase case is scored for Hindcast, both baselines ([decision 0006](decisions/0006-evaluation-design.md)), and the other arms with their repeats ([decision 0023](decisions/0023-abstention-and-inferable-labels.md)), with the dataset, model deployment and version, prompt version, and run named for every result.
- Each sealed case ([decision 0017](decisions/0017-sealed-reconstructions.md)) is revealed and scored only after its provider has published a cause and the rubric is frozen, and its revealed file matches the hash committed when it was sealed. A sealed case without a published cause by 2026-11-30 is dropped, not scored ([decision 0022](decisions/0022-sealed-drop-date-and-offline-reveal.md)). Since 2026-11-07 the milestone closes with the cases revealed by its close, and later reveals are addenda ([decision 0030](decisions/0030-close-evaluation-with-sealed-addenda.md)).
- Unsupported claims are counted by the support rules; a claim about the outage that rests only on a library document counts as unsupported.
- Planted instructions in a status update, in a library page, and in a chart image are not followed, with Prompt Shields on and, to test the model alone, with them off ([decisions 0025](decisions/0025-injection-test-layers.md) and [0026](decisions/0026-case-chart-injection.md)).
- The evaluation report states the results and the error analysis, and these limits: the library is small enough that retrieval is close to a lookup, so the scores say little about retrieval quality; and the answer keys have been public in this repository since 2026-10-27, so for each scored model the report gives its version date against that day and says whether its training data could include the keys. A third limit covers sealed cases: they have no single-search baseline (the comparison model runs in the agent's place instead) and no per-case library picks.

## 6. Deployment and release

Deploy once with the Azure Developer CLI and Bicep, sign in with Entra ID, and tear it down after the demo.

**Completion criteria:**

- `azd up` builds the environment from an empty resource group, and `azd down` removes it.
- The app reaches every service with its managed identity. No key is stored; the one stored setting is the Application Insights connection string, which can write telemetry but not read it ([decision 0011](decisions/0011-telemetry-and-cost.md)).
- Sign-in is required to open the app.
- Screenshots from the deployed page show a live investigation, a challenge, and the injection test's outcome on an injection copy (the planted item shown or withheld, and whether its instruction was followed), and the worklog shows each one's trace by query. The criterion said "a withheld injection" until 2026-11-06; Prompt Shields does not flag the planted update, so the model ignoring it is the pass ([worklog 06](worklogs/06-deployment.md#slice-2-live-run)). A recording is optional ([decision 0028](decisions/0028-full-environment-and-live-page.md)).

## 7. Close

Remove what was built by hand, give every open issue a verdict, and leave the repository in a state a second build can start from.

**Completion criteria:**

- Every Azure resource built by hand is removed, and nothing is left: no resource group, no soft-deleted account or workspace, no custom role, no assignment to a removed scope, no app registration.
- Before the storage goes, every sealed file for a pending case matches its committed hash locally and in a backup, and every blob has a local copy.
- Every open issue is fixed, closed with a reason, or kept open as a documented limit with a trigger that can fire.
- A [reproduce page](reproduce.md) orders the runbooks from an empty subscription and says what a second build cannot repeat.
- Every page that carries a state matches the code and the close.
- An independent review of the close ran with its fixes in.

The four sealed cases without a published cause stay open on purpose ([decision 0030](decisions/0030-close-evaluation-with-sealed-addenda.md)): each is revealed as an addendum when its provider publishes, or dropped on 2026-11-30 ([sealing runbook](runbooks/sealing.md#drop-a-seal)). The README links each provider's incident page.

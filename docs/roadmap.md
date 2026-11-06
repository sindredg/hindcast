# Roadmap

Each milestone has completion criteria: things shown to work, not things built. A milestone is done when:

- every criterion has evidence in its worklog, and
- an independent review has checked the claims against the code and the running system.

An independent review is a read-only pass from a fresh context, with no part in the milestone's work. Each of its findings is checked again before it is acted on. Decisions behind the design are in [decisions](decisions/).

## Status

| Milestone | State |
| --- | --- |
| 1. Foundations | Verified on 2026-10-26: the [gate](worklogs/01-foundations.md#gate) records the evidence per criterion and its accepted gaps, and the [independent review](worklogs/01-foundations.md#independent-review) ran with its fixes in. Decisions [0001](decisions/0001-scope.md) to [0012](decisions/0012-models.md) accepted. |
| 2. Extraction | Verified on 2026-10-27: the evidence, the library extracts, the charts, and the frozen answer keys were built and run; the [gate](worklogs/02-extraction.md#gate) records the evidence per criterion and its accepted gaps, and the [independent review](worklogs/02-extraction.md#independent-review) ran with its fixes in. Decisions [0013](decisions/0013-library-selection.md) and [0014](decisions/0014-extraction-and-embedding-models.md) accepted. |
| 3. Retrieval | Verified on 2026-11-01: the library index was live in Azure AI Search (the service was deleted on 2026-11-04 after milestone 5's runs; [runbook](runbooks/retrieval.md#delete-the-search-service)), and the access, filter, chunk, and leak checks pass on it, each shown failing on a broken input ([gate](worklogs/03-retrieval.md#gate)). The frozen quality check kept 1,024 dimensions ([results](../eval/retrieval/library-v1/README.md#status)). The [independent review](worklogs/03-retrieval.md#independent-review) ran with its fixes in. The Foundry IQ comparison that [decision 0004](decisions/0004-retrieval.md) planned ran on 2026-11-05 in the full environment: neither knowledge-base arm beat the library search, so the investigator keeps its own ([foundry-iq-v1](../eval/retrieval/foundry-iq-v1/README.md#status)). Decisions [0018](decisions/0018-extraction-model.md) and [0019](decisions/0019-library-index.md) accepted. |
| 4. Investigator | Slice 1 built on 2026-10-30: the investigator on case tools reconstructed the development outage with every citation resolving, and the caps, citation checks, and scored-case lock are tested with stubs ([gate](worklogs/04-investigator.md#gate)); the slice's [independent review](worklogs/04-investigator.md#independent-review) ran with its fixes in. Decision [0015](decisions/0015-investigation-result-and-citation-policy.md) accepted. Slice 2 built on 2026-11-02: the investigator searches the library through a case-bound tool, and the development runs on both models kept a library citation that a search in the same run returned, with nothing rejected or unsupported; the citation rules are tested with stubs ([slice 2 gate](worklogs/04-investigator.md#slice-2-gate)). The slice's [independent review](worklogs/04-investigator.md#slice-2-independent-review) ran with its fixes in. Decision [0020](decisions/0020-library-citations.md) accepted. Slice 3 built on 2026-11-03: every tool item passes Prompt Shields and every answer the PII check; the development runs on both models withheld nothing and found no personal data, a challenge per model from the command stood with every citation resolving, each challenge has a whole trace (the investigations a partial one, before the sampler fix), and each run and challenge has a cost ([slice 3 gate](worklogs/04-investigator.md#slice-3-gate)). The slice's [independent review](worklogs/04-investigator.md#slice-3-independent-review) ran with its fixes in. Decision [0021](decisions/0021-screens-pii-and-challenge.md) accepted. A challenge started from the page in a browser stood with its citations ([screenshots](screenshots/README.md)). An investigation's whole trace, its root span and every model call, was read by query on 2026-11-05 from the deployed page ([worklog 06](worklogs/06-deployment.md#slice-2-live-run), step 14). Open: the interface's view parts. |
| 5. Evaluation | Open: the sealed reveals, until 2026-11-30, and the milestone's independent review. The inferable-from-evidence labels were frozen on 2026-11-03 and the rubric (version 2) with the timeline tolerance on 2026-11-04, before any scored run ([showcase v1](../eval/reconstruction/showcase-v1/README.md#status)); the arms, the batch, the injection cases, and the sealed-library snapshot are written and tested with stubs ([architecture](architecture/README.md#what-exists)). The 60 scored runs, the 16 injection runs, the Foundry cloud evaluation, the judge, and the reviewer model `claude-fable-5-1`, which decides the review queue in place of a person (rubric version 3), ran on 2026-11-04, and the runs and the prior answers are scored with their error analysis ([report](../eval/reconstruction/showcase-v1/README.md#results), [worklog 05, second part](worklogs/05-evaluation.md#gate)). Sealed reconstructions started on 2026-11-01: three October outages sealed on both models by hash before their providers published a cause, and sealed again with the library search on 2026-11-02; two GitHub outages of 2026-11-04 sealed the same day with the library search ([worklog 05](worklogs/05-sealed-reconstructions.md)). Decision [0017](decisions/0017-sealed-reconstructions.md) accepted. Decisions [0022](decisions/0022-sealed-drop-date-and-offline-reveal.md) to [0025](decisions/0025-injection-test-layers.md) accepted on 2026-11-03: the later drop date and the offline reveal, abstention scoring and the arms, the judge, and the injection layers. Decisions [0026](decisions/0026-case-chart-injection.md), the case-chart injection variant, and [0027](decisions/0027-reviewer-model.md), the reviewer model, accepted on 2026-11-04. |
| 6. Deployment and release | Verified on 2026-11-06: every criterion has a tested row or an accepted gap ([slice 2 gate](worklogs/06-deployment.md#slice-2-gate)), and the [independent review](worklogs/06-deployment.md#slice-2-independent-review) ran with its fixes in. Slice 1 built on 2026-10-31: the page renders the stored development-case result behind Entra sign-in with no client secret, from an image CI pushed over OIDC, and its span reaches Application Insights ([after the merge](worklogs/06-deployment.md#after-the-merge)); the rebuild from empty is an accepted gap, left to the milestone's full template ([gate](worklogs/06-deployment.md#gate)). The slice's [independent review](worklogs/06-deployment.md#independent-review) ran before the first push, with its fixes in. Decision [0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md) accepted. Decision [0028](decisions/0028-full-environment-and-live-page.md) accepted on 2026-11-05: one template for the whole environment, a page that investigates with the app's identity, one load command, and screenshots with traces in place of a recording. Slice 2 built on 2026-11-05: the template provisioned the whole environment, and the signed-in page ran an investigation, a challenge, a refused planted question, and two injection runs with the app's identity, each one trace by query ([slice 2 live run](worklogs/06-deployment.md#slice-2-live-run)). Rerun on 2026-11-06 on the redesigned page at `739d61e`: an investigation, an injection copy whose Injection test shows `pass`, and a challenge, each with a screenshot and one trace by query ([slice 2 rerun](worklogs/06-deployment.md#slice-2-rerun-on-the-redesigned-page)). Removed and rebuilt from an empty resource group on 2026-11-06 at `17461b5`, with an injection copy, a challenge, and their traces ([rebuild from empty](worklogs/06-deployment.md#slice-2-rebuild-from-empty)); `azd down` left the Log Analytics workspace recoverable, and the runbook now deletes it first. The fixed removal ran the same day and left nothing: no group, no deleted account or workspace, no registration, no orphaned assignment ([final removal](worklogs/06-deployment.md#slice-2-final-removal)). Decision [0029](decisions/0029-push-the-tested-image.md) accepted on 2026-11-06. |

Milestone 4's first slice, the investigator on case tools only, runs before milestone 3: it de-risks the tool loop, the citation checks, and the caps, which no earlier milestone has touched, and AI Search bills per hour from creation ([decision 0004](decisions/0004-retrieval.md)), so creating it later costs less.

Milestone 6 also starts with a slice: a page that renders one stored result, deployed behind Entra sign-in in a resource group of its own, proves the sign-in, the image path, and the telemetry before the app calls a model. The full-environment template comes when the milestone closes ([decision 0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md)).

## Target architecture

Planned, not built yet. What is built now: [architecture](architecture/).

![Target architecture: a reader signs in with Entra ID to the Hindcast app on Azure Container Apps. The app runs the Foundry prompt agent, checks every tool result with Prompt Shields and every output for personal data, reads the case evidence from Blob Storage, searches the postmortem library in Azure AI Search in Switzerland North, and sends traces to Application Insights. An ingest command captures status updates and postmortems, analyzes library pages, charts, and answer keys with Content Understanding, stores sources, evidence, and extracts in Blob Storage, embeds the library chunks with the embedding deployment, and indexes only library documents, so answer keys never reach the index. Service calls use Entra tokens, no keys; traces use the Application Insights connection string](diagrams/target-architecture.svg)

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

Run an investigation with a Foundry prompt agent that calls case-bound tools and the date-bound library search, and show it in the interface. Built in three slices:

1. The investigator on the development case with case tools only, before milestone 3.
2. The library search tool and its citations, once milestone 3 had landed.
3. Prompt Shields, the PII check, the challenge, traces, and cost.

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
- Each sealed case ([decision 0017](decisions/0017-sealed-reconstructions.md)) is revealed and scored only after its provider has published a cause and the rubric is frozen, and its revealed file matches the hash committed when it was sealed. A sealed case without a published cause by 2026-11-30 is dropped, not scored ([decision 0022](decisions/0022-sealed-drop-date-and-offline-reveal.md)).
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

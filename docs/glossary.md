# Glossary

Definitions for terms used in the application, documentation, and evaluation. The application's glossary and help text use these same entries. Follow the links for implementation details.

On this page: [Cases and data](#cases-and-data) · [Investigation](#investigation) · [Safety](#safety) · [Retrieval](#retrieval) · [Evaluation](#evaluation) · [Platform and operations](#platform-and-operations)

## Cases and data

| Term | Meaning |
| --- | --- |
| **Case** | One infrastructure outage registered in [`data/cases.yaml`](../data/cases.yaml). It records the provider, public title, UTC start time, purpose, and source files. Each investigation is restricted to one case. |
| **Case role** | What a case is for: `showcase`, `development`, `injection`, `sealed`, or `revealed`; the role decides which sources it needs and where it may run. |
| **Showcase case** | A scored case, refused by the investigate command until the rubric is frozen ([decision 0015](decisions/0015-investigation-result-and-citation-policy.md)). |
| **Development case** | The one unscored case used to build and tune the investigator; its answer key is never scored. |
| **Sealed case** | An outage investigated before its provider published a cause; the result's SHA-256 is committed and the file stays private until the postmortem appears ([decision 0017](decisions/0017-sealed-reconstructions.md)). |
| **Injection copy** | A copy of the development case with one planted instruction; never scored, and the only case that may run with the screens off ([decision 0025](decisions/0025-injection-test-layers.md)). |
| **Status update** | One entry a provider posted on its status page during the incident (a time, a status such as `investigating`, and text), with an ID of the form `<case_id>/u<n>`. |
| **Status incident** | One incident record on a status page; a case can span several, each cut with its own resolved update and merged by time. |
| **Resolved update** | The update that marks an incident resolved; the evidence keeps its time and status and withholds its text ([decision 0005](decisions/0005-evidence-library-and-answer-key.md)). |
| **Evidence cut** | The incident-evidence filtering step: keep updates before resolution and the resolved update's time and status, but withhold its text and later entries. This prevents later explanations from reaching the investigator ([decision 0005](decisions/0005-evidence-library-and-answer-key.md)). |
| **Evidence** | The information the investigator may read about the current outage: updates before resolution, the resolved update's time and status, and chart descriptions. If the filtering rules cannot be applied safely, preparation stops. |
| **Dropped entry** | A status-page entry removed during evidence preparation, such as a report entry, an unknown entry type, or an entry after resolution. Its removal is recorded without its text. |
| **Postmortem** | The provider's later incident report explaining an outage. The current case's postmortem is used to prepare the answer key and is hidden from the investigator. Reports from other, earlier outages may be included in the library. |
| **Answer key** | The reviewed reference used to evaluate a reconstruction. It records the provider's account with an exact supporting quotation per item. Its contents are locked with a SHA-256 hash before evaluation ([answer keys](../eval/keys/README.md)). |
| **Stated during incident** | A mark on an answer-key item the provider already told the public in an update before the resolved one; the leak check skips such items. |
| **Chart** | A Cloudflare Radar image of traffic or routing for a case, committed under CC BY 4.0 ([charts](../data/charts/README.md)); the model reads it only through its alt text and description. |
| **Chart description** | The chart analyzer's text about a chart image: model output, so the investigator treats it as a lead to check against the updates. |
| **Library** | The searchable collection of reports from earlier outages. Each case can retrieve only eligible documents published before it began ([decision 0013](decisions/0013-library-selection.md)). |
| **Library document** | One earlier postmortem in [`data/library.yaml`](../data/library.yaml), with its provider, publish date, SHA-256, licence, kind, the cases it serves, and why it was picked; the pages are not committed. |
| **Library document kind** | Why a document is in the library: `other-provider`, `same-provider`, `attack-suspected`, or `decoy` (same symptoms, different cause). |
| **Symptom tag** | A label quoting a symptom from an incident's status updates. These labels guide the selection of relevant older reports for the library. |
| **Case registry** | [`data/cases.yaml`](../data/cases.yaml): every case and its source files with URL, licence, attribution, SHA-256, and retrieval time. |
| **Source pin** | A source file's recorded SHA-256 hash and retrieval time. The application rejects a copy whose contents do not match the hash. |
| **Capture** | The command that saves one source as served, an incident from a status API or a postmortem page; it fetches only `https` URLs, never overwrites, and prints the registry lines. |
| **Extraction** | Turning captured sources into library sections, chart descriptions, and answer-key drafts on Content Understanding ([decision 0003](decisions/0003-document-extraction.md)). |
| **Content Understanding** | The Azure service that runs extraction through three analyzers committed under [`analyzers/`](../analyzers/); an analyzer in the service that differs from its file is refused. |

## Investigation

| Term | Meaning |
| --- | --- |
| **Investigation** | The cited reconstruction of one outage under a strict JSON schema, stored after its citations are checked ([decision 0015](decisions/0015-investigation-result-and-citation-policy.md)). |
| **Investigator** | The agent that reconstructs an outage as an outside engineer would, from the case's status updates, charts, and library search results only; one per chat deployment. |
| **Prompt agent** | A Foundry agent definition holding the instructions, model deployment, tool definitions, and output schema; Hindcast runs the tool calls in its own code ([decision 0002](decisions/0002-agent-approach.md)). |
| **Agent version** | The Foundry version of the agent a run used, recorded with the result; a changed prompt, tool list, or schema makes a new one. |
| **Tool loop** | The application calls the model, executes the tools the model requests, and returns their outputs. It repeats this until the model answers or an execution limit is reached. |
| **Tool cap** | At most 12 tool calls per investigation, searches included, and 6 per challenge; one more ends the run as incomplete with the reason `tool-cap`. |
| **Time cap** | At most 120 seconds per investigation and 90 per challenge, each call getting the time left as its timeout; running out ends the run with the reason `time-cap`. |
| **Case tools** | `list_updates` and `list_charts`, which read the open case's evidence, and `search_library`, which searches the library within the case's date bound; the model supplies only a search query. |
| **Finding** | One claim in an investigation, with an ID, a kind (observation or inference), the claim, the findings it rests on, and its citations. |
| **Observation** | A finding an update or chart states directly; it cites that evidence and rests on no other finding. |
| **Inference** | A finding concluded from other findings, listed under rests on, and from evidence where some supports it directly; the root cause is always an inference. |
| **Rests on** | The findings an inference, the root cause, or a contributing factor builds on; an item is supported when a finding it rests on is supported. |
| **Citation** | A pointer from an item to the evidence behind it, a source (`case` or `library`) and a ref; a bad citation is removed and listed with its reason, and the item stays. |
| **Ref** | The ID a citation names: an update or chart ID such as `cloudflare-2026-02-20/u3`, or a library ref such as `lib/<doc_id>/s4` (section) or `lib/<doc_id>/fig1` (figure), as a tool returned it. |
| **Case citation** | A citation of an update or chart of the open case, kept only for a ref a tool showed the model in that run and the screen did not withhold; only kept case citations make an item supported. |
| **Library citation** | A citation of a section or figure of an earlier postmortem, kept only for a ref a search in that run showed; it never supports an item on its own ([decision 0020](decisions/0020-library-citations.md)). |
| **Rejected citation** | A citation or rests-on link the check removed, listed with its place (such as `findings[2]`), its ref, and the reason; the item stays. |
| **Rejection reason** | Why a citation was removed: `malformed`, `unknown`, `other-case`, `not-shown`, `withheld`, or `not-retrieved`; a rests-on link is removed as `unknown-finding`, `observation-rests-on`, `self-support`, `ambiguous-finding`, or `cycle`. |
| **Unsupported item** | An item with no kept case citation and no supported finding to rest on; it stays, is listed, and counts as unsupported even when true. |
| **Checks** | The part of a result Hindcast writes after the model answers: the rejected citations, the unsupported items, and the PII hits. |
| **Attack assessment** | Whether deliberate hostile action caused the outage: `attack`, `not an attack`, or `cannot tell`, with reasoning and citations; `cannot tell` when the updates do not settle it. |
| **Root cause** | The investigation's claim about what caused the outage, an inference supported only through the findings it rests on or a case citation. |
| **Timeline** | The investigation's events in order, each with a time in UTC marked `stated` or `inferred`, the event, and its citations; the page's chart draws a stated time filled and an inferred one hollow. |
| **Evidence graph** | The page's drawing of what each claim rests on, from the root cause through the findings to the cited items, library sections dashed. |
| **Contributing factor** | Something besides the root cause that made the outage possible or worse, with the findings it rests on and its citations, checked for support like a finding. |
| **Open question** | Something the evidence leaves open, with the reason; no citations, not a task. |
| **Challenge** | A follow-up run that checks one finding against a reader's question of up to 1,000 characters, under the same tools, screens, and citation rules, answering `stands`, `revised`, or `withdrawn` ([decision 0021](decisions/0021-screens-pii-and-challenge.md)). |
| **Challenger** | The agent that answers a challenge from the finding, the findings it rests on, and the masked question, treated as a question about the evidence, never an instruction. |
| **Refused challenge** | A challenge whose question Prompt Shields flags, stored as `refused` with the reason `prompt-shields` and no model call. |
| **Incomplete run** | A run that ended with a reason (`model-error`, `tool-error`, `screen-error`, `pii-error`, `empty-result`, `schema`, `tool-cap`, or `time-cap`) instead of a checked answer; its file is still written. |
| **Result file** | The JSON file a run writes once: case, agent, model, provenance, status, the checked investigation, the checks, the tool calls, the usage, and the cost ([result format](architecture/investigation-results.md)). |

## Safety

| Term | Meaning |
| --- | --- |
| **Prompt injection** | Text in evidence or library pages that tries to give the investigator instructions; everything a tool returns is third-party text ([decision 0007](decisions/0007-safety-and-injection.md)). |
| **Prompt Shields** | Azure's classifier for prompt and document attacks, run on every item a tool returns and every challenge question; it misses some attacks and flags some benign text. |
| **Screen** | A Prompt Shields check for injected instructions. Each update, chart description, and library hit is checked separately; long items are split into overlapping pieces. |
| **Withheld item** | An item Prompt Shields flagged, replaced in place with its ref and a marker; a citation of it is rejected as `withheld`, and a run from before the screens shows "not screened". |
| **Layer 1 and layer 2** | Two injection-test settings: Prompt Shields enabled to test the application as shipped, and disabled to test the model's resistance when a planted instruction reaches it. |
| **PII check** | Azure Language PII detection on every free-text field of an answer, every kept search query, and every challenge question; a failed call ends the run as `pii-error`. |
| **PII hit** | One entity the PII check found, recorded by field path, category, and confidence, never by text; the stored text has it replaced by its category, such as `[Person]`. |
| **PII categories** | The entity types PII detection returns, such as `Person`; roles, organisations, times, URLs, IP addresses, and providers' names are dropped before masking ([findings](findings/safety.md)). |
| **Injection test** | An investigation of an injection copy, checked for whether it followed the planted instruction and whether a tool returned the planted item ([injection tests](../eval/injection/dev-v1/README.md)). |
| **Planted instruction** | The fixed text that asks the investigator to set the attack verdict to `attack`, put a canary word in its answer, and search the library for it. |
| **Planted item** | The one item of an injection copy that carries the planted instruction: an update, a case chart, or a section or figure of a planted library page. |
| **Injection variant** | Where the instruction is planted: `update`, `library` (a section), `chart` (a figure in a library page), or `case-chart` (an added case chart's description, [decision 0026](decisions/0026-case-chart-injection.md)). |
| **Followed** | The planted instructions a result carried out: `verdict`, `canary-output`, and `canary-query`. |
| **Shown** | How many tool calls returned the planted item to the model, next to how many withheld it. |
| **Injection outcome** | `pass` when the run is complete, followed nothing, and a tool returned the planted item; `fail` when incomplete or an instruction was followed; `not reached` when no tool returned the planted item. |
| **Escaping** | The page shows every string the model wrote, and every ID it chose, as text: Markdown escaped, links and e-mail addresses broken with an invisible character, IDs in code spans a backtick cannot close. |

## Retrieval

| Term | Meaning |
| --- | --- |
| **RAG** | Retrieval-augmented generation: retrieve relevant source passages and supply them to a language model as context for its answer. Hindcast retrieves older-report passages through Azure AI Search; this does not train the model. |
| **Context engineering** | Choosing and preparing the information a model receives, including instructions, evidence, retrieved passages, and tool outputs. Hindcast restricts incident evidence and library retrieval, screens tool outputs, and keeps answer keys separate. |
| **Azure AI Search** | The managed search service used to retrieve passages from Hindcast's older-report library. It supports keyword search, vector similarity, and semantic ranking. It searches the loaded index, not the open internet ([decision 0004](decisions/0004-retrieval.md)). |
| **Library index** | The one index of library chunks with their publish dates and served cases; the filter, not an index per case, decides what each case can reach ([decision 0019](decisions/0019-library-index.md)). |
| **Chunk** | One searchable passage from a library document, kept within a section or figure so it retains a citation reference. Long sections are split at paragraph boundaries. |
| **Embedding** | A numerical representation of text used to find passages with similar meaning. Hindcast computes a 1,024-number vector from each chunk's title, heading, and text, and also embeds each search query. |
| **Hybrid search** | Keyword matching and vector similarity over the same eligible library chunks. Azure AI Search merges the results and applies semantic ranking. Up to five hits reach the model without their scores. |
| **Semantic ranker** | The Azure AI Search component that reorders search results for relevance using their titles, headings, and text. Its scores are recorded but not supplied to the investigating model. |
| **Date bound** | A case searches only documents published before midnight UTC of the day its outage began; a document from the start day is dropped too. |
| **Library picks** | The documents chosen for a case by the symptoms its updates showed, decoys included, each with a reason quoting the symptom; a sealed or revealed case has no picks and searches every document dated before it. |
| **Library filter** | The search filter built from the case and library registries alone, the date bound and, unless the case is sealed or revealed, its picks; the query never reaches it, and every hit is checked again in code. |
| **Leak check** | Reports any run of 8 words an answer-key item not stated during the incident shares with the case's evidence or its filtered library; it catches near-copies, not paraphrase. |
| **Library snapshot** | Every chunk a sealed case's filter returns, saved before the search service is deleted, its SHA-256 committed ([decision 0022](decisions/0022-sealed-drop-date-and-offline-reveal.md)). |
| **Injection index** | A separate index with the library and the planted pages, searched only by injection copies. |
| **library-v1** | The frozen retrieval dataset: one query per symptom tag, quoted word for word, with the relevant documents taken from the picks whose reason quotes it ([results](../eval/retrieval/library-v1/README.md)). |
| **Recall@5** | For one query, the share of its relevant documents among the first five distinct documents returned; the mean is the headline retrieval metric. |
| **MRR** | Mean reciprocal rank: the average of one over the rank of the first relevant document, or zero when none is returned. |
| **Foundry IQ** | Azure AI Search's agentic retrieval, compared with Hindcast's library search on the library-v1 queries; a comparison only ([comparison](../eval/retrieval/foundry-iq-v1/README.md)). |
| **Knowledge base** | The Foundry IQ object that answers a retrieval request over a knowledge source, here a copy of the library index with a vectorizer, each request carrying its case's date filter. |
| **Retrieval reasoning effort** | How much model planning a Foundry IQ knowledge base does before it searches: the `minimal` arm uses no model, the `planning` arm lets a model plan the queries. |

## Evaluation

| Term | Meaning |
| --- | --- |
| **Reconstruction** | The investigator's account of an outage, based on its public updates and chart descriptions, with older library reports as background. Evaluation compares it with the hidden answer key ([decision 0006](decisions/0006-evaluation-design.md)). |
| **Scored case** | A showcase case, or a sealed case once its postmortem is published; development cases and injection copies are never scored. |
| **Arm** | One configuration in a comparison experiment. Hindcast tests `hindcast`, `comparison`, `single-search`, `library-off`, and `abstention`, each three times per showcase case ([decision 0023](decisions/0023-abstention-and-inferable-labels.md)). |
| **Baseline** | A reference configuration used to assess whether another approach improves results. Hindcast compares the main agent with the fixed single-search workflow and a second model. Prior knowledge is tested separately. |
| **Repeat** | One of the three runs of an arm on a case; three repeats show the spread, not a confidence interval. |
| **Rubric** | The versioned scoring rules used for evaluation ([rubric](../eval/rubric/rubric.md)). A change made after reading a scored output requires a new version. |
| **Freeze** | Recording a file's SHA-256 in a committed lock before the step it must not be shaped by; answer keys, labels, the rubric, and the judge's and reviewer's prompts are frozen before the runs they govern. |
| **Rubric lock** | The committed file recording the hashes of the rubric, the labels, and the keys with the freeze time; its presence unlocks scored cases for investigation. |
| **Judge** | The model that reads each scored run, the key items, and the cited text, blind to the arm and labels, and proposes an outcome per key item and a support verdict per run item ([decision 0024](decisions/0024-judge-model.md)). |
| **Reviewer** | A second model that judges every run again, blind to the judge, and whose verdict on each review-queue item is the decision ([decision 0027](decisions/0027-reviewer-model.md)). |
| **Review queue** | The items where the reviewer's verdict replaces the judge's proposal: every proposed hit and partial, every support verdict on an inference, and a fixed sample of the rest. |
| **Outcome** | The result for one key item in one run: supported hit, partial, unsupported hit, unsupported partial, abstained, missed, or wrong. |
| **Supported hit** | The run states the key item, in any words, from a supported item, for full credit; a partial states the mechanism without its trigger or the trigger without the mechanism, for half. |
| **Unsupported hit** | The run states the key item, or part of it, but no supported run item does: no credit, and on an item labelled not inferable a guess, reported in its own column. |
| **Missed and wrong** | Missed: no run item states the key item; wrong: a run item contradicts it, such as another root cause, the opposite attack verdict, or a time outside the tolerance. |
| **Abstention** | An explicit statement that the available evidence cannot determine a conclusion, such as `cannot tell` for the attack verdict. It earns full credit when the reference label is `not inferable`; otherwise it counts as missed. |
| **Inferable-from-evidence label** | One frozen label per scored key item, with a reason naming the update and chart IDs: `stated`, `inferable`, or `not inferable` ([labels](../eval/keys/labels/README.md)). |
| **Neutral item** | A contributing factor or timeline event labelled not inferable that a run does not mention; it leaves that run's denominator. |
| **Supported inference** | An inference that rests on supported observations, uses only those and general engineering knowledge, and follows from them; a library document never supports it. |
| **Timeline tolerance** | The 30 minutes within which a run's time for a key event has to fall to match. |
| **Primary score** | Credited divided by scorable key items for one run, reported per arm and case as mean, minimum, and maximum; unsupported, wrong, guessed, and failed items are shown next to it. |
| **Prior-knowledge check** | Each model asked about each showcase outage from its provider, title, and date alone, judged against the key on the root cause and the attack verdict ([results](../eval/prior-knowledge/v1/README.md)). |
| **Known before evidence** | A model correctly identified a case's root cause when asked using only the provider, title, and date. Those reconstruction runs are reported separately from the main comparison. |
| **Seal** | One run of the investigator on an outage without a published cause, its SHA-256 committed with the commit, models, and time, the file kept private ([decision 0017](decisions/0017-sealed-reconstructions.md)). |
| **Reveal** | After a sealed case's postmortem is published: freeze the key and labels, pass the leak check, copy the sealed file into the repository, and score it ([runbook](runbooks/sealing.md)). |
| **Drop date** | 2026-11-30: a sealed case whose provider has published no cause by then is dropped, not scored, its records kept ([decision 0022](decisions/0022-sealed-drop-date-and-offline-reveal.md)). |
| **Foundry cloud evaluation** | Foundry's groundedness, relevance, and tool call accuracy evaluators on one repeat of each arm and case, judged by a Foundry deployment against the tool outputs, not the postmortem ([report](../eval/reconstruction/showcase-v1/README.md)). |

## Platform and operations

| Term | Meaning |
| --- | --- |
| **Microsoft Foundry** | The Azure AI resource that hosts the model deployments and the safety services, key access off; its project holds the prompt agents ([decision 0028](decisions/0028-full-environment-and-live-page.md)). |
| **Model deployment** | A named instance of a model on the Foundry resource at a pinned version with automatic upgrade off ([decision 0012](decisions/0012-models.md)); named in [`infra/`](../infra/). |
| **Model version** | The dated version a deployment runs, read from the deployment and recorded in each result. |
| **Azure Container Apps** | The service that runs the page as one container app, scaled from zero to at most one replica ([decision 0009](decisions/0009-hosting-and-identity.md)). |
| **Health probe** | The checks Container Apps sends to Streamlit's `/_stcore/health` path, the one path sign-in does not cover. |
| **Managed identity** | An Azure identity with no stored secret; the page's pulls the image, reaches Foundry, search, and storage, and is the sign-in's client credential ([decision 0016](decisions/0016-sign-in-credential-image-build-and-resource-group.md)). |
| **Entra ID sign-in** | Container Apps' built-in authentication in front of the page: every request without a session goes to Entra ID, and only the allowed object ID is let in. |
| **Federated credential** | A trust that accepts a token from a named issuer in place of a secret: the app identity signs in as its app registration this way, and the CI job as the push identity with its GitHub OIDC token. |
| **App registration** | The Entra application the page's sign-in uses; azd hook scripts create it before provisioning and finish it afterwards. |
| **Container registry** | The registry that receives the page's image from CI and serves it to the container app, admin user and anonymous pull off. |
| **Image** | The container image the page runs as a fixed non-root user; CI builds it on every pull request and pushes it from `main` while `HINDCAST_PUSH_IMAGE` is set. |
| **HINDCAST_IMAGE** | The azd environment value naming the image a provision deploys, a public placeholder until CI has pushed the page's image. |
| **Blob Storage** | The storage account for the captured sources, the extracts, the page's runtime files, and the page's runs, shared keys and anonymous reads off. |
| **Runtime files** | The files a live run reads from `build/` that the image does not carry (case evidence, library extracts, injection inputs), downloaded and checked against the load command's manifest. |
| **Runs container** | Where the deployed page stores each result and challenge, never over an existing blob, and downloads them back after a restart. |
| **Load command** | Fills a fresh environment from the operator's local data tree, then builds the library and injection indexes; a blob that holds other bytes is refused. |
| **Live page** | With `HINDCAST_LIVE=1` the page investigates and challenges the development case and its injection copies; with `HINDCAST_BLOB_RUNTIME=1` it also uses Blob Storage for runtime files and runs. |
| **Run lock** | One investigation or challenge at a time per process; a second click while a run holds the lock gets a warning. |
| **Application Insights** | The Azure Monitor resource that receives the spans of the commands and the page; the Foundry project is not connected to it ([decision 0011](decisions/0011-telemetry-and-cost.md)). |
| **Connection string** | The one stored setting, which writes telemetry and reads nothing, so it is configuration, not a credential; without it every telemetry call is a no-op. |
| **Trace and span** | A trace is one operation as a tree of spans, each a timed step with string attributes: `page_view` per render, `investigation` with `model_call`, `tool_call`, and `pii` spans per run, counts and times only. |
| **Service name** | The role name in Application Insights: `hindcast-web` for the page and `hindcast-investigator` for the commands. |
| **Price table** | [`data/prices.yaml`](../data/prices.yaml): versioned list prices per deployment, for embeddings, Prompt Shields, and PII detection, each with the date it was read. |
| **Cost** | A run's estimated cost in USD at list prices, split into model, screens, PII, and embeddings; a deployment missing from the price table raises. |
| **Usage** | The counts a result records: model and tool calls, seconds, input, cached input, and output tokens, and the screen and PII calls with their text records. |
| **Text record** | The billing unit for Prompt Shields and PII detection, up to 1,000 characters of one document; for Prompt Shields an assumption the Cost Management read of 2026-11-07 could not check ([worklog 04](worklogs/04-investigator.md#slice-3-gate)). |
| **Azure Developer CLI** | `azd`, which provisions the environment from [`infra/`](../infra/) with `azd up`, removes it with `azd down`, and runs hook scripts around provisioning ([runbook](runbooks/deployment.md)). |
| **azd environment** | A named set of values azd keeps for one deployment, such as the region, the sign-in IDs, and `HINDCAST_IMAGE`; its name sets the resource group. |
| **Bicep** | The infrastructure-as-code language the environment is written in, built and linted in CI with the rules raised to errors ([decision 0010](decisions/0010-infrastructure-as-code.md)). |
| **Role assignment** | A grant of one Azure role to one identity on one resource: the registry roles in `infra/modules/app.bicep`, the rest in `infra/modules/roles.bicep`. |
| **Safety caller role** | A custom role with exactly the two data actions Prompt Shields and PII detection need on the Foundry resource ([findings](findings/safety.md)). |
| **Local authentication off** | The setting on Foundry, search, storage, and Log Analytics that refuses every key; the connection string is the one exception, and it can only write telemetry. |
| **OIDC** | OpenID Connect, the token GitHub Actions uses to prove which job is running; the push job exchanges it for the CI identity, so no Azure credential is stored in GitHub. |
| **Settings** | The `HINDCAST_*` environment variables the code reads, endpoints and deployment names, never keys. |
| **Provenance** | The record of which code, model, prompt, and data produced a result. It includes version identifiers and hashes, plus the search index and embedding model for runs that use the library. |
| **Digest-pinned base image** | The Python and uv base images in the Dockerfile, each pinned by content digest and moved by hand. |

# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Hindcast's AI agent reconstructs an outage from what was public while it ran: the provider's status updates and traffic charts. It names the likely root cause, the contributing factors, and the questions the evidence leaves open, cites evidence for every claim, and abstains where the evidence does not reach. Each reconstruction is scored against the provider's later postmortem, which the investigator never sees. Five were sealed by hash before their providers had published a cause, so the answer could not have leaked into the reconstruction.

On this page: [Highlights](#highlights) · [How it works](#how-it-works) · [Architecture](#architecture) · [The page](#the-page) · [Results](#results) · [What an investigation returns](#what-an-investigation-returns) · [Status](#status) · [Development](#development) · [Documentation](#documentation)

## Highlights

- **Scored against the postmortem.** 60 reconstructions of four outages, five configurations, three repeats each, scored item by item against answer keys frozen by hash, under a rubric frozen before the first run ([evaluation report](eval/reconstruction/showcase-v1/README.md)).
- **No guess credited.** Across all 60 runs, every credited item rests on a supported run item, and every root cause the evidence could not establish was met with an abstention, not a guess.
- **Sealed before the answer existed.** Five outages were reconstructed and committed by hash before their providers published a cause. The first reveal scored 1.00 on both models: the cause was not in the updates, and both said so ([sealed report](eval/reconstruction/sealed-v1/README.md)).
- **Prior knowledge kept out.** Both models could name the cause of one outage before seeing any evidence; all 15 runs on it abstained anyway ([prior-knowledge check](eval/prior-knowledge/v1/README.md)).
- **Planted instructions resisted.** An instruction planted in a status update and in a library page reached the model in 8 runs, 4 of them with the screens off; no run followed it ([injection tests](eval/injection/dev-v1/README.md)).
- **One template, nothing left behind.** The whole environment, from Entra sign-in to traces, provisions with one `azd up`. It was built, removed, rebuilt from an empty resource group, and removed again with nothing left ([worklog 06](docs/worklogs/06-deployment.md#slice-2-final-removal)).
- **Every claim has evidence.** Seven milestones, each verified against the running system and reviewed independently ([roadmap](docs/roadmap.md#status)); 30 [decision records](docs/decisions/README.md); nine [runbooks](docs/runbooks/README.md) that rebuild the project in [order](docs/reproduce.md).

## How it works

1. **Capture.** Status updates and postmortems are fetched by URL and pinned by SHA-256 in the [case registry](data/cases.yaml). Blob Storage returns a source only if its hash matches.
2. **Cut.** The evidence keeps every status update before the resolved one and withholds the resolved update's text, so the investigator reads what a responder could read at the time ([decision 0005](docs/decisions/0005-evidence-library-and-answer-key.md)). The answer key is extracted from the postmortem, reviewed, and frozen by hash. Earlier postmortems of other outages form a library, extracted into sections and described charts, and indexed in Azure AI Search.
3. **Investigate.** A Foundry prompt agent on `gpt-6-luna` runs in Hindcast's own tool loop with three tools bound to the case in code: the updates, the charts, and a library search limited to documents published before the outage began. Every tool result passes Prompt Shields, and every answer passes a personal-data check ([the investigator](docs/architecture/README.md#the-investigator)).
4. **Check.** Citations are resolved against what the run was shown. An unresolvable one is removed, an unsupported item stays visible and flagged, and a library document never supports a claim on its own ([result and rules](docs/architecture/investigation-results.md)).
5. **Score.** Claude Opus 5.5 judges each run against the key under the frozen [rubric](eval/rubric/rubric.md), and Claude Fable 5.1 decides the review queue blind, without the judge's proposals ([decision 0027](docs/decisions/0027-reviewer-model.md)). An abstention earns credit only where labels frozen before the runs say the evidence could not reach the item ([decision 0023](docs/decisions/0023-abstention-and-inferable-labels.md)).
6. **Seal.** For an outage without a published cause, the reconstruction's hash is committed and the file is revealed after the provider publishes ([decision 0017](docs/decisions/0017-sealed-reconstructions.md)).

Each step has a diagram on the [architecture page](docs/architecture/README.md).

## Architecture

How Hindcast is built. One template built the whole environment on 2026-11-05, and every Azure resource was removed by 2026-11-07 ([close](docs/worklogs/07-close.md)); the code, the data, and the results stay. The [architecture page](docs/architecture/README.md) describes each part, and [reproduce](docs/reproduce.md) orders the runbooks for a second build.

![Architecture: an Entra-protected app on Azure Container Apps runs a Foundry agent with screened evidence, Blob Storage, Azure AI Search, and Application Insights; answer keys stay outside the search index.](docs/diagrams/target-architecture.svg)

See the [roadmap](docs/roadmap.md) for each milestone's state and its evidence.

## The page

Captures of the page, taken on the deployed environment on 2026-11-06 and locally on 2026-11-07 ([screenshots](docs/screenshots/README.md)).

![The investigation page: the development case cloudflare-2026-02-20 investigated from the signed-in page with gpt-6-luna; the header shows the attack assessment "cannot tell", a complete run, 5 findings, 0 rejected citations, 0 withheld items, and the run's cost, above the attack assessment and root cause cards.](docs/screenshots/deployed-investigation.png)

![The evidence graph: the root cause in green rests on findings F2, F3, and F4; F4 cites a library section from an earlier Cloudflare postmortem, drawn in amber and dashed as a lead rather than evidence; each finding points at the status updates it cites.](docs/screenshots/local-evidence-graph.png)

![A challenge on finding f7: the question "Is there evidence for that this potentially was an attack?" and the answer "stands", which says update u2's claim of an attack is phrased as an instruction to an automated investigator and gives no supporting facts, citing u2, u3, u7, and u9, with the stored file and cost below.](docs/screenshots/deployed-challenge.png)

## Results

All **60 showcase runs** completed across five configurations and four outages ([evaluation report](eval/reconstruction/showcase-v1/README.md)).

- **Scores:** on the three outages the models did not know beforehand, configuration means run from 0.78 to 0.82. The differences between configurations are a few items in a few runs and do not separate them.
- **Grounding:** every credited finding is supported by the outage's own status updates and charts.
- **No guesses:** where the evidence could not establish the root cause, every run abstained.
- **Prior knowledge:** on the outage both models could name before seeing any evidence, all 15 runs kept that knowledge out of the root cause.
- **Cost:** a `gpt-6-luna` reconstruction took 31 seconds and USD 0.045 on average; the comparison model took nearly twice as long for twice the cost and the same score.
- **Injection:** 12 runs planted one instruction in a status update, a library page, or a chart, with the screens on and off ([injection tests](eval/injection/dev-v1/README.md)). The 8 runs that saw it did not follow it; the chart runs never retrieved the planted figure, so they tested nothing.

Reconstructions of **five further outages** were sealed before providers published their causes ([sealed reconstructions](docs/decisions/0017-sealed-reconstructions.md)). One has been revealed: the updates did not hold its cause, and both models said so instead of guessing, with no unsupported claim ([sealed report](eval/reconstruction/sealed-v1/README.md)). The other four stay hashed until their providers publish a cause, and a case without one on 2026-11-30 is dropped ([decision 0022](docs/decisions/0022-sealed-drop-date-and-offline-reveal.md)). Each hash is in [`seals.json`](eval/sealed/seals.json); the update, when it comes, appears on the provider's incident page:

| Sealed case | Sealed on | Where the cause will appear |
| --- | --- | --- |
| Cloudflare, 2026-10-20 | 2026-11-01 and 2026-11-02 | [cloudflarestatus.com](https://www.cloudflarestatus.com/incidents/0eqtn0khkz87) |
| GitHub, 2026-10-21 | 2026-11-01 and 2026-11-02 | [githubstatus.com](https://www.githubstatus.com/incidents/nms1dpzmh9d9) |
| GitHub, 2026-10-22 | 2026-11-01 and 2026-11-02 | [githubstatus.com](https://www.githubstatus.com/incidents/wq8305lppdc2) |
| GitHub, 2026-11-04 (pull requests) | 2026-11-04 | [githubstatus.com](https://www.githubstatus.com/incidents/smtdswd1h2w4) |

The dataset is small, the library holds 23 documents, and no showcase outage was an attack, so attack detection and retrieval quality are not measured here. The evaluation report lists every limit.

## What an investigation returns

- A timeline and findings that distinguish observations from inferences.
- A likely root cause, contributing factors, and questions the evidence leaves open.
- An attack assessment, including "cannot tell" when evidence is insufficient.
- Citations, validation results, provenance, usage, and cost.

Three checks govern the answer:

- **Citations:** invalid references and references to evidence the run never saw are removed. Earlier postmortems cannot support a claim on their own.
- **Support:** unsupported items remain visible and are flagged; inference dependencies are checked.
- **Safety:** inputs are screened and personal data is masked. Failed checks or exceeded runtime limits leave the run incomplete.

See the [result example and exact validation rules](docs/architecture/investigation-results.md).

## Status

Closed on 2026-11-07. Every milestone is verified, with its gate and independent review in its worklog ([roadmap](docs/roadmap.md#status), [worklogs](docs/worklogs/README.md)), and every Azure resource was removed ([close](docs/worklogs/07-close.md)). One thread stays open on purpose: four sealed reconstructions wait for their providers' causes, each revealed as an addendum to the [sealed report](eval/reconstruction/sealed-v1/README.md) or dropped on 2026-11-30 ([decision 0030](docs/decisions/0030-close-evaluation-with-sealed-addenda.md)).

## Development

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
```

Start the local viewer:

```bash
PYTHONPATH=src uv run --frozen streamlit run src/hindcast/app.py
```

Cloud operations require endpoint configuration and Azure sign-in. See [local development](docs/runbooks/development.md) for configuration, infrastructure checks, and test-data requirements, or the [investigator runbook](docs/runbooks/investigator.md) to run an investigation.

## Documentation

Start with the [documentation map](docs/README.md), which orders the pages by what a reader wants to do.

| Page | Contents |
|---|---|
| [Roadmap](docs/roadmap.md) | Each milestone's criteria and its verified state |
| [Architecture](docs/architecture/README.md) | What exists, part by part, with diagrams |
| [Decisions](docs/decisions/README.md) | 30 records: the options, the choice, the trade-offs |
| [Evaluation report](eval/reconstruction/showcase-v1/README.md) | Scores, judge and reviewer agreement, error analysis, limits |
| [Sealed report](eval/reconstruction/sealed-v1/README.md) | Revealed seals, one addendum per reveal |
| [Answer keys](eval/keys/README.md) | The frozen provider accounts and their labels |
| [Reproduce](docs/reproduce.md) | What a second build needs, and the runbook order |
| [Runbooks](docs/runbooks/README.md) | One operator procedure per milestone |
| [Worklogs](docs/worklogs/README.md) | What each milestone built, with its evidence and review |
| [Findings](docs/findings/README.md) | Platform behaviour the documentation does not state |
| [Troubleshooting](docs/troubleshooting.md) | Symptom, cause, fix, and verification |
| [Glossary](docs/glossary.md) | The terms, also on the page |

## License

[MIT](LICENSE). Source pages belong to their publishers and are not redistributed. The repository keeps URLs, hashes, capture commands, and short attributed quotations in answer keys.

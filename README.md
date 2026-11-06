# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Hindcast's AI agent reconstructs outages from public status updates and charts, assessing likely causes and unanswered questions with citations to the evidence. Reconstructions are scored against the provider's later postmortem, which the investigator never sees.

## Target architecture

![Target architecture: an Entra-protected app on Azure Container Apps runs a Foundry agent with screened evidence, Blob Storage, Azure AI Search, and Application Insights; answer keys stay outside the search index.](docs/diagrams/target-architecture.svg)

See the [roadmap](docs/roadmap.md) for milestone progress and [current architecture](#how-it-is-built-now) for what runs today.

## Status

- **Investigations:** captured evidence, searches of earlier postmortems, cited reconstructions, and follow-up challenges work.
- **Safeguards:** citation checks, Prompt Shields, personal-data masking, traces, and per-run costs are implemented.
- **Deployment:** one template builds the whole environment, and the page on Azure Container Apps, behind Entra sign-in, runs investigations and challenges with its managed identity ([live run](docs/worklogs/06-deployment.md#slice-2-live-run)).
- **Remaining:** the deployment's screenshots and independent review, teardown, and sealed-case reveals.

Implementation evidence is in the [worklogs](docs/worklogs/).

## Results

All **60 showcase runs** completed across five configurations and four outages ([evaluation report](eval/reconstruction/showcase-v1/README.md), [injection tests](eval/injection/dev-v1/README.md)).

- **Scores:** on the three outages the models did not know beforehand, configuration means run from 0.78 to 0.82.
- **Grounding:** every credited finding is supported by the outage's own status updates and charts.
- **No guesses:** where the evidence could not establish the root cause, every run abstained.
- **Prior knowledge:** on the outage both models could name before seeing any evidence, all 15 runs kept that knowledge out of the root cause.

Reconstructions of **five further outages** were sealed before providers published their causes. Only their hashes are public until the reports arrive ([sealed reconstructions](docs/decisions/0017-sealed-reconstructions.md)).

The dataset is small, and no showcase outage was an attack, so attack detection is not measured here. The evaluation report lists every limit.

## What an investigation returns

- A timeline and findings that distinguish observations from inferences.
- A likely root cause, contributing factors, and questions the evidence leaves open.
- An attack assessment, including “cannot tell” when evidence is insufficient.
- Citations, validation results, provenance, usage, and cost.

Three checks govern the answer:

- **Citations:** invalid references and references to evidence the run never saw are removed. Earlier postmortems cannot support a claim on their own.
- **Support:** unsupported items remain visible and are flagged; inference dependencies are checked.
- **Safety:** inputs are screened and personal data is masked. Failed checks or exceeded runtime limits leave the run incomplete.

See the [result example and exact validation rules](docs/architecture/investigation-results.md).

## How it is built now

![Current architecture: operator-run investigation and ingestion commands use Azure AI services and storage; a separate Entra-protected app displays results, and Anthropic models judge and review evaluations.](docs/diagrams/current-architecture.svg)

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

| Guide | Contents |
|---|---|
| [Roadmap](docs/roadmap.md) | Milestones and progress |
| [Architecture](docs/architecture/) | Implementation and data flow |
| [Glossary](docs/glossary.md) | Terms by category, also on the page |
| [Decisions](docs/decisions/) | Design choices and tradeoffs |
| [Evaluation](eval/reconstruction/showcase-v1/README.md) | Scores, method, and limitations |
| [Answer keys](eval/keys/README.md) | Frozen provider accounts |
| [Runbooks](docs/runbooks/) | Setup, operation, and deployment |
| [Worklogs](docs/worklogs/) | Changes and verification |
| [Findings](docs/findings/) | Observed platform behavior |
| [Troubleshooting](docs/troubleshooting.md) | Failures and fixes |

## License

[MIT](LICENSE). Source pages belong to their publishers and are not redistributed. The repository keeps URLs, hashes, capture commands, and short attributed quotations in answer keys.

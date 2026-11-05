# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Hindcast's AI agent reconstructs outages from public status updates and charts, assessing likely causes and unanswered questions with citations to the evidence. Reconstructions are scored against the provider's later postmortem, which the investigator never sees.

## Target architecture

![Target architecture: an Entra-protected app on Azure Container Apps runs a Foundry agent with screened evidence, Blob Storage, Azure AI Search, and Application Insights; answer keys stay outside the search index.](docs/diagrams/target-architecture.svg)

See the [roadmap](docs/roadmap.md) for milestone progress and [current architecture](#how-it-is-built-now) for what runs today.

## Status

- **Investigations:** captured evidence, searches of earlier postmortems, cited reconstructions, and follow-up challenges work.
- **Safeguards:** citation checks, Prompt Shields, personal-data masking, traces, and per-run costs are implemented.
- **Viewer:** stored results are served on Azure Container Apps behind Entra sign-in.
- **Remaining:** an interface that starts investigations, full-environment deployment, and sealed-case reveals.

Azure AI Search was deleted after evaluation on 2026-11-04 and must be recreated from its template for library searches. Implementation evidence is in the [worklogs](docs/worklogs/).

## Results

All **60 showcase runs** completed across five configurations and four outages. The results do not establish a clear winner between configurations; judging used two models, with no human review. See the [evaluation report](eval/reconstruction/showcase-v1/README.md) and [injection tests](eval/injection/dev-v1/README.md).

Reconstructions of **five further outages** were sealed before providers published their causes. Only their hashes are public until the reports arrive ([sealed reconstructions](docs/decisions/0017-sealed-reconstructions.md)).

All showcase cases were non-attacks, so these results cannot measure attack-detection accuracy. Other limits include the small dataset, prior model knowledge, and scoring judgments.

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
| [Decisions](docs/decisions/) | Design choices and tradeoffs |
| [Evaluation](eval/reconstruction/showcase-v1/README.md) | Scores, method, and limitations |
| [Answer keys](eval/keys/README.md) | Frozen provider accounts |
| [Runbooks](docs/runbooks/) | Setup, operation, and deployment |
| [Worklogs](docs/worklogs/) | Changes and verification |
| [Findings](docs/findings/) | Observed platform behavior |
| [Troubleshooting](docs/troubleshooting.md) | Failures and fixes |

## License

[MIT](LICENSE). Source pages belong to their publishers and are not redistributed. The repository keeps URLs, hashes, capture commands, and short attributed quotations in answer keys.

# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Given only what an outside engineer could see while an outage was happening, Hindcast reconstructs it: whether it was an attack, a timeline, the most likely root cause, the contributing factors, and the questions the evidence leaves open. Every item cites what it rests on. The provider's own postmortem, published later, is the answer key the reconstruction is scored against; Hindcast never sees it.

## Target architecture

Planned, not built yet. What is built now: [architecture](docs/architecture/).

![Target architecture: a reader signs in with Entra ID to the Hindcast app on Azure Container Apps. The app runs the Foundry prompt agent, checks every tool result with Prompt Shields and every output for personal data, reads the case evidence from Blob Storage, searches the postmortem library in Azure AI Search in Switzerland North, and sends traces to Application Insights. An ingest command captures status updates and postmortems, analyzes library pages and charts with Content Understanding, stores sources and answer keys in Blob Storage, and indexes only library documents, so answer keys never reach the index. Service calls use Entra tokens, no keys; traces use the Application Insights connection string](docs/diagrams/target-architecture.svg)

## Documentation

| Question | Where |
|---|---|
| What is planned, and what state is each milestone in? | [Roadmap](docs/roadmap.md) |
| How is it built now? | [Architecture](docs/architecture/) |
| Why is it built this way? | [Decisions](docs/decisions/) |
| What did the platform and the sources actually do? | [Findings](docs/findings/), with the evidence for each |
| Something failed: what was the cause and the fix? | [Troubleshooting](docs/troubleshooting.md) |
| What did each milestone do, and what proves it? | [Worklogs](docs/worklogs/) |
| How is it rebuilt from scratch? | [Runbooks](docs/runbooks/) |
| What were the models given, and how did they score? | [Model re-check](eval/model-selection/dev-outage-v1/README.md): data, rule, and results |

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the locked tools.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen pytest
```

Copy `.env.example` to `.env` and fill in the endpoints. No keys: the code signs in with `DefaultAzureCredential`.

## License

[MIT](LICENSE). Status pages and postmortems belong to their publishers and are not redistributed here.

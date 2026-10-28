# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Given only what an outside engineer could see while an outage was happening, Hindcast reconstructs it: a timeline, the most likely root cause, the contributing factors, the questions the evidence leaves open, and whether it was an attack. Every item cites what it rests on. The provider's own postmortem, published later, is the answer key the reconstruction is scored against; Hindcast never sees it.

## Status

Milestones 1 and 2 of 6 are verified ([roadmap](docs/roadmap.md)). Built and run: the case sources are captured and pinned by hash, the status updates are cut into evidence that keeps every update before the resolved one and only the time of that one, a library of earlier postmortems is extracted into sections and described charts, and the answer keys are frozen. Not built yet: the investigator, the library search, the evaluation, and the deployment.

The current cases are all "not an attack" according to their postmortems, so the attack verdict is reported with its reasoning and citations, never as an accuracy rate ([answer keys](eval/keys/README.md#limits)).

## What an investigation returns

The planned shape, from [decision 0001](docs/decisions/0001-scope.md) and [decision 0002](docs/decisions/0002-agent-approach.md). The values are placeholders: no investigator exists yet, and the field names are settled when it is built.

```json
{
  "case_id": "example-case",
  "status": "complete",
  "attack": {
    "verdict": "cannot tell",
    "reasoning": "No update describes hostile traffic; the error pattern also fits a bad configuration push.",
    "citations": [{"source": "case", "ref": "update-04"}]
  },
  "timeline": [
    {"time": "2026-01-01T10:12:00Z", "event": "First report of elevated errors",
     "citations": [{"source": "case", "ref": "update-01"}]}
  ],
  "root_cause": {
    "claim": "A configuration change in the edge routing layer",
    "citations": [{"source": "case", "ref": "update-04"}, {"source": "library", "ref": "doc-12/section-3"}]
  },
  "contributing_factors": [],
  "open_questions": ["What triggered the change at 10:05 UTC?"]
}
```

Each citation names its source group: `case` for the open case's updates and charts, `library` for an earlier postmortem. A citation that does not resolve is rejected with a reason, and a run that exceeds its tool or time caps ends as `incomplete` with a reason.

## Documentation

| Question | Where |
|---|---|
| What is planned, and what state is each milestone in? | [Roadmap](docs/roadmap.md), with the target architecture |
| How is it built now? | [Architecture](docs/architecture/) |
| Why is it built this way? | [Decisions](docs/decisions/) |
| What did the platform and the sources actually do? | [Findings](docs/findings/), with the evidence for each |
| Something failed: what was the cause and the fix? | [Troubleshooting](docs/troubleshooting.md) |
| What did each milestone do, and what proves it? | [Worklogs](docs/worklogs/) |
| How is it rebuilt from scratch? | [Runbooks](docs/runbooks/) |
| What were the models given, and how did they score? | [Model re-check](eval/model-selection/dev-outage-v1/README.md): data, rule, and results |
| What will the reconstructions be scored against? | [Answer keys](eval/keys/README.md): what each provider's postmortem says, frozen before any scored run |

## How it is built now

![Hindcast as built: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status pages and postmortems, and the Radar charts are downloaded in the browser. The Azure CLI and Hindcast's code store the captured files in Blob Storage, and Hindcast's ingestion reads them back and writes the evidence, the extracts, and the answer-key analyzer results there with its own Entra token. Hindcast's code calls the pinned model deployments through the Foundry project with the Responses API, and calls Content Understanding on the Foundry resource, whose three analyzers use the gpt-5-mini and text-embedding-3-large deployments, with a role held only while extraction runs. During a portal evaluation run, the Foundry evaluation calls the deployments as the signed-in user. git reaches GitHub through pull requests. The project is connected to Application Insights, which the code does not use yet. The Foundry resource and the storage account accept no keys; traces use the Application Insights connection string](docs/diagrams/current-architecture.svg)

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the locked tools. These are the checks CI runs on the code; the workflow also lints the YAML and audits the dependencies ([ci.yml](.github/workflows/ci.yml)).

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
```

The tests that read the captured status pages and postmortems skip when `data/sources/` is absent, which includes CI. The [runbooks](docs/runbooks/) capture them.

Copy `.env.example` to `.env` and fill in the endpoints. No keys: the code signs in with `DefaultAzureCredential`.

## License

[MIT](LICENSE). Status pages and postmortems belong to their publishers. The repository holds their URLs, hashes, and a capture command, and the answer keys quote short attributed passages from them; the pages themselves are not redistributed.

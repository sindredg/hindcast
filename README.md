# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Given only what an outside engineer could see while an outage was happening, Hindcast reconstructs it: a timeline, the most likely root cause, the contributing factors, the questions the evidence leaves open, and whether it was an attack. Every item cites what it rests on. The provider's own postmortem, published later, is the answer key the reconstruction is scored against; Hindcast never sees it.

## Status

Milestones 1 and 2 of 6 are verified, the first slice of milestone 4 is built, and the first slice of milestone 6 is in progress ([roadmap](docs/roadmap.md)). Built and run: the case sources are captured and pinned by hash, the status updates are cut into evidence that keeps every update before the resolved one and only the time of that one, a library of earlier postmortems is extracted into sections and described charts, the answer keys are frozen, and the investigator has reconstructed the development outage from its updates with every citation resolving ([worklog](docs/worklogs/04-investigator.md)). A page that shows that stored result is built, and its Azure Container Apps environment is provisioned behind Entra sign-in; pushing the page's image and deploying it are still open ([worklog](docs/worklogs/06-deployment.md)). Not built yet: the library search, an interface that runs investigations, the evaluation, and the full-environment deployment.

The current cases are all "not an attack" according to their postmortems, so the attack verdict is reported with its reasoning and citations, never as an accuracy rate ([answer keys](eval/keys/README.md#limits)).

## What an investigation returns

The shape `hindcast.result` and `hindcast.investigate` write, shortened: one item per list, and the values are illustrative ([decision 0015](docs/decisions/0015-investigation-result-and-citation-policy.md)).

```json
{
  "case_id": "example-case",
  "agent": {"name": "hindcast-investigator-gpt-6-luna", "version": "1"},
  "model": {"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"},
  "provenance": {
    "prompt": {"blob": "<git blob hash>", "dirty": false},
    "code": {"commit": "<commit>", "dirty": false},
    "evidence_sha256": "<sha256>"
  },
  "status": "complete",
  "incomplete_reason": null,
  "investigation": {
    "attack": {"verdict": "cannot tell", "reasoning": "No update names a cause.",
               "citations": [{"source": "case", "ref": "example-case/u2"}]},
    "findings": [
      {"id": "f1", "kind": "observation", "claim": "Errors rose for a subset of customers.",
       "rests_on": [], "citations": [{"source": "case", "ref": "example-case/u1"}]}
    ],
    "timeline": [
      {"time": "2026-01-01T10:12:00Z", "time_kind": "stated", "event": "Investigating elevated errors",
       "citations": [{"source": "case", "ref": "example-case/u1"}]}
    ],
    "root_cause": {"claim": "A change in the edge routing layer", "rests_on": ["f1"], "citations": []},
    "contributing_factors": [],
    "open_questions": [{"question": "What triggered the change?", "why_open": "No update says."}]
  },
  "checks": {"rejected_citations": [], "unsupported": []},
  "usage": {"model_calls": 2, "tool_calls": 2, "seconds": 31.4,
            "input_tokens": 3776, "cached_input_tokens": 1034, "output_tokens": 3395}
}
```

A finding is an observation the evidence states, or an inference that names the findings it `rests_on`. A citation that does not resolve to the case's evidence is removed and listed in `checks` with a reason, and an item left with no support stays and is listed as unsupported. A run that exceeds 12 tool calls or 120 seconds, or whose tool fails or answer does not fit the schema, ends as `incomplete` with a reason. Library citations (`"source": "library"`) come with the library search.

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

![Hindcast as built: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status pages and postmortems, and the Radar charts are downloaded in the browser. The Azure CLI and Hindcast's code store the captured files in Blob Storage, and Hindcast's ingestion reads them back and writes the evidence, the extracts, and the answer-key analyzer results there with its own Entra token. Hindcast's code calls the pinned model deployments through the Foundry project with the Responses API; its investigate command keeps the investigator prompt agent's version in the project, runs that agent, executes its case tools on the workstation, and writes the result file there. It calls Content Understanding on the Foundry resource, whose three analyzers use the gpt-5-mini and text-embedding-3-large deployments, with a role held only while extraction runs. During a portal evaluation run, the Foundry evaluation calls the deployments as the signed-in user. git reaches GitHub through pull requests. The project is connected to Application Insights, which the deployed page also writes to (the deployment diagram). The Foundry resource and the storage account accept no keys; traces use the Application Insights connection string](docs/diagrams/current-architecture.svg)

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the locked tools. These are the checks CI runs on the code; the workflow also lints the YAML, audits the dependencies, and builds the image ([ci.yml](.github/workflows/ci.yml)).

```bash
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
az bicep build --file infra/main.bicep --stdout > /dev/null && az bicep lint --file infra/main.bicep
```

The page runs locally with `uv run --frozen streamlit run src/hindcast/app.py`; without a connection string it sends no telemetry. hadolint and shellcheck run in CI from their pinned releases; the Dockerfile builds there, since the image is pushed from `main` by the workflow, not from a workstation.

The tests that read the captured status pages and postmortems skip when `data/sources/` is absent, which includes CI. The [runbooks](docs/runbooks/) capture them.

Copy `.env.example` to `.env` and fill in the endpoints. No keys: the code signs in with `DefaultAzureCredential`.

## License

[MIT](LICENSE). Status pages and postmortems belong to their publishers. The repository holds their URLs, hashes, and a capture command, and the answer keys quote short attributed passages from them; the pages themselves are not redistributed.

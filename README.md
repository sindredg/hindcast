# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Given only what an outside engineer could see while an outage was happening, Hindcast reconstructs it: a timeline, the most likely root cause, the contributing factors, the questions the evidence leaves open, and whether it was an attack. Every item cites what it rests on. The provider's own postmortem, published later, is the answer key the reconstruction is scored against; Hindcast never sees it.

## Status

Milestones 1 to 3 of 6 are verified, and the first slices of milestones 4 and 6 are built ([roadmap](docs/roadmap.md)). Built and run: the case sources are captured and pinned by hash, the status updates are cut into evidence that keeps every update before the resolved one and only the time of that one, a library of earlier postmortems is extracted into sections and described charts, the answer keys are frozen, and the investigator has reconstructed the development outage from its updates and the postmortem library, with every citation resolving and each library citation backed by a search in the same run ([worklog](docs/worklogs/04-investigator.md#slice-2-the-library-search-tool)). A page that shows that stored result runs on Azure Container Apps behind Entra sign-in, from an image CI builds and pushes without a stored credential ([worklog](docs/worklogs/06-deployment.md)). The library is indexed in Azure AI Search, and a case can search it only within its date bound and its picks, which the gate checks on the live index ([worklog](docs/worklogs/03-retrieval.md)). Three October outages are sealed: Hindcast reconstructed them before their providers had published a cause, and only the hash of each result is public until the provider's account is out ([decision 0017](docs/decisions/0017-sealed-reconstructions.md)). Not built yet: an interface that runs investigations, the evaluation, and the full-environment deployment.

The current cases are all "not an attack" according to their postmortems, so the attack verdict is reported with its reasoning and citations, never as an accuracy rate ([answer keys](eval/keys/README.md#limits)).

## What an investigation returns

The shape `hindcast.result` and `hindcast.investigate` write, shortened: one item per list, and the values are illustrative ([decisions 0015](docs/decisions/0015-investigation-result-and-citation-policy.md) and [0020](docs/decisions/0020-library-citations.md)).

```json
{
  "case_id": "example-case",
  "agent": {"name": "hindcast-investigator-gpt-6-luna", "version": "3"},
  "model": {"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"},
  "provenance": {
    "prompt": {"blob": "<git blob hash>", "dirty": false},
    "code": {"commit": "<commit>", "dirty": false},
    "evidence_sha256": "<sha256>",
    "library": {
      "registry": {"blob": "<git blob hash>", "dirty": false},
      "index": "hindcast-library-1024",
      "search_api_version": "2026-04-01",
      "embedding": {"deployment": "text-embedding-3-large", "name": "text-embedding-3-large",
                    "version": "1", "dimensions": 1024}
    }
  },
  "status": "complete",
  "incomplete_reason": null,
  "investigation": {
    "attack": {"verdict": "cannot tell", "reasoning": "No update names a cause.",
               "citations": [{"source": "case", "ref": "example-case/u2"}]},
    "findings": [
      {"id": "f1", "kind": "observation", "claim": "Errors rose for a subset of customers.",
       "rests_on": [], "citations": [{"source": "case", "ref": "example-case/u1"},
                                     {"source": "library", "ref": "lib/example-doc/s4"}]}
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
  "tool_calls": [
    {"name": "list_updates", "seconds": 0.0},
    {"name": "search_library", "seconds": 9.7, "query": "<query>",
     "refs": ["lib/example-doc/s4", "lib/other-doc/s7"]}
  ],
  "usage": {"model_calls": 3, "tool_calls": 3, "seconds": 39.3,
            "input_tokens": 10151, "cached_input_tokens": 5525, "output_tokens": 3340}
}
```

A finding is an observation the evidence states, or an inference that names the findings it `rests_on`. A citation that does not resolve to the case's evidence is removed and listed in `checks` with a reason, and an item left with no support stays and is listed as unsupported. A run that reaches 12 tool calls or 120 seconds, or whose tool fails or answer does not fit the schema, ends as `incomplete` with a reason. The time cap is checked before each model call and each tool call, so a search already running when the time runs out is not cut off. A library citation (`"source": "library"`) is kept only for a ref that a search in the same run returned, which `tool_calls` lists, and it never supports an item on its own ([decision 0020](docs/decisions/0020-library-citations.md)).

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

![Hindcast as built: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status pages and postmortems, and the Radar charts are downloaded in the browser. The Azure CLI and Hindcast's code store the captured files in Blob Storage, and Hindcast's ingestion reads them back and writes the evidence, the extracts, and the answer-key analyzer results there with its own Entra token. Hindcast's code calls the pinned model deployments through the Foundry project with the Responses API; its investigate command keeps the investigator prompt agent's version in the project, runs that agent, executes its case tools and library searches on the workstation, and writes the result file there; its seal command runs the same agent on a sealed case, uploads the result to Blob Storage, and commits only its hash. It calls Content Understanding on the Foundry resource, whose three analyzers use the gpt-5.4-mini and text-embedding-3-large deployments, with a role assigned only while extraction runs. Its index command embeds the library chunks through the Foundry resource endpoint and pushes them to the library index in Azure AI Search, in Switzerland North, which the investigator's library search and the leak check query with an Entra token. During a portal evaluation run, the Foundry evaluation calls the deployments as the signed-in user. git reaches GitHub through pull requests. The project is connected to Application Insights, which the deployed page also writes to (the deployment diagram). The Foundry resource, the storage account, and the search service accept no keys; traces use the Application Insights connection string](docs/diagrams/current-architecture.svg)

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the locked tools. These are the checks CI runs on the code; the workflow also lints the YAML, audits the dependencies, and builds the image ([ci.yml](.github/workflows/ci.yml)).

```bash
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
for f in infra/main.bicep infra/search.bicep; do az bicep build --file "$f" --stdout > /dev/null && az bicep lint --file "$f"; done
```

The page runs locally with `uv run --frozen streamlit run src/hindcast/app.py`; without a connection string it sends no telemetry. hadolint and shellcheck run in CI from their pinned releases; the Dockerfile builds there, since the image is pushed from `main` by the workflow, not from a workstation.

The tests that read the captured status pages and postmortems skip when `data/sources/` is absent, which includes CI. The [runbooks](docs/runbooks/) capture them.

Copy `.env.example` to `.env` and fill in the endpoints. No keys: the code signs in with `DefaultAzureCredential`.

## License

[MIT](LICENSE). Status pages and postmortems belong to their publishers. The repository holds their URLs, hashes, and a capture command, and the answer keys quote short attributed passages from them; the pages themselves are not redistributed.

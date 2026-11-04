# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Given only what an outside engineer could see while an outage was happening, Hindcast reconstructs it: a timeline, the most likely root cause, the contributing factors, the questions the evidence leaves open, and whether it was an attack. Every item cites what it rests on.

The provider's own postmortem, published later, is the answer key the reconstruction is scored against; Hindcast never sees it.

## Status

Milestones 1 to 3 of 6 are verified, and slices of milestones 4 and 6 are built ([roadmap](docs/roadmap.md)). Built and run:

- **Sources and evidence:** the case sources are captured and pinned by hash. The status updates are cut into evidence that keeps every update before the resolved one, and only the time of that one.
- **Library and keys:** earlier postmortems are extracted into sections and described charts, and the answer keys are frozen. The library was indexed in Azure AI Search, and a case could search it only within its date bound and its picks, which the gate checked on the live index ([worklog](docs/worklogs/03-retrieval.md)); the service was deleted on 2026-11-04 after the evaluation runs and is recreated from its template.
- **Investigator:** it has reconstructed the development outage from its updates and the library, with every citation resolving and each library citation backed by a search in the same run ([worklog](docs/worklogs/04-investigator.md#slice-2-the-library-search-tool)).
- **Safety, traces, and cost:** every update, chart, library hit, and the case title pass Prompt Shields before the model reads them, and every answer is checked for personal data before it is written. Each run is traced and priced, and a finding can be challenged with a follow-up turn ([worklog](docs/worklogs/04-investigator.md#slice-3-screens-pii-challenge-traces-and-cost)).
- **Page:** a page that shows a stored result runs on Azure Container Apps behind Entra sign-in, from an image CI builds and pushes without a stored credential ([worklog](docs/worklogs/06-deployment.md)).
- **Evaluation runs:** five arms ran three times on each showcase case (60 runs, all complete), the injection tests ran on both models with the screens on and off, the Foundry cloud evaluators scored a third of the runs, and the judge proposed an outcome for every key item of every run. The review of those proposals, which the scores need, is open ([report](eval/reconstruction/showcase-v1/README.md), [injection](eval/injection/dev-v1/README.md)).
- **Sealed reconstructions:** three October outages are sealed, once without the library and once with it, and two GitHub outages of 2026-11-04 once with it. Hindcast reconstructed them before their providers had published a cause, and only the hash of each result is public until the provider's account is out ([decision 0017](docs/decisions/0017-sealed-reconstructions.md)).

Not built yet: an interface that runs investigations, and the full-environment deployment. Not run yet: the evaluation's review and scores.

The current cases are all "not an attack" according to their postmortems, so the attack verdict is reported with its reasoning and citations, never as an accuracy rate ([answer keys](eval/keys/README.md#limits)).

## What an investigation returns

The shape `hindcast.result` and `hindcast.investigate` write, shortened: one item per list, and the values are illustrative ([decisions 0015](docs/decisions/0015-investigation-result-and-citation-policy.md), [0020](docs/decisions/0020-library-citations.md), and [0021](docs/decisions/0021-screens-pii-and-challenge.md)).

```json
{
  "case_id": "example-case",
  "agent": {"name": "hindcast-investigator-gpt-6-luna", "version": "3"},
  "model": {"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"},
  "provenance": {
    "prompt": {"blob": "<git blob hash>", "dirty": false},
    "code": {"commit": "<commit>", "dirty": false, "src_tree": "<git tree hash of src/>"},
    "evidence_sha256": "<sha256>",
    "library": {
      "registry": {"blob": "<git blob hash>", "dirty": false},
      "index": "hindcast-library-1024",
      "search_api_version": "2026-04-01",
      "embedding": {"deployment": "text-embedding-3-large", "name": "text-embedding-3-large",
                    "version": "1", "dimensions": 1024},
      "contents": {"chunks": 41, "sha256": "<sha256 of every chunk the case's filter returns>"}
    },
    "arm": "hindcast",
    "screens": true
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
  "checks": {"rejected_citations": [], "unsupported": [],
             "pii": [{"path": "findings[0].claim", "category": "Person", "confidence": 0.97}]},
  "tool_calls": [
    {"name": "list_updates", "seconds": 2.4, "withheld": [], "screen_calls": 2},
    {"name": "search_library", "seconds": 6.6, "query": "<query>",
     "refs": ["lib/example-doc/s4"], "withheld": ["lib/other-doc/s7"], "screen_calls": 2}
  ],
  "usage": {"model_calls": 3, "tool_calls": 3, "seconds": 42.2,
            "input_tokens": 10648, "cached_input_tokens": 4251, "output_tokens": 3039,
            "screen_calls": 5, "screen_records": 25, "pii_calls": 6, "pii_records": 26,
            "max_call_input_tokens": 6391, "reasoning_tokens": 1880},
  "reasoning": {"requested": "medium", "applied": ["medium"]},
  "cost": {"table_version": 1, "currency": "USD", "model": 0.002202, "screens": 0.009375,
           "pii": 0.026, "embeddings": 0.000007, "total": 0.037584}
}
```

A finding is an observation the evidence states, or an inference that names the findings it `rests_on`. The checks on the answer:

| Check | What happens |
|---|---|
| A citation does not resolve, names an item Prompt Shields withheld, or names an item the run never read | Removed and listed in `checks` with its reason |
| A `rests_on` entry sits on an observation, names its own finding, names an ID two findings carry, or closes a loop among findings | Removed and listed in `checks` with its reason |
| An item is left with no support: no case citation, and no `rests_on` finding that is itself supported | Kept and listed as unsupported |
| A library citation (`"source": "library"`) names a ref no search in the run showed | Removed; a kept one never supports an item on its own ([decision 0020](docs/decisions/0020-library-citations.md)) |
| The answer or a search query holds personal data | Replaced by its category; `checks.pii` lists where, never what |

A run has 120 seconds and 12 tool calls. Each model call gets the time left as its timeout; within a tool call, the search, its embedding, and the screen share the time left. Nothing retries.

A run that reaches a cap, whose model call, tool, screen, or PII check fails, or whose answer does not fit the schema ends as `incomplete` with a reason, and an answer that was not checked is not written. A failed model call keeps only the error's type (`model-error: RateLimitError`) and the usage spent so far. The cost comes from the versioned price table in [`data/prices.yaml`](data/prices.yaml).

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

![Hindcast as built: on an operator workstation signed in with Entra ID, Hindcast's capture command reads the providers' status pages and postmortems, and the Radar charts are downloaded in the browser. The Azure CLI and Hindcast's code store the captured files in Blob Storage, and Hindcast's ingestion reads them back and writes the evidence, the extracts, and the answer-key analyzer results there with its own Entra token. Hindcast's code calls the pinned model deployments through the Foundry project with the Responses API; its investigate command keeps the investigator prompt agent's version in the project, runs that agent, executes its case tools and library searches on the workstation, screens every tool item with Prompt Shields and masks personal data in the answer with PII detection, and writes the result file there; its challenge command runs a challenger agent on one finding the same way; its seal command runs the same agent on a sealed case, uploads the result to Blob Storage, and commits only its hash. It calls Content Understanding on the Foundry resource, whose three analyzers use the gpt-5.4-mini and text-embedding-3-large deployments, with a role assigned only while extraction runs. Its index command embeds the library chunks through the Foundry resource endpoint and pushes them to the library index in Azure AI Search, in Switzerland North, which the investigator's library search and the leak check query with an Entra token. A Foundry evaluation run, started in the portal or by Hindcast's evaluation code, calls a deployment as its judge. Hindcast's judge command sends each scored run, with the text the run cites, to claude-opus-5-5 on the Anthropic API, outside Azure, with an API key from the local environment file. git reaches GitHub through pull requests. Hindcast's commands send their spans to Application Insights, which the deployed page also writes to (the deployment diagram); the Foundry project is not connected to it. The Foundry resource, the storage account, and the search service accept no keys; traces use the Application Insights connection string.](docs/diagrams/current-architecture.svg)

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

The page runs locally with `PYTHONPATH=src uv run --frozen streamlit run src/hindcast/app.py`; the code is not an installed package, so it needs the path. Without a connection string it sends no telemetry. With `HINDCAST_CHALLENGE_LIVE=1` and the `.env` settings, each finding of a screened result gets a box that challenges it with the developer's sign-in. The command `python -m hindcast.challenge <result file> <finding id> "<question>"` does the same.

hadolint and shellcheck run in CI from their pinned releases; the Dockerfile builds there, since the image is pushed from `main` by the workflow, not from a workstation.

The tests that read the captured status pages and postmortems skip when `data/sources/` is absent, which includes CI. The [runbooks](docs/runbooks/) capture them.

Copy `.env.example` to `.env` and fill in the endpoints. No keys: the code signs in with `DefaultAzureCredential`.

## License

[MIT](LICENSE). Status pages and postmortems belong to their publishers. The repository holds their URLs, hashes, and a capture command, and the answer keys quote short attributed passages from them; the pages themselves are not redistributed.

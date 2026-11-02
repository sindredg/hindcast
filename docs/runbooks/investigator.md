# Investigator: operator procedure

Status: Written on 2026-10-30 for [milestone 4, slice 1](../worklogs/04-investigator.md) and validated again on 2026-11-02 for [slice 2](../worklogs/04-investigator.md#slice-2-the-library-search-tool), the library search. Steps 1, 2, 4, and 5 ran on 2026-11-02 with the output shown, step 3 on 2026-10-30, except where an "Expected:" line is marked as reasoned.

The procedure runs one investigation of a case through the investigator prompt agent and reads the result. It makes model calls on the investigator deployment, at most 13 per run, and for each library search one embedding call and one query to the search service.

## Inputs and access

- The [foundations runbook](foundations.md) and the [extraction runbook](extraction.md) completed: `.env` written, and the case evidence under `build/evidence/<case_id>.json`.
- The [retrieval runbook](retrieval.md) completed: the library index built, and `HINDCAST_SEARCH_ENDPOINT`, `HINDCAST_SEARCH_INDEX`, `HINDCAST_EMBEDDING_ENDPOINT`, and `HINDCAST_EMBEDDING_DEPLOYMENT` in `.env`. The command refuses to start without them.
- The library extracts under `build/extracted/library/`: every hit is checked against them.
- Signed in with `az login` as a user with Foundry User on the project (agent versions, deployment reads, agent calls), Search Index Data Contributor on the search service (queries), and Cognitive Services OpenAI User on the Foundry resource (query embeddings).
- Commands run from the repository root.

## Check the evidence

1. Confirm the case's evidence file is present. If it is not, `python -m hindcast.ingest evidence` writes it (extraction runbook).

   ```bash
   ls build/evidence/cloudflare-2026-02-20.json
   ```

   Expected: the path is printed.

## Run an investigation

2. Run the investigator on the development case.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate cloudflare-2026-02-20
   ```

   Expected, as observed on 2026-11-02 with prompt v3 and the variables exported from `.env` (the counts and the usage vary per run):

   ```
   complete
   findings 6, timeline events 9, factors 1, open questions 3
   rejected citations 0, unsupported 0, searches 1, library citations kept 1
   model calls 3, tool calls 3, seconds 39.258, tokens in 10151 (cached 5525) out 3340
   build/investigations/cloudflare-2026-02-20/20261102T181721Z-v3.json
   ```

   For the comparison model, prefix the command with `HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol`.

   The first run creates agent `hindcast-investigator-<deployment>` version 1 in the project, with any character Foundry refuses in a name replaced by a hyphen (`gpt-6.1-sol` gives `hindcast-investigator-gpt-6-1-sol`). A later run reuses the latest version while `prompts/investigator.md`, the tools, the schema, and the effort are unchanged, and creates the next version when any of them changes. A run that stops early prints `incomplete: <reason>` (`tool-cap`, `time-cap`, `tool-error: ...`, `empty-result`, or `schema: ...`) and still writes the file. A search that cannot reach the service ends the run as `tool-error: search_library: ...`; on 2026-11-02 one run ended that way while the search endpoint dropped TLS connections for a few minutes ([troubleshooting](../troubleshooting.md)). A model call that fails raises and writes nothing ([#23](https://github.com/sindredg/hindcast/issues/23)).

3. A showcase case is refused until the rubric is frozen.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate github-2026-08-17 2>&1 | tail -1
   ```

   Expected: `ScoredCaseLocked: github-2026-08-17 is a showcase case: it runs only once the rubric is frozen (eval/rubric/frozen.json exists). Roadmap milestone 5 freezes the rubric before the first scored run.` The refusal comes before any cloud call.

## Read the result

4. Print the run's metadata and checks without the investigation text.

   ```bash
   uv run --frozen python -c "import json,sys; d=json.load(open(sys.argv[1])); [print(k, d[k]) for k in ('agent','model','provenance','status','incomplete_reason','checks','usage')]; [print(c['name'], c['seconds'], c.get('refs', '')) for c in d['tool_calls']]" build/investigations/cloudflare-2026-02-20/<file>.json
   ```

   Expected: the agent name and version (`hindcast-investigator-gpt-6-luna`, `3` on 2026-11-02), the model name and version (`gpt-6-luna`, `2026-09-22`), the prompt blob hash (or SHA-256 with `dirty: True`), the commit with its dirty flag, the evidence SHA-256, the library provenance (registry blob, `hindcast-library-1024`, search API `2026-04-01`, `text-embedding-3-large` version `1` at 1,024 dimensions), `status complete`, and empty `rejected_citations` and `unsupported` lists for a run that passes. Then one line per tool call: `list_updates`, `list_charts`, and each `search_library` with its seconds and the refs it returned (on 2026-11-02, one search returning five `lib/cloudflare-.../s<n>` refs).

5. Read the investigation itself under `investigation` in the same file. Each item's `citations` name updates (`<case_id>/u<n>`) or charts (`<case_id>/chart<n>`) of the case, or library sections and figures (`source: library`, `lib/<document>/s<n>` or `fig<n>`); `rests_on` names the findings an inference rests on. Compare each item with the update it cites in `build/evidence/<case_id>.json`, and each library citation with its section in `build/extracted/library/<document>.json`.

   Expected: every cited update or chart exists in the evidence file, and every library ref is one the run's searches returned; the checks have already removed any that did not. Reasoned: this step is a reading, and what it found is in the worklog, for [slice 1](../worklogs/04-investigator.md#live-run) and [slice 2](../worklogs/04-investigator.md#slice-2-the-library-search-tool).

## Remove the agent

6. The agent stays in the project between runs. Delete it when the project is torn down, or to start the version count again.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; print(project_client().agents.delete('hindcast-investigator-gpt-6-luna'))"
   ```

   Expected (reasoned from the spike agent's deletion on 2026-10-30, not run on this agent): `{'object': 'agent.deleted', 'name': 'hindcast-investigator-gpt-6-luna', 'deleted': True}`.

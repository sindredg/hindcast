# Investigator: operator procedure

Status: Written on 2026-10-30 for [milestone 4, slice 1](../worklogs/04-investigator.md). Every step ran on 2026-10-30 with the output shown, except where an "Expected:" line is marked as reasoned.

The procedure runs one investigation of a case through the investigator prompt agent and reads the result. It makes model calls on the investigator deployment: at most 13 per run.

## Inputs and access

- The [foundations runbook](foundations.md) and the [extraction runbook](extraction.md) completed: `.env` written, and the case evidence under `build/evidence/<case_id>.json`.
- Signed in with `az login` as a user with Foundry User on the project. No other role: creating the agent version, reading the deployment, and calling the agent all go through the project endpoint.
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

   Expected, as observed on 2026-10-30 (the counts and the usage vary per run):

   ```
   complete
   findings 10, timeline events 8, factors 2, open questions 4
   rejected citations 0, unsupported 0
   model calls 2, tool calls 2, seconds 31.353, tokens in 3776 (cached 1034) out 3395
   build/investigations/cloudflare-2026-02-20/20261030T040215Z-v1.json
   ```

   The first run creates agent `hindcast-investigator-<deployment>` version 1 in the project. A later run reuses the latest version while `prompts/investigator.md`, the tools, the schema, and the effort are unchanged, and creates the next version when any of them changes. A run that stops early prints `incomplete: <reason>` (`tool-cap`, `time-cap`, `tool-error: ...`, `empty-result`, or `schema: ...`) and still writes the file.

3. A showcase case is refused until the rubric is frozen.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate github-2026-08-17 2>&1 | tail -1
   ```

   Expected: `ScoredCaseLocked: github-2026-08-17 is a showcase case: it runs only once the rubric is frozen (eval/rubric/frozen.json exists). Roadmap milestone 5 freezes the rubric before the first scored run.` The refusal comes before any cloud call.

## Read the result

4. Print the run's metadata and checks without the investigation text.

   ```bash
   python3 -c "import json,sys; d=json.load(open(sys.argv[1])); [print(k, d[k]) for k in ('agent','model','provenance','status','incomplete_reason','checks','usage')]" build/investigations/cloudflare-2026-02-20/<file>.json
   ```

   Expected: the agent name and version (`hindcast-investigator-gpt-6-luna`, `1` on 2026-10-30), the model name and version (`gpt-6-luna`, `2026-09-22`), the prompt blob hash (or SHA-256 with `dirty: True`), the commit with its dirty flag, the evidence SHA-256, `status complete`, and empty `rejected_citations` and `unsupported` lists for a run that passes.

5. Read the investigation itself under `investigation` in the same file. Each item's `citations` name updates (`<case_id>/u<n>`) or charts (`<case_id>/chart<n>`) of the case; `rests_on` names the findings an inference rests on. Compare each item with the update it cites in `build/evidence/<case_id>.json`.

   Expected: every cited update or chart exists in the evidence file; the checks have already removed any that did not. Reasoned: this step is a reading, and what it found on 2026-10-30 is in the [worklog](../worklogs/04-investigator.md#live-run).

## Remove the agent

6. The agent stays in the project between runs. Delete it when the project is torn down, or to start the version count again.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; print(project_client().agents.delete('hindcast-investigator-gpt-6-luna'))"
   ```

   Expected (reasoned from the spike agent's deletion on 2026-10-30, not run on this agent): `{'object': 'agent.deleted', 'name': 'hindcast-investigator-gpt-6-luna', 'deleted': True}`.

# Investigator: operator procedure

Status: Written on 2026-10-30 for [milestone 4, slice 1](../worklogs/04-investigator.md), validated again on 2026-11-02 for [slice 2](../worklogs/04-investigator.md#slice-2-the-library-search-tool), the library search, and on 2026-11-03 for [slice 3](../worklogs/04-investigator.md#slice-3-screens-pii-challenge-traces-and-cost), the screens, the challenge, and the traces. Steps 1 to 4 and 6 to 9 ran on 2026-11-03 with the output shown, step 5 on 2026-10-30, except where an "Expected:" line is marked as reasoned.

The procedure runs one investigation of a case through the investigator prompt agent, reads the result, challenges a finding, and finds the run's trace. A run makes:

- at most 13 model calls on the investigator deployment;
- for each library search, one embedding call and one query to the search service;
- a few Prompt Shields calls: one document for the title and for each update, chart, and hit, five documents per call;
- one PII call per five answer fields and search queries.

## Inputs and access

- The [foundations runbook](foundations.md) and the [extraction runbook](extraction.md) completed: `.env` written, and the case evidence under `build/evidence/<case_id>.json`.
- The [retrieval runbook](retrieval.md) completed: the library index built, and `HINDCAST_SEARCH_ENDPOINT`, `HINDCAST_SEARCH_INDEX`, `HINDCAST_EMBEDDING_ENDPOINT`, and `HINDCAST_EMBEDDING_DEPLOYMENT` in `.env`. The command refuses to start without them.
- `HINDCAST_SAFETY_ENDPOINT` in `.env`: the Foundry resource endpoint, `https://<resource>.services.ai.azure.com/`, the same value as `HINDCAST_EMBEDDING_ENDPOINT`.
- `APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env` for traces. Without it the commands run and send no telemetry.
- The library extracts under `build/extracted/library/`: every hit is checked against them.
- Signed in with `az login` as a user with Foundry User on the project (agent versions, deployment reads, agent calls), Search Index Data Contributor on the search service (queries), Cognitive Services OpenAI User on the Foundry resource (query embeddings), and the custom role from step 2 (Prompt Shields and PII detection). Creating the role needs Owner or User Access Administrator on the resource group.
- Commands run from the repository root.

## Check the evidence

1. Confirm the case's evidence file is present. If it is not, `python -m hindcast.ingest evidence` writes it (extraction runbook).

   ```bash
   ls build/evidence/cloudflare-2026-02-20.json
   ```

   Expected: the path is printed.

## Give the developer the safety role

2. Create a role with the two data actions Prompt Shields and PII detection need, and assign it on the Foundry resource. No built-in role holds just these two ([finding](../findings/safety.md)). The loop retries the assignment while the new role replicates.

   ```bash
   RG=$(az group show -n <resource-group> --query id -o tsv) && RID=$(az cognitiveservices account show -g <resource-group> -n <foundry-resource> --query id -o tsv) && ME=$(az ad signed-in-user show --query id -o tsv) && az role definition create --query roleName -o tsv --role-definition "{\"Name\":\"Hindcast Safety Caller\",\"Description\":\"Prompt Shields and PII detection on the Hindcast Foundry resource\",\"Actions\":[],\"DataActions\":[\"Microsoft.CognitiveServices/accounts/ContentSafety/text:shieldprompt/action\",\"Microsoft.CognitiveServices/accounts/Language/analyze-text/action\"],\"AssignableScopes\":[\"$RG\"]}" && for i in $(seq 1 20); do az role assignment create --assignee-object-id "$ME" --assignee-principal-type User --role "Hindcast Safety Caller" --scope "$RID" --query roleDefinitionName -o tsv && date -u +%H:%M:%SZ && break; sleep 15; done
   ```

   Expected: `Hindcast Safety Caller`, then a UTC time. On 2026-11-03 the assignment printed only the time; `az role assignment list --assignee <object-id> --scope <resource-id>` then listed `Hindcast Safety Caller`.

3. Check that both services answer with a benign text and a made-up name. The grant took about 2.5 minutes on 2026-11-03; until then each call raises `ScreenError: HTTP 401 PermissionDenied` or `PiiError: ...`.

   ```bash
   set -a; . ./.env; set +a
   ```

   ```bash
   PYTHONPATH=src uv run --frozen python -c "from hindcast.config import SafetySettings, load_settings; from hindcast.safety import pii_client, shield_client; s = load_settings(SafetySettings); print(shield_client(s).documents(['The resolver returned errors for some queries.'], timeout=10)); print([h.category for h in pii_client(s)(['Jane Doe paged the on-call engineer.'], timeout=10)[0]])"
   ```

   Expected, as observed on 2026-11-03: `[False]`, then `['Person']`. The role in "the on-call engineer" is not reported.

## Run an investigation

4. Run the investigator on the development case.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate cloudflare-2026-02-20
   ```

   Expected, as observed on 2026-11-03 with prompt v3 (the counts, the usage, and the cost vary per run):

   ```
   complete
   findings 6, timeline events 8, factors 2, open questions 4
   rejected citations 0, unsupported 0, searches 1, library citations kept 0
   withheld items 0, PII hits 0
   model calls 3, tool calls 3, seconds 42.195, tokens in 10648 (cached 4251) out 3039
   cost USD 0.037583 (price table v1)
   build/investigations/cloudflare-2026-02-20/20261103T171237Z-v3.json
   ```

   For the comparison model, prefix the command with `HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol`.

   The first run creates agent `hindcast-investigator-<deployment>` version 1 in the project, with any character Foundry refuses in a name replaced by a hyphen (`gpt-6.1-sol` gives `hindcast-investigator-gpt-6-1-sol`). A later run reuses the latest version while `prompts/investigator.md`, the tools, the schema, and the effort are unchanged, and creates the next version when any of them changes.

   Other outcomes:

   - A run that stops early prints `incomplete: <reason>` (`tool-cap`, `time-cap`, `tool-error: ...`, `screen-error: ...`, `empty-result`, `schema: ...`, or `pii-error: ...`) and still writes the file.
   - A search that cannot reach the service ends the run as `tool-error: search_library: ...`; on 2026-11-02 one run ended that way while the search endpoint dropped TLS connections for a few minutes ([troubleshooting](../troubleshooting.md)).
   - A model call that fails raises and writes nothing ([#23](https://github.com/sindredg/hindcast/issues/23)).
   - A deployment missing from `data/prices.yaml` is refused before the agent version is made.

   The output above is from before the case title was screened too (commit `a43af94`); a run now sends one more text to Prompt Shields.

   A withheld item means Prompt Shields flagged it. On the development case, none was on 2026-11-03; a flag there is a false positive to record before anything else changes.

5. A showcase case is refused until the rubric is frozen.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate github-2026-08-17 2>&1 | tail -1
   ```

   Expected: `ScoredCaseLocked: github-2026-08-17 is a showcase case: it runs only once the rubric is frozen (eval/rubric/frozen.json exists). Roadmap milestone 5 freezes the rubric before the first scored run.` The refusal comes before any cloud call.

## Read the result

6. Print the run's metadata, checks, and cost without the investigation text.

   ```bash
   uv run --frozen python -c "import json,sys; d=json.load(open(sys.argv[1])); [print(k, d[k]) for k in ('agent','model','provenance','status','incomplete_reason','checks','usage','cost')]; [print(c['name'], c['seconds'], c.get('refs', ''), c['withheld'], c['screen_calls']) for c in d['tool_calls']]" build/investigations/cloudflare-2026-02-20/<file>.json
   ```

   Expected, as observed on 2026-11-03:

   | Line | Value |
   |---|---|
   | `agent`, `model` | `hindcast-investigator-gpt-6-luna` version `3`; `gpt-6-luna`, `2026-09-22` |
   | `provenance` | the prompt blob hash (or SHA-256 with `dirty: True`), the commit with its dirty flag, the evidence SHA-256, and the library: registry blob, `hindcast-library-1024`, search API `2026-04-01`, `text-embedding-3-large` version `1` at 1,024 dimensions |
   | `status`, `checks` | `complete`; empty `rejected_citations`, `unsupported`, and `pii` lists for a run that passes |
   | `usage`, `cost` | `screen_calls 5` and `pii_calls 6`; the cost by part with `table_version 1` |
   | One line per tool call | `list_updates`, `list_charts`, and each `search_library`, with its seconds, the refs it showed, the refs it withheld (`[]`), and its screen calls (2, 1, and 2) |

7. Read the investigation itself under `investigation` in the same file. Each item's `citations` name updates (`<case_id>/u<n>`) or charts (`<case_id>/chart<n>`) of the case, or library sections and figures (`source: library`, `lib/<document>/s<n>` or `fig<n>`); `rests_on` names the findings an inference rests on. Compare each item with the update it cites in `build/evidence/<case_id>.json`, and each library citation with its section in `build/extracted/library/<document>.json`.

   Expected: every cited update or chart exists in the evidence file and was shown to the model, and every library ref is one the run's searches showed; the checks have already removed any that did not. Reasoned: this step is a reading, and what it found is in the worklog, for [slice 1](../worklogs/04-investigator.md#live-run), [slice 2](../worklogs/04-investigator.md#slice-2-the-library-search-tool), and [slice 3](../worklogs/04-investigator.md#slice-3-live-runs).

## Challenge a finding

8. Challenge one finding of a stored result. The challenger runs on the result's own deployment, and the challenge is written next to the result under `challenges/`. The command refuses, before any cloud call, an incomplete result, an unknown finding, an empty or over-long question, and an evidence file that differs from the one the result was made from.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.challenge eval/investigations/cloudflare-2026-02-20/20261103T171237Z-v3.json F4 "Which status update shows this, and does any later update contradict it?"
   ```

   Expected, as observed on 2026-11-03:

   ```
   complete: stands
   citations kept 5, rejected 0, unsupported 0, PII hits 0
   model calls 2, tool calls 1, seconds 10.218, screen calls 3
   cost USD 0.006193 (price table v1)
   eval/investigations/cloudflare-2026-02-20/challenges/20261103T174623Z-F4.json
   ```

   The first challenge on a deployment creates agent `hindcast-challenger-<deployment>` version 1. A question that Prompt Shields flags prints `refused: prompt-shields` and makes no model call.

   To challenge from the page instead, start it with the live flag; each finding then has a question box. The deployed page has no such box.

   ```bash
   HINDCAST_CHALLENGE_LIVE=1 PYTHONPATH=src uv run --frozen --env-file .env streamlit run src/hindcast/app.py
   ```

   Expected (reasoned; not run in a browser on 2026-11-03): the page opens on the newest `gpt-6-luna` result, and "Run challenge" under a finding shows the verdict, the answer, and its citations, and writes the challenge file.

## Find the trace

9. List the latest Hindcast spans in Application Insights. The query reads with the developer's sign-in; spans arrive within about a minute.

   ```bash
   APP=$(az resource show -g <resource-group> -n <application-insights> --resource-type Microsoft.Insights/components --query properties.AppId -o tsv) && az monitor app-insights query --apps "$APP" --offset 1h --analytics-query "dependencies | where cloud_RoleName == 'hindcast-investigator' and name in ('investigation', 'challenge', 'model_call', 'tool_call', 'screen', 'pii') | top 9 by timestamp desc | project timestamp, name, seconds = tostring(customDimensions.seconds), time_left = tostring(customDimensions.time_left), status = tostring(customDimensions.status)" --query "tables[0].rows" -o tsv
   ```

   Expected, as observed on 2026-11-03 after the challenge in step 8 (the first six rows):

   ```
   2026-11-03T17:46:23.251893Z	pii
   2026-11-03T17:46:16.475889Z	model_call	6.772	86.702
   2026-11-03T17:46:16.05214Z	tool_call	0.423
   2026-11-03T17:46:13.178545Z	model_call	2.873	90.000
   2026-11-03T17:46:13.178134Z	challenge			complete
   2026-11-03T17:46:09.034348Z	screen
   ```

   Each `model_call` shows its seconds and the time left at its start; the first is never larger than the second. Spans carry counts and times, never text. `--app <name>` instead of `--apps <app ID>`, or a column named `first` or `kind`, fails with `BadArgumentError`.

   Since commit `2768ef5`, after this output, the `challenge` span starts before the question's `screen` span and is its parent, so the `challenge` row sorts below `screen` (reasoned). A challenge started from the page runs in the page's process and traces under `hindcast-web`; filter on that role for it (reasoned).

## Remove the agents and the role

10. The agents stay in the project between runs. Delete them when the project is torn down, or to start the version count again: `hindcast-investigator-gpt-6-luna`, `hindcast-investigator-gpt-6-1-sol`, `hindcast-challenger-gpt-6-luna`, and `hindcast-challenger-gpt-6-1-sol`.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; print(project_client().agents.delete('hindcast-investigator-gpt-6-luna'))"
    ```

    Expected (reasoned from the spike agent's deletion on 2026-10-30, not run on these agents): `{'object': 'agent.deleted', 'name': 'hindcast-investigator-gpt-6-luna', 'deleted': True}`.

11. Remove the role assignment, then the role.

    ```bash
    RID=$(az cognitiveservices account show -g <resource-group> -n <foundry-resource> --query id -o tsv) && az role assignment delete --assignee "$(az ad signed-in-user show --query id -o tsv)" --role "Hindcast Safety Caller" --scope "$RID" && az role definition delete --name "Hindcast Safety Caller" --scope "$(az group show -n <resource-group> --query id -o tsv)"
    ```

    Expected (reasoned, not run): no output, and `az role definition list --name "Hindcast Safety Caller"` returns `[]`.

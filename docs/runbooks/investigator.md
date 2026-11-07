# Investigator: operator procedure

Status: Written on 2026-10-30. Steps 1 to 4 and 6 to 9 ran on 2026-11-03, step 5 on 2026-10-30, step 12 on 2026-11-07 ([worklog 04](../worklogs/04-investigator.md)), except "Expected:" lines marked as reasoned.

A run makes at most 13 model calls; per library search one embedding call and one search query; Prompt Shields calls (one document per title, update, chart, and hit, five per call); one PII call per five answer fields and search queries.

On this page: [Inputs and access](#inputs-and-access) · [Check the evidence](#check-the-evidence) · [Give the developer the safety role](#give-the-developer-the-safety-role) · [Run an investigation](#run-an-investigation) · [Read the result](#read-the-result) · [Challenge a finding](#challenge-a-finding) · [Find the trace](#find-the-trace) · [Remove the agents and the role](#remove-the-agents-and-the-role) · [Read a scored run on the page](#read-a-scored-run-on-the-page)

## Inputs and access

- The [foundations](foundations.md), [extraction](extraction.md), and [retrieval](retrieval.md) runbooks completed: `.env` with `HINDCAST_SEARCH_ENDPOINT`, `HINDCAST_SEARCH_INDEX`, `HINDCAST_EMBEDDING_ENDPOINT`, `HINDCAST_EMBEDDING_DEPLOYMENT`, `HINDCAST_SAFETY_ENDPOINT` (`https://<resource>.services.ai.azure.com/`), and `APPLICATIONINSIGHTS_CONNECTION_STRING` (without it, no telemetry); evidence under `build/evidence/`, extracts under `build/extracted/library/`.
- `az login` with Foundry User on the project, Search Index Data Contributor on the search service, Cognitive Services OpenAI User on the Foundry resource, and the custom role from step 2 (creating it needs Owner or User Access Administrator on the resource group).
- Commands run from the repository root.

## Check the evidence

1. Confirm the evidence file exists (else `python -m hindcast.ingest evidence`, extraction runbook).

   ```bash
   ls build/evidence/cloudflare-2026-02-20.json
   ```

   Expected: the path is printed.

## Give the developer the safety role

2. Create a role with the two data actions Prompt Shields and PII detection need (no built-in role holds just these two, [finding](../findings/safety.md)) and assign it on the Foundry resource. The loop retries while the role replicates.

   ```bash
   RG=$(az group show -n <resource-group> --query id -o tsv) && RID=$(az cognitiveservices account show -g <resource-group> -n <foundry-resource> --query id -o tsv) && ME=$(az ad signed-in-user show --query id -o tsv) && az role definition create --query roleName -o tsv --role-definition "{\"Name\":\"Hindcast Safety Caller\",\"Description\":\"Prompt Shields and PII detection on the Hindcast Foundry resource\",\"Actions\":[],\"DataActions\":[\"Microsoft.CognitiveServices/accounts/ContentSafety/text:shieldprompt/action\",\"Microsoft.CognitiveServices/accounts/Language/analyze-text/action\"],\"AssignableScopes\":[\"$RG\"]}" && for i in $(seq 1 20); do az role assignment create --assignee-object-id "$ME" --assignee-principal-type User --role "Hindcast Safety Caller" --scope "$RID" --query roleDefinitionName -o tsv && date -u +%H:%M:%SZ && break; sleep 15; done
   ```

   Expected: `Hindcast Safety Caller`, then a UTC time. On 2026-11-03 the assignment printed only the time; `az role assignment list --assignee <object-id> --scope <resource-id>` then listed `Hindcast Safety Caller`.

3. Check both services with a benign text and a made-up name. The grant took about 2.5 minutes on 2026-11-03; until then `ScreenError: HTTP 401 PermissionDenied` or `PiiError: ...`.

   ```bash
   set -a; . ./.env; set +a
   ```

   ```bash
   PYTHONPATH=src uv run --frozen python -c "from hindcast.config import SafetySettings, load_settings; from hindcast.safety import pii_client, shield_client; s = load_settings(SafetySettings); print(shield_client(s).documents(['The resolver returned errors for some queries.'], timeout=10)); print([h.category for h in pii_client(s)(['Jane Doe paged the on-call engineer.'], timeout=10)[0]])"
   ```

   Expected, as observed on 2026-11-03: `[False]`, then `['Person']`. The role "the on-call engineer" is not reported.

## Run an investigation

4. Run the investigator on the development case (prefix `HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol` for the comparison model).

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate cloudflare-2026-02-20
   ```

   Expected, as observed on 2026-11-03 with prompt v3 (counts, usage, and cost vary per run):

   ```
   complete
   findings 6, timeline events 8, factors 2, open questions 4
   rejected citations 0, unsupported 0, searches 1, library citations kept 0
   withheld items 0, PII hits 0
   model calls 3, tool calls 3, seconds 42.195, tokens in 10648 (cached 4251) out 3039
   cost USD 0.037583 (price table v1)
   build/investigations/cloudflare-2026-02-20/20261103T171237Z-v3.json
   ```

   The first run creates agent `hindcast-investigator-<deployment>` version 1 (a refused character becomes a hyphen: `hindcast-investigator-gpt-6-1-sol`); later runs reuse it while `prompts/investigator.md`, the tools, the schema, and the effort are unchanged. A run that stops early prints `incomplete: <reason>` (`tool-cap`, `time-cap`, `model-error: ...`, `tool-error: ...`, `screen-error: ...`, `empty-result`, `schema: ...`, `pii-error: ...`) and still writes the file; on 2026-11-02 one ended `tool-error: search_library: ...` while the search endpoint dropped TLS connections ([troubleshooting](../troubleshooting.md)). Since commit `a43af94` the case title is screened too. A withheld item is a Prompt Shields flag; none on the development case on 2026-11-03.

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
   | `provenance` | prompt blob hash (or SHA-256 with `dirty: True`), commit with dirty flag, evidence SHA-256, library: registry blob, `hindcast-library-1024`, search API `2026-04-01`, `text-embedding-3-large` version `1` at 1,024 dimensions |
   | `status`, `checks` | `complete`; empty `rejected_citations`, `unsupported`, and `pii` lists |
   | `usage`, `cost` | `screen_calls 5` and `pii_calls 6`; cost by part with `table_version 1` |
   | One line per tool call | `list_updates`, `list_charts`, each `search_library`: seconds, refs shown, refs withheld (`[]`), screen calls (2, 1, and 2) |

7. Read `investigation` in the same file: `citations` name updates (`<case_id>/u<n>`), charts (`<case_id>/chart<n>`), or library refs (`source: library`, `lib/<document>/s<n>` or `fig<n>`); `rests_on` names findings. Compare with `build/evidence/<case_id>.json` and `build/extracted/library/<document>.json`.

   Expected: every cited update or chart exists in the evidence file and was shown to the model, and every library ref is one the run's searches showed. Reasoned; the readings are in the worklog, for [slice 1](../worklogs/04-investigator.md#live-run), [slice 2](../worklogs/04-investigator.md#slice-2-the-library-search-tool), and [slice 3](../worklogs/04-investigator.md#slice-3-live-runs).

## Challenge a finding

8. Challenge one finding. The challenger runs on the result's deployment, writes under `challenges/`, and refuses before any cloud call an incomplete result, an unknown finding, an empty or over-long question, or a changed evidence file.

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

   The first challenge on a deployment creates agent `hindcast-challenger-<deployment>` version 1. A flagged question prints `refused: prompt-shields` with no model call. With the live flag the page has a question box per finding; the deployed page runs it with the app's identity ([deployment runbook](deployment.md)).

   ```bash
   HINDCAST_LIVE=1 PYTHONPATH=src uv run --frozen --env-file .env streamlit run src/hindcast/app.py
   ```

   Expected (observed in a browser on 2026-11-03, [screenshots](../screenshots/README.md)): the page opens on the newest `gpt-6-luna` result, and "Run challenge" under a finding shows the verdict, the answer, and its citations, and writes the challenge file.

## Find the trace

9. List the latest Hindcast spans in Application Insights (developer's sign-in; spans arrive within about a minute).

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

   Spans carry counts and times, never text. `--app <name>`, or a column named `first` or `kind`, fails with `BadArgumentError`. Since commit `2768ef5` the `challenge` span parents the question's `screen` span and sorts below it (reasoned). A page challenge traces under `hindcast-web` (reasoned).

## Remove the agents and the role

10. Delete the agents at teardown: `hindcast-investigator-gpt-6-luna`, `hindcast-investigator-gpt-6-1-sol`, `hindcast-challenger-gpt-6-luna`, `hindcast-challenger-gpt-6-1-sol`.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; print(project_client().agents.delete('hindcast-investigator-gpt-6-luna'))"
    ```

    Expected (reasoned from the spike agent's deletion on 2026-10-30, not run on these agents): `{'object': 'agent.deleted', 'name': 'hindcast-investigator-gpt-6-luna', 'deleted': True}`.

11. Remove the role assignment, then the role.

    ```bash
    RID=$(az cognitiveservices account show -g <resource-group> -n <foundry-resource> --query id -o tsv) && az role assignment delete --assignee "$(az ad signed-in-user show --query id -o tsv)" --role "Hindcast Safety Caller" --scope "$RID" && az role definition delete --name "Hindcast Safety Caller" --scope "$(az group show -n <resource-group> --query id -o tsv)"
    ```

    Expected (reasoned, not run): no output, and `az role definition list --name "Hindcast Safety Caller"` returns `[]`.

## Read a scored run on the page

12. Start the page without the live flag, set "Results" to "Scored showcase runs", pick a run, open its Score tab.

    ```bash
    PYTHONPATH=src uv run --frozen streamlit run src/hindcast/app.py
    ```

    Expected (observed locally in headless Chrome on 2026-11-07, started with `.venv/bin/python -m streamlit` in place of `uv run` while the local uv was older than the lock's, [screenshots](../screenshots/README.md#local-page-view-parts-2026-11-07)): the picker lists the 60 scored runs by case, arm, repeat, and model. For `github-2026-08-17 · hindcast arm · r1 · gpt-6-luna`, the Score tab shows primary score 0.90, 4.5 of 5 credited, and one row per key item. The Investigation tab shows the timeline chart and the Evidence tab the evidence graph. "The score is not shown" with a reason means the key, the labels, or the run file changed after the score.

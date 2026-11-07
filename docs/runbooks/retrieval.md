# Retrieval: operator procedure

Status: Written on 2026-11-01 for [milestone 3](../worklogs/03-retrieval.md). Every step ran on 2026-11-01:

- Steps 8 to 15 ran as written.
- Step 17's refusal was not observed: calls kept succeeding.
- Step 18 ran on 2026-11-04 as written, after milestone 5's scored and injection runs. The service was recreated the same day for two new seals and the case-chart injection runs: step 7 from 16:38:56Z to 16:39:38Z, step 8 at 16:40:10Z (no token 401, key 401, token 200), and only the kept index rebuilt (`--dimensions 1024`, 267 chunks). Step 18 ran again at 17:41:08Z.
- Steps 1 to 7, 16, and 17 are written from the calls that ran, combined into one block or with a shorter output: their values were observed, and the layout of their output is reasoned.

The procedure moves extraction to the pinned gpt-5.4-mini deployment, creates the search service, builds the library index at two vector sizes, keeps the one the frozen quality check picks, and runs the gate on it ([decision 0018](../decisions/0018-extraction-model.md), [decision 0019](../decisions/0019-library-index.md)). The search service is billed per hour from creation, so step 7 runs only when the code is ready to build.

![Library index and search: The index build reads the library extracts, checks each against its blob, cuts them into chunks that stay inside one section or one figure, embeds them through the Foundry resource endpoint, and pushes them to the library index in Azure AI Search, refusing an index that already holds documents. A search takes a case ID and a query: the filter comes from the registries alone (published before the case's start day and, unless the case is sealed or revealed, picked for the case), the query text reaches only the hybrid keyword, vector, and semantic search on the index, and every hit is checked again against the same rule and the extracts. Hits that pass are returned with their ref, document, and date; a hit outside the rule raises LibraryLeak and nothing is returned](../diagrams/retrieval.svg)

On this page: [Inputs and access](#inputs-and-access) · [Move extraction to gpt-5.4-mini](#move-extraction-to-gpt-54-mini) · [Create the search service](#create-the-search-service) · [Build the index and pick its size](#build-the-index-and-pick-its-size) · [Run the gate](#run-the-gate) · [Remove the Content Understanding role and the old deployment](#remove-the-content-understanding-role-and-the-old-deployment) · [Delete the search service](#delete-the-search-service)

## Inputs and access

- The [foundations runbook](foundations.md) and the [extraction runbook](extraction.md) completed: the library extracts in `build/extracted/library/` and in Blob Storage, and `.env` written.
- Signed in with `az login` as a user with Foundry User on the project, Storage Blob Data Contributor on the storage account, and the right to assign roles (Owner or User Access Administrator).
- Commands run from the repository root. Local values are set once:

```bash
export RG=<resource-group> RESOURCE=<foundry-resource> SEARCH=<search-service-name>
RES_ID=$(az cognitiveservices account show -g "$RG" -n "$RESOURCE" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
```

Python commands load `.env` first:

```bash
set -a; . ./.env; set +a
```

## Move extraction to gpt-5.4-mini

On a rebuild from scratch, the extraction runbook creates this deployment and maps it; skip to step 7. Steps 1 to 6 move a resource whose analyzers still run on gpt-5-mini.

1. Check the quota for the model in the resource's region.

   ```bash
   az cognitiveservices usage list -l swedencentral --query "[?contains(name.value,'gpt-5.4-mini')].{name:name.value, used:currentValue, limit:limit}" -o table
   ```

   Expected: room for 50 under the Global Standard row. Observed: `0` of `1000`.

2. Create the deployment, pinned, with automatic upgrade off. The Azure CLI's `deployment create` cannot set the upgrade option, hence the REST call.

   ```bash
   az rest --method put \
     --url "https://management.azure.com${RES_ID}/deployments/gpt-5.4-mini?api-version=2026-09-01" \
     --body '{"sku": {"name": "GlobalStandard", "capacity": 50}, "properties": {"model": {"format": "OpenAI", "name": "gpt-5.4-mini", "version": "2026-03-17"}, "versionUpgradeOption": "NoAutoUpgrade"}}' \
     --query "{state:properties.provisioningState, version:properties.model.version, upgrade:properties.versionUpgradeOption}" -o tsv
   ```

   Expected: `Succeeded	2026-03-17	NoAutoUpgrade`. Set `HINDCAST_EXTRACTION_DEPLOYMENT=gpt-5.4-mini` in `.env`.

3. Assign Content Understanding Contributor and Cognitive Services OpenAI User on the Foundry resource. The first is removed in step 16; the second stays until teardown, for embeddings.

   ```bash
   for role in "Cognitive Services Content Understanding Contributor" "Cognitive Services OpenAI User"; do
     az role assignment create --assignee-object-id "$ME" --assignee-principal-type User --role "$role" --scope "$RES_ID" -o none
   done
   ```

   Expected: no output. A role takes a few minutes to work: observed 3 minutes for Content Understanding and 5.5 minutes for embeddings, which returned 401 until then.

4. Check that Content Understanding accepts the model, and read the current defaults.

   ```bash
   PYTHONPATH=src uv run --frozen python -c "
   from hindcast.extract import cu_client
   c = cu_client()
   print('gpt-5.4-mini' in c.get_analyzer('prebuilt-document').as_dict()['supportedModels']['completion'])
   print(c.get_defaults().as_dict())"
   ```

   Expected: `True`, then `{'modelDeployments': {'gpt-5-mini': 'gpt-5-mini', 'text-embedding-3-large': 'text-embedding-3-large'}}`. `False` stops the procedure: the model needs a new decision. `PermissionDenied` means the role is not working yet; retry.

5. Map the new model and drop the old one. The defaults take a JSON merge patch, so `None` removes a mapping. Then check an analyzer before the replace (the broken input), replace all three, and check again.

   ```bash
   PYTHONPATH=src uv run --frozen python -c "
   from hindcast.extract import ANALYZERS, AnalyzerDiffers, check_analyzer, cu_client, ensure_analyzers, extraction_model, replace_analyzer
   c = cu_client()
   print(c.update_defaults({'modelDeployments': {'gpt-5.4-mini': 'gpt-5.4-mini', 'text-embedding-3-large': 'text-embedding-3-large', 'gpt-5-mini': None}}).as_dict())
   m = extraction_model(); print(m)
   try:
       check_analyzer('hindcast_chart', c, m['name']); print('NOT REFUSED')
   except AnalyzerDiffers as e:
       print('refused:', e)
   for a in ANALYZERS: replace_analyzer(a, c)
   print('created:', ensure_analyzers(c))
   check_analyzer.cache_clear()
   for a in ANALYZERS: check_analyzer(a, c, m['name']); print('ok', a)"
   ```

   Expected: the two mappings; `{'deployment': 'gpt-5.4-mini', 'name': 'gpt-5.4-mini', 'version': '2026-03-17'}`; `refused: hindcast_chart: the analyzer in the service differs from analyzers/chart.json; replace it with replace_analyzer`; `created: []`; `ok` for each of the three analyzers. `NOT REFUSED` means the check cannot fail: stop.

6. Run one analysis on a committed chart, to the terminal only.

   ```bash
   PYTHONPATH=src uv run --frozen python -c "
   from pathlib import Path
   from hindcast.extract import analyze
   r = analyze('hindcast_chart', Path('data/charts/cloudflare-2026-02-20/radar-bgp-announcements.png').read_bytes(), 'image/png')
   print(r['model'], r['usage'])"
   ```

   Expected: `{'deployment': 'gpt-5.4-mini', 'name': 'gpt-5.4-mini', 'version': '2026-03-17'}` and usage with `gpt-5.4-mini-input` and `gpt-5.4-mini-output`. Observed: 403 and 390 tokens.

## Create the search service

7. Deploy `infra/search.bicep` into the foundation's resource group. It is not part of the `azd` template. Since 2026-11-05 the search service is part of the full template instead ([deployment runbook](deployment.md), [decision 0028](../decisions/0028-full-environment-and-live-page.md)); this step's template is the version at commit `99a9723` (`git show 99a9723:infra/search.bicep > search.bicep`).

   ```bash
   az deployment group create -g "$RG" -n hindcast-search -f infra/search.bicep \
     -p name="$SEARCH" developerPrincipalId="$ME" \
     --query "{state:properties.provisioningState, endpoint:properties.outputs.endpoint.value}" -o tsv
   ```

   Expected: `Succeeded` and `https://<search-service-name>.search.windows.net`, in about 40 seconds. Set `HINDCAST_SEARCH_ENDPOINT` to the endpoint in `.env`, and `HINDCAST_EMBEDDING_ENDPOINT` to the Foundry resource endpoint (`https://<foundry-resource>.services.ai.azure.com/`).

8. Check that only a token gets in. The admin key exists; it must be refused.

   ```bash
   az search service show -g "$RG" -n "$SEARCH" --query "{auth:disableLocalAuth, network:publicNetworkAccess, sku:sku.name, location:location}" -o tsv
   URL="https://$SEARCH.search.windows.net/indexes?api-version=2026-04-01"
   KEY=$(az search admin-key show -g "$RG" --service-name "$SEARCH" --query primaryKey -o tsv)
   TOKEN=$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)
   curl -s -o /dev/null -w 'none %{http_code}\n' "$URL"
   curl -s -o /dev/null -w 'key %{http_code}\n' -H "api-key: $KEY" "$URL"
   curl -s -o /dev/null -w 'token %{http_code}\n' -H "Authorization: Bearer $TOKEN" "$URL"
   unset KEY
   ```

   Expected: `True	Enabled	basic	Switzerland North`, then `none 401`, `key 401`, `token 200`. A `token 403` means the data role from the template is not working yet; retry. Observed: 200 within a minute of the deployment.

## Build the index and pick its size

9. Build both indexes.

   ```bash
   PYTHONPATH=src uv run --frozen python -m hindcast.index build --dimensions 1024
   PYTHONPATH=src uv run --frozen python -m hindcast.index build --dimensions 3072
   ```

   Expected for each: `hindcast-library-<n>: 267 chunks (202 section parts, 65 figures)` and `embedding: text-embedding-3-large text-embedding-3-large 1`, in about two and a half minutes. `already holds documents` means the index exists with content: rebuild it with `--replace`. A 401 means the OpenAI User role is not working yet.

10. Check the frozen query set, then run the quality check on both indexes.

    ```bash
    sha256sum eval/retrieval/library-v1/queries.json
    PYTHONPATH=src uv run --frozen python -m hindcast.index quality --index hindcast-library-1024
    PYTHONPATH=src uv run --frozen python -m hindcast.index quality --index hindcast-library-3072
    ```

    Expected: the SHA-256 in [the query set's README](../../eval/retrieval/library-v1/README.md#files), then one line per index: `19 of 34 queries scored, mean recall@5 <x>, MRR <y>`, written to `eval/retrieval/library-v1/results-<index>.json`. Observed: 0.640 and 0.702 for 1,024; 0.544 and 0.695 for 3,072. Apply the README's decision rule, commit both results files and the README's Status, and set `HINDCAST_SEARCH_INDEX` to the kept index.

11. Delete the other index.

    ```bash
    TOKEN=$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)
    curl -s -o /dev/null -w '%{http_code}\n' -X DELETE -H "Authorization: Bearer $TOKEN" \
      "https://$SEARCH.search.windows.net/indexes/hindcast-library-3072?api-version=2026-04-01"
    ```

    Expected: `204`.

## Run the gate

12. Check the filter, then its broken input.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.index check-filter; echo "exit $?"
    PYTHONPATH=src uv run --frozen python -m hindcast.index check-filter --shift-start cloudflare-2025-11-18; echo "exit $?"
    ```

    Expected: `hindcast-library-1024: 8 cases, 0 problems` and `exit 0`; then `1 problems`, a line `cloudflare-2025-11-18: listed but not allowed [], allowed but not listed [...]` naming three documents, and `exit 1`. A broken-input run that exits 0 means the check cannot fail: stop.

13. Check the chunks against the extracts.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.index check-chunks; echo "exit $?"
    ```

    Expected: `267 chunks listed, 267 counted, 0 problems` and `exit 0`.

14. Run the leak check, then its planted run.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.leak; echo "exit $?"
    PYTHONPATH=src uv run --frozen python -m hindcast.leak --plant; echo "exit $?"
    ```

    Expected: one line per case with a frozen key, each ending `0 hits`, and `exit 0`; then the same lines with `1 hits` and the planted item under each, and `exit 0`. A hit in the first run is reviewed and listed by item and source ID, never by text.

15. Run one search for the development case.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.search cloudflare-2026-02-20 "the last subset of prefixes which were withdrawn"
    ```

    Expected: `cloudflare-2026-02-20: 5 hits`, each a `lib/<doc_id>/s<n>` or `fig<n>` ref of a document published before 2026-02-20.

## Remove the Content Understanding role and the old deployment

16. Remove the role, delete gpt-5-mini, and read both back.

    ```bash
    az role assignment delete --assignee "$ME" --role "Cognitive Services Content Understanding Contributor" --scope "$RES_ID"
    az cognitiveservices account deployment delete -g "$RG" -n "$RESOURCE" --deployment-name gpt-5-mini
    az role assignment list --assignee "$ME" --scope "$RES_ID" --query "[].roleDefinitionName" -o tsv
    az cognitiveservices account deployment list -g "$RG" -n "$RESOURCE" --query "[].name" -o tsv
    ```

    Expected: `Cognitive Services OpenAI User` as the only role, and no `gpt-5-mini` in the list.

17. Retry a Content Understanding read until it is refused. The assignment list is not proof ([identity findings](../findings/identity-and-access.md)).

    ```bash
    until ! PYTHONPATH=src uv run --frozen python -c "from hindcast.extract import cu_client; cu_client().get_analyzer('hindcast_chart')" 2>/dev/null; do date -u +%TZ; sleep 120; done; echo "refused $(date -u +%TZ)"
    ```

    Expected: `refused <time>`. Not observed on 2026-11-01: reads and a defaults write kept succeeding for more than 85 minutes after the removal ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)). The next calls, on 2026-11-04 at 03:05 and 03:06 UTC, were refused; when access ended in between is not known. Until the call is refused, treat the role as still held.

## Delete the search service

18. Delete the search service when nothing needs a search any more. It bills per hour from creation; `infra/search.bicep` and steps 8 to 11 recreate it, and the index build rebuilds the indexes from the extracts.

    ```bash
    az search service delete -g "$RG" -n "$SEARCH" --yes
    az search service list -g "$RG" --query "[].name" -o tsv
    ```

    Expected: no output from either command. The search roles assigned on the service go with it. On 2026-11-04 the service held `hindcast-library-1024` and `hindcast-injection-1024`.


# Deployment: operator procedure

Status: Written on 2026-11-05 ([decision 0028](../decisions/0028-full-environment-and-live-page.md)). Steps 3 to 15 ran on 2026-11-05 ([live run](../worklogs/06-deployment.md#slice-2-live-run)); the removal and the rebuild from an empty resource group on 2026-11-06, then the fixed steps 16 and 17 ([rebuild](../worklogs/06-deployment.md#slice-2-rebuild-from-empty), [final removal](../worklogs/06-deployment.md#slice-2-final-removal)). Step 2 ran without the subscription value; step 16 ran as separate commands. The 403 for a second account in step 12 is an accepted gap ([gate](../worklogs/06-deployment.md#slice-2-gate)).

One `azd up` builds the environment, the local data tree fills it, the signed-in page runs an investigation, a challenge, and an injection copy, and `azd down` removes it. A clean clone needs the [extraction runbook](extraction.md) first for `data/sources/` and `build/`.

On this page: [Inputs and access](#inputs-and-access) · [Tools](#tools) · [Environment](#environment) · [Preview](#preview) · [Provision](#provision) · [Image](#image) · [Data](#data) · [The page](#the-page) · [Traces](#traces) · [Foundry IQ](#foundry-iq) · [Remove](#remove)

## Inputs and access

- Azure Developer CLI 1.37.2 and Bicep CLI 0.48.1 (`az bicep`), the newest stable on 2026-11-05 (CI pins Bicep 0.49.2 since 2026-11-07); Azure CLI 2.88.0; GitHub CLI; uv.
- A subscription Owner who can create app registrations; a GitHub user who can set environment secrets.
- Global Standard quota in Sweden Central of 50 thousand tokens per minute free for each of gpt-6-luna, gpt-6.1-sol, gpt-5.4-mini, and text-embedding-3-large (`az cognitiveservices usage list -l swedencentral`).
- `data/sources/` with every pinned source; `build/evidence/`, `build/extracted/library/`, `build/injection/`.
- The `azure` deployment environment, limited to `main` ([worklog 06](../worklogs/06-deployment.md)).
- No other Container Apps environment in Sweden Central (a second fails with `MaxNumberOfRegionalEnvironmentsInSubExceeded`, [troubleshooting](../troubleshooting.md#deployment-the-second-provision-fails-with-maxnumberofregionalenvironmentsinsubexceeded-2026-11-05)): `az containerapp env list --query "[?location=='Sweden Central'].name" -o tsv` prints nothing.
- Placeholders: `<subscription-id>`; `<sha>`, the commit CI pushed in step 7.
- Commands run from the repository root.

## Tools

1. Read the tool versions.

   ```bash
   azd version && az bicep version
   ```

   Expected: the versions the last run used, on 2026-11-06: `azd version 1.37.2` and `Bicep CLI version 0.48.1`. CI pins Bicep in `.github/workflows/ci.yml`.

## Environment

2. Create the azd environment `hindcast-full` (`azd down` deletes `rg-<environment>`; `hindcast` and `hindcast-app` are older groups). `HINDCAST_IMAGE` starts as a public placeholder: the registry does not exist yet.

   ```bash
   azd auth login && azd env new hindcast-full --no-prompt && azd env set AZURE_SUBSCRIPTION_ID <subscription-id> && azd env set AZURE_LOCATION swedencentral && azd env set HINDCAST_IMAGE mcr.microsoft.com/k8se/quickstart@sha256:3a4d93c34c6753f24765ab17a36f1754aee9b02082b7d9553d17697b9e8252c4 && git status --short
   ```

   Expected: a browser sign-in, then `git status` prints nothing (`.azure/` is git-ignored).

## Preview

3. Run the pre-provision hook (creates the app registration `hindcast-full`, reads the OIDC subject prefix), then preview with inline parameters (`infra/main.parameters.json` holds `${...}` placeholders only azd fills).

   ```bash
   azd hooks run preprovision && az deployment sub what-if --location swedencentral --name hindcast-full-whatif --template-file infra/main.bicep -p environmentName=hindcast-full location=swedencentral principalId="$(az ad signed-in-user show --query id -o tsv)" authClientId="$(azd env get-value AUTH_CLIENT_ID)" allowedUserObjectId="$(azd env get-value AUTH_ALLOWED_USER_OBJECT_ID)" imageName="$(azd env get-value HINDCAST_IMAGE)" githubSubjectPrefix="$(azd env get-value GITHUB_SUBJECT_PREFIX)"
   ```

   Expected: `app registration: hindcast-full (created)`, then 17 `Create` lines, all in `rg-hindcast-full`: the group, the Foundry resource with its project and four deployments, the custom role, the storage account with its blob service and four containers, Log Analytics, Application Insights, and the search service. What-if omits the app's and the roles' resources, whose inputs are other modules' outputs. Observed on 2026-11-05 with placeholder sign-in values: 17 `Create`, all in `rg-hindcast-full`.

## Provision

4. Create everything.

   ```bash
   azd provision
   ```

   Expected: `SUCCESS: Your application was provisioned in Azure`. The post-provision hook sets the redirect URI and the federated credential. Observed on 2026-11-05: `SUCCESS` in 3 minutes 51 seconds, on the third provision ([troubleshooting](../troubleshooting.md#deployment-the-first-provision-fails-with-requestconflict-on-the-foundry-project-2026-11-05)); on 2026-11-06 from an empty resource group: 15 minutes 1 second, 8 minutes 51 seconds of it the search service. On `RoleDefinitionDoesNotExist`, run `azd provision` again.

5. Read the resources back: one group, keys off, and the app identity's roles.

   ```bash
   RG=rg-hindcast-full && az resource list -g "$RG" --query "[].type" -o tsv | sort | uniq -c
   ```

   ```bash
   RG=rg-hindcast-full && az cognitiveservices account list -g "$RG" --query "[].properties.disableLocalAuth" -o tsv && az storage account list -g "$RG" --query "[].allowSharedKeyAccess" -o tsv && az search service list -g "$RG" --query "[].disableLocalAuth" -o tsv && az monitor log-analytics workspace list -g "$RG" --query "[].features.disableLocalAuth" -o tsv
   ```

   ```bash
   az role assignment list --assignee "$(azd env get-value SERVICE_WEB_IDENTITY_PRINCIPAL_ID)" --all --query "[].roleDefinitionName" -o tsv | sort
   ```

   Expected: one Foundry resource and project, one storage account, one search service, a container app, an environment, a registry, two identities, Log Analytics, and Application Insights; then `true`, `false`, `true`, `true` (Foundry, storage, search, and Log Analytics refuse keys); then `AcrPull`, `Cognitive Services OpenAI User`, `Foundry User`, `Hindcast Safety Caller (hindcast-full)`, `Search Index Data Reader`, `Storage Blob Data Contributor`, `Storage Blob Data Reader`.

## Image

6. Point the `azure` environment's secrets at the new CI identity and registry.

   ```bash
   gh secret set AZURE_CLIENT_ID --env azure --body "$(azd env get-value CI_IDENTITY_CLIENT_ID)" && gh secret set AZURE_CONTAINER_REGISTRY_NAME --env azure --body "$(azd env get-value AZURE_CONTAINER_REGISTRY_NAME)" && gh secret list --env azure && gh variable set HINDCAST_PUSH_IMAGE --body true && gh variable list
   ```

   Expected: two `Set Actions secret` lines, four names in the secret list, and `HINDCAST_PUSH_IMAGE  true` in the variable list. The variable gates the push job.

7. Push the image from `main`: CI pushes the checked image as `hindcast:<sha>` and `hindcast:main` ([decision 0029](../decisions/0029-push-the-tested-image.md)).

   ```bash
   gh workflow run CI --ref main && sleep 30 && gh run watch "$(gh run list --workflow CI --branch main --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

   Expected: the run ends green with `Push the image` as its last job.

8. Point the app at the image with a provision, not `azd deploy` (the template also sets port 8501 and the probes). From here every `azd` command passes `-e hindcast-full`.

   ```bash
   az acr repository show-tags -n "$(azd env get-value -e hindcast-full AZURE_CONTAINER_REGISTRY_NAME)" --repository hindcast -o tsv
   ```

   ```bash
   azd env set -e hindcast-full HINDCAST_IMAGE "$(azd env get-value -e hindcast-full AZURE_CONTAINER_REGISTRY_ENDPOINT)/hindcast:<sha>" && azd provision -e hindcast-full --no-prompt
   ```

   ```bash
   curl -s "$(azd env get-value -e hindcast-full SERVICE_WEB_URI)/_stcore/health"
   ```

   Expected: `main` and `<sha>`; then `SUCCESS`; then `ok`. Observed: `SUCCESS` in 6 minutes 28 seconds on 2026-11-05, and in 2 minutes 18 seconds on 2026-11-06.

## Data

9. Write the operator's settings to a git-ignored file; wait a few minutes for the roles to reach the data planes.

   ```bash
   azd env get-values -e hindcast-full | grep -E '^(HINDCAST_|AZURE_)' > .env.full && grep -c HINDCAST_ .env.full && git status --short
   ```

   Expected: `12` (the 11 settings the template outputs, and `HINDCAST_IMAGE`), and `git status` prints nothing (`.env.*` is ignored).

10. Load the data: sources checked against their hashes, extracts, runtime files with their manifest last, then both indexes.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.load
    ```

    Expected: `hindcast-library-1024` with 267 chunks, the injection index line with its planted count, then `blobs uploaded: 106, already there: 0` (42 sources, 23 extracts, 40 runtime files, and the manifest, counted locally on 2026-11-05). A second run with `--skip-index` prints `already there: 106`. Too soon after step 8 the first upload can fail with `ResourceNotFound`: wait a minute (observed once on 2026-11-06).

## The page

11. A request without a session is redirected; the health path is not.

    ```bash
    URI=$(azd env get-value -e hindcast-full SERVICE_WEB_URI) && curl -s -o /dev/null -H 'User-Agent: Mozilla/5.0' -H 'Accept: text/html' -w '%{http_code} %{redirect_url}\n' "$URI/" | cut -c1-38 && curl -s -o /dev/null -w '%{http_code}\n' "$URI/" && curl -s -o /dev/null -w '%{http_code}\n' "$URI/_stcore/health"
    ```

    Expected: `302 https://login.microsoftonline.com/`, then `401`, then `200`.

12. Sign in with the allowed account; the sidebar shows "Run an investigation" (runtime files downloaded and hashed). Run, in order, with a screenshot of each:

    1. Investigate `cloudflare-2026-02-20`. Expected: a complete run with every section, no rejected citation, and a cost.
    2. Open one finding and challenge it. Expected: a verdict with citations.
    3. Investigate `cloudflare-2026-02-20-inject-update`. Expected: the Injection test section shows the planted update `u2` shown 1 and withheld 0, followed none, outcome `pass`. Prompt Shields withheld this item in none of the `dev-v1` runs ([injection report](../../eval/injection/dev-v1/README.md)): "Withheld items: 0" is expected, and the pass is the model ignoring the instruction.

    Another account gets `403`: the auth config allows one object ID (`az containerapp auth show`). Not checked live on 2026-11-05 (accepted gap).

13. Download the runs the page stored and check each.

    ```bash
    mkdir -p build/page-runs && az storage blob download-batch --account-name "$(azd env get-value -e hindcast-full HINDCAST_STORAGE_URL | cut -d/ -f3 | cut -d. -f1)" --auth-mode login -s runs -d build/page-runs -o none && find build/page-runs -name '*.json' | sort
    ```

    Expected: one result file per investigation under `build/investigations/<case_id>/` and one per challenge under `.../challenges/`, each named by its UTC time. Then check each injection-copy run:

    ```bash
    for f in build/page-runs/build/investigations/cloudflare-2026-02-20-inject-update/*.json; do PYTHONPATH=src uv run --frozen python -m hindcast.injection check "$f"; done
    ```

    Expected: per run, `status: complete`, `followed: []`, `planted text reached the tools: {'shown': 1, 'withheld': 0}`, and `pass`, exit 0.

## Traces

14. About three minutes after the runs, count the spans per operation.

    ```bash
    APP=$(az resource show -g rg-hindcast-full -n "$(azd env get-value -e hindcast-full APPLICATIONINSIGHTS_NAME)" --resource-type Microsoft.Insights/components --query properties.AppId -o tsv) && az monitor app-insights query --apps "$APP" --offset 2h --analytics-query "dependencies | where cloud_RoleName == 'hindcast-web' | summarize spans = count(), roots = countif(name in ('investigation', 'challenge')), models = countif(name == 'model_call') by operation_Id" --query "tables[0].rows" -o tsv
    ```

    Expected: one row per investigation and challenge, each with `roots` 1 and `models` equal to the run file's `usage.model_calls`. The page's `page_view` spans are other operations ([investigator runbook](investigator.md)).

## Foundry IQ

15. Build the knowledge base's index, then set up and run each arm ([foundry-iq-v1](../../eval/retrieval/foundry-iq-v1/README.md)). The search service's roles on the Foundry resource take a few minutes.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.foundry_iq index
    ```

    ```bash
    for arm in minimal planning; do PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.foundry_iq setup --arm $arm && PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.foundry_iq quality --arm $arm; done
    ```

    Expected: `hindcast-library-1024-kb: 267 chunks`; then per arm, `19 of 34 queries scored` with its recall@5 and MRR, the count of queries with no reference, and `results-<arm>.json` written. A returned document outside a case's filter stops the run with `LibraryLeak`. Count and refusal from the code, not observed.

## Remove

16. Delete the custom role first: definitions outlive the group, an assigned one cannot be deleted, and `az role assignment list --all --role` fails on its name ([troubleshooting](../troubleshooting.md#deployment-the-custom-roles-delete-fails-with-roledefinitionhasassignments-2026-11-06)).

    ```bash
    ROLE="Hindcast Safety Caller (hindcast-full)" && RGID=$(az group show -n rg-hindcast-full --query id -o tsv) && RID=$(az role definition list --custom-role-only true --name "$ROLE" --scope "$RGID" --query "[0].name" -o tsv) && test -n "$RID" && az role assignment list --all --query "[?ends_with(roleDefinitionId, '$RID')].id" -o tsv | xargs -r az role assignment delete --ids && az role definition delete --name "$ROLE" --custom-role-only true --scope "$RGID" && az role definition list --custom-role-only true --query "[].roleName" -o tsv
    ```

    Expected: the list no longer shows `Hindcast Safety Caller (hindcast-full)`.

17. Delete the Log Analytics workspace for good, then the environment with a purge. `azd down --purge` alone leaves the workspace soft-deleted for 14 days, and the next `azd up` recovers its traces ([troubleshooting](../troubleshooting.md#deployment-a-rebuilt-environment-shows-the-removed-environments-traces-2026-11-06)).

    ```bash
    az monitor log-analytics workspace delete -g rg-hindcast-full -n log-hindcast --force true --yes && azd down -e hindcast-full --purge --force && az group exists -n rg-hindcast-full && az cognitiveservices account list-deleted --query "[].name" -o tsv && az monitor log-analytics workspace list-deleted-workspaces --query "[].name" -o tsv
    ```

    Expected: `false`, and no Hindcast name among the deleted accounts or the deleted workspaces.

18. Delete the environment's app registration, and turn the push job off.

    ```bash
    az ad app delete --id "$(azd env get-value -e hindcast-full AUTH_CLIENT_ID)" && az ad app list --display-name hindcast-full --query "[].displayName" -o tsv && gh variable delete HINDCAST_PUSH_IMAGE && gh variable list
    ```

    Expected: an empty list twice.

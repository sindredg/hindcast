# Deployment: operator procedure

Status: Rewritten on 2026-11-05 for the full environment ([decision 0028](../decisions/0028-full-environment-and-live-page.md)). Validated on 2026-11-05: steps 3 to 15 ran live, with the results in [worklog 06](../worklogs/06-deployment.md#slice-2-live-run); step 2 ran without the subscription value it now sets, and steps 4 and 8 needed the fixes below before they passed. The 403 for a second account in step 12 is an accepted gap ([gate](../worklogs/06-deployment.md#slice-2-gate)). Steps 16 to 18 have not run. The procedure it replaces, which deployed the app's resource group only, ran on 2026-10-31 ([worklog 06](../worklogs/06-deployment.md)).

The procedure builds all of Hindcast in one resource group with one `azd up`, fills it from the operator's local data tree, runs an investigation, a challenge, and an injection copy from the signed-in page, and removes it all with `azd down`. The data is the operator's: `data/sources/` and `build/` are not in the repository, so a clean clone also needs the [extraction runbook](extraction.md) first.

## Inputs and access

- Azure Developer CLI 1.37.2 and Bicep CLI 0.48.1 (through `az bicep`), the newest stable releases on 2026-11-05; Azure CLI 2.88.0; GitHub CLI; uv.
- Signed in as an Owner of the subscription who can create app registrations in the tenant, and as a GitHub user who can set the repository's environment secrets.
- Global Standard quota in Sweden Central of 50 thousand tokens per minute free for each of gpt-6-luna, gpt-6.1-sol, gpt-5.4-mini, and text-embedding-3-large (`az cognitiveservices usage list -l swedencentral`).
- The local data tree: `data/sources/` with every source the registries pin, and `build/evidence/`, `build/extracted/library/`, and `build/injection/` from the extraction and injection runbooks.
- The `azure` deployment environment on the repository, limited to `main` (created in the slice 1 procedure; [worklog 06](../worklogs/06-deployment.md)).
- No other Container Apps environment in Sweden Central: a subscription gets one per region, and a second fails the provision with `MaxNumberOfRegionalEnvironmentsInSubExceeded` ([troubleshooting](../troubleshooting.md#deployment-the-second-provision-fails-with-maxnumberofregionalenvironmentsinsubexceeded-2026-11-05)). `az containerapp env list --query "[?location=='Sweden Central'].name" -o tsv` prints nothing.
- Placeholder: `<subscription-id>` is the subscription to deploy to.
- Placeholder: `<sha>` is the commit CI pushed in step 7.
- Commands run from the repository root.

## Tools

1. Read the tool versions.

   ```bash
   azd version && az bicep version
   ```

   Expected: `azd version 1.37.2` and `Bicep CLI version 0.48.1`.

## Environment

2. Create the azd environment `hindcast-full`. Not `hindcast` or `hindcast-app`: those names belong to resource groups built before this template, and `azd down` deletes `rg-<environment>`. `HINDCAST_IMAGE` starts as a public placeholder, because the registry does not exist before the first provision. Without `AZURE_SUBSCRIPTION_ID`, `azd provision` stops to ask for the subscription.

   ```bash
   azd auth login && azd env new hindcast-full --no-prompt && azd env set AZURE_SUBSCRIPTION_ID <subscription-id> && azd env set AZURE_LOCATION swedencentral && azd env set HINDCAST_IMAGE mcr.microsoft.com/k8se/quickstart@sha256:3a4d93c34c6753f24765ab17a36f1754aee9b02082b7d9553d17697b9e8252c4 && git status --short
   ```

   Expected: a browser sign-in, then `git status` prints nothing (`.azure/` is git-ignored).

## Preview

3. Run the pre-provision hook by name, then preview. The hook creates the Entra app registration named after the environment, `hindcast-full`, and reads the repository's OIDC subject prefix from GitHub.

   ```bash
   azd hooks run preprovision && az deployment sub what-if --location swedencentral --name hindcast-full-whatif --template-file infra/main.bicep -p environmentName=hindcast-full location=swedencentral principalId="$(az ad signed-in-user show --query id -o tsv)" authClientId="$(azd env get-value AUTH_CLIENT_ID)" allowedUserObjectId="$(azd env get-value AUTH_ALLOWED_USER_OBJECT_ID)" imageName="$(azd env get-value HINDCAST_IMAGE)" githubSubjectPrefix="$(azd env get-value GITHUB_SUBJECT_PREFIX)"
   ```

   The parameters go inline: `infra/main.parameters.json` holds `${...}` placeholders that only azd fills in.

   Expected: `app registration: hindcast-full (created)`, then 17 `Create` lines, all in `rg-hindcast-full`: the group, the Foundry resource with its project and four deployments, the custom role, the storage account with its blob service and four containers, Log Analytics, Application Insights, and the search service. Nothing in `rg-hindcast` or `rg-hindcast-app`. What-if does not list the app's and the roles' resources, because their inputs are other modules' outputs. Observed with `az deployment sub what-if` on 2026-11-05 with placeholder sign-in values: 17 `Create`, all in `rg-hindcast-full`.

## Provision

4. Create everything. The deployments are created one at a time; the role assignments come last.

   ```bash
   azd provision
   ```

   Expected: `SUCCESS: Your application was provisioned in Azure`. The post-provision hook sets the registration's redirect URI and the app identity's federated credential. Observed on 2026-11-05: `SUCCESS` in 3 minutes 51 seconds, on the third provision, after the two fixes in [troubleshooting](../troubleshooting.md#deployment-the-first-provision-fails-with-requestconflict-on-the-foundry-project-2026-11-05). A failure that names `RoleDefinitionDoesNotExist` means the new custom role had not replicated when its assignments ran (the [investigator runbook](investigator.md) retries the same assignment by hand); run `azd provision` again.

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

6. Point the `azure` environment's secrets at the new CI identity and registry. The tenant and subscription stay the same.

   ```bash
   gh secret set AZURE_CLIENT_ID --env azure --body "$(azd env get-value CI_IDENTITY_CLIENT_ID)" && gh secret set AZURE_CONTAINER_REGISTRY_NAME --env azure --body "$(azd env get-value AZURE_CONTAINER_REGISTRY_NAME)" && gh secret list --env azure
   ```

   Expected: two `Set Actions secret` lines and four names in the list.

7. Push the image from `main`. CI writes the provenance manifest, builds and checks the image, and, once every check job has passed, pushes that same image as `hindcast:<sha>` and `hindcast:main` ([decision 0029](../decisions/0029-push-the-tested-image.md)).

   ```bash
   gh workflow run CI --ref main && sleep 30 && gh run watch "$(gh run list --workflow CI --branch main --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

   Expected: the run ends green with `Push the image` as its last job.

8. Point the app at the pushed image. A provision, not `azd deploy`: the template also moves the port to 8501 and adds the probes. Every `azd` command from here on names the environment with `-e hindcast-full`, so it cannot act on another environment that is azd's default.

   ```bash
   az acr repository show-tags -n "$(azd env get-value -e hindcast-full AZURE_CONTAINER_REGISTRY_NAME)" --repository hindcast -o tsv
   ```

   ```bash
   azd env set -e hindcast-full HINDCAST_IMAGE "$(azd env get-value -e hindcast-full AZURE_CONTAINER_REGISTRY_ENDPOINT)/hindcast:<sha>" && azd provision -e hindcast-full --no-prompt
   ```

   ```bash
   curl -s "$(azd env get-value -e hindcast-full SERVICE_WEB_URI)/_stcore/health"
   ```

   Expected: `main` and `<sha>`; then `SUCCESS`; then `ok`. Observed on 2026-11-05: `SUCCESS` in 6 minutes 28 seconds.

## Data

9. Write the operator's settings for the new environment into a git-ignored file, then wait for the operator's roles to reach the data planes (a few minutes after the provision).

   ```bash
   azd env get-values -e hindcast-full | grep -E '^(HINDCAST_|AZURE_)' > .env.full && grep -c HINDCAST_ .env.full && git status --short
   ```

   Expected: `12` (the 11 settings the template outputs, and `HINDCAST_IMAGE`), and `git status` prints nothing (`.env.*` is ignored).

10. Load the data: every source checked against its registry hash, the extracts, the runtime files with their manifest last, then the library index and the injection index.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.load
    ```

    Expected: `hindcast-library-1024` with 267 chunks, the injection index line with its planted count, then `blobs uploaded: 106, already there: 0` (42 sources, 23 extracts, 40 runtime files, and the manifest, counted locally on 2026-11-05). A second run prints `already there: 106` with `--skip-index`.

## The page

11. A request without a session is redirected; the health path is not.

    ```bash
    URI=$(azd env get-value -e hindcast-full SERVICE_WEB_URI) && curl -s -o /dev/null -H 'User-Agent: Mozilla/5.0' -H 'Accept: text/html' -w '%{http_code} %{redirect_url}\n' "$URI/" | cut -c1-38 && curl -s -o /dev/null -w '%{http_code}\n' "$URI/" && curl -s -o /dev/null -w '%{http_code}\n' "$URI/_stcore/health"
    ```

    Expected: `302 https://login.microsoftonline.com/`, then `401`, then `200`.

12. In a browser, sign in with the allowed account. The sidebar shows "Run an investigation" (the runtime files downloaded and passed their hashes). Run, in order, and take a screenshot of each result:

    1. Investigate `cloudflare-2026-02-20`. Expected: a complete run with every section, no rejected citation, and a cost.
    2. Open one finding and challenge it. Expected: a verdict with citations.
    3. Investigate `cloudflare-2026-02-20-inject-update`. Expected: the Injection test section shows the planted update `u2` shown 1 and withheld 0, followed none, and the outcome `pass`. Prompt Shields does not flag this planted instruction: with the screens on, it withheld the planted item in none of the `dev-v1` runs that returned it ([injection report](../../eval/injection/dev-v1/README.md)), so the checks' "Withheld items: 0" is the expected value, and the model ignoring the instruction is the pass.

    Another account from the tenant gets `403`: the auth config allows one object ID (`az containerapp auth show`). Not checked live on 2026-11-05 (accepted gap).

13. Download the runs the page stored, and check each one's status and the withheld item.

    ```bash
    mkdir -p build/page-runs && az storage blob download-batch --account-name "$(azd env get-value -e hindcast-full HINDCAST_STORAGE_URL | cut -d/ -f3 | cut -d. -f1)" --auth-mode login -s runs -d build/page-runs -o none && find build/page-runs -name '*.json' | sort
    ```

    Expected: one result file per investigation under `build/investigations/<case_id>/` and one file per challenge under `.../challenges/`, each named by its UTC time. Then the injection check on each injection-copy run prints its outcome:

    ```bash
    for f in build/page-runs/build/investigations/cloudflare-2026-02-20-inject-update/*.json; do PYTHONPATH=src uv run --frozen python -m hindcast.injection check "$f"; done
    ```

    Expected: per run, `status: complete`, `followed: []`, `planted text reached the tools: {'shown': 1, 'withheld': 0}`, and `pass`, exit 0.

## Traces

14. Each run is one trace with its root span. Wait about three minutes after the runs, then count the spans per operation.

    ```bash
    APP=$(az resource show -g rg-hindcast-full -n "$(azd env get-value -e hindcast-full APPLICATIONINSIGHTS_NAME)" --resource-type Microsoft.Insights/components --query properties.AppId -o tsv) && az monitor app-insights query --apps "$APP" --offset 2h --analytics-query "dependencies | where cloud_RoleName == 'hindcast-web' | summarize spans = count(), roots = countif(name in ('investigation', 'challenge')), models = countif(name == 'model_call') by operation_Id" --query "tables[0].rows" -o tsv
    ```

    Expected: one row per investigation and challenge, each with `roots` 1 and `models` equal to the run file's `usage.model_calls`. The spans are in `dependencies`, as in the [investigator runbook](investigator.md); the page opens its own `page_view` spans in other operations.

## Foundry IQ

15. Build the knowledge base's index, then set up and run each arm ([foundry-iq-v1](../../eval/retrieval/foundry-iq-v1/README.md)). The search service's roles on the Foundry resource can take a few minutes to apply.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.foundry_iq index
    ```

    ```bash
    for arm in minimal planning; do PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.foundry_iq setup --arm $arm && PYTHONPATH=src uv run --frozen --env-file .env.full python -m hindcast.foundry_iq quality --arm $arm; done
    ```

    Expected: `hindcast-library-1024-kb: 267 chunks`; then per arm, `19 of 34 queries scored` with its recall@5 and MRR, and `results-<arm>.json` written.

## Remove

16. Delete the custom role first: role definitions are not deleted with the resource group, and an assigned one cannot be deleted. Its assignments go, then the definition, while its scope still exists.

    ```bash
    ROLE="Hindcast Safety Caller (hindcast-full)" && az role assignment list --all --role "$ROLE" --query "[].id" -o tsv | xargs -r az role assignment delete --ids && az role definition delete --name "$ROLE" --custom-role-only true --scope "$(az group show -n rg-hindcast-full --query id -o tsv)" && az role definition list --custom-role-only true --query "[].roleName" -o tsv
    ```

    Expected: the list no longer shows `Hindcast Safety Caller (hindcast-full)`.

17. Remove the environment, purging the soft-deleted Foundry resource, and check that nothing is left.

    ```bash
    azd down -e hindcast-full --purge --force && az group exists -n rg-hindcast-full && az cognitiveservices account list-deleted --query "[].name" -o tsv
    ```

    Expected: `false`, and no Hindcast name among the deleted accounts.

18. Delete the environment's app registration.

    ```bash
    az ad app delete --id "$(azd env get-value -e hindcast-full AUTH_CLIENT_ID)" && az ad app list --display-name hindcast-full --query "[].displayName" -o tsv
    ```

    Expected: an empty list.

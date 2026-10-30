# Deployment: operator procedure

Status: Written on 2026-10-30 for [milestone 6, slice 1](../worklogs/06-deployment.md). Steps marked "Expected, as observed" ran on the date given with the output shown; the others are reasoned from the templates and not yet run.

The procedure deploys the Hindcast page to Azure Container Apps from one `azd up`, with Entra sign-in and telemetry, from an image CI builds. It creates nothing in the resource group that holds Foundry and the storage account; it reads two resources there by name ([decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md)).

## Inputs and access

- The [foundations runbook](foundations.md) completed: the Foundry resource with its Application Insights and Log Analytics resources, and the GitHub repository with its ruleset.
- Azure Developer CLI 1.37.2, Bicep CLI 0.48.1 (through `az bicep`), Azure CLI, GitHub CLI.
- Signed in as an Owner of the subscription who can create app registrations in the tenant, and as a GitHub user who can set repository secrets and the ruleset.
- Placeholders: `<app-insights>` and `<log-analytics>` are the resource names from the foundations runbook; `<registry>` and `<sha>` come from steps 5 and 9.
- Commands run from the repository root.

## Tools

1. Install or update the two tools and read their versions back.

   ```bash
   curl -fsSL https://aka.ms/install-azd.sh | bash && azd version
   ```

   ```bash
   az bicep upgrade && az bicep version
   ```

   Expected: `azd version 1.37.2` and `Bicep CLI version 0.48.1`.

## Environment

2. Create the azd environment. Its files live under `.azure/`, which is git-ignored because they hold real resource names.

   ```bash
   azd auth login && azd env new hindcast-app --no-prompt && azd env set AZURE_LOCATION swedencentral && azd env set APPLICATIONINSIGHTS_NAME <app-insights> && azd env set LOG_ANALYTICS_NAME <log-analytics> && azd env set HINDCAST_IMAGE_TAG main && git status --short
   ```

   Expected: a browser sign-in, then `git status` prints nothing.

## Preview

3. Preview the deployment. The pre-provision hook creates the Entra app registration `hindcast-app` (single tenant, ID tokens on) and writes its IDs into the azd environment; the what-if then lists what Bicep would create.

   ```bash
   azd provision --preview
   ```

   Expected: `app registration: hindcast-app (created)`, then a what-if with `rg-hindcast-app` and eleven resources as Create (two identities and a federated credential, the registry and two role assignments, the environment and its diagnostic setting, the container app and its auth config) and no change in the other resource group.

## Provision

4. Create the resources. The container app starts on a public placeholder image until CI has pushed the app image (step 9). The post-provision hook adds the app's redirect URI to the registration and the federated credential that lets the app's identity sign in without a client secret.

   ```bash
   azd provision
   ```

   Expected: `SUCCESS: Your application was provisioned in Azure`, with `redirect uri: added` and `federated credential: created` from the hook.

5. Read the resources back and check that the one container secret is the override name, whose value is the identity's client ID, not a credential.

   ```bash
   az resource list -g rg-hindcast-app --query "[].type" -o tsv | sort | uniq -c
   ```

   ```bash
   az containerapp secret list -n ca-hindcast -g rg-hindcast-app --query "[].name" -o tsv && azd env get-value AZURE_CONTAINER_REGISTRY_NAME
   ```

   Expected: one line per type (`Microsoft.App/containerApps`, `Microsoft.App/managedEnvironments`, `Microsoft.ContainerRegistry/registries`, two `Microsoft.ManagedIdentity/userAssignedIdentities`); then `override-use-mi-fic-assertion-client-id` and the registry name (`<registry>`).

## Sign-in

6. A request without a session is redirected to sign-in; the health path is not.

   ```bash
   URI=$(azd env get-value SERVICE_WEB_URI) && curl -sI "$URI/" | grep -i '^location' && curl -sIL "$URI/" | grep -i '^location' | tail -1 && curl -s -o /dev/null -w '%{http_code}\n' "$URI/_stcore/health"
   ```

   Expected: a `Location: /.auth/login/aad?...` line, then one that starts `location: https://login.microsoftonline.com/`, then a status that is not `302` (`404` on the placeholder image, `200` once the app image runs).

7. Open the URL in a browser and sign in with the deploying account. Another account from the tenant gets `403`.

   Expected: the placeholder page (step 4) or the Hindcast page (step 10).

   If the sign-in page returns an error that names an invalid client secret, the federated path did not work on this platform. Fall back to a client secret, which the template stores as the container secret `microsoft-provider-authentication-secret`:

   ```bash
   azd env set AUTH_CLIENT_SECRET "$(az ad app credential reset --id "$(azd env get-value AUTH_CLIENT_ID)" --years 0.1 --query password -o tsv)" && azd provision
   ```

   Then repeat step 6 and record the path that worked in the worklog.

## Image

8. Create the `azure` deployment environment on the repository, limited to `main`, and set its four secrets. They hold IDs and a resource name, not credentials; the push step signs in with the workflow's OIDC token.

   ```bash
   gh api -X PUT repos/sindredg/hindcast/environments/azure --input - <<'EOF'
   {"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
   EOF
   ```

   ```bash
   gh api -X POST repos/sindredg/hindcast/environments/azure/deployment-branch-policies -f name=main -f type=branch --jq '.name'
   ```

   ```bash
   gh secret set AZURE_CLIENT_ID --env azure --body "$(azd env get-value CI_IDENTITY_CLIENT_ID)" && gh secret set AZURE_TENANT_ID --env azure --body "$(az account show --query tenantId -o tsv)" && gh secret set AZURE_SUBSCRIPTION_ID --env azure --body "$(az account show --query id -o tsv)" && gh secret set AZURE_CONTAINER_REGISTRY_NAME --env azure --body "$(azd env get-value AZURE_CONTAINER_REGISTRY_NAME)" && gh secret list --env azure
   ```

   Expected: the environment JSON, then `main`, then four secret names.

9. Push the image: merge the pull request that carries this runbook, or run the workflow on `main` by hand. The `Push the image` job builds the image and pushes `hindcast:<sha>` and `hindcast:main`.

   ```bash
   gh workflow run CI --ref main && sleep 30 && gh run watch "$(gh run list --workflow CI --branch main --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

   ```bash
   az acr repository show-tags -n <registry> --repository hindcast -o tsv
   ```

   Expected: the run ends green with `Push the image` as its last job, and the tag list holds `main` and a commit SHA (`<sha>`).

## Deploy

10. Point the container app at the pushed image.

    ```bash
    azd env set HINDCAST_IMAGE_TAG <sha> && azd deploy
    ```

    ```bash
    az containerapp revision list -n ca-hindcast -g rg-hindcast-app --query "[?properties.active].properties.healthState" -o tsv && curl -s "$(azd env get-value SERVICE_WEB_URI)/_stcore/health"
    ```

    Expected: `SUCCESS: Your application was deployed to Azure`, then `Healthy` and `ok`. In the browser, after sign-in, the Hindcast page shows the development-case result and an expander opens (the WebSocket is through).

## Telemetry

11. Load the page once, wait about three minutes, then look for the page-view span.

    ```bash
    az monitor app-insights query -g rg-hindcast -a <app-insights> --analytics-query "union requests, dependencies, traces | where timestamp > ago(30m) | where name == 'page_view' or operation_Name == 'page_view' | project timestamp, itemType, name | take 5" --query "tables[0].rows" -o tsv
    ```

    Expected: at least one row with `page_view`.

## Remove and rebuild

12. Remove everything azd created, confirm the other resource group is untouched, and build it again. The hooks are idempotent (`found`, `present`, `updated`). The CI identity is new after a rebuild, so step 8's `AZURE_CLIENT_ID` is set again.

    ```bash
    azd down --purge --force && az group exists -n rg-hindcast-app && az group show -n rg-hindcast --query properties.provisioningState -o tsv
    ```

    ```bash
    azd up
    ```

    Expected: `false` and `Succeeded`, then a second provision with the same resource names.

## Teardown

13. At the end of the project: `azd down --purge --force`, then delete the app registration, and check that the agent-identity registrations Foundry created with the investigator agent go with the Foundry resource.

    ```bash
    az ad app delete --id "$(azd env get-value AUTH_CLIENT_ID)" && az ad app list --display-name hindcast --query "[].displayName" -o tsv
    ```

    Expected: no `hindcast-app` in the list.

## Ruleset

14. After this pull request's first green run of `Image and infrastructure`, make it the fourth required check: run the [foundations runbook](foundations.md) step 2 JSON with `PUT` against the existing ruleset instead of `POST` to create one.

    ```bash
    gh api -X PUT "repos/sindredg/hindcast/rulesets/<ruleset-id>" --input ruleset.json --jq '[.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context] | join(", ")'
    ```

    Expected: `Python lint and tests, YAML and workflow lint, Dependency audit, Image and infrastructure`.

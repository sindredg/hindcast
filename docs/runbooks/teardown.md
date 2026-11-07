# Teardown: operator procedure

Status: Validated on 2026-11-07: steps 1, 2, and 4 to 10 ran with the output shown ([close worklog](../worklogs/07-close.md#teardown)). Step 3 did not run as a step; the agents went with the resource in step 6 and their registrations in step 8.

Removes what the [foundations](foundations.md), [extraction](extraction.md), [investigator](investigator.md), and [retrieval](retrieval.md) runbooks built by hand: the resource group and its contents, the agents, the custom role, the developer's role assignments, and the app registration from milestone 6's first slice. Run the full environment's removal first if it exists ([deployment runbook](deployment.md#remove)). Nothing is reversible; the sealed files of pending cases are in Blob Storage until step 6, so steps 1 and 2 are not optional.

## Inputs and access

- `az login` as a subscription Owner who can delete role assignments and app registrations.
- The repository root with `.env`, `build/sealed/`, and `~/backups/hindcast/`. Local values:

```bash
export RG=<resource-group> RESOURCE=<foundry-resource> STORAGE=<storage-account> WORKSPACE=<log-analytics-workspace> APP=<app-registration-client-id>
```

## Before anything is deleted

1. Check every sealed file against its committed hash, locally and in the backup archive.

   ```bash
   D=$(mktemp -d) && tar -xzf ~/backups/hindcast/sealed-*.tgz -C "$D" && python3 - "$D" <<'EOF'
   import hashlib, json, pathlib, sys
   bk = {p.name: p for p in pathlib.Path(sys.argv[1]).rglob("*.json")}
   seals = json.load(open("eval/sealed/seals.json"))["seals"]
   h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
   ok = sum(h(pathlib.Path("build/sealed") / s["case_id"] / s["file"]) == s["sha256"] == h(bk[s["file"]]) for s in seals)
   print(ok, "of", len(seals), "match local and backup")
   EOF
   ```

   Expected: `16 of 16 match local and backup`. Observed on 2026-11-07. A differing or missing copy stops the procedure.

2. Download every blob into a dated folder and compare with the local tree by hash; the answer-key analyzer results under `extracted/keys/` exist only here.

   ```bash
   B=~/backups/hindcast/blob-$(date -u +%Y%m%d) && for c in sources extracted; do mkdir -p "$B/$c" && az storage blob download-batch --account-name "$STORAGE" --auth-mode login -s "$c" -d "$B/$c" --no-progress -o tsv | wc -l; done
   ```

   Expected: one count per container. Observed on 2026-11-07: `39` and `57`, 96 files, 6.9 MB; by hash, 91 matched a local copy under `data/sources/` or `build/`, none differed, and 5 (`extracted/keys/*-result.json`) had no local copy.

## Remove

3. Delete the agents (the investigator runbook lists them).

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; c=project_client(); names=[a.name for a in c.agents.list()]; [print(c.agents.delete(n)) for n in names]; print('remaining', [a.name for a in c.agents.list()])"
   ```

   Expected (reasoned from the spike agent's deletion on 2026-10-30, not run on these agents): one deletion record per agent (six on 2026-11-07: two investigators, two challengers, two arm agents) and `remaining []`. Skipped on 2026-11-07: the agents went in step 6, their registrations in step 8.

4. Delete the custom role's assignment, then the role, while its scope exists ([troubleshooting](../troubleshooting.md#deployment-the-custom-roles-delete-fails-with-roledefinitionhasassignments-2026-11-06)).

   ```bash
   RGID=$(az group show -n "$RG" --query id -o tsv) && RID=$(az role definition list --custom-role-only true --name "Hindcast Safety Caller" --scope "$RGID" --query "[0].name" -o tsv) && test -n "$RID" && az role assignment list --all --query "[?ends_with(roleDefinitionId, '$RID')].id" -o tsv | xargs -r az role assignment delete --ids && az role definition delete --name "Hindcast Safety Caller" --custom-role-only true --scope "$RGID" && az role definition list --custom-role-only true --query "[].roleName" -o tsv
   ```

   Expected: no output. `test -n` guards against an empty ID, which would match every assignment.

5. Delete the developer's data-plane assignments in the group (Foundry User, Storage Blob Data Contributor, Cognitive Services OpenAI User).

   ```bash
   test -n "$RG" && az role assignment list --all --query "[?contains(scope, '/resourceGroups/$RG/')].id" -o tsv | xargs -r az role assignment delete --ids && az role assignment list --all --query "[?contains(scope, '$RG')].roleDefinitionName" -o tsv
   ```

   Expected: no output.

6. Delete the Log Analytics workspace for good, then the resource group. A plain group delete leaves the workspace soft-deleted for 14 days ([troubleshooting](../troubleshooting.md#deployment-a-rebuilt-environment-shows-the-removed-environments-traces-2026-11-06)).

   ```bash
   az monitor log-analytics workspace delete -g "$RG" -n "$WORKSPACE" --force true --yes && az group delete -n "$RG" --yes && az group exists -n "$RG"
   ```

   Expected: `false`, after some minutes. Observed on 2026-11-07: the group was gone 2m11s after the workspace.

7. Purge the soft-deleted Foundry resource and check that no deleted account or workspace is left.

   ```bash
   az cognitiveservices account purge -l swedencentral -g "$RG" -n "$RESOURCE" && az cognitiveservices account list-deleted --query "[].name" -o tsv && az monitor log-analytics workspace list-deleted-workspaces --query "[].name" -o tsv
   ```

   Expected: no names printed.

8. Delete the app registration from milestone 6's first slice, then list Foundry's agent identity registrations (`<resource>-<project>-...-AgentIdentityBlueprint`, one per agent plus one for the project). Read the list before deleting.

   ```bash
   az ad app delete --id "$APP" && az ad app list --all --query "[?starts_with(displayName, '$RESOURCE-')].displayName" -o tsv
   ```

   Expected: the project's blueprint registrations only. On 2026-11-07 six remained after step 7 (eleven existed before it). Then delete them:

   ```bash
   az ad app list --all --query "[?starts_with(displayName, '$RESOURCE-')].appId" -o tsv | xargs -r -n1 az ad app delete --id; az ad app list --all --query "[?starts_with(displayName, '$RESOURCE-') || displayName=='hindcast-app'].displayName" -o tsv
   ```

   Expected: no output from the final list.

9. Final check: nothing named after the project, no custom role, no assignment to an unknown principal.

   ```bash
   az resource list --query "[?contains(name, 'hindcast')].name" -o tsv; az role definition list --custom-role-only true --query "[].roleName" -o tsv; az role assignment list --all --query "[?principalType=='Unknown' || principalName==''].id" -o tsv
   ```

   Expected: three empty results. Observed on 2026-11-07 at 12:35:50Z.

10. Remove the `azure` environment's secrets (IDs, not credentials) and the push variable, if the deployment runbook's step 18 has not.

    ```bash
    for s in $(gh secret list --env azure --json name --jq '.[].name'); do gh secret delete "$s" --env azure; done; gh secret list --env azure; gh variable delete HINDCAST_PUSH_IMAGE 2>/dev/null; gh variable list
    ```

    Expected: two empty lists. Observed on 2026-11-07: four `Deleted secret` lines, then `no secrets found`; the variable was never set in this repository.

`.env` is kept for the names it records. The local data tree, the backups, and the repository hold everything the [reproduce page](../reproduce.md) needs.

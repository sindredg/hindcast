# Teardown: operator procedure

Status: Written on 2026-11-07. Steps 1 and 2 ran on 2026-11-07 with the output shown; steps 3 to 9 are written from the removal that ran for the full environment ([deployment runbook](deployment.md#remove)) and the live inventory of 2026-11-07, and their expected values are reasoned until the [close worklog](../worklogs/07-close.md#teardown) records the run.

The procedure removes everything the [foundations](foundations.md), [extraction](extraction.md), [investigator](investigator.md), and [retrieval](retrieval.md) runbooks built by hand: the resource group with the Foundry resource and project, the storage account, Application Insights and its workspace, the agents, the custom role, the developer's role assignments, and the app registration from milestone 6's first slice. The full environment has its own removal ([deployment runbook](deployment.md#remove)); run that first if it exists.

Nothing here is reversible. The sealed files for the cases still waiting on a cause live in Blob Storage until step 6, so steps 1 and 2 come first and are not optional.

## Inputs and access

- Signed in with `az login` as an Owner of the subscription, who can delete role assignments and app registrations.
- The repository root with `.env` from the foundations runbook (the Python step reads the project endpoint from it) and the local data tree: `build/sealed/` and `~/backups/hindcast/` for step 1.
- Local values set once:

```bash
export RG=<resource-group> RESOURCE=<foundry-resource> STORAGE=<storage-account> WORKSPACE=<log-analytics-workspace> APP=<app-registration-client-id>
```

## Before anything is deleted

1. Check every sealed file against its committed hash, locally and in the backup archive. The reveal of a pending case depends on these copies once the storage account is gone.

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

   Expected: `16 of 16 match local and backup`. Observed on 2026-11-07. A copy that differs or is missing stops the procedure here.

2. Download every blob into a dated folder and compare it with the local tree by hash. A file that exists only in Blob Storage (the answer-key analyzer results under `extracted/keys/`) is kept by this copy alone.

   ```bash
   B=~/backups/hindcast/blob-$(date -u +%Y%m%d) && for c in sources extracted; do mkdir -p "$B/$c" && az storage blob download-batch --account-name "$STORAGE" --auth-mode login -s "$c" -d "$B/$c" --no-progress -o tsv | wc -l; done
   ```

   Expected: one count per container. Observed on 2026-11-07: `39` and `57`, 96 files, 6.9 MB; by hash, 91 matched a local copy under `data/sources/` or `build/`, none differed, and 5 (`extracted/keys/*-result.json`) had no local copy.

## Remove

3. Delete the agents. The names come from the project; the investigator runbook lists them.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; c=project_client(); names=[a.name for a in c.agents.list()]; [print(c.agents.delete(n)) for n in names]; print('remaining', [a.name for a in c.agents.list()])"
   ```

   Expected: one deletion record per agent (six on 2026-11-07: the two investigators, the two challengers, and the two arm agents) and `remaining []`.

4. Delete the custom role's assignment, then the role, while its scope exists. An assigned role definition cannot be deleted ([troubleshooting](../troubleshooting.md#deployment-the-custom-roles-delete-fails-with-roledefinitionhasassignments-2026-11-06)).

   ```bash
   RGID=$(az group show -n "$RG" --query id -o tsv) && RID=$(az role definition list --custom-role-only true --name "Hindcast Safety Caller" --scope "$RGID" --query "[0].name" -o tsv) && az role assignment list --all --query "[?ends_with(roleDefinitionId, '$RID')].id" -o tsv | xargs -r az role assignment delete --ids && az role definition delete --name "Hindcast Safety Caller" --custom-role-only true --scope "$RGID" && az role definition list --custom-role-only true --query "[].roleName" -o tsv
   ```

   Expected: no output.

5. Delete the developer's data-plane assignments in the group (Foundry User on the project, Storage Blob Data Contributor on the storage account, Cognitive Services OpenAI User on the Foundry resource), so none is left behind as an assignment to a deleted scope.

   ```bash
   az role assignment list --all --query "[?contains(scope, '$RG')].id" -o tsv | xargs -r az role assignment delete --ids && az role assignment list --all --query "[?contains(scope, '$RG')].roleDefinitionName" -o tsv
   ```

   Expected: no output.

6. Delete the Log Analytics workspace for good, then the resource group. A plain group delete leaves the workspace soft-deleted for 14 days ([troubleshooting](../troubleshooting.md#deployment-a-rebuilt-environment-shows-the-removed-environments-traces-2026-11-06)).

   ```bash
   az monitor log-analytics workspace delete -g "$RG" -n "$WORKSPACE" --force true --yes && az group delete -n "$RG" --yes && az group exists -n "$RG"
   ```

   Expected: `false`, after some minutes.

7. Purge the soft-deleted Foundry resource and check that no deleted account or workspace is left.

   ```bash
   az cognitiveservices account purge -l swedencentral -g "$RG" -n "$RESOURCE" && az cognitiveservices account list-deleted --query "[].name" -o tsv && az monitor log-analytics workspace list-deleted-workspaces --query "[].name" -o tsv
   ```

   Expected: no names printed.

8. Delete the app registration from milestone 6's first slice, and any registration Foundry made for the agents' identities (`...-AgentIdentityBlueprint`, one per agent plus one for the project).

   ```bash
   az ad app delete --id "$APP" && az ad app list --query "[?starts_with(displayName, 'hindcast') || contains(displayName, 'AgentIdentityBlueprint')].appId" -o tsv | xargs -r -n1 az ad app delete --id; az ad app list --query "[?starts_with(displayName, 'hindcast') || contains(displayName, 'AgentIdentityBlueprint')].displayName" -o tsv
   ```

   Expected: no output from the final list.

9. Final check: nothing named after the project in the subscription, no custom role, and no assignment to an unknown principal.

   ```bash
   az resource list --query "[?contains(name, 'hindcast')].name" -o tsv; az role definition list --custom-role-only true --query "[].roleName" -o tsv; az role assignment list --all --query "[?principalType=='Unknown' || principalName==''].id" -o tsv
   ```

   Expected: three empty results.

After the teardown, `.env` points at nothing; it is kept for the names it records. The local data tree, the backup folders, and the repository hold everything the [reproduce page](../reproduce.md) needs.

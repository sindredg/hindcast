# Foundations: operator procedure

Status: Written on 2026-10-25 for [milestone 1](../worklogs/01-foundations.md); "Re-check the model choice" added on 2026-10-26, after its steps ran on 2026-10-25 (steps 1 and 2) and 2026-10-26 (steps 3 to 8; in step 3 the role was assigned once and the check ran in this form afterwards). Every step ran once with the results the worklog records, but not in this order: the Azure foundation was created on 2026-10-24 and 2026-10-25 before the repository existed, and key access on the Foundry resource (step 4 under "Create the Azure foundation") was turned off before the prior-knowledge answers were collected. The Foundry resource, project, and deployments were created in the Foundry portal as it was that day. Not run again from an empty subscription. "Check the repository" gained pyright on 2026-10-28 and ran in this form on 2026-10-30.

Build the milestone 1 foundation from scratch: the repository checks, the GitHub repository and its protection, the Azure resources and roles, the case sources, and the prior-knowledge answers. [Decision 0009](../decisions/0009-hosting-and-identity.md) records why every call uses Entra ID and no keys.

## Prerequisites

- An Azure subscription where you can create resources and assign roles (Owner, or Contributor plus User Access Administrator).
- Global Standard quota in Sweden Central of at least 50,000 tokens per minute for gpt-6-luna and for gpt-6.1-sol (`az cognitiveservices usage list -l swedencentral`).
- An operator machine with Git, [uv](https://docs.astral.sh/uv/), the Azure CLI (2.88.0 used), the GitHub CLI, `openssl`, and a browser. Sign in with `az login` and `gh auth login`. Commits are signed (`git config commit.gpgsign true` with an SSH or GPG signing key).
- A clone of the repository. Run every command from its root.

Set the local values once per shell. Pick a globally unique storage account name (3 to 24 lowercase letters and digits). `GH_REPO` is also the repository the GitHub CLI uses by default:

```bash
export RG=<resource-group> STORAGE=<storage-account> GH_REPO=<owner>/hindcast
```

## Check the repository

1. Install the locked environment and run the checks.

   ```bash
   uv sync --frozen
   uv run --frozen ruff check . && uv run --frozen ruff format --check .
   uv run --frozen pyright
   uv run --frozen yamllint --strict .
   uv run --frozen pytest -q
   ```

   Expected: `All checks passed!`, `files already formatted`, `0 errors` from pyright, no yamllint output, and all tests passed.

## Protect the repository on GitHub

1. Create the repository empty and push `main`.

   ```bash
   gh repo create "$GH_REPO" --public --description "Evidence-grounded AI investigations of infrastructure outages."
   git remote add origin "https://github.com/$GH_REPO.git"
   git push -u origin main
   ```

   Expected: `git ls-remote origin main` prints the commit of your local `main`, and the CI run on it is green (`gh run list --workflow CI --limit 1`).

2. Add the branch ruleset: enforcement active, no bypass list, restrict deletions, block force pushes, require signed commits, require a pull request before merging (squash or rebase, threads resolved), and require the three CI checks with the branch up to date.

   ```bash
   cat > ruleset.json <<'EOF'
   {"name": "main", "target": "branch", "enforcement": "active", "bypass_actors": [],
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [
     {"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "required_signatures"},
     {"type": "pull_request", "parameters": {"required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false, "require_code_owner_review": false,
      "require_last_push_approval": false, "required_review_thread_resolution": true,
      "allowed_merge_methods": ["squash", "rebase"]}},
     {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false, "required_status_checks": [
       {"context": "Python lint and tests", "integration_id": 15368},
       {"context": "YAML and workflow lint", "integration_id": 15368},
       {"context": "Dependency audit", "integration_id": 15368}]}}]}
   EOF
   gh api -X POST "repos/$GH_REPO/rulesets" --input ruleset.json --jq '.name + " " + .enforcement'
   rm ruleset.json
   gh api "repos/$GH_REPO/rules/branches/main" --jq '[.[].type] | join(",")'
   ```

   Expected: `main active`, then `deletion,non_fast_forward,required_signatures,pull_request,required_status_checks`. `15368` is the GitHub Actions app, so only checks from Actions count. A full read-back (`gh api "repos/$GH_REPO/rulesets/<ruleset-id>"`) also lists `require_extra_approval_for_unattributed_changes: true` and `required_reviewers: []` under the pull request rule: GitHub defaults that this JSON does not set.

3. Turn on secret scanning, push protection, Dependabot alerts, and Dependabot security updates, then read them back.

   ```bash
   gh api -X PATCH "repos/$GH_REPO" -F 'security_and_analysis[secret_scanning][status]=enabled' -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled' --silent
   gh api -X PUT "repos/$GH_REPO/vulnerability-alerts" --silent
   gh api -X PUT "repos/$GH_REPO/automated-security-fixes" --silent
   gh api "repos/$GH_REPO" --jq '.security_and_analysis | to_entries | map(.key + "=" + .value.status) | join(" ")'
   gh api -i "repos/$GH_REPO/vulnerability-alerts" | head -1
   ```

   Expected: `dependabot_security_updates=enabled`, `secret_scanning=enabled`, and `secret_scanning_push_protection=enabled` in the first line, and `HTTP/2.0 204` (Dependabot alerts on) from the second.

4. Check that a direct push to `main` is refused.

   ```bash
   git switch -c push-test && git commit -S --allow-empty -m "test: direct push"
   git push origin push-test:main; git switch main && git branch -D push-test
   ```

   Expected: `GH013: Repository rule violations found for refs/heads/main` and `[remote rejected]`; `git ls-remote origin main` is unchanged.

## Create the Azure foundation

1. Register the resource providers the project uses.

   ```bash
   for p in Microsoft.CognitiveServices Microsoft.Storage Microsoft.Insights Microsoft.OperationalInsights Microsoft.Search Microsoft.App Microsoft.ContainerRegistry Microsoft.KeyVault; do
     az provider register --namespace "$p"
   done
   az provider show -n Microsoft.CognitiveServices --query registrationState -o tsv
   ```

   Expected: `Registered` (repeat the last command after a few minutes if it says `Registering`).

2. Create the resource group.

   ```bash
   az group create --name "$RG" --location swedencentral --query properties.provisioningState -o tsv
   ```

   Expected: `Succeeded`.

3. Create the Foundry resource and project in the portal. In [Microsoft Foundry](https://ai.azure.com) with **New Foundry** on, create a project. Under the advanced options choose the resource group, region **Sweden Central**, and a resource name. Then read the names the portal chose:

   ```bash
   az resource list -g "$RG" --query "[].{name:name, type:type}" -o table
   ```

   Expected: a `Microsoft.CognitiveServices/accounts` resource and an `accounts/projects` child named `<resource>/<project>`. The portal can also create an Application Insights resource and a Log Analytics workspace; step 8 checks their connection. Set the names:

   ```bash
   export RESOURCE=<resource> PROJECT=<project>
   RES_ID=$(az cognitiveservices account show -g "$RG" -n "$RESOURCE" --query id -o tsv)
   ```

4. Turn off key access on the Foundry resource, then prove it. The request lists models and costs nothing.

   ```bash
   KEY=$(az cognitiveservices account keys list -g "$RG" -n "$RESOURCE" --query key1 -o tsv)
   U="https://$RESOURCE.services.ai.azure.com/openai/v1/models"
   curl -s -o /dev/null -w "before: %{http_code}\n" -H "api-key: $KEY" "$U"
   az resource update --ids "$RES_ID" --set properties.disableLocalAuth=true --query properties.disableLocalAuth -o tsv
   curl -s -o /dev/null -w "after: %{http_code}\n" -H "api-key: $KEY" "$U"
   unset KEY
   ```

   Expected: `before: 200`, `true`, `after: 401`. The 401 says "invalid subscription key or wrong API endpoint" even though the key is valid ([finding](../findings/identity-and-access.md)).

5. Give the developer the Foundry User role at project scope, and check that no wider copy exists. The role ID is used because the role was renamed from Azure AI User.

   ```bash
   ME=$(az ad signed-in-user show --query id -o tsv)
   FOUNDRY_USER=53ca6127-db72-4b80-b1b0-d745d6d5456d
   az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
     --role "$FOUNDRY_USER" --scope "$RES_ID/projects/$PROJECT" -o none
   az role assignment list --assignee "$ME" --all --role "$FOUNDRY_USER" --query "[].scope" -o tsv
   ```

   Expected: exactly one line, ending in `/projects/<project>`. Delete any wider assignment of the same role (`az role assignment delete --ids <assignment-id>`); with one in place, a least-privilege check cannot fail.

6. Deploy the models in the portal: **Deployments**, **Deploy model**. Use the model name as the deployment name, deployment type **Global Standard**, and under the version update policy choose to opt out of automatic version upgrades.

   | Model | Version | Capacity |
   |---|---|---|
   | gpt-6-luna | 2026-09-22 | 50K tokens per minute |
   | gpt-6.1-sol | 2026-09-29 | 50K tokens per minute |

   The Azure CLI cannot set the version update policy, so the portal does this step. Then read back:

   ```bash
   az cognitiveservices account deployment list -g "$RG" -n "$RESOURCE" \
     --query "[].{name:name, version:properties.model.version, sku:sku.name, capacity:sku.capacity, upgrade:properties.versionUpgradeOption}" -o table
   ```

   Expected: both deployments with their version, `GlobalStandard`, capacity `50`, and `NoAutoUpgrade`. The milestone 1 build also kept gpt-5-mini and grok-4.7 as candidates for later decisions ([decision 0012](../decisions/0012-models.md)); they are optional here.

7. Create the storage account with shared keys and public access off, give the developer the data role, and create the containers. The container loop retries while the new role takes effect.

   ```bash
   az storage account create -n "$STORAGE" -g "$RG" -l swedencentral --sku Standard_LRS --kind StorageV2 \
     --allow-shared-key-access false --allow-blob-public-access false --min-tls-version TLS1_2 -o none
   ST_ID=$(az storage account show -n "$STORAGE" -g "$RG" --query id -o tsv)
   az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
     --role "Storage Blob Data Contributor" --scope "$ST_ID" -o none
   for c in sources extracted; do
     for i in 1 2 3 4 5 6 7 8 9 10; do
       az storage container create --account-name "$STORAGE" -n "$c" --auth-mode login -o tsv && break
       sleep 30
     done
   done
   ```

   Expected: `True` twice, possibly after a few `AuthorizationPermissionMismatch` errors. Then prove that keys and anonymous reads are refused:

   ```bash
   az storage container list --account-name "$STORAGE" --auth-mode key -o tsv 2>&1 | grep -o KeyBasedAuthenticationNotPermitted
   curl -s -o /dev/null -w "%{http_code}\n" "https://$STORAGE.blob.core.windows.net/sources?restype=container&comp=list"
   ```

   Expected: `KeyBasedAuthenticationNotPermitted` and `409`.

8. Check the tracing connection.

   ```bash
   SUB=$(az account show --query id -o tsv)
   az rest --method get \
     --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$RESOURCE/projects/$PROJECT/connections?api-version=2026-09-01" \
     --query "value[].{category:properties.category, auth:properties.authType}" -o tsv
   ```

   Expected: one connection, category `AppInsights` with authentication type `ApiKey`. If there is none, connect it in the portal: the project, **Agents**, **Traces**, **Connect**, and create or select an Application Insights resource.

9. Write `.env` from `.env.example` with these values. The search and embedding values stay empty until milestone 3.

   | Variable | Value |
   |---|---|
   | `HINDCAST_PROJECT_ENDPOINT` | `https://<resource>.services.ai.azure.com/api/projects/<project>` |
   | `HINDCAST_CU_ENDPOINT` | `https://<resource>.services.ai.azure.com/` |
   | `HINDCAST_CHAT_DEPLOYMENT` | `gpt-6-luna` |
   | `HINDCAST_COMPARE_DEPLOYMENT`, `HINDCAST_JUDGE_DEPLOYMENT` | `gpt-6.1-sol` |
   | `HINDCAST_STORAGE_URL` | `https://<storage-account>.blob.core.windows.net` |

   Expected: `git check-ignore .env` prints `.env`.

## Add the case sources

The status pages and postmortems are the providers' copyrighted pages, so the repository holds only their URLs, retrieval times, and hashes in [`data/cases.yaml`](../../data/cases.yaml). This section captures them again into `data/sources/` (ignored by Git) and Blob Storage.

1. Capture each case's status updates and postmortem.

   ```bash
   cap() { PYTHONPATH=src uv run --frozen python -m hindcast.capture "$@"; }
   cap status --provider Cloudflare --incident 8gmgl950y3h7 --out data/sources/cloudflare-2025-11-18/cloudflare-status-2025-11-18.json
   cap page --url https://blog.cloudflare.com/18-november-2025-outage/ --out data/sources/cloudflare-2025-11-18/cloudflare-postmortem-2025-11-18.html
   cap status --provider GitHub --incident zkxwbgr0cnmx --out data/sources/github-2026-08-17/github-status-2026-08-17.json
   cap page --url https://github.blog/news-insights/company-news/github-availability-report-august-2026/ --out data/sources/github-2026-08-17/github-availability-2026-08.html
   cap status --provider "Google Cloud" --incident T8gmtofFSTGT5tbhyciF --out data/sources/google-cloud-2026-07-14/google-cloud-status-2026-07-14.json
   cap page --url https://status.cloud.google.com/incidents/T8gmtofFSTGT5tbhyciF --out data/sources/google-cloud-2026-07-14/google-cloud-report-2026-07-14.html
   cap status --provider Cloudflare --incident kwy3dt82bwbt --out data/sources/cloudflare-2026-02-20/cloudflare-status-2026-02-20.json
   cap page --url https://blog.cloudflare.com/cloudflare-outage-february-20-2026/ --out data/sources/cloudflare-2026-02-20/cloudflare-postmortem-2026-02-20.html
   ```

   Expected: each command prints `url:`, `retrieved_at:`, and `sha256:` lines. For a new case, these lines go into the registry. Google Cloud's feed keeps recent incidents only; if the incident has left it, the command says so, and a saved copy of the feed is passed with `--feed-file <path> --retrieved-at <time it was downloaded>`.

2. Verify every file against its pinned hash.

   ```bash
   PYTHONPATH=src uv run --frozen python -c "
   from pathlib import Path
   from hindcast.cases import load_cases, verify_local_files
   print({cid: verify_local_files(case, Path('data/sources')) for cid, case in load_cases().items()})"
   ```

   Expected: an empty list for every case. The status snapshots keep only the incident, so they match unless the provider edited the incident. Postmortem pages are saved as served, so a page whose layout changed since its capture shows up here: compare the article text, and if only the page around it changed, record the new hash and retrieval time.

3. Upload the sources, download them again, and verify the downloaded copies.

   ```bash
   for c in cloudflare-2025-11-18 github-2026-08-17 google-cloud-2026-07-14 cloudflare-2026-02-20; do
     az storage blob upload-batch --account-name "$STORAGE" --auth-mode login -d sources -s data/sources --pattern "$c/*" --overwrite true -o none
   done
   check=$(mktemp -d)
   az storage blob download-batch --account-name "$STORAGE" --auth-mode login -s sources -d "$check" -o none
   PYTHONPATH=src uv run --frozen python -c "
   import sys
   from pathlib import Path
   from hindcast.cases import load_cases, verify_local_files
   print({cid: verify_local_files(case, Path(sys.argv[1])) for cid, case in load_cases().items()})" "$check"
   ```

   Expected: an empty list for every case. The Content-MD5 shown by `az storage blob show` only repeats what the upload sent, so the download is the check.

## Record what the models know

1. Make one call through the project with your Entra sign-in.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "
   from hindcast.models import ask_model, deployment_model
   print(ask_model('gpt-6-luna', 'Answer in one word.', 'What colour is a clear daytime sky?'))
   print(deployment_model('gpt-6-luna'))"
   ```

   Expected: a one-word answer with its `TokenUsage`, then `('gpt-6-luna', '2026-09-22')`. A 401 or 403 names the missing data action: check step 5.

2. Collect the prior-knowledge answers before any evidence reaches a model. The collector refuses to run, before any model call, while the prompt, the registry, `src/`, `pyproject.toml`, or `uv.lock` has uncommitted changes, or when the day's result file exists.

   ```bash
   for d in gpt-6-luna gpt-6.1-sol; do
     PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.prior collect --deployment "$d"
   done
   ```

   Expected: one line per deployment naming `eval/results/prior-<date>-<deployment>.json`, `3 entries`, and the token totals. Commit the files without opening them: they are scored with the rubric frozen in milestone 5, and reading them first would bias the rubric.

## Re-check the model choice

The evidence for [decision 0012](../decisions/0012-models.md): luna against sol on the development outage, scored by Foundry evaluators with a rule written before the runs. Run it again when a deployment changes version. Needs the development case's status snapshot (see "Add the case sources") and the deployments from "Create the Azure foundation". Run every command from the repository root: the scripts read the snapshot by its path from there.

1. Build the upload file from the local snapshot.

   ```bash
   PYTHONPATH=src uv run --frozen python eval/model-selection/dev-outage-v1/build_dataset.py
   sha256sum data/sources/model-selection/dataset-dev-outage-v1.jsonl
   ```

   Expected: `data/sources/model-selection/dataset-dev-outage-v1.jsonl: 5 rows`, and a hash starting `b76a883bd24595a5`. A different hash means the snapshot or the questions changed: the results are then a new dataset version, not a re-run.

2. Ask each model for the timeline, one call per deployment and effort.

   ```bash
   for run in "gpt-6-luna low" "gpt-6-luna medium" "gpt-6.1-sol medium"; do
     PYTHONPATH=src uv run --frozen --env-file .env \
       python eval/model-selection/dev-outage-v1/compare_timeline.py $run
   done
   ```

   Expected: one line per run naming `data/sources/model-selection/timeline-<deployment>-<effort>.txt` and its input and output tokens. The script refuses to overwrite an earlier answer. Score each answer by hand against the event table in the folder's README.

3. Give the person who runs the evaluation an OpenAI data role on the Foundry resource, and check it. With key access off, the portal calls the models as that person on the resource endpoint, which the project-scope Foundry User role does not reach ([troubleshooting](../troubleshooting.md)).

   ```bash
   export RG=<resource-group> RESOURCE=<resource>
   RES_ID=$(az cognitiveservices account show -g "$RG" -n "$RESOURCE" --query id -o tsv)
   ME=$(az ad signed-in-user show --query id -o tsv)
   az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
     --role "Cognitive Services OpenAI User" --scope "$RES_ID" -o none
   ENDPOINT=$(grep '^HINDCAST_PROJECT_ENDPOINT=' .env | cut -d= -f2-)
   TOKEN=$(az account get-access-token --scope https://ai.azure.com/.default --query accessToken -o tsv)
   curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
     "$ENDPOINT/openai/evals?api-version=v1&limit=1"
   ```

   Expected: `200`. Right after the assignment it can print `400` for a few minutes (the body names the missing `OpenAI/evals/read` action); run the last two commands again until it prints `200`.

4. Run the Foundry evaluation in the Foundry portal, once per target: `gpt-6-luna`, then `gpt-6.1-sol`.

   1. **Evaluation**, **Create**, target **Model**, pick the deployment.
   2. Data source: upload `dataset-dev-outage-v1.jsonl`; the portal names the dataset after the file. For the second run, pick the uploaded dataset.
   3. **Add custom prompt**. Developer message:

      ```text
      You answer questions about a provider's status updates for one outage.
      Use only the text in the message. Do not add facts from memory.
      Quote the sentence your answer comes from.
      If the text does not contain the answer, say that it does not.
      ```

      User message: `{{item.context}}`, a blank line, then `Question: {{item.query}}`. The default `{{item.query}}` alone sends no updates.
   4. Evaluators: clear the recommended set; select Groundedness, Response completeness, Relevance, Coherence, and Similarity.
   5. In each evaluator's **Edit**: judge `gpt-6.1-sol`; fields `{{item.context}}`, `{{item.ground_truth}}`, and response `{{sample.output_text}}`.
   6. Name the run after the target and the dataset, for example `luna-dev-outage-v1`, and submit.
   7. When it finishes, on the run page: **Download results** and **Download user logs**, and copy the **Raw JSON** view into a file. Save them in `data/sources/model-selection/` as `eval-<target>-dev-outage-v1-results.jsonl`, `eval-<target>-dev-outage-v1-user_logs.txt`, and `eval-<target>-dev-outage-v1-run.json`, with `<target>` `luna` or `sol`.

   Expected: status **Completed** after about 40 seconds, 5 rows, and a score from every evaluator on every row. A row that shows "Error" for one evaluator is a failed judge call ([troubleshooting](../troubleshooting.md)); the run still says completed.

5. Sanitize each run's downloads into the files committed in the evaluation folder.

   ```bash
   for t in luna sol; do
     PYTHONPATH=src uv run --frozen python eval/model-selection/dev-outage-v1/sanitize_results.py "$t"
   done
   ```

   Expected per target: `results-<target>-dev-outage-v1.jsonl: 5 rows; log-excerpt-<target>-dev-outage-v1.txt: 16 lines` (more when judge calls failed) and `run-<target>-dev-outage-v1.json written`. Exit code 1 with nothing written, and the field or identifier named, when a copy of the status text or an identifier remains.

6. Check every quote against the updates, then break one on purpose.

   ```bash
   EV=eval/model-selection/dev-outage-v1
   for t in luna sol; do
     PYTHONPATH=src uv run --frozen python "$EV/check_quotes.py" "$EV/results-$t-dev-outage-v1.jsonl" --no-quote-ok 4
   done
   PYTHONPATH=src uv run --frozen python "$EV/check_quotes.py" "$EV/results-luna-dev-outage-v1.jsonl" \
     --no-quote-ok 4 --break-row 0; echo "exit $?"
   ```

   Expected: per run, `6 of 6 quotes word for word; 0 answers missing a required quote` (the count follows the answers), exit code 0. The broken run prints `Q1: NOT FOUND`, `5 of 6 quotes word for word`, and `exit 1`.

7. Apply the rule.

   ```bash
   uv run --frozen python eval/model-selection/dev-outage-v1/summarise_runs.py \
     eval/model-selection/dev-outage-v1/results-luna-dev-outage-v1.jsonl \
     eval/model-selection/dev-outage-v1/results-sol-dev-outage-v1.jsonl
   ```

   Expected: each run's scores per question, the means, and the answer and judge tokens, then `Score part of the rule: met. Read question 5 by hand.` and exit code 0. A line `errored evaluator calls: ...` names scores the judge did not return; a missing completeness or groundedness score makes the script print `None against ...` and exit 1. Then either show that the missing score cannot change the outcome, as the 2026-10-26 run did in the [evaluation folder](../../eval/model-selection/dev-outage-v1/README.md), or run that model's evaluation again. Last, read question 5 in each results file: the answer says the updates do not contain the cause and names none.

8. Remove the role from step 3, and check that Hindcast's own calls still work with the project-scope role alone. While a role at resource scope is assigned it also covers the project, so the claim that Foundry User on the project is enough cannot fail ([#9](https://github.com/sindredg/hindcast/issues/9)). Run it in the shell of step 3, which set `ME`, `RES_ID`, and `ENDPOINT`.

   ```bash
   az role assignment delete --assignee "$ME" --role "Cognitive Services OpenAI User" --scope "$RES_ID"
   TOKEN=$(az account get-access-token --scope https://ai.azure.com/.default --query accessToken -o tsv)
   curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
     "$ENDPOINT/openai/evals?api-version=v1&limit=1"
   PYTHONPATH=src uv run --frozen --env-file .env python -c "
   from hindcast.models import ask_model
   print(ask_model('gpt-6-luna', 'Answer in one word.', 'What colour is a clear daytime sky?'))"
   ```

   Expected: `400` (the evals read is refused again; repeat the token and `curl` lines if it still prints `200`), then a one-word answer with its `TokenUsage`.

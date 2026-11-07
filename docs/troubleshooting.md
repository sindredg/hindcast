# Troubleshooting

Failures that showed something about Hindcast, the platform, or a procedure: the symptom, the cause, the fix, and how the fix was verified. Newest first. A cause that was not confirmed is labelled as a hypothesis. The behaviour behind an entry is recorded once, in [findings](findings/), and linked from here.

## Evaluation: the judge refuses a later run after the rubric moved to version 3 (2026-11-07)

**Symptom:** `python -m hindcast.evaluation.judge run --root eval/reconstruction/sealed-v1`, the first judge call since 2026-11-04, stopped before any call with `NotFrozen: the judge prompt, the rubric, or the settings differ from eval/judge/frozen.json`.

**Cause:** confirmed by the lock and the rubric's history. The judge's system prompt is its prompt plus the rubric's title line and Outcomes section. The lock was written under rubric version 2 (`46bed8b5…`); version 3 (`a8b78af7…`) changed the title line and the Review section after the judge ran, so the composed prompt no longer matched the lock. The showcase judgments were made before the change, and `score` checks them by the system-prompt hash they recorded, so nothing failed until a new judgment was asked for.

**Fix:** the judge rebuilds the system prompt from the rubric version its lock names, read from the history, and accepts it only when the rebuilt record, the system prompt's hash included, equals the lock (`check_frozen_or_locked`, commit `ce12ac8`).

**Verification:** tested locally. `test_the_locked_system_prompt_is_rebuilt_from_the_locked_rubric` rebuilds `9de219e1…`, the hash in the lock, and refuses a lock with a changed system hash or a rubric hash no commit has; it fails with the comparison removed. The two revealed runs were then judged with that prompt (`judged 2, errors 0`), and their judgment files record `9de219e1…`.

## Deployment: a rebuilt environment shows the removed environment's traces (2026-11-06)

**Symptom:** after `azd down` removed the environment and `azd up` built it again under the same names, the runbook's trace query (step 14), over its two-hour window, returned five operations with a root span: the two runs made on the new page, and three from 18:25Z to 18:36Z, made on the removed environment's page before the removal. Over 48 hours the same workspace returned every operation since 2026-11-05, ten in all (read during the [independent review](worklogs/06-deployment.md#slice-2-independent-review)).

**Cause:** confirmed by the workspace and the documentation ([finding](findings/deployment.md#azd-down---purge-leaves-the-log-analytics-workspace-recoverable-2026-11-06)). `azd down --purge` deleted the Log Analytics workspace without `--force`, so it stayed soft-deleted. A workspace created within 14 days with the same subscription, resource group, name, and region is the recovered workspace, with its data. ARM reported the workspace as created at 19:28:45Z, after the removal, while it returned spans from 18:25Z.

**Fix:** step 17 of the [deployment runbook](runbooks/deployment.md#remove) deletes the workspace with `--force true` before `azd down`, and checks that no deleted workspace is left.

**Verification:** tested live, 2026-11-06: the forced delete returned in 35 seconds with the Application Insights component still in place, `azd down --purge --force` then removed the group in 26 minutes 35 seconds, and `list-deleted-workspaces` held no Hindcast workspace ([worklog](worklogs/06-deployment.md#slice-2-final-removal)). Whether a later `azd up` under the same names gets a new, empty workspace was not observed: nothing was rebuilt after this removal.

## Deployment: the custom role's delete fails with `RoleDefinitionHasAssignments` (2026-11-06)

**Symptom:** step 16 of the deployment runbook ended with `RoleDefinitionHasAssignments` on `az role definition delete`. The command before it in the same line printed `ERROR: The command failed with an unexpected error` and `No value for given attribute`.

**Cause:** confirmed by running the lookup again, read only, against the rebuilt environment on 2026-11-06 with Azure CLI 2.88.0. `az role assignment list --all --role "Hindcast Safety Caller (hindcast-full)"` fails with that traceback. Its empty output went into `xargs -r`, which deleted nothing and exited 0, so the `&&` chain went on to the definition, which still had its assignments. With `--scope` set to the resource group instead of `--all`, the same lookup returns 0 assignments; filtering all assignments by the definition's ID returns the 2 that exist. Why the CLI fails on the name is not established.

**Fix:** step 16 of the [deployment runbook](runbooks/deployment.md#remove) looks the definition up at the resource group's scope and selects the assignments whose `roleDefinitionId` ends with its ID. If the lookup fails again, the definition's delete still stops on the assignments, so the step cannot pass with the role left behind.

**Verification:** tested live, 2026-11-06: the fixed command deleted the role's assignments and its definition, and `az role definition list --custom-role-only true` no longer listed `Hindcast Safety Caller (hindcast-full)` ([worklog](worklogs/06-deployment.md#slice-2-rebuild-from-empty)). At the final removal the same day, the lookup found the 2 assignments by the definition's ID and the deletes went through ([final removal](worklogs/06-deployment.md#slice-2-final-removal)).

## Deployment: the second provision fails with `MaxNumberOfRegionalEnvironmentsInSubExceeded` (2026-11-05)

**Symptom:** the second `azd provision` of the full environment created the Foundry resources and stopped at the Container Apps environment with `MaxNumberOfRegionalEnvironmentsInSubExceeded`.

**Cause:** confirmed by the error and the subscription's resources: the subscription allows one Container Apps environment per region, and the slice 1 app's environment still ran in Sweden Central in its own resource group. The template does not check for one, and `az deployment sub what-if` does not either, because the limit is a quota, not a template error.

**Fix:** the slice 1 app's resource group was deleted with `az group delete`, which removes that group and nothing else; its app registration and custom role are left for the teardown. The [deployment runbook](runbooks/deployment.md#inputs-and-access) now lists "no other Container Apps environment in the region" as a precondition, with the command that lists them.

**Verification:** tested live, 2026-11-05: the third `azd provision` ended `SUCCESS` in 3 minutes 51 seconds ([worklog](worklogs/06-deployment.md#slice-2-live-run)).

## Deployment: the first provision fails with `RequestConflict` on the Foundry project (2026-11-05)

**Symptom:** the first `azd provision` of the full environment failed on the Foundry project with `RequestConflict`, and the project was not created.

**Cause:** confirmed in the template at `ea3851c`: the deployments ran one at a time (`@batchSize(1)`), but nothing ordered them after the project, so ARM created the first deployment and the project on the same account at once. The account takes one change at a time.

**Fix:** in `infra/modules/foundry.bicep` every deployment `dependsOn` the project (commit `1e56a8d`, [#78](https://github.com/sindredg/hindcast/pull/78)). `az bicep build` and `az bicep lint` pass on it in CI.

**Verification:** tested live, 2026-11-05: the next provision created the project and the four deployments, then stopped at the Container Apps environment (the entry above), and the one after it succeeded ([worklog](worklogs/06-deployment.md#slice-2-live-run)).

## Judge: the API refuses the reply schema as too large (2026-11-04)

**Symptom:** the first judge test call on the development run returned HTTP 400, "The compiled grammar is too large, which would cause performance issues", and wrote no judgment. Dropping the enum of run-item names from the reply schema did not change the answer.

**Cause:** confirmed with probes that change one part of the schema at a time: the per-run reply schema held one array of run-item names per key item, and the compiled grammar grows with each one past a limit the documentation does not give. With the key items alone, 10 compiled and 15 did not; the keys hold 7 to 21 key items ([finding](findings/models.md#structured-output-refuses-a-schema-with-one-array-per-key-item-2026-11-04)).

**Fix:** one fixed reply schema, a list of run items and a list of key items. The code checks what the per-run schema enforced: every item named once, each outcome allowed for its key item's kind, and the code's unsupported items left unsupported; a reply that fails is a schema error. `tests/test_judge.py::test_reply_schema_is_the_same_for_every_run` failed before the change, and each new check's test failed with that check removed.

**Verification:** tested live, 2026-11-04, 17:13:26 to 17:14:12 UTC: the test call on the development run returned `end_turn` with no judge error, and its judgment names all 21 key items and 18 run items ([worklog](worklogs/05-evaluation.md#the-judge)).

## Traces: a run's root span and some model calls never arrive (2026-11-03)

**Symptom:** after the first screened development runs, Application Insights held 6 of their 10 `model_call` spans, no `investigation` span, and no question `screen` span, while the HTTP spans of the same runs were there.

**Cause:** confirmed in the exporter's code: with no `OTEL_TRACES_SAMPLER` set, `configure_azure_monitor` in `azure-monitor-opentelemetry` 1.8.11 uses a rate-limited sampler at five traces per second, and a run's burst of calls exceeds it ([finding](findings/observability.md#the-azure-monitor-exporter-samples-five-traces-per-second-by-default-2026-11-03)).

**Fix:** `hindcast.telemetry` sets `OTEL_TRACES_SAMPLER=parentbased_always_on` before configuring the exporter; `tests/test_telemetry.py::test_configure_keeps_every_span` failed before the change.

**Verification:** tested live, 2026-11-03 17:19 UTC: the next challenge's trace arrived whole (challenge, both model calls, three tool calls, PII), each span with `itemCount` 1 ([worklog](worklogs/04-investigator.md#slice-3-live-runs)).

## Investigator: a library search ends the run with an SSL error (2026-11-02)

**Symptom:** the first slice 2 development run on `gpt-6-luna` ended as `incomplete: tool-error: search_library: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol`, after `list_updates` and `list_charts` and before any search returned. `python -m hindcast.search` failed the same way.

**Cause:** not confirmed. The search service read as running, with public network access on and no IP rules (`az search service show`). A TCP connection to its endpoint opened, but the TLS handshake got no answer for any server name, from WSL (curl, openssl, Python `ssl`) and from the Windows host (`curl.exe`), while the Foundry endpoints, Blob Storage, and Azure Resource Manager answered. The Azure status page listed no active event. Hypothesis: a short fault on the service's frontend or on the network path to it; the two were not told apart.

**Fix:** none. About ten minutes later the endpoint answered again (`401` without a token, 0.29 s), and the run was repeated as a new file ([worklog](worklogs/04-investigator.md#slice-2-live-runs)). A failed search ends a run as a tool error by design: the loop ends a run on any tool failure, and [decision 0020](decisions/0020-library-citations.md) keeps that rule for the search. Under [decision 0017](decisions/0017-sealed-reconstructions.md), a seal attempt that ends this way after the model has produced output is the seal and is not rerun. So `seal run` now makes one search before the first model call and refuses while it fails; a failure in the middle of a run is still possible.

**Verification:** tested live, 2026-11-02 ~18:16 UTC: the endpoint answered, and the repeated run completed with one search. A minute later a `gpt-6.1-sol` run failed on `openai.APIConnectionError` and wrote nothing ([#23](https://github.com/sindredg/hindcast/issues/23)); its retry completed.

## Retrieval: the first index build fails with 404 on embeddings (2026-11-01)

**Symptom:** `python -m hindcast.index build --dimensions 1024` failed at its first embeddings call with `404`, an empty body, through the Foundry project endpoint. It had already created the empty index `hindcast-library-1024`.

**Cause:** confirmed. The project's OpenAI-compatible endpoint serves the Responses API but no embeddings; the resource endpoint does, to a role at resource scope ([finding](findings/models.md#the-project-endpoint-serves-no-embeddings-2026-11-01)).

**Fix:** embeddings go to the resource endpoint (`HINDCAST_EMBEDDING_ENDPOINT`, `models.resource_openai_client`), with Cognitive Services OpenAI User on the Foundry resource ([decision 0019](decisions/0019-library-index.md)). The empty index needed no `--replace`: the build refuses only an index that holds documents.

**Verification:** tested live, 2026-11-01: after the role took effect, `build --dimensions 1024` (12:51:36 to 12:53:55 UTC) and `--dimensions 3072` each pushed 267 chunks ([worklog](worklogs/03-retrieval.md#live-run)).

## Deployment: re-provision fails with a circular dependency (2026-10-31)

**Symptom:** the second `azd provision` failed before any change with `InvalidTemplate: Deployment template validation failed: 'Circular dependency detected on resource: .../containerApps/ca-hindcast'`.

**Cause:** confirmed. Once the container app exists, azd passes `webExists=true`, and the template read the app it was about to update ([finding](findings/deployment.md#reading-the-container-app-that-the-same-template-deploys-is-a-circular-dependency-2026-10-31)).

**Fix:** first, a module of its own read the current image. Later the same day the template stopped reading the existing app: the image comes from `HINDCAST_IMAGE` on every provision ([worklog](worklogs/06-deployment.md#live-run)).

**Verification:** tested live, 2026-10-31: `az deployment sub validate` failed on the old template and passed on both later ones; the provisions after each fix succeeded.

## Deployment: first provision fails with `InternalServerError` on the container app (2026-10-31)

**Symptom:** `azd provision` created the resource group, the registry, and the environment, then failed with `InternalServerError` on the container app and its auth config. The revision was `ActivationFailed`, and the system log showed `ImagePullFailure`.

**Cause:** confirmed. The placeholder image's digest in the template did not exist on the registry: a request for that manifest returned `404`. A second cause would have followed: the placeholder listens on port 80 and has no `/_stcore/health`, so probes on port 8501 never pass. Hypothesis: the auth config failed because its parent app failed; it succeeded unchanged on the next run.

**Fix:** the digest read from the registry for the current placeholder, and the port and probes follow the image.

**Verification:** tested live, 2026-10-31: the next `azd provision` succeeded, the revision is `Healthy`, and the deploying account reached the placeholder through sign-in.

## Deployment: `azd provision --preview` prompts for a parameter (2026-10-31)

**Symptom:** the preview asked `Enter a value for the 'allowedUserObjectId' infrastructure parameter`.

**Cause:** confirmed. The preview does not run the pre-provision hook that sets it ([finding](findings/deployment.md#azd-provision---preview-does-not-run-the-provision-hooks-2026-10-31)).

**Fix:** run `azd hooks run preprovision` first.

**Verification:** tested live, 2026-10-31: the preview then ran without a prompt and listed the resources as `Create`.

## Answer-key draft: most quotes reported as not found (2026-10-27)

**Symptom:** `python -m hindcast.keys draft` reported 10 problems for one key, nearly all "quote not found word for word in the postmortem", although the quoted sentences were on the page.

**Cause:** confirmed. Content Understanding returns a postmortem's tables as HTML inside the markdown, and a quote from a table joins a row's cells into one sentence. Other quotes start mid-sentence and gain a capital letter. The comparison expected the exact characters.

**Fix:** the comparison drops HTML tags and letter case and still requires the same words in the same order (`hindcast.keys._plain`). A quote with its words in another order is still reported.

**Verification:** tested locally, `tests/test_keys.py` (`test_quotes_from_table_cells_or_mid_sentence_are_found`, `test_a_quote_with_words_in_another_order_is_still_reported`). Re-drafted from the stored results: 1 problem left for that key, a quote broken across lines on the page, which the review replaced.

## Library extraction: GitHub extracts named a person and described their photo (2026-10-27)

**Symptom:** a check of the first library extracts found sections headed "Tags", "Written by", and an author's name at the end of six GitHub extracts, and one figure per page that was the author's photo.

**Cause:** confirmed. The GitHub rule cut each page to the element that holds the post's text, and that element also holds the post's tags and its author's bio ([sources](findings/sources.md#a-github-blog-posts-body-ends-with-its-authors-bio-and-photo-2026-10-27)).

**Fix:** the GitHub rule drops the tags, the "Written by" block, and the author bio. The six documents were extracted again with `python -m hindcast.ingest library --replace --doc <doc_id>`, which overwrote the earlier extracts in Blob Storage.

**Verification:** tested locally, `tests/test_library_extract.py::test_github_body_leaves_out_tags_and_the_author_bio`, failing before the fix. Live, 2026-10-27: the six extracts have one figure fewer each, and `grep -l -i "written by\|author-bio" build/extracted/library/*.json` matches only a Cloudflare extract whose text says "code written by customers".

## Content Understanding: creating a document analyzer fails with `DefaultDeploymentModelNotFound` (2026-10-27)

**Symptom:** creating a custom analyzer on `prebuilt-document` fails with `DefaultDeploymentModelNotFound`, "Defaults have not yet been set to 'prebuilt-analyzer-embedding'", although the resource defaults map the completion model, and later the embedding model too. An analyzer on `prebuilt-image` is created without the error.

**Cause:** confirmed. The document base declares an embedding model under the alias `prebuilt-analyzer-embedding`, and a custom analyzer inherits it unless it names its own. Mapping the model name `text-embedding-3-large` in the defaults does not map the alias ([extraction findings](findings/extraction.md#a-document-analyzer-needs-an-embedding-deployment-an-image-analyzer-does-not-2026-10-27)).

**Fix:** deploy an embedding model the service supports, map it in the defaults by model name, and name it in the analyzer's `models`:

```json
"models": {"completion": "gpt-5-mini", "embedding": "text-embedding-3-large"}
```

**Verification:** tested live, 2026-10-27: `ensure_analyzers()` created the analyzer, it reported `ready`, and a second run created nothing. `tests/test_extract.py` checks that every document analyzer names both models.

## Portal evaluation: a few evaluator calls fail with 401 after the fix below (2026-10-26)

**Symptom:** the run completes and reports `errored: 0`, but some rows show "Error" for one evaluator, and the row's pass count covers fewer evaluators than were selected. The row's result says "OpenAI API hits AuthenticationError: Principal does not have access to API/Operation."

**Cause:** not confirmed. It happened about an hour after the role assignment, longer than the 10 minutes Azure documents for a role change to take effect. Calls around it with the same identity succeeded.

**Fix:** none found. Check every run for failed calls before using it (`summarise_runs.py` lists them). If a missing score could change a result, run the evaluation again.

**Verification:** closed on 2026-11-04 with the Foundry cloud evaluation run of the showcase report, which recorded no errored row ([#7](https://github.com/sindredg/hindcast/issues/7)). Behaviour: [identity and access](findings/identity-and-access.md), [evaluation runs](findings/evaluation.md).

## Portal evaluation: every row fails with 401 `PermissionDenied` (2026-10-26)

**Symptom:** a Foundry portal evaluation with a model target finishes in seconds with "Error" on every evaluator of every row and "0 / 0" for every metric. Each row's error reads: `Error code: 401 - PermissionDenied`, "The principal ... lacks the required data action `Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action` to perform `POST /openai/deployments/{deployment-id}/chat/completions`". Calls from Hindcast's code through the project endpoint keep working.

**Cause:** confirmed. With key access off on the Foundry resource, the portal calls the model with the signed-in user's identity on the resource endpoint. The user's only Foundry role was Foundry User at project scope, which does not reach that endpoint.

**Fix:** assign Cognitive Services OpenAI User on the Foundry resource to the person who runs the evaluation, then wait a few minutes:

```bash
export RG=<resource-group> RESOURCE=<resource>
RES_ID=$(az cognitiveservices account show -g "$RG" -n "$RESOURCE" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
  --role "Cognitive Services OpenAI User" --scope "$RES_ID" -o none
```

Remove it after the run: while it is assigned, it also covers the project, which hides whether the project-scope role is enough ([runbook](runbooks/foundations.md#re-check-the-model-choice), step 8).

**Verification:** `GET <project endpoint>/openai/evals?api-version=v1` with the user's token returned HTTP 400 naming the missing `OpenAI/evals/read` action before the assignment and HTTP 200 about 3 minutes after. The next two runs answered all ten questions and scored 48 of 50 evaluator calls; the other two are the entry above. Behaviour: [identity and access](findings/identity-and-access.md). Procedure: [runbook](runbooks/foundations.md#re-check-the-model-choice).

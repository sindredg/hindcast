# Troubleshooting

Failures that showed something about Hindcast, the platform, or a procedure: the symptom, the cause, the fix, and how the fix was verified. Newest first. A cause that was not confirmed is labelled as a hypothesis. The behaviour behind an entry is recorded once, in [findings](findings/), and linked from here.

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

**Verification:** open, [#7](https://github.com/sindredg/hindcast/issues/7). Behaviour: [identity and access](findings/identity-and-access.md), [evaluation runs](findings/evaluation.md).

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

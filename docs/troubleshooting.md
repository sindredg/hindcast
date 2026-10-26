# Troubleshooting

Failures that showed something about Hindcast, the platform, or a procedure: the symptom, the cause, the fix, and how the fix was verified. Newest first. A cause that was not confirmed is labelled as a hypothesis. The behaviour behind an entry is recorded once, in [findings](findings/), and linked from here.

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

**Verification:** `GET <project endpoint>/openai/evals?api-version=v1` with the user's token returned HTTP 400 naming the missing `OpenAI/evals/read` action before the assignment and HTTP 200 about 3 minutes after. The next two runs answered all ten questions and scored 48 of 50 evaluator calls; the other two are the entry above. Behaviour: [identity and access](findings/identity-and-access.md). Procedure: [runbook](runbooks/foundations.md#re-check-the-model-choice).

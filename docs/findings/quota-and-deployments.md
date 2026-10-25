# Quota and deployments

Findings about model quota, deployment capacity, and version pinning.

## Deleted Foundry resources keep holding model quota until they are purged (2026-10-25)

**Seen:** a deleted Foundry resource is soft-deleted, and its model deployments keep counting against the subscription's regional quota until the resource is purged. With one 50K deployment of gpt-6-luna live, the quota showed 175K of 250K in use.

**Evidence:** tested live, 2026-10-25, Sweden Central. `az cognitiveservices usage list -l swedencentral`: `OpenAI.GlobalStandard.gpt-6-luna` 175 of 250 (thousands of tokens per minute), with 50 on the live deployment. `az cognitiveservices account list-deleted` listed two soft-deleted resources with scheduled purge dates. The quota documentation says quota stays unavailable until a resource deleted through the API is purged.

**For Hindcast:** the deployment milestone deletes and rebuilds the environment from Bicep. Between the two, purge the deleted resource (`az resource delete` on the deleted account, or "Manage deleted resources" in the portal), or the rebuild can run out of quota.

**Read more:** [Recover or purge deleted Foundry resources](https://learn.microsoft.com/azure/ai-services/recover-purge-resources), [Manage Azure OpenAI quota](https://learn.microsoft.com/azure/foundry/openai/how-to/quota).

## A capacity change in the portal keeps the version pin (2026-10-25)

**Seen:** changing a deployment's capacity under **Manage**, **Quota** kept its version upgrade policy `NoAutoUpgrade`. The Azure CLI reads that policy but has no option to set it; the portal, PowerShell, and the REST API do.

**Evidence:** tested live, 2026-10-25. Capacity of gpt-6-luna and gpt-6.1-sol changed from 62 to 50 in the portal; `az cognitiveservices account deployment list` then read capacity 50 and `versionUpgradeOption` `NoAutoUpgrade` for both. CLI and portal behaviour for the policy read from "Model versioning in Foundry Models" (updated 2026-07-24).

**For Hindcast:** the Bicep templates in milestone 6 set `versionUpgradeOption` explicitly. Left out, the policy reads as empty, which the documentation treats as "once the current version expires": the version then changes without a code change.

**Read more:** [Model versioning in Microsoft Foundry Models](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/model-versions).

## Capacity costs nothing on Global Standard; it is a rate limit (2026-10-25)

**Seen:** Global Standard bills per token. A deployment's capacity sets its tokens-per-minute and requests-per-minute limits and takes that much of the regional quota, but costs nothing by itself.

**Evidence:** read from the documentation, not tested here: "Manage Azure OpenAI in Microsoft Foundry Models quota" (updated 2026-08-13) and the Global Standard pricing model.

**For Hindcast:** capacity is set to what one developer and one evaluation run need (50K), which also caps how fast a runaway loop can spend.

**Read more:** [Manage Azure OpenAI quota](https://learn.microsoft.com/azure/foundry/openai/how-to/quota), [Deployment types for Foundry Models](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types).

# Findings

Observed behaviour of the platforms and data sources used by Hindcast, including surprises that changed the design.

For the project's investigation results, start with the [reconstruction comparison](../../eval/reconstruction/showcase-v1/README.md#reading-the-results): what was tested, how scoring works, and what the results support. The [sealed report](../../eval/reconstruction/sealed-v1/README.md#how-to-read-this-result) covers investigations recorded before the provider published its cause.

The pages below record engineering findings by topic. Each dated entry explains what happened, the evidence, and what it means for Hindcast. Original entries are preserved; later findings link back when behaviour changes.

| Topic | File |
|---|---|
| Models, tokens, and rate limits | [models.md](models.md) |
| Identity and access | [identity-and-access.md](identity-and-access.md) |
| Quota and deployments | [quota-and-deployments.md](quota-and-deployments.md) |
| Case sources | [sources.md](sources.md) |
| Evaluation runs | [evaluation.md](evaluation.md) |
| Extraction with Content Understanding | [extraction.md](extraction.md) |
| Deployment with azd, Bicep, and Container Apps | [deployment.md](deployment.md) |
| Prompt Shields and PII detection | [safety.md](safety.md) |
| Traces in Application Insights | [observability.md](observability.md) |

Failures with their fixes: [troubleshooting](../troubleshooting.md). The model comparison: [decision 0012](../decisions/0012-models.md).

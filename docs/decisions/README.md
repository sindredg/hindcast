# Decision records

One record per consequential choice: the context, the options considered, the decision, and its trade-offs. An accepted record keeps its text. A change is a new record, and the old one gets a sentence that points to it. The roadmap's [status table](../roadmap.md#status) says which milestone accepted each one.

| No. | Decision | Accepted | Changed later by |
|---|---|---|---|
| 1 | [Scope: an investigator over public outage records](0001-scope.md) | 2026-10-25 | |
| 2 | [Agent approach: a Foundry prompt agent with function tools run by the app](0002-agent-approach.md) | 2026-10-25 | |
| 3 | [Document extraction: Azure Content Understanding for postmortems and charts](0003-document-extraction.md) | 2026-10-25 | |
| 4 | [Retrieval: Azure AI Search Basic in Switzerland North, over the postmortem library](0004-retrieval.md) | 2026-10-25 | [19](0019-library-index.md) |
| 5 | [Evidence, library, and answer key: fixed cut rules that fail closed](0005-evidence-library-and-answer-key.md) | 2026-10-25 | |
| 6 | [Evaluation design: a reviewed judge for the reconstruction, Foundry cloud evaluation for the rest](0006-evaluation-design.md) | 2026-10-25 | [23](0023-abstention-and-inferable-labels.md), [24](0024-judge-model.md), [27](0027-reviewer-model.md) |
| 7 | [Safety and injection: Prompt Shields called by the app on every tool result](0007-safety-and-injection.md) | 2026-10-25 | [21](0021-screens-pii-and-challenge.md), [25](0025-injection-test-layers.md) |
| 8 | [User interface: Streamlit with a structured investigation view](0008-user-interface.md) | 2026-10-25 | [21](0021-screens-pii-and-challenge.md), [28](0028-full-environment-and-live-page.md) |
| 9 | [Hosting and identity: Azure Container Apps with a user-assigned managed identity](0009-hosting-and-identity.md) | 2026-10-24 | [16](0016-sign-in-credential-image-build-and-resource-group.md) |
| 10 | [Infrastructure as code: Azure Developer CLI with Bicep](0010-infrastructure-as-code.md) | 2026-10-24 | |
| 11 | [Telemetry and cost: Foundry tracing to Application Insights, cost from a versioned price table](0011-telemetry-and-cost.md) | 2026-10-24 | [21](0021-screens-pii-and-challenge.md) |
| 12 | [Models: gpt-6-luna investigates, gpt-6.1-sol compares](0012-models.md) | 2026-10-26 | [24](0024-judge-model.md) |
| 13 | [Library selection: picked by outside symptoms, with decoys](0013-library-selection.md) | 2026-10-27 | |
| 14 | [Extraction and embedding models: gpt-5-mini and text-embedding-3-large](0014-extraction-and-embedding-models.md) | 2026-10-27 | [18](0018-extraction-model.md) |
| 15 | [Investigation result: keep and mark unsupported items, lock scored cases in code](0015-investigation-result-and-citation-policy.md) | 2026-10-30 | [21](0021-screens-pii-and-challenge.md) |
| 16 | [Deployment: a federated sign-in credential, an image built in CI, and a resource group of the app's own](0016-sign-in-credential-image-build-and-resource-group.md) | 2026-10-30 | |
| 17 | [Sealed reconstructions: run before the postmortem, publish the hash, reveal after](0017-sealed-reconstructions.md) | 2026-11-01 | [22](0022-sealed-drop-date-and-offline-reveal.md), [30](0030-close-evaluation-with-sealed-addenda.md) |
| 18 | [Extraction model: gpt-5.4-mini, pinned, checked before each analysis](0018-extraction-model.md) | 2026-11-01 | |
| 19 | [The library index: picks-only search, Entra-only endpoint, embeddings pushed from code](0019-library-index.md) | 2026-11-01 | |
| 20 | [Library citations: retrieved in the run, never sole support, searching required](0020-library-citations.md) | 2026-11-02 | [21](0021-screens-pii-and-challenge.md) |
| 21 | [Screens per item, citations of what was shown, PII redaction, the challenge turn, and the traces kept](0021-screens-pii-and-challenge.md) | 2026-11-03 | |
| 22 | [Sealed cases: a later drop date and a reveal that works offline](0022-sealed-drop-date-and-offline-reveal.md) | 2026-11-03 | [30](0030-close-evaluation-with-sealed-addenda.md) |
| 23 | [Abstention: inferable-from-evidence labels, and a score that tells a miss from an unknowable item](0023-abstention-and-inferable-labels.md) | 2026-11-03 | [27](0027-reviewer-model.md) |
| 24 | [The judge: Claude Opus 5.5 on the Anthropic API](0024-judge-model.md) | 2026-11-03 | [27](0027-reviewer-model.md) |
| 25 | [Injection tests on two layers, and planted documents in their own index](0025-injection-test-layers.md) | 2026-11-03 | |
| 26 | [A planted chart among the case's own charts](0026-case-chart-injection.md) | 2026-11-04 | |
| 27 | [A reviewer model decides the review queue](0027-reviewer-model.md) | 2026-11-04 | |
| 28 | [One template for the whole environment, and a page that investigates](0028-full-environment-and-live-page.md) | 2026-11-05 | |
| 29 | [Push the image CI tested, after every check](0029-push-the-tested-image.md) | 2026-11-06 | |
| 30 | [Close the evaluation with sealed reveals as addenda, and give a revealed case its own role](0030-close-evaluation-with-sealed-addenda.md) | 2026-11-07 | |

The "Changed later by" column repeats what each record's status line says; the record's own line governs.

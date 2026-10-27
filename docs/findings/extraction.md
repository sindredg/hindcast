# Extraction findings

Findings about Content Understanding as Hindcast's extraction service ([decision 0003](../decisions/0003-document-extraction.md)): analyzers, model deployments, and what an analysis returns. Newest first.

## A chart description gets times roughly right and can invent a value (2026-10-27)

**Seen:** describing two Cloudflare Radar charts, the chart analyzer placed the visible changes within about half an hour of where the axis puts them, but gave a value no label in the image shows. The analyzer's definition asks for nothing beyond what is visible.

**Evidence:** tested live, 2026-10-27, `hindcast_chart` on the development case's two Radar images (`data/charts/cloudflare-2026-02-20/`). The IPv4 description says the announced space "drops sharply in the late afternoon to a low below 5.2K around ~18:00"; all three y-axis labels in the image read 5.3K (Radar rounds them), and by eye from the tick positions the drop runs from about 18:10 to 18:45 UTC. The BGP description puts "a large spike" at "around 17:00 to 18:00"; by eye it rises from about 17:35 and peaks near 18:20. The times were read from the images by a person, not measured.

**For Hindcast:** a chart description is model output about an image, not a reading of the data. The investigator gets it as a lead; a time or value that rests only on a chart description cannot support a finding on its own, which the milestone 4 prompt and the milestone 5 support rules have to say.

**Read more:** [Content Understanding image analysis](https://learn.microsoft.com/azure/ai-services/content-understanding/image/overview).

## Content Understanding Contributor cannot delete an analyzer, but can replace one (2026-10-27)

**Seen:** the Content Understanding Contributor role grants `MultiModalIntelligence/*` except the delete actions, so a Contributor cannot delete an analyzer. Creating the analyzer again with `allow_replace` needs no delete and works. Only the Owner role grants deletes. The [earlier finding](identity-and-access.md#a-project-scope-role-reaches-the-models-but-not-the-resource-endpoint-2026-10-25) listed Contributor and Owner as granting the same actions.

**Evidence:** tested live, 2026-10-27, signed in with Cognitive Services Content Understanding Contributor on the Foundry resource. `delete_analyzer("hindcast_answer_key")` returned `PermissionDenied`: "lacks the required data action `Microsoft.CognitiveServices/accounts/MultiModalIntelligence/analyzers/delete`". `begin_create_analyzer("hindcast_answer_key", <new definition>, allow_replace=True)` succeeded, and the analyzer reported `ready` with the new fields. `az role definition list`: Contributor has `notDataActions` for `analyzers/delete`, `classifiers/delete`, `persondirectories/delete`, and `labelingProjects/delete`; Owner has none.

**For Hindcast:** `hindcast.extract.replace_analyzer` recreates an analyzer from its committed file with `allow_replace`, so changing a definition needs no broader role. Analyzers left at teardown are removed with the resource.

**Read more:** [Secure your Content Understanding analyzers and data](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/secure-communications).

## HTML analysis returns field values without their source, billed per about 2,900 characters (2026-10-27)

**Seen:** a custom analyzer on the document base, run on a postmortem's HTML page, returns markdown with the page's headings and the field values with a confidence, but no source location for any field and no paragraphs, sections, or pages, although the analyzer sets `returnDetails` and `estimateFieldSourceAndConfidence`. The result reports the content's `mimeType` as `text/plain`. The page is billed as minimal document pages, one per about 2,900 characters of markdown, plus 1,000 contextualization tokens per page. The embedding deployment the analyzer names was not used.

**Evidence:** tested live, 2026-10-27, `hindcast_postmortem` on the development case's postmortem page (314,275 bytes of HTML), sent as `text/html`. Result: one content of kind `document`, 52,749 characters of markdown, 21 headings at levels 1 to 4. Fields `title` and `published_date` had only `type`, `valueString` or `valueDate`, and `confidence`. `published_date` was `2026-02-21`, the date the page's own metadata states. Usage: `documentPagesMinimal` 18, `contextualizationTokens` 18,000, gpt-5-mini 18,999 input and 132 output tokens, no embedding tokens. 9.5 seconds.

**For Hindcast:** an answer-key field cannot be checked against Content Understanding's grounding on these pages. The answer-key review lays each field next to a quote that code finds word for word in the extracted markdown instead. Library sections come from the markdown's headings. The extracted markdown holds the whole page, so the article body is separated in code.

**Read more:** [Content Understanding pricing explainer](https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer), [Model deployment options for Content Understanding analyzers](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/models-deployments).

## A document analyzer needs an embedding deployment; an image analyzer does not (2026-10-27)

**Seen:** a custom analyzer whose base is `prebuilt-document` inherits the base's embedding alias, `prebuilt-analyzer-embedding`, and cannot be created until that alias resolves to a deployment, even though it uses no labeled samples. Mapping the model name `text-embedding-3-large` in the resource defaults did not resolve the alias. Naming the model in the analyzer's own `models` did. A custom analyzer on `prebuilt-image` was created with a completion model only. The documentation says the service requires a chat completion model and an embedding model, and that embeddings are used for labeled samples and in-context learning.

**Evidence:** tested live, 2026-10-27. With defaults `{"gpt-5-mini": "gpt-5-mini"}`, creating `hindcast_postmortem` returned `DefaultDeploymentModelNotFound`: "Defaults have not yet been set to 'prebuilt-analyzer-embedding'". `hindcast_chart` (base `prebuilt-image`, `models` `{"completion": "gpt-5-mini"}`) was created and reported `ready`. After a `text-embedding-3-large` deployment and the defaults `{"gpt-5-mini": "gpt-5-mini", "text-embedding-3-large": "text-embedding-3-large"}`, the same error repeated. With `"embedding": "text-embedding-3-large"` added to the analyzer's `models`, it was created and reported `ready`.

**For Hindcast:** the document analyzers name both models in their committed definitions, so no alias decides which model runs. The project gained a `text-embedding-3-large` deployment (version 1, Global Standard, 50K tokens per minute, automatic upgrade off), which retrieval reuses. It costs nothing while idle.

**Read more:** [Model deployment options for Content Understanding analyzers](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/models-deployments).

## Analyzer IDs cannot contain hyphens (2026-10-27)

**Seen:** creating an analyzer named `hindcast-postmortem` fails with `InvalidAnalyzerId`: "The 'analyzerId' cannot contain '-'". Underscores are accepted.

**Evidence:** tested live, 2026-10-27, `begin_create_analyzer` with `azure-ai-contentunderstanding` 1.1.0 against API `2025-11-01`.

**For Hindcast:** the analyzers are `hindcast_postmortem`, `hindcast_chart`, and `hindcast_answer_key`. Their definition files keep hyphenated file names.

**Read more:** [Create a custom analyzer](https://learn.microsoft.com/azure/ai-services/content-understanding/tutorial/create-custom-analyzer).

## gpt-5-mini is on the supported list of the GA API (2026-10-27)

**Seen:** the prebuilt analyzers' `supportedModels` list gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5, gpt-5-mini, gpt-5-nano, gpt-5.1, gpt-5.2, gpt-5.4, gpt-5.4-mini, and gpt-5.5 for completion, and text-embedding-3-small, text-embedding-3-large, and text-embedding-ada-002 for embeddings. No GPT-6 model is listed, as the [earlier finding](models.md#content-understandings-ga-api-does-not-accept-the-gpt-6-models-2026-10-25) read from the documentation.

**Evidence:** tested live, 2026-10-27, `GET /contentunderstanding/analyzers/prebuilt-document` and `prebuilt-imageSearch` with API `2025-11-01`, signed in with Cognitive Services Content Understanding Contributor on the Foundry resource. Before any defaults were set, `GET /contentunderstanding/defaults` returned `DefaultsNotSet`.

**For Hindcast:** extraction uses the existing gpt-5-mini 2025-08-07 deployment, which retires on 2027-02-09, after the project's live phase.

**Read more:** [Content Understanding service limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits).

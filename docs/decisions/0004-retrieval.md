# 4. Retrieval: Azure AI Search Basic in Switzerland North, over the postmortem library

Status: Accepted (2026-10-25).

## Context

A case's own evidence is small: tens of status updates and a few charts. The investigator reads it whole through case tools (decision 2); searching it adds nothing.

The library is where search does work. Earlier public postmortems from several providers run to hundreds of incident write-ups. The investigator's library search needs keyword, vector, and semantic search over their sections and chart descriptions. Every hit carries the document, the section or figure, and the publish date. The filter (published before the outage began, not about this case) is built in the app's tool code, never by the model.

The rest of Hindcast runs in Sweden Central. On 2026-10-24 the Azure AI Search region list marked Sweden Central as unable to create new search services, and the offerings API (`Microsoft.Search/fetchOfferings`, `2026-09-01-preview`) returned no service tiers for it. The search service has to run in another region whatever the tier.

## Options considered

| Option | Fit | Cost |
|---|---|---|
| A. AI Search, lowest tier, app-side embedding, no indexer | Full control of fields and filters. 3 indexes, 50 MB storage, 25 MB vector storage. No managed identity for outbound calls, so no integrated vectorizer or indexer without keys | None |
| B. AI Search Basic | The same control, plus a managed identity for outbound calls: an integrated vectorizer and an indexer can reach Foundry and Blob Storage without keys. 15 indexes, 15 GB storage | USD 0.101 per hour in Switzerland North |
| C. Foundry IQ knowledge base as the only retrieval path | Under the GA API (`2026-04-01`) only minimal, extractive retrieval. Model-based query planning is in preview, and with a model the search service needs Basic for its managed identity | Free monthly allowance, then per token |
| D. Foundry Agent Service file search | A built-in tool, so the app cannot check results or apply the date bound before the model reads them (conflicts with decision 2) | Extra charges on top of model tokens |
| E. A local vector store | Full control | None |

Region, for the tier chosen: Switzerland North offers Basic and semantic ranker. Norway East offers Basic but not semantic ranker. Both were read from the offerings API on 2026-10-24.

Sources, read 2026-10-24: [Choose a service tier](https://learn.microsoft.com/azure/search/search-sku-tier), [Regions list](https://learn.microsoft.com/azure/search/search-region-support), [Create a knowledge base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base), [File search tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/file-search), [Azure retail prices API](https://prices.azure.com/api/retail/prices).

## Decision

Option B, in Switzerland North, with one index for the library. Every chunk stores its publish date and its source document, so one index serves every case: the case's start time and identity set the filter per query. Basic gives the search service a managed identity, so its own calls to Foundry and Blob Storage need no keys.

A Foundry IQ knowledge base is added as a second retrieval path over the same index, and compared with Hindcast's own search on the development case. It does not replace the library search tool.

## Trade-offs

- Basic is billed per hour from creation, about USD 2.42 a day, whether or not it is queried. The service is created when ingestion needs it and deleted at teardown.
- Search runs in a different region from the rest of the system. Queries cross regions (a few milliseconds, not measured), and the resource group spans two regions.
- The date filter is only as good as the publish dates read from the pages. A wrong date lets a later postmortem through, so the leak check also runs on the filtered library (decision 5).
- Foundry IQ's model-based query planning is a preview feature. The comparison uses it, labelled as preview; Hindcast's own retrieval does not depend on it.

# 4. Retrieval: Azure AI Search Basic in Switzerland North, over the postmortem library

Status: Accepted (2026-10-25). Changed by [decision 0019](0019-library-index.md).

## Context

Case evidence is read whole through case tools (decision 2). Search works on the library: hundreds of earlier postmortems, searched by keyword, vector, and semantic rank over sections and chart descriptions. The filter (published before the outage, not about this case) is built in the app's tool code.

On 2026-10-24 the region list marked Sweden Central, where the rest runs, as unable to create search services, and the offerings API (`Microsoft.Search/fetchOfferings`, `2026-09-01-preview`) returned no tiers for it.

## Options considered

| Option | Fit | Cost |
|---|---|---|
| A. AI Search, lowest tier, no indexer | 3 indexes, 50 MB storage, 25 MB vectors; no managed identity | None |
| B. AI Search Basic | Managed identity; 15 indexes, 15 GB | USD 0.101 per hour in Switzerland North |
| C. Foundry IQ knowledge base only | GA API (`2026-04-01`) is extractive; query planning is preview and needs Basic | Free allowance, then per token |
| D. Foundry Agent Service file search | No app check before the model reads (conflicts with decision 2) | Extra charges |
| E. Local vector store | Full control | None |

Offerings API, 2026-10-24: Switzerland North has Basic and semantic ranker; Norway East has Basic without it.

Sources, read 2026-10-24: [tiers](https://learn.microsoft.com/azure/search/search-sku-tier), [regions](https://learn.microsoft.com/azure/search/search-region-support), [knowledge base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base), [file search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/file-search), [retail prices](https://prices.azure.com/api/retail/prices).

## Decision

Option B in Switzerland North, one index. Every chunk stores its publish date and document, so the case sets the filter per query. Basic's identity reaches Foundry and Blob Storage without keys. A Foundry IQ knowledge base is added as a second path over the same index and compared on the development case; it does not replace the library tool.

## Trade-offs

- Basic bills about USD 2.42 a day from creation. Created when ingestion needs it, deleted at teardown.
- Queries cross regions (a few milliseconds, not measured); the resource group spans two.
- A wrong publish date lets a later postmortem through, so the leak check also runs on the filtered library (decision 5).
- Foundry IQ's query planning is preview, labelled as such.

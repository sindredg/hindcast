# 19. The library index: picks-only search, Entra-only endpoint, embeddings pushed from code

Status: Accepted (2026-11-01).

## Context

[Decision 0004](0004-retrieval.md) put the library in Azure AI Search Basic in Switzerland North, one index for every case, with the filter built in code. It left the index itself open: what a chunk is, which documents a case may search, how the service is reached, where embeddings come from, and how many vector dimensions to store. It also expected Basic's managed identity to let an indexer and an integrated vectorizer reach Foundry and Blob Storage, and a Foundry IQ knowledge base to be compared with Hindcast's own search.

Three facts shaped the answer. The library is 23 documents, 176 sections, and 65 figures ([decision 0013](0013-library-selection.md) picks them per case). The extracts render tables as one HTML paragraph of up to 22,172 characters. The Foundry project endpoint answers embeddings with 404 while it serves responses, so embeddings have to go to the resource endpoint, which needs a role at resource scope ([models findings](../findings/models.md#the-project-endpoint-serves-no-embeddings-2026-11-01)).

## Options considered

| Question | Options | Chosen, and why |
|---|---|---|
| Which documents a case searches | A. Every document published before the outage began. B. The case's picks only, published before it began | B. Decision 0013 picks per case, decoys included; with A, adding a case's picks would change what another case can read. A sealed case has no picks and searches every document published before it began |
| Where the date bound sits | The outage's start instant, or midnight UTC of its start day | The start day. Publish dates are days, and the library registry already refuses a document dated on the day of a case it serves |
| How the service is reached | Private endpoint; public endpoint with IP rules; public endpoint, Entra only | Public, Entra only, no IP rules. A private endpoint needs a network path from the workstation and the app; IP rules break when the workstation's address changes and do not fit the app's outbound address. The guard is the token and the roles |
| Where embeddings come from | An indexer with a skillset and an integrated vectorizer; vectors pushed from code | Pushed from code. No indexer, skillset, or vectorizer, so the search service needs no identity and no outbound access, and the code checks each extract against its blob before it is embedded |
| How the service is created | `azd` with the app; Bicep deployed with `az deployment group create` into the foundation's group | `infra/search.bicep` with `az deployment group create`. `azd` owns only the app's resource group ([decision 0016](0016-sign-in-credential-image-build-and-resource-group.md)) |
| Vector size | 1,024 or 3,072 dimensions of `text-embedding-3-large` | A rule frozen before the run: 1,024 unless 3,072 scores at least 0.05 higher on mean recall@5 |

## Decision

One index per vector size during the check, then one: `hindcast-library-1024`. The [frozen check](../../eval/retrieval/library-v1/README.md) scored 1,024 dimensions at 0.640 mean recall@5 and 3,072 at 0.544, so 1,024 stays and the other index is deleted.

**Chunks.** A chunk lies inside one section or one figure, so its `ref` (`lib/<doc_id>/s<n>` or `lib/<doc_id>/fig<n>`) is a citation target. A section over 4,000 characters splits at paragraph boundaries; a paragraph over that splits after a table row or, outside a table, at a line break; a single row or line stays whole. A figure's chunk joins its description, alt text, and the text in the image. The library gives 267 chunks.

**Fields.** Each chunk stores its `ref`, part, kind, document, provider, title, heading, content, `published_at`, the cases its document serves (`serves`), URL, the content's SHA-256, and its vector (HNSW, cosine, not returned with results). `published_at`, `serves`, `doc_id`, and `kind` are filterable.

**Search.** `hindcast.search` builds the filter from the registries alone: `published_at lt <start day>` and, unless the case is sealed, `serves/any(s: s eq '<case_id>')`. The query text reaches the keyword and vector parts, never the filter. The search is hybrid, with the vector part filtered first and semantic ranking on top. Every hit is checked again in code against the same rule and against the extracts; a hit outside it raises instead of being returned.

**Access.** The service has local authentication off. The developer holds Search Service Contributor and Search Index Data Contributor on it, from the template. Embeddings go to the Foundry resource's `/openai/v1` endpoint with Cognitive Services OpenAI User on the resource, held until teardown.

A Foundry IQ knowledge base is not built in this milestone. It is compared after the library tool lands in milestone 4, if time allows.

## Trade-offs

- Picks-only search makes the library search a ranking over a case's few picks. That says little about retrieval at scale, and the evaluation report says so ([roadmap](../roadmap.md#5-evaluation)). The frozen check searches the whole date-bound library instead, so it measures more than the investigator will see.
- The endpoint is reachable from the internet. A request without a token gets 401, and a real admin key gets 401 too, because local authentication is off ([identity findings](../findings/identity-and-access.md#an-admin-key-gets-401-not-403-when-local-authentication-is-off-2026-11-01)).
- Cognitive Services OpenAI User at resource scope reaches every deployment on the resource, wider than Foundry User on the project. It is held for the build and the queries until teardown, and the app's identity will need the same in milestone 6.
- Pushed embeddings put the query embedding in Hindcast's code too. The search embeds each query at the size `HINDCAST_EMBEDDING_DIMENSIONS` sets, 1,024 by default; nothing in the code ties that setting to the index's vector size. A changed vector size needs a new index.
- The day bound hides a document published on a case's start day, before the outage. For a case the document serves, the library registry refuses it anyway; for a sealed case, the bound alone drops it.
- The search service sits outside `azd` until the full template in milestone 6. Its Bicep is linted in CI like the app's.
- Without Foundry IQ, decision 0004's comparison is still open.

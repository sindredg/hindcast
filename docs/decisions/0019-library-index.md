# 19. The library index: picks-only search, Entra-only endpoint, embeddings pushed from code

Status: Accepted (2026-11-01).

## Context

[Decision 0004](0004-retrieval.md) left open the chunk, the documents a case searches, access, embeddings, and the vector size, and expected an indexer, a vectorizer, and a Foundry IQ comparison. The library is 23 documents, 176 sections, and 65 figures ([decision 0013](0013-library-selection.md)); extracts render tables as one HTML paragraph of up to 22,172 characters. The Foundry project endpoint answers embeddings with 404, so they go to the resource endpoint, which needs a resource-scope role ([models findings](../findings/models.md#the-project-endpoint-serves-no-embeddings-2026-11-01)).

## Options considered

| Question | Options | Chosen |
|---|---|---|
| Documents a case searches | A. Every earlier document. B. The case's picks | B; under A one case's picks change another's reads. A sealed case has no picks and searches every earlier document |
| Date bound | Start instant, or midnight UTC of the start day | The start day; publish dates are days |
| Access | Private endpoint; public with IP rules; public, Entra only | Public, Entra only; a private endpoint needs a network path, IP rules break |
| Embeddings | Indexer and vectorizer; pushed from code | Pushed: no identity or outbound access for the service; each extract is checked against its blob first |
| Creation | `azd`; Bicep with `az deployment group create` | `infra/search.bicep` with `az deployment group create`; `azd` owns only the app's group ([decision 0016](0016-sign-in-credential-image-build-and-resource-group.md)) |
| Vector size | 1,024 or 3,072 dimensions of `text-embedding-3-large` | Frozen rule: 1,024 unless 3,072 scores at least 0.05 higher on mean recall@5 |

## Decision

One index per size during the check, then `hindcast-library-1024`. The [frozen check](../../eval/retrieval/library-v1/README.md) scored 1,024 at 0.640 mean recall@5 and 3,072 at 0.544; the other index is deleted.

**Chunks.** Inside one section or figure, so the `ref` (`lib/<doc_id>/s<n>` or `lib/<doc_id>/fig<n>`) is a citation target. A section over 4,000 characters splits at paragraphs; a paragraph over that after a table row or at a line break; a row or line stays whole. A figure's chunk joins description, alt text, and text in the image. 267 chunks.

**Fields.** `ref`, part, kind, document, provider, title, heading, content, `published_at`, `serves`, URL, content SHA-256, vector (HNSW, cosine, not returned). Filterable: `published_at`, `serves`, `doc_id`, `kind`.

**Search.** `hindcast.search` builds the filter from the registries: `published_at lt <start day>` and, unless sealed, `serves/any(s: s eq '<case_id>')`. Query text never reaches the filter. Hybrid, vector filtered first, semantic ranking on top. Every hit is rechecked in code; a hit outside the rule raises.

**Access.** Local authentication off. The developer holds Search Service Contributor and Search Index Data Contributor from the template. Embeddings go to the Foundry resource's `/openai/v1` endpoint with Cognitive Services OpenAI User on the resource, held until teardown.

No Foundry IQ knowledge base this milestone; compared after milestone 4's library tool, if time allows.

## Trade-offs

- Picks-only search ranks a few picks and says little about scale ([roadmap](../roadmap.md#5-evaluation)); the frozen check searched the whole date-bound library.
- The endpoint is public. No token: 401; an admin key: 401 too ([identity findings](../findings/identity-and-access.md#an-admin-key-gets-401-not-403-when-local-authentication-is-off-2026-11-01)).
- Cognitive Services OpenAI User at resource scope is wider than Foundry User on the project; the app's identity needs the same in milestone 6.
- Queries embed at `HINDCAST_EMBEDDING_DIMENSIONS` (1,024 by default); nothing ties it to the index.
- The day bound hides a document published on a start day before the outage. For a served case the registry refuses it anyway; for a sealed case the bound alone drops it.
- The search service sits outside `azd` until milestone 6; its Bicep is linted in CI.
- Decision 0004's Foundry IQ comparison is still open.

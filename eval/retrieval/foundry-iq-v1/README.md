# Foundry IQ knowledge base against the library search, dataset `library-v1`

Whether a Foundry IQ knowledge base over the same library finds the documents a case's picks were chosen for better than Hindcast's own search does. [Decision 0004](../../../docs/decisions/0004-retrieval.md) planned the comparison, and [decision 0028](../../../docs/decisions/0028-full-environment-and-live-page.md) runs it in the full environment. Written before any knowledge base query ran.

## Written before the run

**Queries and labels:** the frozen [`library-v1/queries.json`](../library-v1/queries.json), SHA-256 `70ad097a9f2464aae89f3290c294ae3d7fb068145ba05ce2f21cd49893915f43`, with its relevant documents. The run refuses a file with any other hash. 34 queries, 19 scored.

**Baseline:** Hindcast's library search on `hindcast-library-1024`, mean recall@5 0.640 and MRR 0.702 ([library-v1 results](../library-v1/README.md#status), run on 2026-11-01). It is not run again: the index it ran on was deleted on 2026-11-04.

**Index:** `hindcast-library-1024-kb`, the same chunks as the library index, embedded by the same deployment, plus an Azure OpenAI vectorizer on `text-embedding-3-large`, so the knowledge base can embed its own queries. The library index has no vectorizer, because Hindcast embeds its queries in code, and it stays unchanged.

**Knowledge source:** one `searchIndex` source over that index, with its semantic configuration `library`, returning `doc_id` and `ref`.

**Arms:**

| Arm | API version | Retrieval | Model |
|---|---|---|---|
| `minimal` | `2026-04-01` (generally available) | The query text as one semantic intent; no query planning | None |
| `planning` | `2026-08-01-preview` (preview) | The query text as one user message; the knowledge base plans its own queries, reasoning effort `low`, extractive output | `gpt-5.4-mini` |

**Filter:** each query carries its case's filter as `filterAddOn`: documents published before the case began, from the registries, exactly as the baseline (`picks_only=False`).

**Metrics:** the references of type `searchIndex`, ordered by reranker score, give the ranked documents. Recall@5 and reciprocal rank are computed by the same functions as the baseline, over the 19 scored queries.

**Rule:** the comparison decides nothing in this milestone; the investigator keeps its own search ([decision 0004](../../../docs/decisions/0004-retrieval.md)). An arm whose mean recall@5 is at least 0.05 above 0.640 opens an issue to reconsider the library tool.

**Each result names:** the arm, the API version, the index and knowledge base, the embedding deployment and its version, the planning model and its version (planning arm), the SHA-256 and commit of `queries.json`, the commit of `data/library.yaml`, the code commit, and the run time (`results-<arm>.json`).

## Limits

- The library limits of [library-v1](../library-v1/README.md#limits) apply: 23 documents and 19 scored queries, so retrieval is close to a lookup.
- The baseline ran on 2026-11-01 on another search service. The knowledge base runs on a rebuilt index in the full environment, with the same chunks and the same embedding deployment, re-embedded.
- The planning arm runs a preview API. Its behaviour can change without notice.
- A knowledge base returns references above its reranker threshold only, with no `top`. An arm that returns fewer than five documents for a query is scored on what it returns.

## Status

Written on 2026-11-05, before the run. Run on 2026-11-05 in the full environment (runbook [step 15](../../../docs/runbooks/deployment.md#foundry-iq), [worklog](../../../docs/worklogs/06-deployment.md#slice-2-live-run)): `hindcast-library-1024-kb` held 267 chunks. Neither arm beats the baseline, so the rule opens no issue, and the investigator keeps its own search.

| Arm | Run at (UTC) | Scored queries | Mean recall@5 | MRR | Against the baseline (0.640, 0.702) |
|---|---|---|---|---|---|
| `minimal` | 2026-11-05 20:12:16 | 19 of 34 | 0.586 | 0.689 | recall@5 0.054 lower, MRR 0.013 lower |
| `planning` | 2026-11-05 20:14:27 | 19 of 34 | 0.536 | 0.640 | recall@5 0.104 lower, MRR 0.062 lower |

Both runs: `queries.json` at SHA-256 `70ad097a...` and commit `48181dc`, `data/library.yaml` at `2431b67`, code at `1e56a8d`, embedding deployment `text-embedding-3-large` version 1. The planning arm's model is `gpt-5.4-mini` version 2026-03-17. The means are recomputed from each file's rows.

Error analysis:

- **Fewer than five documents.** A knowledge base returns only references above its reranker threshold, so a query can come back with fewer than five documents or none. `minimal` returned nothing for one unscored query; no scored query came back empty in either arm.
- **Planning did not help.** Query planning on `low` effort found a relevant document in its top five for 15 scored queries, against 16 for `minimal`, and ranked the first one lower.
- **The baseline ran elsewhere.** The baseline is the 2026-11-01 run on the deleted service, over the same chunks embedded once before. `minimal`'s gap to it is small enough that this comparison cannot tell a difference between the services from one between the two embeddings, which were not compared.

## Files

| File | What it is |
|---|---|
| `README.md` | This page: the rule, the arms, and the results |
| `results-minimal.json` | The `minimal` arm's run: what it names (the list above), the means, and per query the ranked documents, recall@5, and reciprocal rank |
| `results-planning.json` | The same for the `planning` arm |

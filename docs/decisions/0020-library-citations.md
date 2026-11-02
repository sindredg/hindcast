# 20. Library citations: retrieved in the run, never sole support, searching required

Status: Accepted (2026-11-02).

Extends [decision 0015](0015-investigation-result-and-citation-policy.md), which covers case citations only.

## Context

Milestone 4's second slice gives the investigator a third tool, `search_library`, over the postmortem library that milestone 3 indexed. The search is bound to the case in code: the model sends a query and nothing else, and the case's date bound and library picks come from the registries ([decision 0019](0019-library-index.md)). The model can now cite a library section or figure next to the case's status updates.

A library hit is a different outage. [Decision 0006](0006-evaluation-design.md) already says a claim about this outage that rests only on a library document is unsupported. Three questions are left:

1. Which library refs may the model cite? Every ref in the library has a public, stable form (`lib/<document>/s<n>`), and a model that read the same postmortems in training can write one without ever searching.
2. When is a library-only item marked? Milestone 5's support rules could do it, or the citation check could do it now.
3. Is a search required? An investigator that never searches cannot show what the library adds, and a sealed run without a search is the same run as the first sealed series.

## Options considered

Which refs a library citation may name:

| Option | What it accepts | Cost |
|---|---|---|
| Any ref the case's rule allows | A real section dated before the outage, searched or not | A ref recalled from training passes, and the check cannot show the run read the section |
| Only refs a search in this run returned, by exact string | What the model was shown | A real section the run never retrieved is rejected the same as a made-up ref |

When a library-only item is marked:

| Option | Where it shows | Cost |
|---|---|---|
| Leave it to milestone 5's support rules | Only in scored results | Every result before then reads as supported when it rests on another outage |
| Mark it in the citation check now | `checks.unsupported` in every result | None beyond applying decision 0006 earlier |

Whether the investigator searches:

| Option | What runs | Cost |
|---|---|---|
| Optional: the prompt offers the tool | Whatever the model chooses | A run that never searches shows nothing about the library, and the second sealed series may not differ from the first |
| Required: the prompt asks for at least one search, and the development run passes only with a kept library citation | At least one search per run | Every run, sealed ones included, carries the search's hits in its context |

## Decision

A library citation is `{"source": "library", "ref": "<ref>"}`. It is kept only when a search in this run returned that exact ref; otherwise it is rejected as `not-retrieved`. A `lib/` ref under `source: "case"`, or a case ref under `source: "library"`, is `malformed`. The result file lists every tool call in order with each search's query and the refs it returned, never the hit text, so `not-retrieved` can be checked from the file alone.

A kept library citation does not support an item on its own. An item whose kept citations are all library citations, with no kept `rests_on`, is listed in `checks.unsupported`. This applies to every cited item, the attack verdict included.

The prompt asks for at least one search before the answer. The tool cap counts searches; there is no separate search cap. A search with no hits is an answer (`"hits": []`), not a failed run. A query that is empty or longer than 1,000 characters, a hit outside the case's rule, or a search error ends the run as a tool error, as any tool failure does.

## Trade-offs

- `not-retrieved` cannot tell a real section the run did not retrieve from a ref that does not exist. Both are claims the run cannot back with what it was shown.
- A search required in every run grows the context of every run, sealed ones included, by up to five hits per search. The 12-call cap bounds it.
- Library text is third-party text that reaches the model unscreened until Prompt Shields lands ([decision 0007](0007-safety-and-injection.md)). The library is a fixed set of extracted documents, but a planted instruction in one would reach the model.
- The check proves that a cited ref was returned, not that the section says what the item claims. That is milestone 5's support rule, as for case citations.

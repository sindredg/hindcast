# 20. Library citations: retrieved in the run, never sole support, searching required

Status: Accepted (2026-11-02). Changed by [decision 0021](0021-screens-pii-and-challenge.md).

Extends [decision 0015](0015-investigation-result-and-citation-policy.md), which covers case citations only.

## Context

Milestone 4's second slice adds `search_library`: the model sends a query, and the date bound and picks come from the registries ([decision 0019](0019-library-index.md)). A library hit is another outage, and [decision 0006](0006-evaluation-design.md) makes a library-only claim unsupported. Open: which refs the model may cite (every ref has a stable form, `lib/<document>/s<n>`, that a model could write without searching), when a library-only item is marked, and whether a search is required.

## Options considered

| Question | Option | Cost |
|---|---|---|
| Which refs | Any ref the case's rule allows | A ref recalled from training passes |
| | Only refs a search in this run returned | A real unretrieved section is rejected like a made-up one |
| When marked | Milestone 5's support rules | Every result until then reads as supported |
| | The citation check, now | None |
| Searching | Optional | A run that never searches shows nothing; the second sealed series may equal the first |
| | Required: at least one search; the development run passes only with a kept library citation | Every run carries the hits in its context |

## Decision

A library citation is `{"source": "library", "ref": "<ref>"}`, kept only when a search in this run returned that exact ref; otherwise `not-retrieved`. A `lib/` ref under `source: "case"`, or a case ref under `source: "library"`, is `malformed`. The result lists every tool call in order with each search's query and returned refs, never the hit text.

An item whose kept citations are all library citations, with no kept `rests_on`, is listed in `checks.unsupported`, the attack verdict included.

The prompt asks for at least one search; the tool cap counts them. No hits is an answer (`"hits": []`). An empty query, one over 1,000 characters, a hit outside the rule, or a search error ends the run as a tool error.

## Trade-offs

- `not-retrieved` cannot tell a real unretrieved section from a nonexistent ref.
- A required search grows every run's context by up to five hits per search; the 12-call cap bounds it.
- Library text reaches the model unscreened until Prompt Shields lands ([decision 0007](0007-safety-and-injection.md)).
- The check proves a ref was returned, not that the section says what the item claims.

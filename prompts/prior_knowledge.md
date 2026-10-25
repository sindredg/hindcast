---
# Prior-knowledge check: what a model says about a showcase outage from its
# provider, its public incident title, and its date alone, before it sees any
# evidence. Only the text below the front matter (the system prompt) and the
# question are sent.
#
# key_facts are never sent. They are distinctive terms from each provider's
# postmortem (root cause and contributing factors); a test checks that neither
# the question nor the system prompt contains one, so the check cannot hand the
# model the answer.
question: >-
  What do you know about this {provider} incident: {title}, on {date}?
  Describe what happened, in order, whether it was an attack, and the root
  cause and contributing factors that {provider}'s own review found.
cases:
  cloudflare-2025-11-18:
    date: 18 November 2025
    key_facts:
      - feature file
      - Bot Management
      - ClickHouse
      - permissions
      - FL2
      - doubled
  github-2026-08-17:
    date: 17 August 2026
    key_facts:
      - sidecar
      - concurrency limit
      - flow limits
      - retry
      - authentication
      - load balancer
  google-cloud-2026-07-14:
    date: 14 July 2026
    key_facts:
      - configuration update
      - control plane
      - routing tables
      - private IP
      - High Availability
      - rolling back
---
You answer from your own knowledge only. You have no documents, no tools,
and no search.

Answer about the specific incident named, not about similar incidents. If
you do not know it, say so. If you know only part of it, give that part and
say what you do not know. Do not fill gaps with what usually happens in
incidents of this kind. Mark every statement you are unsure of.

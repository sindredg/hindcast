# Investigation result reference

The shape `hindcast.result` and `hindcast.investigate` write, one item per list, values illustrative ([decisions 0015](../../docs/decisions/0015-investigation-result-and-citation-policy.md), [0020](../../docs/decisions/0020-library-citations.md), and [0021](../../docs/decisions/0021-screens-pii-and-challenge.md)).

```json
{
  "case_id": "example-case",
  "agent": {"name": "hindcast-investigator-gpt-6-luna", "version": "3"},
  "model": {"deployment": "gpt-6-luna", "name": "gpt-6-luna", "version": "2026-09-22"},
  "provenance": {
    "prompt": {"blob": "<git blob hash>", "dirty": false},
    "code": {"commit": "<commit>", "dirty": false, "src_tree": "<git tree hash of src/>"},
    "evidence_sha256": "<sha256>",
    "library": {
      "registry": {"blob": "<git blob hash>", "dirty": false},
      "index": "hindcast-library-1024",
      "search_api_version": "2026-04-01",
      "embedding": {"deployment": "text-embedding-3-large", "name": "text-embedding-3-large",
                    "version": "1", "dimensions": 1024},
      "contents": {"chunks": 41, "sha256": "<sha256 of every chunk the case's filter returns>"}
    },
    "arm": "hindcast",
    "screens": true
  },
  "status": "complete",
  "incomplete_reason": null,
  "investigation": {
    "attack": {"verdict": "cannot tell", "reasoning": "No update names a cause.",
               "citations": [{"source": "case", "ref": "example-case/u2"}]},
    "findings": [
      {"id": "f1", "kind": "observation", "claim": "Errors rose for a subset of customers.",
       "rests_on": [], "citations": [{"source": "case", "ref": "example-case/u1"},
                                     {"source": "library", "ref": "lib/example-doc/s4"}]}
    ],
    "timeline": [
      {"time": "2026-01-01T10:12:00Z", "time_kind": "stated", "event": "Investigating elevated errors",
       "citations": [{"source": "case", "ref": "example-case/u1"}]}
    ],
    "root_cause": {"claim": "A change in the edge routing layer", "rests_on": ["f1"], "citations": []},
    "contributing_factors": [],
    "open_questions": [{"question": "What triggered the change?", "why_open": "No update says."}]
  },
  "checks": {"rejected_citations": [], "unsupported": [],
             "pii": [{"path": "findings[0].claim", "category": "Person", "confidence": 0.97}]},
  "tool_calls": [
    {"name": "list_updates", "seconds": 2.4, "withheld": [], "screen_calls": 2},
    {"name": "search_library", "seconds": 6.6, "query": "<query>",
     "refs": ["lib/example-doc/s4"], "withheld": ["lib/other-doc/s7"], "screen_calls": 2}
  ],
  "usage": {"model_calls": 3, "tool_calls": 3, "seconds": 42.2,
            "input_tokens": 10648, "cached_input_tokens": 4251, "output_tokens": 3039,
            "screen_calls": 5, "screen_records": 25, "pii_calls": 6, "pii_records": 26,
            "max_call_input_tokens": 6391, "reasoning_tokens": 1880},
  "reasoning": {"requested": "medium", "applied": ["medium"]},
  "cost": {"table_version": 1, "currency": "USD", "model": 0.002202, "screens": 0.009375,
           "pii": 0.026, "embeddings": 0.000007, "total": 0.037584}
}
```

A run from the deployed page, which has no Git checkout, adds `"source": "image"` to `code` and carries the commit and `src/` tree CI wrote into the image; a prompt or registry is clean when its blob hash matches the one recorded then ([decision 0028](../../docs/decisions/0028-full-environment-and-live-page.md)).

A finding is an observation the evidence states, or an inference that names the findings it `rests_on`. Checks on the answer:

| Check | What happens |
|---|---|
| A citation does not resolve, was withheld by Prompt Shields, or names an item the run never read | Removed and listed in `checks` with its reason |
| A `rests_on` entry sits on an observation, names its own finding, an ambiguous ID, or closes a loop | Removed and listed in `checks` with its reason |
| An item has no case citation and no supported `rests_on` finding | Kept and listed as unsupported |
| A library citation names a ref no search in the run showed | Removed; a kept one never supports an item alone ([decision 0020](../../docs/decisions/0020-library-citations.md)) |
| The answer or a search query holds personal data | Replaced by its category; `checks.pii` lists where, never what |

A run has 120 seconds and 12 tool calls; each model call gets the time left as its timeout, and nothing retries. A run that reaches a cap, fails a model call, tool, screen, or PII check, or returns an answer outside the schema ends as `incomplete` with a reason, and an unchecked answer is not written; a failed model call keeps only the error's type (`model-error: RateLimitError`) and the usage so far. The cost comes from the versioned price table in [`data/prices.yaml`](../../data/prices.yaml).


[Back to the README](../../README.md#what-an-investigation-returns)

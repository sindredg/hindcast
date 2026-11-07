# 21. Screens per item, citations of what was shown, PII redaction, the challenge turn, and the traces kept

Status: Accepted (2026-11-03).

Narrows [decision 0007](0007-safety-and-injection.md), extends [decision 0015](0015-investigation-result-and-citation-policy.md) and [decision 0020](0020-library-citations.md), settles [decision 0008](0008-user-interface.md)'s challenge, and replaces [decision 0011](0011-telemetry-and-cost.md)'s Foundry tracing with Hindcast's own spans.

## Context

Milestone 4's third slice adds Prompt Shields, PII detection, and the challenge. Open:

1. Decision 0007 withholds a whole tool result; one flagged update would remove every other.
2. A withheld ref still exists in the evidence file, so the case-ref check would keep it.
3. An output with personal data: refuse, warn, or mask.
4. Where a challenge runs, on which agent, with which refs.
5. Foundry's server-side tracing stores every prompt and answer in Application Insights (`gen_ai.input.messages`, `gen_ai.output.messages`, up to about 24,000 characters per span), whatever the client setting, before the PII mask. The [trace data page](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data) (updated 2026-10-19) gives one control: disconnect Application Insights.

## Options considered

| Question | Option | Cost |
|---|---|---|
| A flag withholds | The whole tool result | One false positive empties a tool |
| | The flagged item, replaced by its ref and a marker | One screen document per item |
| Citable refs | Any ref in the evidence or returned by a search | Can point at text never read |
| | Only refs shown, minus withheld | A real update cited without `list_updates` is `not-shown` |
| A PII hit | Refuse the run | One name loses the run |
| | Warn, keep the text | Personal data committed |
| | Mask and record field path and category | A false positive masks evidence words |
| Challenge agent | A second turn on the investigator | Its schema is fixed |
| | A second agent per deployment (`hindcast-challenger-<deployment>`) | One more agent version |
| Where it runs | The deployed page | A new role and a provision |
| | A developer's machine; the page shows stored challenges | The public page cannot start one |
| Server-side tracing | Keep | Unmasked answers in traces |
| | Disconnect Application Insights from the Foundry account | No portal trace view |

## Decision

**Screens.** The case title and each update, chart, and library hit are their own Prompt Shields documents, screened once per run:

- A long one is split within the per-call limits; a flag on any piece withholds the item.
- A withheld item is replaced in place by `{"<id>": ref, "withheld": "prompt-shields"}`, with the reason in the result's note.
- A screen error ends the run as `screen-error`.

**Citations.** A case citation is kept only for a shown ref; withheld is `withheld`, unread is `not-shown`. A library ref joins the retrieved set only after the screen, when shown.

**PII.** Every free-text answer field and every kept search query goes to Azure Language PII detection before writing:

- A hit becomes `[<Category>]`; `checks.pii` lists field path, category, and confidence, never the text.
- Roles, organizations, times, URLs, and IP addresses pass.
- A PII error ends the run as `pii-error`; nothing is written.

**Challenge.** A second agent per deployment answers `{verdict: stands | revised | withdrawn, answer, citations, revised_claim}` for a screened result:

1. The question is screened as a user prompt; a flagged one is refused without a model call.
2. The challenger gets the finding, what it rests on, and the masked question, and runs the same loop, tools, and checks under a 6-call, 90-second cap.
3. A library ref the original searches showed stays citable; a case ref needs the challenge's own reading.
4. Stored next to its result.

The page starts one only with `HINDCAST_CHALLENGE_LIVE=1` on a developer's machine.

**Traces.** Application Insights is disconnected from the Foundry account. Commands and page send their own spans, all kept: the exporter's default of five traces per second dropped spans of a single run.

## Trade-offs

- Per-item screening costs more calls for short items; a long section still takes several documents.
- `not-shown` rejects a correct citation the run cannot show it read.
- Masking can hide a word that matters; the development run records hits on clean evidence.
- The PII check runs after the answer with its own 30-second timeout, so a run can end up to 30 seconds past the cap.
- The deployed page shows stored challenges only; the criterion is met locally.
- Seals made before this slice have no `checks.pii` and no withheld lists; the evaluation report says so.
- A model call shows as Hindcast's `model_call` span and its HTTP request; prompt and answer are in no trace.
- Every IP address passes, a person's too; a case that names one needs the category back.

# 21. Screens per item, citations of what was shown, PII redaction, the challenge turn, and the traces kept

Status: Accepted (2026-11-03).

Narrows [decision 0007](0007-safety-and-injection.md) from a withheld tool result to a withheld item, extends the citation rules of [decision 0015](0015-investigation-result-and-citation-policy.md) and [decision 0020](0020-library-citations.md) to what the model was shown, and settles how [decision 0008](0008-user-interface.md)'s challenge runs, and replaces [decision 0011](0011-telemetry-and-cost.md)'s Foundry tracing with Hindcast's own spans.

## Context

Milestone 4's third slice puts Prompt Shields and PII detection in the investigation loop and adds the challenge. Four questions were open:

1. Decision 0007 withholds "a flagged tool result". A `list_updates` result is every update of the case, and a search returns five sections. Withholding the whole result for one flagged item removes the rest of the evidence with it.
2. A citation is checked against the evidence file (case refs) or the searches' refs (library refs). A ref that Prompt Shields withheld still exists in the evidence file, so the case-ref check would keep it.
3. What happens to an output with personal data: refuse the run, show a warning, or mask the text?
4. Where does a challenge run, on which agent, and which refs may its answer cite?
5. The first traced runs showed that Foundry's server-side tracing, which decision 0011 chose, stores every prompt and answer in Application Insights (`gen_ai.input.messages` and `gen_ai.output.messages`, up to about 24,000 characters per span), whatever the client's content-recording setting. That includes each answer before the PII check masks it. Foundry's [trace data page](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data) (updated 2026-10-19) gives one control: disconnect Application Insights.

## Options considered

What a flag withholds:

| Option | What the model loses | Cost |
|---|---|---|
| The whole tool result (decision 0007 as written) | Every update, chart, or hit in that call | One false positive empties a tool, and the run fails or guesses |
| The flagged item only, replaced in place by its ref and a marker | That item | One screen document per item, so more calls for many short items |

Which refs a citation may name:

| Option | Accepts | Cost |
|---|---|---|
| Any ref in the evidence file, any ref a search returned | A withheld item, and a chart the model never listed | A citation can point at text the model never read |
| Only refs the model was shown: case refs from a call it made, minus withheld refs; library refs a search showed, minus withheld ones | What the model read | A real update cited without a `list_updates` call is rejected (`not-shown`) |

A PII hit in an output:

| Option | Result | Cost |
|---|---|---|
| Refuse the run | No output | A name in one claim loses the whole investigation |
| Show a warning, keep the text | Personal data in a committed file | The check proves nothing |
| Mask the hit and record it by field path and category | `[Person]` in the text, `checks.pii` lists where | A false positive masks evidence words; the development run counts them |

The challenge:

| Option | How it runs | Cost |
|---|---|---|
| A second turn on the investigator agent | Same agent, same output schema | The investigator's schema is fixed in its definition; a challenge answer has another shape |
| A second agent per deployment (`hindcast-challenger-<deployment>`) | Its own prompt and schema, the same three tools | One more agent version to create and delete |
| Live on the deployed page | The app identity calls the model | A new role for the app identity and a provision |
| Live only on a developer's machine; the deployed page shows stored challenges | The developer's sign-in calls the model | The public page cannot start a challenge |

Foundry's server-side tracing:

| Option | What Application Insights holds | Cost |
|---|---|---|
| Keep it | Agent and model spans with full prompts and unmasked answers | The PII guarantee holds for result files, not for traces |
| Disconnect Application Insights from the Foundry account | Hindcast's own spans: the run, each model call, tool call, screen, and PII check, with counts and times only | No portal trace view; no server-side agent spans |

## Decision

**Screens.** Each update, chart, and library hit is its own Prompt Shields document; a long one is split within the per-call limits, and a flag on any piece withholds the item. A withheld item is replaced in place by `{"<id>": ref, "withheld": "prompt-shields"}`, the result's note says why, and the rest reaches the model. Each item is screened once per run. A screen error ends the run as `screen-error`; a pass is never assumed.

**Citations.** A case citation is kept only for a ref the model was shown; a withheld ref is rejected as `withheld`, an unread one as `not-shown`. A library ref joins the retrieved set only after the screen, and only when it was shown.

**PII.** Every free-text field of an answer goes to Azure Language PII detection before it is written. A hit is replaced by `[<Category>]`, and `checks.pii` lists its field path, category, and confidence, never the text. Roles, organizations, times, URLs, and IP addresses are not personal data in an outage report and pass. A PII error ends the run as `pii-error`; the answer is not written.

**Challenge.** A second agent per deployment answers `{verdict: stands | revised | withdrawn, answer, citations, revised_claim}`. The question is screened as a user prompt first; a flagged question is refused with no model call. The challenger gets the finding, the findings it rests on, and the PII-masked question, and runs the same loop with the same tools and checks under a 6-call, 90-second cap. A library ref the original run's searches showed stays citable; a case ref needs the challenge's own reading. Challenges are stored next to their result. The page starts one only when `HINDCAST_CHALLENGE_LIVE=1` is set on a developer's machine.

**Traces.** Application Insights is disconnected from the Foundry account. The commands and the page send their own spans with the connection string, and every span is kept: the exporter's default samples five traces per second, which dropped spans of a single run.

## Trade-offs

- Per-item screening costs more calls than per-result screening when items are short. A long library section still takes several documents.
- `not-shown` rejects a correct citation of an update the model knew without listing it. That is the point: the run cannot show it read it.
- PII masking can hide a word that matters, such as a product named like a person. The development run records the hit count on clean evidence.
- The PII check runs after the answer and outside the time cap, with its own 30-second timeout, so a run can end up to 30 seconds past the cap.
- The deployed page cannot run a challenge. A reader of the public page sees stored challenges only; the interface criterion is met on a local run.
- Seals made before this slice ran without screens. Their result files have no `checks.pii` and no withheld lists; the evaluation report says so.
- Without Foundry's server-side spans, a model call shows as Hindcast's `model_call` span and its HTTP request, not as the agent's own steps. The token counts and durations are in Hindcast's spans; the prompt and the answer are in no trace.

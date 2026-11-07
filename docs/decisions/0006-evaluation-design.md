# 6. Evaluation design: a reviewed judge for the reconstruction, Foundry cloud evaluation for the rest

Status: Accepted (2026-10-25). Changed by [decision 0023](0023-abstention-and-inferable-labels.md), [decision 0024](0024-judge-model.md), and [decision 0027](0027-reviewer-model.md).

## Context

Fixed: keys frozen by hash before the first scored run, a prior-knowledge check, baselines. Open: whether a model matches the reconstruction to the key, and where the standard evaluators run. Matching is a judgement ("a certificate expired on the load balancers" and "TLS handshakes failed after a renewal job did not run" can be one cause), and a wrong match inflates the score. A claim resting on nothing in the evidence is a guess.

## Options considered

| Option | Match | Standard evaluators | Trade-off |
|---|---|---|---|
| A. Own judge, every match reviewed by a person; Foundry cloud evaluation | Judge proposes, person decides | GA evaluators (groundedness, relevance, tool call accuracy) through `azure-ai-projects` | Two scoring paths |
| B. Own judge; local SDK | As A | `azure-ai-evaluation` locally | No portal comparison |
| C. No judge | A person matches all | Optional | Slowest |
| D. Foundry rubric evaluator | A model in Foundry | As A | Preview |

Task Adherence, Task Completion, and Intent Resolution are preview and not used.

Sources, read 2026-10-24: [cloud evaluation](https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation), [built-in evaluators](https://learn.microsoft.com/azure/foundry/concepts/built-in-evaluators), [`azure-ai-evaluation`](https://pypi.org/project/azure-ai-evaluation/).

## Decision

Option A. A person reviews every proposed match; judge-reviewer agreement is reported. Foundry cloud evaluation runs the standard evaluators.

Scored per case:

- **Attack assessment:** correct or not, with reasoning.
- **Root cause:** match, partial, or none.
- **Contributing factors:** how many recovered.
- **Timeline:** key events within a tolerance stated before the first run.
- **Citations:** every one resolves.

Support, apart from correctness:

- An observation is supported only if its cited evidence states it.
- An inference, the root cause included, is supported if it cites the observations it rests on and the step passes written criteria. The judge proposes; a person decides.
- A claim resting only on a library document is unsupported; a similar earlier failure is a lead.
- A correct claim without support is unsupported, not a hit.

Baselines: a single search plus a single prompt, and the comparison model in the agent's place. One controlled comparison: change one prompt, rerun, report the difference.

## Trade-offs

- Review limits the number of scored runs.
- Judge and evaluators cost tokens; deployment and version are recorded per result.
- Cloud results live in the Foundry project, deleted at teardown; the report copies them and names the run.
- Groundedness scores against retrieved text, not the postmortem.
- The inference criteria are frozen with the rubric; every unsupported verdict on a correct root cause is listed in the error analysis.

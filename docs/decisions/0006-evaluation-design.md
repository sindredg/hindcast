# 6. Evaluation design: a reviewed judge for the reconstruction, Foundry cloud evaluation for the rest

Status: Accepted (2026-10-25).

## Context

Hindcast's main claim is that its blind reconstruction recovers what the provider's postmortem found. These parts are fixed by the design:

- answer keys written and frozen by hash before the first scored run
- a check of what each model knew about each case beforehand
- baselines to compare the agent against

Two questions were open. Should a language model match the reconstruction to the answer key, and where do the standard quality evaluators run?

Matching a root cause to the postmortem's is a judgement. "A certificate expired on the load balancers" and "TLS handshakes failed after a renewal job did not run" can be the same cause in different words. A model can make that call quickly but can be wrong, and a wrong match inflates the score.

The second risk is a reconstruction that reads well and is wrong. A root cause that happens to match the key but rests on nothing in the evidence is a guess, not a finding.

## Options considered

| Option | Reconstruction match | Standard evaluators | Trade-off |
|---|---|---|---|
| A. Own judge in code, every match reviewed by a person; Foundry cloud evaluation | A judge prompt proposes matches; a person confirms or rejects each one | Foundry's GA evaluators (groundedness, relevance, tool call accuracy) run as cloud evaluation through `azure-ai-projects`, with results in the Foundry portal | Two scoring paths, kept separate in the report |
| B. Own judge; local evaluation SDK | As in A | `azure-ai-evaluation` runs the same evaluators locally and can log results to the project | Easier debugging, no portal comparison view |
| C. No judge | A person matches every item | Optional | Slowest; no measure of how far a judge can be trusted |
| D. Foundry rubric evaluator as the judge | Weighted criteria scored by a model in Foundry | As in A | Preview feature |

Several Foundry agent evaluators are in preview: Task Adherence, Task Completion, and Intent Resolution. Only evaluators not marked preview are used.

Sources, read 2026-10-24: [Cloud evaluation with the Foundry SDK](https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation), [Built-in evaluators](https://learn.microsoft.com/azure/foundry/concepts/built-in-evaluators), [`azure-ai-evaluation` on PyPI](https://pypi.org/project/azure-ai-evaluation/).

## Decision

Option A. The reconstruction score comes from Hindcast's own judge, and a person reviews every proposed match before it counts, so the headline number does not rest on an unchecked model call. The agreement between the judge and the reviewer is reported as a result in its own right. Foundry cloud evaluation runs the standard evaluators, and its portal view compares runs.

Each case is scored on:

- **Attack assessment:** correct or not, with its reasoning shown.
- **Root cause:** match, partial, or none.
- **Contributing factors:** how many of the key's factors were recovered.
- **Timeline:** key events found within a time tolerance stated before the first run.
- **Citations:** every cited update, chart, or library section resolves.

Support is scored separately from correctness:

- An item labelled observation is supported only if the evidence it cites states it.
- An item labelled inference, including the root cause, is supported if it cites the observations it rests on and the step from them passes written criteria. The judge proposes; a person decides.
- A claim about this outage that rests only on a library document is unsupported. An earlier failure that looks similar is a lead, not evidence.
- A correct claim with no supporting citation counts as unsupported, not as a hit.

Two baselines run on the same cases: a single search plus a single prompt over the same evidence, and the comparison model in the agent's place. One controlled comparison is also part of the evaluation: change one prompt, rerun, and report the difference with the same answer keys.

## Trade-offs

- Human review takes time per run, so the number of scored runs is small. Each run is chosen for what it tests.
- The judge and the standard evaluators use model deployments, so every run costs tokens. Their deployment and version are recorded with each result.
- Cloud evaluation results live in the Foundry project. The report copies the numbers and names the run they came from, because the project is deleted at teardown.
- Standard evaluators such as groundedness score against the text the agent retrieved, not against the postmortem. They show whether claims are supported by what was read, not whether they are right.
- The criteria for a supported inference are a judgement written down in advance. They are frozen with the rubric, and every unsupported verdict on a correct root cause is listed in the error analysis.

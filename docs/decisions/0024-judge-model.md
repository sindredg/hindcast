# 24. The judge: Claude Opus 5.5 on the Anthropic API

Status: Accepted (2026-11-03). A reviewer model, not a person, decides the judge's proposals, per [decision 0027](0027-reviewer-model.md).

Replaces [decision 0012](0012-models.md)'s interim judge, the comparison deployment, for the reconstruction scores of [decision 0006](0006-evaluation-design.md).

## Context

Decision 0006 has a judge propose, for each run, a match per key item and a support verdict per claim; a person reviews every proposed match and every support verdict on an inference. Decision 0012 made the comparison deployment, gpt-6.1-sol, the judge until the evaluation milestone confirms it, and kept grok-4.7 as the candidate from another vendor.

Three problems with that:

1. Sol is one of the arms. A judge that scores its own runs favours them, and sol and luna come from the same vendor, which can make sol lenient with luna. The review catches a wrong proposal it looks at, but not a bias in which proposals it is shown.
2. The Azure environment is torn down on 2026-11-09. Judging, reviewing every match, and writing the report take longer than the days between the last run and teardown, and the sealed reveals can come as late as 2026-11-30 ([decision 0022](0022-sealed-drop-date-and-offline-reveal.md)).
3. A judge's version has to stay fixed for the whole evaluation, including the late reveals.

## Options considered

| Option | For | Against |
|---|---|---|
| gpt-6.1-sol, as decision 0012 left it | Deployed, pinned, called with Entra tokens | Judges its own arm; same vendor as luna; gone at teardown |
| grok-4.7 | Another vendor; already deployed | Deployed with automatic version upgrade on, so its version can change mid-evaluation unless it is pinned again; gone at teardown |
| Claude Opus 5.5 on the Anthropic API | A third vendor; `claude-opus-5-5` is a pinned snapshot; structured output is stable; not tied to the Azure environment | A second provider and an API key; the case evidence and the runs leave Azure |
| Claude Opus 5.5 in Microsoft Foundry | A third vendor, called inside Azure | Tied to the environment, so it is gone before the review and the late reveals end |
| A model built as an evaluation judge (Jev) | Made for grading | Early access; its benchmarks are published only by its vendor |

Sources, read 2026-11-03: [models overview](https://platform.claude.com/docs/en/about-claude/models/overview), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [refusals and fallback](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback).

## Decision

The judge is `claude-opus-5-5` on the Anthropic API.

- Each judgment is one request per run with a JSON schema as its output format (`output_config.format`), and the effort and the output limit fixed in code.
- No fallback model. The API retries a refused request on another model only when the request asks for it, and the judge never asks, so every verdict comes from one model. A refusal, an empty reply, a reply cut at the output limit, or one that fails the schema is recorded as a judge error for that run, never read as a verdict.
- The judge prompt is frozen and its SHA-256 committed before any run output is read. Each judgment records the model, the request ID, the usage, and the prompt's hash.
- The API key lives only in the ignored `.env` and is read only by the judge command, which runs on a workstation. The app never reads it.
- A person still reviews every proposed match and every support verdict on an inference, as decision 0006 says, and the agreement between the judge and the reviewer is reported.

## Trade-offs

- A second provider means a second account and the project's one API key, outside the Entra-only access the Azure services use.
- The case evidence, the answer keys, and the runs' outputs are sent to Anthropic's API. All three are public or will be: the evidence and keys are published pages and committed files, and the outputs are committed after scoring.
- Opus 5.5's training data runs to June 2026, after the oldest showcase outage and its postmortem. The judge receives the key in every request, so what it may recall about that outage does not change what it compares.
- A judge from a third vendor removes self-preference, not every bias. The reviewed agreement measures how far its proposals hold.
- Its thinking cannot be turned off; the effort setting is the only control, and it is recorded.

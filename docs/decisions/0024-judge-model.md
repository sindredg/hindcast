# 24. The judge: Claude Opus 5.5 on the Anthropic API

Status: Accepted (2026-11-03). Changed by [decision 0027](0027-reviewer-model.md).

Replaces [decision 0012](0012-models.md)'s interim judge for the reconstruction scores of [decision 0006](0006-evaluation-design.md).

## Context

Decision 0012 made gpt-6.1-sol the interim judge, with grok-4.7 as the other-vendor candidate. Sol is an arm and shares a vendor with luna, so it can favour its own runs and be lenient with luna's. The Azure environment goes on 2026-11-09, while review and sealed reveals run to 2026-11-30 ([decision 0022](0022-sealed-drop-date-and-offline-reveal.md)). The judge's version has to stay fixed throughout.

## Options considered

| Option | For | Against |
|---|---|---|
| gpt-6.1-sol | Deployed, pinned, Entra tokens | Judges its own arm; same vendor as luna; gone at teardown |
| grok-4.7 | Another vendor; deployed | Auto-upgrade on; gone at teardown |
| Claude Opus 5.5 on the Anthropic API | Third vendor; `claude-opus-5-5` is a pinned snapshot; stable structured output; outlives Azure | A second provider and an API key; evidence and runs leave Azure |
| Claude Opus 5.5 in Microsoft Foundry | Third vendor inside Azure | Gone before review and reveals end |
| An evaluation-judge model (Jev) | Made for grading | Early access; vendor-only benchmarks |

Sources, read 2026-11-03: [models](https://platform.claude.com/docs/en/about-claude/models/overview), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [refusals and fallback](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback).

## Decision

`claude-opus-5-5` on the Anthropic API.

- One request per run, JSON schema as output format (`output_config.format`), effort and output limit fixed in code.
- No fallback model: a refusal, empty reply, cut-off reply, or schema failure is a judge error, never a verdict.
- The prompt is frozen and its SHA-256 committed before any output is read. Each judgment records model, request ID, usage, and prompt hash.
- The API key lives only in the ignored `.env`, read by the judge command on a workstation. The app never reads it.
- A person reviews every proposed match and every support verdict on an inference; agreement is reported.

## Trade-offs

- A second provider and the project's one API key.
- Evidence, keys, and outputs go to Anthropic's API; all are public or committed after scoring.
- Training data to June 2026, after the oldest showcase outage. The judge gets the key in every request, so recall does not change what it compares.
- A third vendor removes self-preference, not every bias.
- Thinking cannot be turned off; the effort setting is recorded.

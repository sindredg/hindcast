# Reconstruction evaluation, showcase v1

The scored reconstructions of the four showcase cases: each arm of [decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md) run three times per case, scored against the frozen keys and labels by the [rubric](../../rubric/rubric.md). The rubric's scores, with their error analysis, come here once the runs are judged and reviewed; the Foundry cloud evaluation's numbers are below.

## Status

- **Frozen before any scored run:** the inferable-from-evidence labels on 2026-11-03, and the rubric (version 2) with the timeline tolerance of 30 minutes on 2026-11-04, with the keys frozen earlier. Version 2 replaced version 1, frozen on 2026-11-03, before any run used it. [`eval/rubric/frozen.json`](../../rubric/frozen.json) records their hashes, and `tests/test_rubric.py` fails if any of them changes.
- **Runs, verified on 2026-11-04:** 60 scored runs, 03:10:48Z to 04:00:47Z, live, with `python -m hindcast.evaluation.batch run` ([runbook](../../../docs/runbooks/evaluation.md#scored-runs), steps 9 and 10). Every slot filled on its first attempt: 60 entries in `attempts.json`, all `complete`, none `no-result`.
- **Foundry cloud evaluation, verified on 2026-11-04:** repeat 1 of each arm and case, completed at 04:28:33Z ([below](#foundry-cloud-evaluation)).
- **Judge, verified on 2026-11-04:** prompt version 1 frozen ([`eval/judge/frozen.json`](../../judge/frozen.json)) before any judge call and before any run output was read. `claude-opus-5-5`, effort `high`, judged all 60 runs from 17:16:57Z to 17:23:51Z with no judge error (`python -m hindcast.evaluation.judge run`, [runbook](../../../docs/runbooks/evaluation.md#judge), step 17). The judgments were committed before any review decision.
- **Review and scores:** open. The review queue holds 880 items over the 60 runs (`python -m hindcast.evaluation.score --draft`).

## Dataset

| Part | Where | Frozen |
|---|---|---|
| Cases | `cloudflare-2025-11-18`, `github-2026-08-17`, `google-cloud-2026-07-14`, `github-2026-10-07` in [`data/cases.yaml`](../../../data/cases.yaml) | The registry pins each source by SHA-256 |
| Answer keys | [`eval/keys/`](../../keys/README.md) | SHA-256 per key in `eval/keys/frozen.json` |
| Labels | [`eval/keys/labels/`](../../keys/labels/README.md) | SHA-256 per file in `eval/keys/labels/frozen.json` |
| Rubric | [`eval/rubric/rubric.md`](../../rubric/rubric.md) | SHA-256 in `eval/rubric/frozen.json` |

Each run records the SHA-256 of the evidence file it read. Every run of a case read the same file:

| Case | Evidence SHA-256 |
|---|---|
| `cloudflare-2025-11-18` | `8b7e1ccb5bf0188613b7f7c76719ebc665d5787fcf90197ece0ae0d295f60fb6` |
| `github-2026-08-17` | `f45a778dc5a4db145f2ae8ab3c6f5100a1d5da187648531c7669ca1b07c768ee` |
| `google-cloud-2026-07-14` | `b4fa7c503cf93b309310bd6e8796a7fdaab6daa98b995f7defc863f8623e7b26` |
| `github-2026-10-07` | `9589943f72e1123ebb1c4d976ee36fe3274c851e268e7563c8776a80cc76938d` |

## Arms

The five arms of [decision 0023](../../../docs/decisions/0023-abstention-and-inferable-labels.md), three repeats per case, 12 runs per arm. All 60 runs ran from code commit `8d175ac` (tree `3144277a…` for `src/`) with a clean code and prompt tree, Prompt Shields and the PII check on, and, where the arm searches, the index `hindcast-library-1024` on search API version `2026-04-01`. The values below are read from `attempts.json` and each run's provenance.

| Arm | Deployment, model version | Agent, version | Prompt | Prompt blob |
|---|---|---|---|---|
| `hindcast` | `gpt-6-luna`, 2026-09-22 | `hindcast-investigator-gpt-6-luna`, 3 | `prompts/investigator.md` | `1d0911f4…` |
| `comparison` | `gpt-6.1-sol`, 2026-09-29 | `hindcast-investigator-gpt-6-1-sol`, 2 | `prompts/investigator.md` | `1d0911f4…` |
| `single-search` | `gpt-6-luna`, 2026-09-22 | none: one search, one model call | `prompts/single-search.md` | `939340e0…` |
| `library-off` | `gpt-6-luna`, 2026-09-22 | `hindcast-investigator-gpt-6-luna-library-off`, 1 | `prompts/investigator-library-off.md` | `60d84db0…` |
| `abstention` | `gpt-6-luna`, 2026-09-22 | `hindcast-investigator-gpt-6-luna-abstention`, 1 | `prompts/investigator-abstention.md` | `4fc4aed8…` |

The `hindcast` and `comparison` agents are the versions that made the sealed runs with the library search, on [2026-11-02](../../../docs/worklogs/05-sealed-reconstructions.md#second-seals-with-the-library-2026-11-02) and [2026-11-04](../../../docs/worklogs/05-sealed-reconstructions.md#third-seals-two-github-outages-of-2026-11-04) (`eval/sealed/seals.json`). A run's ID is `<arm>/<case_id>/r<repeat>/a<attempt>`; every run ID is in `attempts.json`.

The prior-knowledge answers that decide the known-before-evidence table are scored separately: [prior-knowledge check](../../prior-knowledge/v1/README.md).

## Foundry cloud evaluation

The generally available Foundry evaluators on repeat 1 of each arm and case ([decision 0006](../../../docs/decisions/0006-evaluation-design.md)): groundedness and relevance on every arm, tool call accuracy on the four agent arms (the single-search arm makes no tool calls of its own). Judge deployment `gpt-6.1-sol`, model version 2026-09-29. Live, 2026-11-04: `python -m hindcast.evaluation.foundry build`, `submit` (04:19:59Z), and `results` (04:28:33Z), runbook steps 12 to 14.

| Dataset | Rows | SHA-256 | Evaluation | Run |
|---|---|---|---|---|
| `hindcast-showcase-v1-quality` version 1 | 20 | `6aa87095…` | `eval_aec1d0f8bb7d4ae8aab749d603622dff` | `evalrun_b2062f4eff8d479ab0078f2f210cd01b` |
| `hindcast-showcase-v1-tools` version 1 | 16 | `6b9a2a92…` | `eval_1174097b41ca4f06bc3b33b3049f604c` | `evalrun_114619cbc16942faac568f78c428e37a` |

Mean score on the evaluators' 1 to 5 scale, over four rows per arm (one per case); failed rows in brackets:

| Arm | Groundedness | Relevance | Tool call accuracy |
|---|---|---|---|
| `hindcast` | 5.0 | 5.0 | 5.0 |
| `comparison` | 5.0 | 5.0 | 5.0 |
| `abstention` | 4.5 | 5.0 | 5.0 |
| `library-off` | 4.25 (1 failed) | 5.0 | 5.0 |
| `single-search` | 4.0 (1 failed) | 5.0 | not applicable |

Errored rows: 0 in both runs, counted per row as well as read from the service's own counts (quality: 18 passed, 2 failed, 0 errored; tools: 16 passed). A row with no score, no verdict, or an error would count as errored ([#7](https://github.com/sindredg/hindcast/issues/7)).

What these numbers can and cannot say:

- Groundedness compares a run's answer with the tool outputs it was shown, not with the postmortem. A grounded answer can still be wrong about the cause; the rubric's scores answer that.
- `gpt-6.1-sol` judges its own arm, `comparison`, as well as the others.
- One repeat of each arm and case: 20 runs of 60.
- A run file keeps the library refs a search returned, not the chunk text. For 10 of the 57 refs searched across all runs, the section spans more than one chunk, and the dataset's context holds the whole section: more than the run was shown.

## Limits

Written before the scores.

| Limit | What it means for the scores |
|---|---|
| A small library: 23 documents | Retrieval is close to a lookup, so the scores say little about retrieval quality ([retrieval check](../../retrieval/library-v1/README.md#limits)) |
| The keys have been public in this repository since 2026-10-27 | `gpt-6-luna` is version 2026-09-22 and `gpt-6.1-sol` version 2026-09-29, both before that day, so neither version's training data can include the keys. A later version could. The judge sees the key in every request, so its own training data does not change what it compares ([decision 0024](../../../docs/decisions/0024-judge-model.md)) |
| Training cutoffs | `cloudflare-2025-11-18` is the only showcase case that began before both models' training cutoffs. The [prior-knowledge check](../../prior-knowledge/v1/README.md) decides which model and case pairs go to the known-before-evidence table |
| Four cases, every key `not an attack` | A run that always answers "not an attack" gets every attack verdict right; no case tests an attack ([#19](https://github.com/sindredg/hindcast/issues/19)) |
| Abstention credit rests on the labels | The labels mark the root cause `not inferable` in three of the four cases (all but `google-cloud-2026-07-14`), and the attack verdict in the same three. On those items an abstention earns full credit. Each label is a judgment, approved by a person and frozen before any run ([labels](../../keys/labels/README.md#status)) |
| One judge model | `claude-opus-5-5` proposes every outcome. The review decides every proposed hit and partial and every support verdict on an inference, and a quarter of the rest ([rubric](../../rubric/rubric.md)) |
| A library citation resolves to the whole section | A run file keeps the refs a search returned, not the chunk text. For a section split over several chunks, the judge and the reviewer see more of it than the run was shown |
| Sealed cases | They have no single-search baseline (the comparison model runs in the agent's place) and no per-case library picks ([decision 0017](../../../docs/decisions/0017-sealed-reconstructions.md)). Their scores come in their own section at each reveal |

Known differences, each with no effect on these scores:

- **Abstention wording ([#65](https://github.com/sindredg/hindcast/issues/65)).** Decision 0023 defines a root-cause abstention as "a hedged claim and an open question that names what is missing". The rubric defines it as a root cause that "says the evidence does not determine it, names what is missing, and an open question asks for it", and counts a hedged statement as "a statement of what it hedges". The frozen rubric governs, and it matches the abstention prompt.
- **A stated label on a resolved update's time ([#66](https://github.com/sindredg/hindcast/issues/66)).** `github-2026-08-17` `timeline/1` is labelled `stated` on the resolved update alone, whose text the investigator never sees; its time is shown. `stated` and `inferable` earn the same credit.
- **Single-search `pii-error` keeps the model call's checks ([#64](https://github.com/sindredg/hindcast/issues/64)).** A `pii-error` attempt is not scored, and none of the 60 attempts ended that way.
- **Prior-knowledge effort ([#4](https://github.com/sindredg/hindcast/issues/4)).** The answers record the effort requested, `medium`, not the effort the service reports using.

## Files

| File | What it is |
|---|---|
| `README.md` | This page |
| `attempts.json` | One entry per attempt: run ID, arm, case, repeat, attempt, status, reason, result file and its SHA-256, usage, cost, agent, model, code commit |
| `runs/<arm>/<case_id>/r<repeat>-a<attempt>-<UTC time>.json` | One result per run, as `python -m hindcast.evaluation.batch` writes it |
| `foundry/runs.json` | The Foundry evaluation's judge deployment, datasets with their SHA-256, evaluation and run IDs, and criteria |
| `foundry/results.json` | Per arm and evaluator: rows passed, failed, and errored, and the mean score, with the service's own counts |
| `judgments/<arm>/<case_id>/r<repeat>/a<attempt>.json` | The judge's proposal for one run: an outcome per key item and a support verdict per run item, each with a reason; the run's ID, arm, and SHA-256; the code commit; the judge's model, effort, output limit, system prompt and input hashes, time, and request ID; the stop reason, usage, and any judge error |

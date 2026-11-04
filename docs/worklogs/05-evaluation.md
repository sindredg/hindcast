# Milestone 5, second part: Scoring the reconstructions

Status: In progress on 2026-11-04. The 60 scored runs, the 12 injection runs, and the Foundry cloud evaluation ran live; the judge, the review page, and the scoring are built and tested with stubs, and the judge prompts are frozen. The judge has not run, so nothing is scored yet. Milestone state: [roadmap](../roadmap.md#status).

## Scope

Score the blind reconstructions of the four showcase cases against their frozen keys, with five arms and three repeats each, and test planted instructions on two layers ([decision 0006](../decisions/0006-evaluation-design.md), [decisions 0022 to 0025](../decisions/)). The sealed reconstructions and the October case are the [first part](05-sealed-reconstructions.md). The procedure is the [evaluation runbook](../runbooks/evaluation.md).

## Work completed

### Preparation (#67)

The arms, the batch, the labels, the injection cases, the sealed-library snapshot, and rubric version 2, frozen before the first scored run ([#67](https://github.com/sindredg/hindcast/pull/67)). The rubric and the labels were approved item by item before the freeze.

### Excerpts

`hindcast.excerpts.resolve` turns a citation into the text it cites: an update or a chart from the case's evidence file, a library section or figure from the local extracts. Neither needs the search service, which was deleted after the runs. A library section resolves whole, because a result file keeps the ref and not the chunk; for a section longer than one chunk the excerpt holds more than the run was shown.

### The judge

`hindcast.evaluation.judge` sends one run at a time to `claude-opus-5-5` on the Anthropic API, effort `high`, streamed, `max_tokens` 64,000, with no server-side fallback ([decision 0024](../decisions/0024-judge-model.md)). The input is the key items with their postmortem quotes, the run's items after the citation checks, the open questions, the items the code found unsupported, and the text of every cited ref. It leaves out the run's arm and model and the labels: no outcome depends on them, and the score applies the labels afterwards.

Each item's support rule follows the run's own structure: a finding keeps the kind it declared, a timeline event is an observation when its time is stated, and the attack verdict, the root cause, and the factors are judged as inferences. The reply follows one fixed JSON schema: a list of run items, each with a support verdict, and a list of key items, each with an outcome and the run items it rests on. The code checks that the reply names every key item and every run item once, that each outcome is one rubric version 2 allows for that kind of key item, and that no item the code found unsupported is judged supported; a reply that fails is a schema error. The judgment is stored keyed by item.

The first version put those rules in a schema built per run, with one entry per key item and per run item. The API refused it on the first test call: the compiled grammar was too large, and probes put the cause in the one list per key item ([troubleshooting](../troubleshooting.md#judge-the-api-refuses-the-reply-schema-as-too-large-2026-11-04)).

A refusal, an empty reply, a reply cut at `max_tokens`, a schema failure, or outcomes that contradict the reply's own support verdicts is recorded as a judge error with its kind, never read as a verdict. `run` judges an errored run again on the next call and keeps every good judgment. It refuses unless `prompts/judge.md` and the rubric match `eval/judge/frozen.json`.

`hindcast.evaluation.judge_prior` uses the same model and settings on the 14 prior-knowledge answers: hit, partial, abstained, missed, or wrong on the root cause and the attack verdict, with its own lock, `eval/judge/frozen-prior.json`.

### Review and scores

`hindcast.evaluation.review` builds the queue rubric version 2 asks for: every proposed supported hit, partial, unsupported hit, and unsupported partial, every support verdict on an inference, and a quarter of the rest drawn per run with the seed 20261104 (rounded up). `src/hindcast/review.py` is a local Streamlit page that shows one item per screen with the cited text, under a blind run ID in a seeded order that does not follow the arm. Each decision is saved with the hash of the judgment it reviews, and the page resumes at the first open item. A second mode reviews the prior answers.

`hindcast.evaluation.score` replaces the judge's proposals with the reviewed decisions, applies the frozen labels' credit, and writes per run the primary score and, beside it, the unsupported, wrong, and guessed items, the supported items outside the key, and any review decisions that contradict each other. Per arm and case it gives the mean, minimum, and maximum, summed outcomes, failures, seconds, and cost; a model's runs on a case its prior answer already hit move to a known-before-evidence table. It refuses while a review item is open.

## Live runs

All on 2026-11-04 unless stated, from the developer's sign-in, with the commands in the [runbook](../runbooks/evaluation.md).

| Step | Result |
|---|---|
| Sealed library snapshots (2026-11-03, 21:24Z) | 267 chunks for each of the three sealed cases, under `build/sealed-library/`, recorded in `eval/sealed/library-snapshots.json` |
| Injection runs, 03:43:28Z to 03:53:25Z | 12 runs: 8 pass, 4 not reached, 0 fail ([report](../../eval/injection/dev-v1/README.md)) |
| Scored runs, 03:10:48Z to 04:00:47Z | 60 runs, all `complete` on the first attempt; summed cost USD 3.0871 by price table version 1 ([report](../../eval/reconstruction/showcase-v1/README.md#status)) |
| Foundry cloud evaluation, 04:19:59Z to 04:28:33Z | Both runs `completed`, 0 errored rows ([report](../../eval/reconstruction/showcase-v1/README.md#foundry-cloud-evaluation)) |
| Clean-up | The search service deleted at 05:40Z; Content Understanding Contributor removed at 05:49:42Z and a read refused 27 seconds later ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)) |
| Judge test calls on the development run, 16:40:56Z and 17:07Z | HTTP 400, "The compiled grammar is too large", before and after the enum was dropped from the reply schema; no judgment written ([troubleshooting](../troubleshooting.md#judge-the-api-refuses-the-reply-schema-as-too-large-2026-11-04)) |
| Schema probes, 17:08Z to 17:10Z | One part of the schema changed per request: the cause is the one array per key item ([finding](../findings/models.md#structured-output-refuses-a-schema-with-one-array-per-key-item-2026-11-04)) |
| Judge test call on the development run, 17:13:26Z to 17:14:12Z | `end_turn`, no judge error, all 21 key items and 18 run items judged; 6,770 input, 2,429 cache-write, and 3,925 output tokens |

The first scored run read its `reasoning.applied` as `[medium]` ([#26](https://github.com/sindredg/hindcast/issues/26)) and its library contents as 143 chunks with their SHA-256 ([#47](https://github.com/sindredg/hindcast/issues/47)). Its trace in Application Insights held the `investigation` span with three `model_call`, three `tool_call`, and two `pii` children.

## Checks

Every new check was run once against a broken copy of its code, locally, on 2026-11-04, and failed; each copy was then restored and the suite passed (794 tests).

| Broken | Failed tests |
|---|---|
| The resolver ignores a citation's source | `test_resolve_unknown_is_none` |
| The judge's refusal check removed | `test_refusal_is_error_not_verdict`, `test_judge_all_keeps_a_judgment_and_retries_an_error` |
| The `max_tokens` check removed | `test_cut_reply_is_error` |
| The local schema check removed | `test_schema_failure_is_error`, `test_prior_judge_errors_are_recorded_and_retried` |
| The check that each item appears once removed | `test_judgment_names_each_item_once` |
| The check that every key item and run item appears removed | `test_judgment_covers_every_key_item` |
| The outcome-per-kind check removed | `test_outcome_must_fit_the_key_item` |
| A key item may list a run item the run does not have | `test_a_key_item_naming_an_unknown_run_item_is_error` |
| The code-unsupported check removed | `test_code_unsupported_items_cannot_be_judged_supported` |
| The judgment stored in the reply's order | `test_judgment_is_stored_keyed_by_item` |
| The consistency check removed | `test_inconsistent_reply_is_error` |
| `fallbacks` sent | `test_no_fallbacks_sent` |
| No-result attempts judged | `test_judge_skips_no_result_attempts` |
| The freeze comparison off | `test_judge_refuses_unfrozen_prompt` |
| Good judgments redone | `test_judge_all_keeps_a_judgment_and_retries_an_error` |
| The prior judge without its freeze check, with partial allowed on the attack verdict, or redoing good judgments | `test_prior_judge_refuses_unfrozen_prompt`, `test_prior_judge_errors_are_recorded_and_retried`, `test_prior_judge_writes_one_judgment_per_answer` |
| Only supported hits required in the queue | `test_queue_has_every_proposed_match` |
| Inference verdicts only sampled | `test_queue_has_every_inference_support_verdict`, `test_queue_samples_a_quarter_of_the_rest` |
| An unseeded draw | `test_queue_sample_is_deterministic` |
| Code-unsupported items reviewed | `test_code_unsupported_items_are_not_reviewed` |
| The judgment hash not checked | `test_review_refuses_decisions_on_another_judgment` |
| Any decision accepted | `test_a_decision_must_be_one_of_the_choices` |
| The page without resume, with the run ID in its title, or saving nothing | `test_review_saves_and_resumes` |
| An unsupported hit credited | `test_unsupported_hit_scores_zero` |
| Every abstention credited | `test_justified_abstention_credited_only_when_not_inferable` |
| A not-inferable miss scored 0 | `test_unmentioned_not_inferable_factor_leaves_denominator`, `test_aggregate_gives_mean_min_max_and_failures` |
| The review ignored | `test_review_overrides_judge`, `test_a_match_that_contradicts_its_support_verdicts_is_listed` |
| Kappa without the chance term | `test_kappa_on_known_table` |
| The known-before-evidence row ignored, or the prior review ignored | `test_known_before_evidence_row`, `test_known_before_evidence_comes_from_a_reviewed_prior_hit` |

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Keys, labels, rubric, support criteria, and tolerance frozen before the first scored run, and the leak check passes | Tested, live and locally | Labels frozen 2026-11-03T21:17Z, rubric version 2 2026-11-04T02:53:28Z (`eval/rubric/frozen.json`), keys last changed 2026-11-01; first scored run 03:10:48Z. `tests/test_rubric.py` and `tests/test_labels.py` fail on a changed file ([#67](https://github.com/sindredg/hindcast/pull/67)). Leak check live on 2026-11-01, 0 hits for every case with a frozen key ([worklog 03](03-retrieval.md#gate)); the keys and `data/library.yaml` are unchanged since |
| Each showcase case scored for every arm with its repeats, each result named | Open | Runs: tested live, 60 of 60 with their provenance in `attempts.json` and each result file. Judging, review, and scores not run |
| Each sealed case revealed and scored only after its provider published a cause | Open | No provider had published a cause by 2026-11-04; drop date 2026-11-30 ([decision 0022](../decisions/0022-sealed-drop-date-and-offline-reveal.md)) |
| Unsupported claims counted by the support rules; library-only claims unsupported | Tested locally, with stubs | The citation checks in code ([#25](https://github.com/sindredg/hindcast/issues/25)); the judge's support verdicts and the score's counts, tests above. Not run on the scored runs |
| Planted instructions in an update, a library page, and a chart image not followed, screens on and off | Tested live for the update and the library page; open for the chart | 8 runs saw the planted text, none followed it; no search returned the planted chart in the 4 chart runs ([report](../../eval/injection/dev-v1/README.md)) |
| The report states results, error analysis, and the named limits | Open | Written after the scores |

## Issues

None opened yet in this part.

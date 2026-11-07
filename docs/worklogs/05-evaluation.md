# Milestone 5, second part: Scoring the reconstructions

Status: Verified on 2026-11-07. Every criterion in the [gate](#gate) has a tested row or an accepted gap, the [independent review](#independent-review) of 2026-11-04 and the [milestone close review](#milestone-close-review) ran with their fixes in, and the first sealed case is revealed and scored ([sealed report](../../eval/reconstruction/sealed-v1/README.md)). Four sealed cases remain, each an addendum or dropped on 2026-11-30 ([decision 0030](../decisions/0030-close-evaluation-with-sealed-addenda.md)). Milestone state: [roadmap](../roadmap.md#status).

## Scope

Score the blind reconstructions of the four showcase cases against their frozen keys, with five arms and three repeats each, and test planted instructions on two layers ([decision 0006](../decisions/0006-evaluation-design.md), [decisions 0022 to 0026](../decisions/)). The sealed reconstructions and the October case are the [first part](05-sealed-reconstructions.md). The procedure is the [evaluation runbook](../runbooks/evaluation.md).

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

### Case-chart injection variant

No search in the four library chart runs returned the planted figure, so that variant tested nothing. [Decision 0026](../decisions/0026-case-chart-injection.md) adds a fourth injection copy, `cloudflare-2026-02-20-inject-case-chart`, that puts the planted chart after the development case's two charts, where `list_charts` returns it in every run that calls it. A case chart reaches the model as its alt text and description only; the analyzer put the planted text in `text_in_image`, so the copy writes the instruction into the description. `hindcast.injection.case_chart_shows_planted_text` records the as-described result offline, and `reached` counts the planted chart in `list_charts` calls ([report](../../eval/injection/dev-v1/README.md#case-chart-variant)).

### The reviewer

A person's review of 898 items would take days, so [decision 0027](../decisions/0027-reviewer-model.md) gives it to a second model, decided before any review decision existed and while no person had read a scored output. Rubric version 3 changes only its Review section; the queue, the outcomes, and the credit stay as version 2 froze them.

`hindcast.evaluation.reviewer` runs the judge's code with `claude-fable-5-1` and its own locks, on the same input and without the judge's proposals. Its prompts are the judge's less the sentence "A person reviews your verdicts."; a test fails if they differ in anything else. `apply` writes its verdict on each queue item as the review decision, naming the model and the SHA-256 of its judgment, and refuses a second judgment made on other input or under another lock.

Version 3's title line is part of the judge's system prompt, so composing the prompt again would no longer match the judgments made under version 2. The score now checks each judgment's recorded system-prompt hash and model against its lock, and the judge's locks keep version 2's hash as the record of what the judge was given.

### Review and scores

`hindcast.evaluation.review` builds the queue rubric version 2 froze and version 3 keeps: every proposed supported hit, partial, unsupported hit, and unsupported partial, every support verdict on an inference, and a quarter of the rest drawn per run with the seed 20261104 (rounded up). `src/hindcast/review.py` is a local Streamlit page that shows one item per screen with the cited text, under a blind run ID in a seeded order that does not follow the arm. Each decision is saved with the hash of the judgment it reviews, and the page resumes at the first open item. A second mode reviews the prior answers.

`hindcast.evaluation.score` replaces the judge's proposals with the reviewed decisions, applies the frozen labels' credit, and writes per run the primary score and, beside it, the unsupported, wrong, and guessed items, the supported items outside the key, and any review decisions that contradict each other. Per arm and case it gives the mean, minimum, and maximum, summed outcomes, failures, seconds, and cost; a model's runs on a case its prior answer already hit move to a known-before-evidence table. It refuses while a review item is open.

### Scores after the review

The first scores showed three contradictions between a match and its support. Each was the same artifact: where the judge proposed missed and the reviewer found a partial or a hit, the reviewer's outcome was checked against the judge's run items, and the judge listed none. A decision the reviewer model made now rests on the run items its own judgment listed, and the score refuses a decision whose reviewer judgment is missing or has another hash. No primary score moved; the contradictions went to 0, and the counts of supported items outside the key shifted.

The queue's agreement covers mostly proposed hits. `scores.json` therefore also carries `second_opinion`: the agreement over every key item and run item, and each arm's mean with the judge's judgment alone and with the reviewer's alone. Neither replaces the rubric's score; they show how far the choice of judge moves it. They are written only when every run has a decision from the reviewer model, and `score` says when it leaves them out.

### Spend

`hindcast.evaluation.spend` prices the Claude API usage that every judgment file records, per stage and model, at `data/claude-prices.yaml` (version 1, read 2026-11-04 from the Claude pricing page), and writes `eval/judge/spend.json`. The Claude table stays apart from the Azure one: it bills to another account, and its units include cache writes. A call that errored and was run again leaves only its error kind, so it is counted as unpriced, never as free; a stage with no files is refused.

## Live runs

All on 2026-11-04 unless stated, from the developer's sign-in, with the commands in the [runbook](../runbooks/evaluation.md).

| Step | Result |
|---|---|
| Sealed library snapshots (2026-11-03, 21:24Z) | 267 chunks for each of the three sealed cases, under `build/sealed-library/`, recorded in `eval/sealed/library-snapshots.json` |
| Injection runs, 03:43:28Z to 03:53:25Z | 12 runs: 8 pass, 4 not reached, 0 fail ([report](../../eval/injection/dev-v1/README.md)) |
| Scored runs, 03:10:48Z to 04:00:47Z | 60 runs, all `complete` on the first attempt; summed cost USD 3.0871 by price table version 1 ([report](../../eval/reconstruction/showcase-v1/README.md#status)) |
| Foundry cloud evaluation, 04:19:59Z to 04:28:33Z | Both runs `completed`, 0 errored rows ([report](../../eval/reconstruction/showcase-v1/README.md#foundry-cloud-evaluation)) |
| Clean-up | The search service deleted at 05:40Z; Content Understanding Contributor removed at 05:49:42Z and a read refused 27 seconds later ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)) |
| Search service recreated, 16:38:56Z to 16:39:38Z | From `infra/search.bicep`, for the [new seals](05-sealed-reconstructions.md#third-seals-two-github-outages-of-2026-11-04) and the case-chart runs; `hindcast-library-1024` rebuilt with 267 chunks, 16:40:18Z to 16:42:38Z |
| Judge test calls on the development run, 16:40:56Z and 17:07Z | HTTP 400, "The compiled grammar is too large", before and after the enum was dropped from the reply schema; no judgment written ([troubleshooting](../troubleshooting.md#judge-the-api-refuses-the-reply-schema-as-too-large-2026-11-04)) |
| Schema probes, 17:08Z to 17:10Z | One part of the schema changed per request: the cause is the one array per key item ([finding](../findings/models.md#structured-output-refuses-a-schema-with-one-array-per-key-item-2026-11-04)) |
| Judge test call on the development run, 17:13:26Z to 17:14:12Z | `end_turn`, no judge error, all 21 key items and 18 run items judged; 6,770 input, 2,429 cache-write, and 3,925 output tokens |
| Judge, 17:16:57Z to 17:23:51Z | `judged 60, errors 0, kept 0`, four workers; 438,615 input, 145,740 cache-read, and 187,630 output tokens. Every call read the cached system prompt |
| Prior-knowledge judge, 17:24:07Z to 17:24:56Z | `judged 14, errors 0, kept 0`; 11,775 input, 1,237 cache-write, 16,081 cache-read, and 2,712 output tokens |
| Review queue | `python -m hindcast.evaluation.score --draft`: 880 open items over the 60 runs and 18 over the 14 prior answers. The judgments were committed (`bda8758`) before any review decision |
| Injection index rebuilt, 17:36:24Z | `hindcast-injection-1024`: 91 chunks, 2 with planted text, as on the first build |
| Case-chart injection runs, 17:36:43Z to 17:40:45Z | 4 runs, all pass: the planted chart shown in each, nothing followed, none withheld by the screen ([report](../../eval/injection/dev-v1/README.md#case-chart-variant)) |
| Clean-up | The search service deleted again at 17:41:08Z |
| Rubric version 3 and the reviewer's locks, 18:56:41Z and 18:57:31Z | Committed and pushed before the full reviewer run (`dafd2df`, `fac02e9`) |
| Reviewer test call, 18:58:01Z to 18:59:23Z | `runs: judged 1, errors 0`: `hindcast/cloudflare-2025-11-18/r1/a1`, `end_turn` from `claude-fable-5-1`, the same input hash as the judge's, all 20 key items and 22 run items; 7,769 input, 2,418 cache-write, and 6,935 output tokens |
| Reviewer, 19:02:48Z to 19:17:22Z | Runs `judged 59, errors 0, kept 1`, prior answers `judged 14, errors 0`, four workers, every call `end_turn`; 450,390 input, 3,644 cache-write, 158,600 cache-read, and 296,580 output tokens over all second judgments |
| Review decisions, 19:17:49Z to 19:17:50Z, locally | `reviewer apply`: `runs 60, decisions 880, missing 0` and `prior answers 14, decisions 18, missing 0`; a second `apply` wrote none. Committed with the second judgments (`cb81716`, `2f08ed2`) |
| Scores, locally | `score`: `open review items 0` for the 14 answers and the 60 runs; `scores.json` in both roots. Results: [report](../../eval/reconstruction/showcase-v1/README.md#results), [prior knowledge](../../eval/prior-knowledge/v1/README.md#results) |
| Spend, locally | `spend`: judge USD 5.54 (runs) and 0.11 (answers), reviewer USD 19.14 and 0.27, `total USD 25.07, 0 unpriced calls`. Not compared yet with the Anthropic Console's billed total |

The first scored run read its `reasoning.applied` as `[medium]` ([#26](https://github.com/sindredg/hindcast/issues/26)) and its library contents as 143 chunks with their SHA-256 ([#47](https://github.com/sindredg/hindcast/issues/47)). Its trace in Application Insights held the `investigation` span with three `model_call`, three `tool_call`, and two `pii` children.

## Checks

Every new check was run once against a broken copy of its code, locally, on 2026-11-04, and failed; each copy was then restored and the suite passed (797 tests; 820 after the reviewer; 833 after the scores and the spend; 836 after the independent review's fixes). The copies run with pytest's path pointed at them (`-o pythonpath=<copy>`): the project's `pythonpath = ["src"]` otherwise loads the unbroken code first, and every copy passes.

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
| The instruction not written into the planted chart's description, the planted chart displayed, or its number not checked | `test_case_chart_copy_adds_the_planted_chart_with_the_instruction_in_its_description` |
| A case chart read as showing `text_in_image` | `test_a_case_chart_shows_the_model_no_text_read_off_the_image` |
| `list_charts` calls not counted for the case-chart variant | `test_reached_counts_the_planted_case_chart_in_list_charts` |
| The judge call, the judge lock, or the prior judge ignoring the model it is given | `test_judge_all_calls_and_records_the_model_it_is_given`, `test_a_lock_for_one_model_refuses_another`, `test_prior_judge_calls_and_records_the_model_it_is_given` |
| The locked prompt not checked against its file | `test_locked_system_outlives_a_rubric_version_but_not_a_prompt_change` |
| The score ignoring a judgment's model, or the prior score ignoring the lock | `test_score_refuses_a_judgment_from_another_prompt_or_model[change1]`, `test_prior_score_refuses_a_judgment_from_another_prompt` |
| The decision taken from the judge's proposal instead of the reviewer's verdict | `test_decisions_are_the_second_judgments_verdicts`, `test_prior_decisions_come_from_the_second_judgment` |
| The input check, the error check, the open-item filter, or `decided_by` removed | `test_a_second_judgment_on_other_input_is_refused`, `test_an_errored_second_judgment_is_refused`, `test_apply_is_idempotent`, `test_decisions_name_the_reviewer_and_its_judgment` |
| A second judgment from another lock accepted, an errored one applied, or no-result attempts read | `test_apply_runs_refuses_a_second_judgment_from_another_lock` (both cases), `test_apply_runs_counts_a_missing_or_errored_second_judgment`, `test_apply_runs_writes_the_reviews_of_every_filled_run` |
| The reviewer's prompt changed beyond the removed sentence | `test_reviewer_prompts_are_the_judges_less_the_review_sentence` |
| Cache reads left out of the Claude price | `test_claude_cost_prices_each_part`, `test_claude_cost_missing_usage_field_raises`, `test_spend_per_stage_and_model` |
| A missing usage field priced as zero | `test_claude_cost_missing_usage_field_raises` |
| The cached tokens subtracted from the input count | `test_claude_cost_prices_each_part`, `test_spend_per_stage_and_model` |
| An errored call that was run again, or a record without usage, not counted as unpriced | `test_spend_counts_calls_it_cannot_price` (both) |
| A stage with no files accepted | `test_spend_refuses_an_empty_stage` |
| A stage folder other than the one the reviewer writes | `test_stages_are_the_folders_the_judge_and_reviewer_write` |
| A price table without the reviewer's model | `test_committed_table_prices_the_judge_and_reviewer_models` |
| A reviewer decision checked against, or listed by, the judge's run items | `test_a_reviewer_decision_rests_on_the_reviewers_run_items` (both) |
| A reviewer decision scored without its judgment | `test_a_reviewer_decision_without_its_judgment_is_refused` |
| The reviewer judgment's hash not checked | `test_second_judgments_load_only_when_their_hash_matches` |
| The whole-judgment agreement without the support verdicts, or comparing the judge with itself | `test_whole_judgment_agreement_counts_every_item` (both) |
| The judge-alone score taken from the reviewer, or the reviewer-alone score from the judge | `test_each_judge_alone_is_scored_without_the_review` (both) |
| A person's decision checked against the reviewer's run items whenever any item of the run was the reviewer's | `test_a_person_decision_keeps_the_judges_run_items` |
| The first decision on an item naming who decided, instead of the latest | `test_the_latest_decision_on_an_item_names_who_decided` |
| The second opinion written when only some runs have a reviewer judgment | `test_second_opinion_needs_a_reviewer_judgment_for_every_run` |

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Keys, labels, rubric, support criteria, and tolerance frozen before the first scored run, and the leak check passes | Tested, live and locally | Labels frozen 2026-11-03T21:17Z, rubric version 2 2026-11-04T02:53:28Z (`eval/rubric/frozen.json`), keys last changed 2026-11-01; first scored run 03:10:48Z. `tests/test_rubric.py` and `tests/test_labels.py` fail on a changed file ([#67](https://github.com/sindredg/hindcast/pull/67)). Leak check live on 2026-11-01, 0 hits for every case with a frozen key ([worklog 03](03-retrieval.md#gate)); `data/library.yaml` and every key and label entry locked then are unchanged since. On 2026-11-07 the revealed case added its key and labels after the lock, which `tests/test_rubric.py` allows only for a case in `reveals.json`, and its leak check against the library snapshot found 0 hits ([worklog 05, reveal](05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07)) |
| Each showcase case scored for every arm with its repeats, each result named | Tested, live and locally | Runs: live, 60 of 60 with their provenance in `attempts.json` and each result file. Judge and reviewer: live, 60 runs and 14 answers each with no error; 880 and 18 decisions, none open. Scores: locally, `scores.json` from the committed judgments and reviews. Each result is named in the report: the keys, labels, and rubric by hash, the evidence SHA-256 per case, and per arm the deployment, model version, agent version, prompt blob, and run IDs ([dataset](../../eval/reconstruction/showcase-v1/README.md#dataset), [arms](../../eval/reconstruction/showcase-v1/README.md#arms)) |
| Each sealed case revealed and scored only after its provider published a cause | Tested live and locally for `github-2026-11-04-actions` on 2026-11-07; accepted gap for the other four | The reveal refused to open a seal until the key and labels were frozen, the leak check passed, and the cause's publication time (2026-11-07T01:04:38Z) was after both seals; both files match their hashes, and both runs are scored ([worklog 05, reveal](05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07), [sealed report](../../eval/reconstruction/sealed-v1/README.md)). The four others had no published cause on 2026-11-07; each is revealed as an addendum or dropped on 2026-11-30 ([decision 0030](../decisions/0030-close-evaluation-with-sealed-addenda.md)) |
| Unsupported claims counted by the support rules; library-only claims unsupported | Tested live for the counts; accepted gap for the library-only rule on scored runs | The judge and the reviewer judged the support of all 1,242 run items in the 60 runs; 5 are unsupported, and the report lists each ([error analysis](../../eval/reconstruction/showcase-v1/README.md#unsupported-run-items)). The library-only rule is tested with stubs only: no scored run item cites a library document alone (13 cite one next to case evidence, counted from the run files), so the live runs could not exercise it. Check again at the first scored run item that cites only the library |
| Planted instructions in an update, a library page, and a chart image not followed, screens on and off | Tested live for the update, the library page, and a planted chart's description; accepted gap for text carried only in an image | 12 runs saw the planted text, none followed it. No search returned the library figure in the 4 chart runs; the 4 case-chart runs read the instruction from the chart's description, where it was written because the analyzer kept it in `text_in_image` ([decision 0026](../decisions/0026-case-chart-injection.md), [report](../../eval/injection/dev-v1/README.md#case-chart-variant)). The gap is accepted because text read off an image has one way to the model: a case chart shows `alt_text` and `description` only (`list_charts` in `src/hindcast/tools.py`), and a library figure's `text_in_image` reaches it as part of the figure's search chunk (`chunks` in `src/hindcast/index.py`), the same search-result path the library-page variant reached and passed in 4 of 4 runs. Not tested: whether the analyzer's reading of an image changes what Prompt Shields or the model do with the text. Check again when a tool shows the model `text_in_image` in another way |
| The report states results, error analysis, and the named limits | Tested locally, by the [independent review](#independent-review) | The review recomputed the report's numbers from the data files, reproduced `scores.json` and `spend.json` byte for byte, and found 13 statements to correct, all fixed. Results per arm, per arm and case, and known before evidence, with the full outcome table; the judge-reviewer agreement; the error analysis with the list decision 0006 asks for (empty) ([report](../../eval/reconstruction/showcase-v1/README.md#results)). The named limits are rows of its Limits table: the 23-document library, the keys public since 2026-10-27 against each model version's date, and the sealed cases without a single-search baseline or library picks. The [sealed report](../../eval/reconstruction/sealed-v1/README.md#limits) states the same limits for the revealed seals, and the [milestone 5 close review](05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07) recomputed its scores and spend from the files |

## Independent review

On 2026-11-04 a read-only review of the branch at `654cb40` checked the spend and score code and their tests, every number and claim in the two reports against `scores.json`, `attempts.json`, the judgments, the reviews, the keys, the labels, the run files, and `spend.json`, the scores against the rubric, the state pages for stale statements, and the public text. It reproduced both `scores.json` files and `spend.json` byte for byte. Each finding was checked against the data before acting on it.

Fixed in this pull request:

| Finding | Fix |
|---|---|
| The report said only `u24` names Issues and Pull Requests; nine updates do | It says none of the updates the finding cites names them |
| The unsupported-items lead said all five carry a detail from an uncited update; two do, two rest on one that does, one is about a withheld text | The lead names the three kinds |
| "Each `not an attack` adds 0.20" is not exact: one run gains 0.17 | Per-run differences against `hindcast` instead |
| A limits row said the differences between arms are smaller than the change of judge; three are larger (0.041, 0.037, 0.033 against 0.030) | The row gives the largest difference next to the judge's swing |
| `comparison` was said to fall "from third to last"; under the rubric it is fourth | Its rank under each of the three scorings |
| "Supported items outside the key" were called reviewed; 521 of 831 carry the judge's verdict only | The definition says whose verdict it is |
| The cost table counted runs as calls and read as the whole evaluation | Runs and calls named; the injection runs and the Foundry judge calls named as left out |
| The architecture page named `eval/*/v1/scores.json`, which misses the showcase file | Both paths |
| The Abstained column holds 12 abstentions the credit counts as missed | A sentence under the table |
| The report's gate row named no check | This review is its check |
| `gpt-6.1-sol` "in the same agent": the arms use two agents with the same prompt and tools | Reworded |
| A test built a review it never used | Removed |
| Decision 0023 had no pointer to decision 0027 | One sentence in its status line |
| Three score paths had no test: a person's decision next to a reviewer's, the latest decision on an item, and the second opinion with some runs not reviewer-decided | Tests added (checks table); the second opinion's condition is a function of its own, and `score` says when it leaves it out |
| The judge split the same 17:44 claim on `timeline/10` between wrong and missed | The wrong-items row says so |

Planned, not fixed here: [#75](https://github.com/sindredg/hindcast/issues/75), the evaluation diagram's missing input.

## Milestone close review

On 2026-11-07 a read-only review from a fresh context checked the close on `feat/m5-reveal-close` at `f2504c9`: the reveal code and its tests, the reveal's evidence recomputed from the files, the key and labels against the captured summary and the evidence, `scores.json` and `spend.json` recomputed from the judgments, reviews, labels, and price table (both matched exactly), the judge's lock rebuild, the `--root` options, the rubric lock check, every role check in `src/`, decision 0030 against 0006, 0017, 0022, and 0023, the sealed report, the runbook, the stale pages, the public-text rules, and the issues. It ran the suite (1004 passed) and mutated a copy of `reveal.py`; it called no API.

Verdicts: 9 of 15 items OK, 6 with findings. Fixed in the same pull request:

| Finding | Fix |
|---|---|
| The worklog said the reveal ran from a clean commit; it ran from an uncommitted tree, and runbook step 18 was skipped | Worklog and runbook say what happened; the reveal now refuses an uncommitted tree and records its commit (`17c864f`) |
| The sealed report left out the roadmap's third limit and the prompts it ran with | Limits, the investigator prompt blob, and the judge and reviewer prompt hashes added; gate row 6 links the sealed report |
| Five reveal refusals could be removed with every test passing | Tests for the registry hash, an existing target, no resolved update, the equality boundary, and a dirty tree; a refusal now also leaves no ledger and reads no sealed file; each shown failing with its rule removed |
| Nothing tied a revealed case's key, labels, and evidence to its reveal record, and a `revealed` role needed no record | `record_problems` compares the three hashes and requires a record for every revealed role; the rubric lock takes its revealed set from `reveals.json` (`47f226f`) |
| The investigation-loop diagram, its alt text, and the challenge row left out the `revealed` refusal | Fixed; diagram checked, rendered, and read |
| Gate row 1 said the keys were unchanged since the lock | Reworded to the locked entries, with the revealed case's additions |
| The report did not name the one judge-reviewer disagreement | Named in the error analysis (`timeline/0`, the same tolerance pattern), and added to #99 |
| A malformed sealed file could leave a half-revealed case | Every file is parsed into its ledger entry before anything is written |
| The judge's module help and the "Last compared" order were stale | Fixed |
| #75 was due at the close | The evaluation diagram's reviewer arrow reads `ALL VERDICTS`, and its alt text names the full judgments the score reads |

Plan only, opened as issues: [#102](https://github.com/sindredg/hindcast/issues/102) (the publication time is the last edit of the summary), [#103](https://github.com/sindredg/hindcast/issues/103) (`keys draft` without `--case`), [#104](https://github.com/sindredg/hindcast/issues/104) (`--root` paths compared as written). The review's first plan item, a reveal without a clean tree, was fixed instead.

## Issues

- [#69](https://github.com/sindredg/hindcast/issues/69): every injection copy's case ID and refs contain `inject`, which the model can read.
- [#71](https://github.com/sindredg/hindcast/issues/71): an abstention earns credit when its root-cause item is unsupported.
- [#72](https://github.com/sindredg/hindcast/issues/72): a partial on a `not inferable` factor lowers the run's score.
- [#75](https://github.com/sindredg/hindcast/issues/75): the evaluation diagram leaves out the reviewer judgments the score reads.

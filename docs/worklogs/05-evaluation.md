# Milestone 5, second part: Scoring the reconstructions

Status: Verified on 2026-11-07 ([gate](#gate), [independent review](#independent-review), [milestone close review](#milestone-close-review)). One sealed case revealed and scored ([sealed report](../../eval/reconstruction/sealed-v1/README.md)); four remain, each an addendum or dropped on 2026-11-30 ([decision 0030](../decisions/0030-close-evaluation-with-sealed-addenda.md)). Milestone state: [roadmap](../roadmap.md#status).

On this page: [Scope](#scope) · [Work completed](#work-completed) · [Live runs](#live-runs) · [Checks](#checks) · [Gate](#gate) · [Independent review](#independent-review) · [Milestone close review](#milestone-close-review) · [Issues](#issues)

## Scope

Score the blind reconstructions of the four showcase cases against their frozen keys, five arms and three repeats each, and test planted instructions on two layers ([decision 0006](../decisions/0006-evaluation-design.md), [decisions 0022 to 0026](../decisions/)). Sealed reconstructions and the October case: the [first part](05-sealed-reconstructions.md). Procedure: the [evaluation runbook](../runbooks/evaluation.md).

## Work completed

### Preparation (#67)

- Arms, batch, labels, injection cases, sealed-library snapshot, and rubric version 2 frozen before the first scored run ([#67](https://github.com/sindredg/hindcast/pull/67)).

### Excerpts

- `hindcast.excerpts.resolve` turns a citation into its text from the case's evidence file or the local extracts, without the search service. A library section resolves whole, so a multi-chunk section's excerpt holds more than the run saw.

### The judge

- `hindcast.evaluation.judge`: one run per call to `claude-opus-5-5` on the Anthropic API, effort `high`, streamed, `max_tokens` 64,000, no server-side fallback ([decision 0024](../decisions/0024-judge-model.md)).
- Input: key items with quotes, run items after the citation checks, open questions, code-unsupported items, and every cited ref's text. Not the arm, model, or labels.
- A finding keeps its declared kind; a timeline event with a stated time is an observation; attack verdict, root cause, and factors are inferences.
- One fixed JSON schema: a support verdict per run item, an outcome per key item with its run items. Checked: every item named once, each outcome allowed by rubric version 2 for its kind, no code-unsupported item judged supported. Stored keyed by item.
- A per-run schema was refused as too large; the cause was the one list per key item ([troubleshooting](../troubleshooting.md#judge-the-api-refuses-the-reply-schema-as-too-large-2026-11-04)).
- A refusal, an empty reply, a cut at `max_tokens`, a schema failure, or self-contradicting outcomes is a judge error with its kind, retried on the next `run`, never a verdict. `run` refuses unless `prompts/judge.md` and the rubric match `eval/judge/frozen.json`.
- `hindcast.evaluation.judge_prior`: the same settings on the 14 prior-knowledge answers (hit, partial, abstained, missed, or wrong), lock `eval/judge/frozen-prior.json`.

### Case-chart injection variant

- The four library chart runs never retrieved the planted figure. [Decision 0026](../decisions/0026-case-chart-injection.md) adds `cloudflare-2026-02-20-inject-case-chart`: the planted chart after the development case's two, returned by every `list_charts` call, its instruction in the description (a case chart reaches the model as alt text and description only; the analyzer had put the text in `text_in_image`). `hindcast.injection.case_chart_shows_planted_text` records the result offline; `reached` counts `list_charts` calls ([report](../../eval/injection/dev-v1/README.md#case-chart-variant)).

### The reviewer

- 898 items are too many for a person; [decision 0027](../decisions/0027-reviewer-model.md) gives the review to a second model, decided before any review decision or read of a scored output. Rubric version 3 changes only its Review section.
- `hindcast.evaluation.reviewer`: the judge's code with `claude-fable-5-1`, its own locks, the same input, no judge proposals; prompts are the judge's less "A person reviews your verdicts." (tested). `apply` writes each verdict as the review decision with the model and the judgment's SHA-256; it refuses a judgment on other input or another lock.
- The score checks each judgment's system-prompt hash and model against its lock; the judge's locks keep version 2's hash.

### Review and scores

- `hindcast.evaluation.review`: the queue is every proposed supported hit, partial, unsupported hit, and unsupported partial, every inference support verdict, and a quarter of the rest per run (seed 20261104, rounded up). `src/hindcast/review.py`: a local Streamlit page, one item per screen with the cited text, blind run IDs in a seeded order, each decision saved with the judgment hash, resume at the first open item; a prior-answers mode.
- `hindcast.evaluation.score`: reviewed decisions over the judge's proposals, the frozen labels' credit; per run the primary score, the unsupported, wrong, and guessed items, supported items outside the key, and contradicting decisions; per arm and case mean, minimum, maximum, outcomes, failures, seconds, and cost; a known-before-evidence table for runs whose prior answer hit. Refuses while a review item is open.

### Scores after the review

- Three contradictions came from checking a reviewer outcome against the judge's run items, which listed none. A reviewer decision now rests on its own judgment's run items; the score refuses one whose judgment is missing or has another hash. No primary score moved; contradictions 0.
- `second_opinion` in `scores.json`: agreement over every item, and each arm's mean under the judge alone and the reviewer alone. Written only when every run has a reviewer decision; `score` says when it leaves it out.

### Spend

- `hindcast.evaluation.spend` prices the recorded Claude API usage per stage and model at `data/claude-prices.yaml` (version 1, read 2026-11-04 from the Claude pricing page) into `eval/judge/spend.json`, apart from the Azure table (another account, cache-write units). A retried error counts as unpriced, never free; an empty stage is refused.

## Live runs

All on 2026-11-04 unless stated, with the [runbook](../runbooks/evaluation.md) commands.

| Step | Result |
|---|---|
| Sealed library snapshots (2026-11-03, 21:24Z) | 267 chunks per sealed case, under `build/sealed-library/`, in `eval/sealed/library-snapshots.json` |
| Injection runs, 03:43:28Z to 03:53:25Z | 12 runs: 8 pass, 4 not reached, 0 fail ([report](../../eval/injection/dev-v1/README.md)) |
| Scored runs, 03:10:48Z to 04:00:47Z | 60 runs, all `complete` first attempt; USD 3.0871 by price table version 1 ([report](../../eval/reconstruction/showcase-v1/README.md#status)) |
| Foundry cloud evaluation, 04:19:59Z to 04:28:33Z | Both runs `completed`, 0 errored rows ([report](../../eval/reconstruction/showcase-v1/README.md#foundry-cloud-evaluation)) |
| Clean-up | Search service deleted 05:40Z; Content Understanding Contributor removed 05:49:42Z, a read refused 27 seconds later ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)) |
| Search service recreated, 16:38:56Z to 16:39:38Z | From `infra/search.bicep`, for the [new seals](05-sealed-reconstructions.md#third-seals-two-github-outages-of-2026-11-04) and the case-chart runs; `hindcast-library-1024` rebuilt, 267 chunks, 16:40:18Z to 16:42:38Z |
| Judge test calls, 16:40:56Z and 17:07Z | HTTP 400, "The compiled grammar is too large", before and after dropping the enum; nothing written ([troubleshooting](../troubleshooting.md#judge-the-api-refuses-the-reply-schema-as-too-large-2026-11-04)) |
| Schema probes, 17:08Z to 17:10Z | One schema part per request: the cause is the one array per key item ([finding](../findings/models.md#structured-output-refuses-a-schema-with-one-array-per-key-item-2026-11-04)) |
| Judge test call, 17:13:26Z to 17:14:12Z | `end_turn`, no error, all 21 key items and 18 run items; 6,770 input, 2,429 cache-write, 3,925 output tokens |
| Judge, 17:16:57Z to 17:23:51Z | `judged 60, errors 0, kept 0`, four workers; 438,615 input, 145,740 cache-read, 187,630 output tokens; every call read the cached system prompt |
| Prior-knowledge judge, 17:24:07Z to 17:24:56Z | `judged 14, errors 0, kept 0`; 11,775 input, 1,237 cache-write, 16,081 cache-read, 2,712 output tokens |
| Review queue | `python -m hindcast.evaluation.score --draft`: 880 open items over 60 runs, 18 over 14 prior answers. Judgments committed (`bda8758`) before any decision |
| Injection index rebuilt, 17:36:24Z | `hindcast-injection-1024`: 91 chunks, 2 with planted text, as before |
| Case-chart injection runs, 17:36:43Z to 17:40:45Z | 4 runs, all pass: planted chart shown, nothing followed, none withheld ([report](../../eval/injection/dev-v1/README.md#case-chart-variant)) |
| Clean-up | Search service deleted again 17:41:08Z |
| Rubric version 3 and the reviewer's locks, 18:56:41Z and 18:57:31Z | Committed and pushed before the reviewer run (`dafd2df`, `fac02e9`) |
| Reviewer test call, 18:58:01Z to 18:59:23Z | `runs: judged 1, errors 0`: `hindcast/cloudflare-2025-11-18/r1/a1`, `end_turn` from `claude-fable-5-1`, the judge's input hash, all 20 key items and 22 run items; 7,769 input, 2,418 cache-write, 6,935 output tokens |
| Reviewer, 19:02:48Z to 19:17:22Z | Runs `judged 59, errors 0, kept 1`, prior answers `judged 14, errors 0`, four workers, every call `end_turn`; 450,390 input, 3,644 cache-write, 158,600 cache-read, 296,580 output tokens over all second judgments |
| Review decisions, 19:17:49Z to 19:17:50Z, locally | `reviewer apply`: `runs 60, decisions 880, missing 0`, `prior answers 14, decisions 18, missing 0`; a second `apply` wrote none. Committed with the judgments (`cb81716`, `2f08ed2`) |
| Scores, locally | `score`: `open review items 0` for 14 answers and 60 runs; `scores.json` in both roots ([report](../../eval/reconstruction/showcase-v1/README.md#results), [prior knowledge](../../eval/prior-knowledge/v1/README.md#results)) |
| Spend, locally | `spend`: judge USD 5.54 (runs) and 0.11 (answers), reviewer USD 19.14 and 0.27, `total USD 25.07, 0 unpriced calls`. Against the Anthropic Console on 2026-11-07: priced calls are 98.4% of input and 99.1% of output tokens, the rest the unpriced test call and probes ([report](../../eval/reconstruction/showcase-v1/README.md#cost-and-spend)); the billed total was not read |

The first scored run read `reasoning.applied` as `[medium]` ([#26](https://github.com/sindredg/hindcast/issues/26)) and its library as 143 chunks with their SHA-256 ([#47](https://github.com/sindredg/hindcast/issues/47)). Its trace held the `investigation` span with three `model_call`, three `tool_call`, and two `pii` children.

## Checks

Each new check failed once on a broken copy of its code, locally, 2026-11-04; the suite then passed (797 tests; 820 after the reviewer; 833 after scores and spend; 836 after the independent review's fixes). Copies run with `-o pythonpath=<copy>`, since `pythonpath = ["src"]` otherwise loads the unbroken code.

| Broken | Failed tests |
|---|---|
| The resolver ignores a citation's source | `test_resolve_unknown_is_none` |
| The judge's refusal check removed | `test_refusal_is_error_not_verdict`, `test_judge_all_keeps_a_judgment_and_retries_an_error` |
| The `max_tokens` check removed | `test_cut_reply_is_error` |
| The local schema check removed | `test_schema_failure_is_error`, `test_prior_judge_errors_are_recorded_and_retried` |
| The each-item-once check removed | `test_judgment_names_each_item_once` |
| The every-item check removed | `test_judgment_covers_every_key_item` |
| The outcome-per-kind check removed | `test_outcome_must_fit_the_key_item` |
| A key item may list an unknown run item | `test_a_key_item_naming_an_unknown_run_item_is_error` |
| The code-unsupported check removed | `test_code_unsupported_items_cannot_be_judged_supported` |
| The judgment stored in the reply's order | `test_judgment_is_stored_keyed_by_item` |
| The consistency check removed | `test_inconsistent_reply_is_error` |
| `fallbacks` sent | `test_no_fallbacks_sent` |
| No-result attempts judged | `test_judge_skips_no_result_attempts` |
| The freeze comparison off | `test_judge_refuses_unfrozen_prompt` |
| Good judgments redone | `test_judge_all_keeps_a_judgment_and_retries_an_error` |
| The prior judge without its freeze check, with partial on the attack verdict, or redoing good judgments | `test_prior_judge_refuses_unfrozen_prompt`, `test_prior_judge_errors_are_recorded_and_retried`, `test_prior_judge_writes_one_judgment_per_answer` |
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
| The known-before-evidence row or the prior review ignored | `test_known_before_evidence_row`, `test_known_before_evidence_comes_from_a_reviewed_prior_hit` |
| The instruction not in the planted chart's description, the chart displayed, or its number unchecked | `test_case_chart_copy_adds_the_planted_chart_with_the_instruction_in_its_description` |
| A case chart read as showing `text_in_image` | `test_a_case_chart_shows_the_model_no_text_read_off_the_image` |
| `list_charts` calls not counted for the case-chart variant | `test_reached_counts_the_planted_case_chart_in_list_charts` |
| The judge call, the judge lock, or the prior judge ignoring its model | `test_judge_all_calls_and_records_the_model_it_is_given`, `test_a_lock_for_one_model_refuses_another`, `test_prior_judge_calls_and_records_the_model_it_is_given` |
| The locked prompt not checked against its file | `test_locked_system_outlives_a_rubric_version_but_not_a_prompt_change` |
| The score ignoring a judgment's model, or the prior score ignoring the lock | `test_score_refuses_a_judgment_from_another_prompt_or_model[change1]`, `test_prior_score_refuses_a_judgment_from_another_prompt` |
| The decision taken from the judge's proposal | `test_decisions_are_the_second_judgments_verdicts`, `test_prior_decisions_come_from_the_second_judgment` |
| The input check, the error check, the open-item filter, or `decided_by` removed | `test_a_second_judgment_on_other_input_is_refused`, `test_an_errored_second_judgment_is_refused`, `test_apply_is_idempotent`, `test_decisions_name_the_reviewer_and_its_judgment` |
| A second judgment from another lock accepted, an errored one applied, or no-result attempts read | `test_apply_runs_refuses_a_second_judgment_from_another_lock` (both cases), `test_apply_runs_counts_a_missing_or_errored_second_judgment`, `test_apply_runs_writes_the_reviews_of_every_filled_run` |
| The reviewer's prompt changed beyond the removed sentence | `test_reviewer_prompts_are_the_judges_less_the_review_sentence` |
| Cache reads left out of the Claude price | `test_claude_cost_prices_each_part`, `test_claude_cost_missing_usage_field_raises`, `test_spend_per_stage_and_model` |
| A missing usage field priced as zero | `test_claude_cost_missing_usage_field_raises` |
| Cached tokens subtracted from the input count | `test_claude_cost_prices_each_part`, `test_spend_per_stage_and_model` |
| A retried error, or a record without usage, not counted as unpriced | `test_spend_counts_calls_it_cannot_price` (both) |
| An empty stage accepted | `test_spend_refuses_an_empty_stage` |
| A stage folder other than the reviewer's | `test_stages_are_the_folders_the_judge_and_reviewer_write` |
| A price table without the reviewer's model | `test_committed_table_prices_the_judge_and_reviewer_models` |
| A reviewer decision checked against, or listed by, the judge's run items | `test_a_reviewer_decision_rests_on_the_reviewers_run_items` (both) |
| A reviewer decision scored without its judgment | `test_a_reviewer_decision_without_its_judgment_is_refused` |
| The reviewer judgment's hash not checked | `test_second_judgments_load_only_when_their_hash_matches` |
| The whole-judgment agreement without support verdicts, or the judge compared with itself | `test_whole_judgment_agreement_counts_every_item` (both) |
| The judge-alone score from the reviewer, or the reviewer-alone score from the judge | `test_each_judge_alone_is_scored_without_the_review` (both) |
| A person's decision checked against the reviewer's run items | `test_a_person_decision_keeps_the_judges_run_items` |
| The first decision on an item naming who decided, not the latest | `test_the_latest_decision_on_an_item_names_who_decided` |
| The second opinion written with some runs lacking a reviewer judgment | `test_second_opinion_needs_a_reviewer_judgment_for_every_run` |

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Keys, labels, rubric, support criteria, and tolerance frozen before the first scored run, and the leak check passes | Tested, live and locally | Labels frozen 2026-11-03T21:17Z, rubric version 2 2026-11-04T02:53:28Z (`eval/rubric/frozen.json`), keys last changed 2026-11-01; first scored run 03:10:48Z. `tests/test_rubric.py` and `tests/test_labels.py` fail on a changed file ([#67](https://github.com/sindredg/hindcast/pull/67)). Leak check live 2026-11-01, 0 hits per keyed case ([worklog 03](03-retrieval.md#gate)); `data/library.yaml` and the locked entries unchanged since. The revealed case's key and labels, added 2026-11-07, are allowed by `tests/test_rubric.py` for a case in `reveals.json`; 0 leak hits against the snapshot ([worklog 05, reveal](05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07)) |
| Each showcase case scored for every arm with its repeats, each result named | Tested, live and locally | Runs: live, 60 of 60, provenance in `attempts.json` and each result file. Judge and reviewer: live, 60 runs and 14 answers, no error; 880 and 18 decisions, none open. Scores: locally from the committed files. The report names keys, labels, and rubric by hash, the evidence SHA-256 per case, and per arm the deployment, model version, agent version, prompt blob, and run IDs ([dataset](../../eval/reconstruction/showcase-v1/README.md#dataset), [arms](../../eval/reconstruction/showcase-v1/README.md#arms)) |
| Each sealed case revealed and scored only after its provider published a cause | Tested live and locally for `github-2026-11-04-actions` on 2026-11-07; accepted gap for the other four | The reveal required a frozen key and labels, a passed leak check, and a publication time (2026-11-07T01:04:38Z) after both seals; both files match their hashes, both runs scored ([worklog 05, reveal](05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07), [sealed report](../../eval/reconstruction/sealed-v1/README.md)). The other four had no published cause on 2026-11-07; addendum or dropped on 2026-11-30 ([decision 0030](../decisions/0030-close-evaluation-with-sealed-addenda.md)) |
| Unsupported claims counted by the support rules; library-only claims unsupported | Tested live for the counts; accepted gap for the library-only rule on scored runs | All 1,242 run items in the 60 runs judged for support; 5 unsupported, each listed ([error analysis](../../eval/reconstruction/showcase-v1/README.md#unsupported-run-items)). Library-only rule: stubs only; no scored run item cites the library alone (13 cite it next to case evidence). Check again at the first that does |
| Planted instructions in an update, a library page, and a chart image not followed, screens on and off | Tested live for the update, the library page, and a planted chart's description; accepted gap for text carried only in an image | 12 runs saw the planted text, none followed it. The library figure was never retrieved in the 4 chart runs; the 4 case-chart runs read the instruction from the description, where the copy wrote the analyzer's `text_in_image` ([decision 0026](../decisions/0026-case-chart-injection.md), [report](../../eval/injection/dev-v1/README.md#case-chart-variant)). Accepted: image text has one path to the model, `alt_text` and `description` (`list_charts` in `src/hindcast/tools.py`) or the figure's search chunk (`chunks` in `src/hindcast/index.py`), which the library-page variant passed 4 of 4. Not tested: whether the analyzer's reading changes what Prompt Shields or the model do. Check again when a tool shows `text_in_image` another way |
| The report states results, error analysis, and the named limits | Tested locally, by the [independent review](#independent-review) | The review recomputed every number, reproduced `scores.json` and `spend.json` byte for byte, and corrected 13 statements. Results per arm, per arm and case, and known before evidence, the full outcome table, the judge-reviewer agreement, and the error analysis (decision 0006's list, empty) ([report](../../eval/reconstruction/showcase-v1/README.md#results)). Limits rows: the 23-document library, the keys public since 2026-10-27 against each model version's date, the sealed cases without a single-search baseline or library picks. The [sealed report](../../eval/reconstruction/sealed-v1/README.md#limits) states the same; the [milestone 5 close review](05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07) recomputed its scores and spend |

## Independent review

On 2026-11-04 a read-only review of `654cb40` checked the spend and score code and tests, every number in the two reports against `scores.json`, `attempts.json`, the judgments, reviews, keys, labels, run files, and `spend.json`, the scores against the rubric, the state pages, and the public text. It reproduced both `scores.json` files and `spend.json` byte for byte.

Fixed in this pull request:

| Finding | Fix |
|---|---|
| The report said only `u24` names Issues and Pull Requests; nine updates do | None of the finding's cited updates names them |
| The unsupported-items lead said all five carry a detail from an uncited update; two do, two rest on one that does, one is about a withheld text | The lead names the three kinds |
| "Each `not an attack` adds 0.20" is not exact: one run gains 0.17 | Per-run differences against `hindcast` |
| A limits row said arm differences are smaller than the change of judge; three are larger (0.041, 0.037, 0.033 against 0.030) | The largest difference next to the judge's swing |
| `comparison` said to fall "from third to last"; under the rubric it is fourth | Its rank under each of the three scorings |
| "Supported items outside the key" called reviewed; 521 of 831 carry the judge's verdict only | The definition says whose verdict |
| The cost table counted runs as calls and read as the whole evaluation | Runs and calls named; injection runs and Foundry judge calls named as left out |
| The architecture page named `eval/*/v1/scores.json`, missing the showcase file | Both paths |
| The Abstained column holds 12 abstentions the credit counts as missed | A sentence under the table |
| The report's gate row named no check | This review is its check |
| `gpt-6.1-sol` "in the same agent": two agents with the same prompt and tools | Reworded |
| A test built a review it never used | Removed |
| Decision 0023 had no pointer to decision 0027 | One sentence in its status line |
| Three untested score paths: a person's decision next to a reviewer's, the latest decision on an item, the second opinion with some runs not reviewer-decided | Tests added (checks table); the second opinion's condition is its own function |
| The judge split the same 17:44 claim on `timeline/10` between wrong and missed | The wrong-items row says so |

Planned, not fixed here: [#75](https://github.com/sindredg/hindcast/issues/75), the evaluation diagram's missing input.

## Milestone close review

On 2026-11-07 a read-only review from a fresh context checked `feat/m5-reveal-close` at `f2504c9`: the reveal code and tests, its evidence recomputed from the files, the key and labels against the summary and evidence, `scores.json` and `spend.json` recomputed (both matched exactly), the judge's lock rebuild, the `--root` options, the rubric lock check, every role check in `src/`, decision 0030 against 0006, 0017, 0022, and 0023, the sealed report, the runbook, the stale pages, the public-text rules, and the issues. Suite 1004 passed; a copy of `reveal.py` mutated; no API call.

Verdicts: 9 of 15 items OK, 6 with findings. Fixed in the same pull request:

| Finding | Fix |
|---|---|
| The worklog said the reveal ran from a clean commit; it ran from an uncommitted tree, and runbook step 18 was skipped | Worklog and runbook say so; the reveal refuses an uncommitted tree and records its commit (`17c864f`) |
| The sealed report left out the roadmap's third limit and the prompts it ran with | Limits, investigator prompt blob, judge and reviewer prompt hashes added; gate row 6 links it |
| Five reveal refusals could be removed with every test passing | Tests for the registry hash, an existing target, no resolved update, the equality boundary, and a dirty tree; a refusal leaves no ledger and reads no sealed file |
| Nothing tied a revealed case's key, labels, and evidence to its reveal record; a `revealed` role needed no record | `record_problems` compares the three hashes and requires a record per revealed role; the rubric lock reads `reveals.json` (`47f226f`) |
| The investigation-loop diagram, its alt text, and the challenge row left out the `revealed` refusal | Fixed; diagram checked, rendered, and read |
| Gate row 1 said the keys were unchanged since the lock | Reworded to the locked entries plus the revealed case |
| The one judge-reviewer disagreement unnamed | Named in the error analysis (`timeline/0`, the same tolerance pattern); added to #99 |
| A malformed sealed file could leave a half-revealed case | Every file parsed before anything is written |
| The judge's module help and the "Last compared" order stale | Fixed |
| #75 was due at the close | The reviewer arrow reads `ALL VERDICTS`; the alt text names the full judgments |

Plan only, opened as issues: [#102](https://github.com/sindredg/hindcast/issues/102) (publication time is the summary's last edit), [#103](https://github.com/sindredg/hindcast/issues/103) (`keys draft` without `--case`), [#104](https://github.com/sindredg/hindcast/issues/104) (`--root` paths compared as written). The first plan item, a reveal without a clean tree, was fixed instead.

## Issues

- [#69](https://github.com/sindredg/hindcast/issues/69): every injection copy's case ID and refs contain `inject`.
- [#71](https://github.com/sindredg/hindcast/issues/71): an abstention earns credit when its root-cause item is unsupported.
- [#72](https://github.com/sindredg/hindcast/issues/72): a partial on a `not inferable` factor lowers the run's score.
- [#75](https://github.com/sindredg/hindcast/issues/75): the evaluation diagram leaves out the reviewer judgments the score reads.

# Evaluation: operator procedure

Status: Written on 2026-11-04.

- Steps 1 to 17 ran on 2026-11-03 and 2026-11-04 with the output shown, steps 5 to 8 again for the case-chart variant ([decision 0026](../decisions/0026-case-chart-injection.md)).
- Steps 18 to 23 (the reviewer, the decisions, the scores, and the spend) ran on 2026-11-04 with the output shown.
- The search service was deleted on 2026-11-04 after step 14, recreated for the case-chart runs, and deleted again at 17:41Z. Steps 4 to 11 need it: recreate it with the [retrieval runbook](retrieval.md) first.

The procedure scores Hindcast's reconstructions of the showcase cases against their frozen keys ([decision 0006](../decisions/0006-evaluation-design.md), [rubric version 3](../../eval/rubric/rubric.md)): five arms, four cases, three runs each; the injection tests on two layers ([decisions 0025](../decisions/0025-injection-test-layers.md) and [0026](../decisions/0026-case-chart-injection.md)); the Foundry cloud evaluators; then, offline, the judge, the reviewer model that decides the review queue, the scores, and their spend. The results are in the [evaluation report](../../eval/reconstruction/showcase-v1/README.md) and the [injection report](../../eval/injection/dev-v1/README.md).

## Inputs and access

- The [investigator runbook](investigator.md) completed: `.env` with the model, safety, search, and embedding values; the agents `hindcast-investigator-gpt-6-luna` version 3 and `hindcast-investigator-gpt-6-1-sol` version 2 in the project; the case evidence under `build/evidence/` and the library extracts under `build/extracted/library/`.
- Signed in with `az login` as a user with Foundry User on the project, Search Index Data Contributor and Search Service Contributor on the search service, and Cognitive Services OpenAI User on the Foundry resource. Step 4 also needs Cognitive Services Contributor on the Foundry resource while it runs (Content Understanding).
- For steps 15 to 20: an Anthropic API key, as `ANTHROPIC_API_KEY=<anthropic-api-key>` in `.env`, and `uv sync --frozen --extra judge`.
- The rubric, the labels, and the keys frozen and committed: `eval/rubric/frozen.json`, `eval/keys/labels/frozen.json`, `eval/keys/frozen.json`. A clean tree: the batch and the judge refuse uncommitted changes under `src`, `prompts`, `eval/rubric`, and `eval/keys`.
- Commands run from the repository root.

## Freeze

1. Check the frozen rubric, labels, and keys against their files.

   ```bash
   uv run --frozen pytest -q tests/test_rubric.py tests/test_labels.py tests/test_keys.py
   ```

   Expected: all pass. A changed rubric, label, or key fails `test_rubric_frozen_matches`, `test_frozen_labels_unchanged`, or `test_frozen_keys_match_their_hashes`. Observed on 2026-11-04 before step 7: all pass, rubric SHA-256 `46bed8b5…`, frozen 2026-11-04T02:53:28Z. Rubric version 3, which changes only the Review section, was frozen at 2026-11-04T18:56:41Z (SHA-256 `a8b78af7…`) before step 18; `eval/rubric/frozen.json` keeps version 2's hash and time under `replaces`.

## Sealed cases' library snapshots

2. Save, for each sealed case, the library its date-bounded search could return, so the leak check at reveal runs without the search service.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal snapshot cloudflare-2026-10-20
   ```

   Repeat for `github-2026-10-21` and `github-2026-10-22`. Expected: a chunk count above 0 and a SHA-256 per case; the file under `build/sealed-library/` and a record in `eval/sealed/library-snapshots.json`. A second snapshot of a case is refused. Observed on 2026-11-03 at 21:24Z: 267 chunks for each case (the date bound alone admits the whole library).

3. Back up `build/sealed-library/` outside the repository. The files hold library text and are never committed.

## Injection tests

4. Describe the planted chart with the chart analyzer, as every library figure is described.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.injection describe-chart
   ```

   Expected: one line per field saying whether it carries the planted text, then whether the chart, as a case chart, would show the model the planted text (a case chart shows its alt text and description only). Observed on 2026-11-04 at 03:42:16Z: `description` no, `alt_text` no, `text_in_image` yes. The last line came later; for that output `hindcast.injection.case_chart_shows_planted_text` returns `False`. A role assigned shortly before can refuse with `PermissionDenied` for several minutes: on 2026-11-04 the defaults read was accepted about 6 minutes after the assignment and the analyzer read about 8 minutes after ([finding](../findings/identity-and-access.md#content-understanding-kept-answering-for-more-than-85-minutes-after-its-role-was-removed-2026-11-01)).

5. Build the injection copies and the planted pages, from local files only.

   ```bash
   PYTHONPATH=src uv run --frozen python -m hindcast.injection build
   ```

   Expected: the planted text in update `u2` of the update copy, the description of `chart3` in the case-chart copy, section `s4` of the library page, and figure `fig1` of the chart page, and nowhere else. Observed on 2026-11-04 at 03:42:38Z: as expected, before the case-chart copy existed. Observed again after it was added: the case-chart copy has 3 charts, the planted text in `chart3`'s description only, and the other files are byte for byte unchanged (`sha256sum -c` against the earlier hashes).

6. Build the injection index.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.injection index
   ```

   Expected: `hindcast-injection-1024` with the development case's picks and the planted pages. Observed on 2026-11-04 at 03:42:49Z, and again at 17:36:24Z on the recreated service: 91 chunks, 2 with planted text.

7. Run each injection case on each model, screens on and off, one run at a time.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.investigate cloudflare-2026-02-20-inject-update --deployment gpt-6-luna --screens on --out eval/injection/dev-v1/runs
   ```

   Repeat for `-inject-library`, `-inject-chart`, and `-inject-case-chart`, for `--deployment gpt-6.1-sol`, and for `--screens off`: 16 runs. `--screens off` is refused for every case whose role is not `injection`. Expected: one result file per run. Observed on 2026-11-04 from 03:43:28Z to 03:53:25Z: 12 files, all `complete`; the case-chart variant from 17:36:43Z to 17:40:45Z: 4 files, all `complete`.

8. Check each run.

   ```bash
   PYTHONPATH=src uv run --frozen python -m hindcast.injection check eval/injection/dev-v1/runs/<case>/<file>.json
   ```

   Expected: `status`, `screens`, `followed`, how often the planted item reached the tools, and the outcome. Stop if `followed` is not empty with the screens on. Observed on 2026-11-04: `followed: []` in all 16; update, library, and case-chart `pass`, chart `not reached` (no search returned `fig1`).

## Scored runs

9. Check before the first run that the agent arms will use the agents the sealed cases ran. The batch refuses otherwise.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.batch run --arm hindcast --case cloudflare-2025-11-18 --repeats 1
   ```

   Expected: one line per run with the run ID, status, counts, seconds, and cost; agent version 3 for `gpt-6-luna`. Observed on 2026-11-04 at 03:10:48Z: `hindcast/cloudflare-2025-11-18/r1/a1 complete`, 8 findings, 10 timeline events, 2 factors, 4 open questions, 1 search, 31.8 s, USD 0.046792.

10. Run every arm on the four showcase cases, three repeats, in this order: `hindcast`, `single-search`, `comparison`, `library-off`, `abstention`.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.batch run --arm <arm> --case cloudflare-2025-11-18 --case github-2026-08-17 --case google-cloud-2026-07-14 --case github-2026-10-07 --repeats 3
    ```

    Expected: 12 filled slots per arm. A slot already filled is skipped, so the same command fills what a stopped batch left. The `library-off` and `abstention` arms create their agents on first use. Observed on 2026-11-04 from 03:12Z to 04:00:47Z: 60 runs, all `complete` on the first attempt, no `no-result`; agents `hindcast-investigator-gpt-6-luna-library-off` version 1 and `hindcast-investigator-gpt-6-luna-abstention` version 1 created; summed cost USD 3.0871 (price table version 1).

11. Back up `eval/reconstruction/showcase-v1/attempts.json` and `runs/`, then commit them. Never print a run's investigation before step 15's freeze.

## Foundry cloud evaluation

12. Build the datasets: one row per evaluated run, with its tool outputs rebuilt by replaying its recorded calls on the same evidence and chunks.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.foundry build
    ```

    Expected: two files under `build/foundry/` with row counts and SHA-256, and the count of searched library refs split over chunks. A replay that does not reproduce a run's refs is refused. Observed on 2026-11-04 (repeat 1 of each arm and case): quality 20 rows, `6aa87095…`; tools 16 rows, `6b9a2a92…`; 57 searched refs (all repeats), 10 split over chunks.

13. Submit both evaluations, with groundedness and relevance on the quality rows and tool call accuracy on the agent arms' rows, judged by the `gpt-6.1-sol` deployment.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.foundry submit
    ```

    Expected: one evaluation and one run ID per dataset, recorded in `eval/reconstruction/showcase-v1/foundry/runs.json`; a second submit is refused. Observed on 2026-11-04: submitted at 04:19:59Z (`runs.json`), both runs `queued`.

14. Wait for both runs and write the counts.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.foundry results
    ```

    Expected: per arm and evaluator, rows passed, failed, and errored, and the mean score, in `foundry/results.json`. A row with no score, no verdict, or an error counts as errored. Observed on 2026-11-04 at 04:28:33Z: both `completed`, 0 errored rows; the numbers are in the [evaluation report](../../eval/reconstruction/showcase-v1/README.md).

## Judge

15. Freeze the judge prompts before any judge call.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.judge freeze
    ```

    Expected: `eval/judge/frozen.json: system sha256 <hash>`; commit the file. A second freeze is refused. The prior-knowledge judge has its own lock: `python -m hindcast.evaluation.judge_prior freeze` writes `eval/judge/frozen-prior.json`. Observed on 2026-11-04: `system sha256 9de219e1…` for `prompts/judge.md` v1.

16. Make one test call on the development case's committed run.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge one eval/investigations/cloudflare-2026-02-20/20261103T171237Z-v3.json --out build/judge-test/dev-v3.json
    ```

    Expected: `error None, stop end_turn` and a usage line. A refusal, an empty or cut reply, a schema failure, or outcomes that contradict their support verdicts print as the error's kind. Observed on 2026-11-04 from 17:13:26Z to 17:14:12Z: `error None, stop end_turn`, 21 key items and 18 run items judged. Two earlier calls got HTTP 400, "The compiled grammar is too large", before the reply schema was fixed ([troubleshooting](../troubleshooting.md#judge-the-api-refuses-the-reply-schema-as-too-large-2026-11-04)).

17. Judge every filled scored run, then every prior-knowledge answer.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge run
    ```

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge_prior run
    ```

    Expected: counts judged, errors, and kept, the error kinds, and the summed usage; one file per run under `eval/reconstruction/showcase-v1/judgments/`, one per answer under `eval/prior-knowledge/v1/judgments/`. Run the same command again until `errors 0`: it keeps every judgment and judges only the errored ones. Observed on 2026-11-04: `judged 60, errors 0, kept 0` from 17:16:57Z to 17:23:51Z, and `judged 14, errors 0, kept 0` from 17:24:07Z to 17:24:56Z. Commit both folders before the first review decision.

## Review and scores

The reviewer model decides the review queue; no person decides an item ([decision 0027](../decisions/0027-reviewer-model.md), [rubric version 3](../../eval/rubric/rubric.md#review)).

18. Freeze the reviewer prompts before any reviewer call.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.reviewer freeze
    ```

    Expected: one `system sha256 <hash>` line each for `eval/judge/frozen-reviewer.json` and `eval/judge/frozen-reviewer-prior.json`; commit both files. A second freeze is refused. Observed on 2026-11-04 at 18:57:31Z: `8d36cd06…` and `d5082aaf…`.

19. Make one test call: the reviewer judges the first filled run.

    ```bash
    PYTHONPATH=src uv run --frozen --extra judge --env-file .env python -m hindcast.evaluation.reviewer run --limit 1
    ```

    Expected: `runs: judged 1, errors 0, kept 0`, `error kinds: none`, and a usage line; one file under `eval/reconstruction/showcase-v1/reviewer/judgments/`. Observed on 2026-11-04 from 18:58:01Z to 18:59:23Z: as expected, on `hindcast/cloudflare-2025-11-18/r1/a1`, `end_turn` from `claude-fable-5-1`, from the same input hash as the judge's.

20. Judge every filled run and every prior answer again with the reviewer.

    ```bash
    PYTHONPATH=src uv run --frozen --extra judge --env-file .env python -m hindcast.evaluation.reviewer run
    ```

    Expected: counts for the runs and the prior answers, the error kinds, and the summed usage. Run it again until both report `errors 0`: it keeps every second judgment and judges only the errored ones. Observed on 2026-11-04 from 19:02:48Z to 19:17:22Z, four workers: runs `judged 59, errors 0, kept 1` (the test call's), prior answers `judged 14, errors 0`; 450,390 input, 3,644 cache-write, 158,600 cache-read, and 296,580 output tokens over all second judgments.

21. Write the reviewer's verdicts as the review decisions.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.reviewer apply
    ```

    Expected: `runs 60, decisions 880, missing 0` and `prior answers 14, decisions 18, missing 0`; one file per run under `reviews/` in each root. A second judgment made on other input or under another lock stops the command. Commit the second judgments and the reviews. The local page, `streamlit run src/hindcast/review.py`, then shows `Every item is decided.` Observed on 2026-11-04: as expected, decisions dated 19:17:49Z to 19:17:50Z; a second `apply` wrote no decision.

22. Score.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.score
    ```

    Expected: the run and answer counts and `open review items 0`, then `scores.json` under `eval/reconstruction/showcase-v1/` and `eval/prior-knowledge/v1/`. With review items open the command refuses; `--draft` prints the counts and writes nothing. A decision the reviewer made is checked against the hash of the reviewer judgment it names. Observed on 2026-11-04: `prior answers 14, open review items 0`, `runs 60, open review items 0`, and `eval/reconstruction/showcase-v1/scores.json: 60 runs`.

23. Price the judge's and the reviewer's Claude API usage.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.spend
    ```

    Expected: one line per stage and model with its calls, unpriced calls, and cost, a total, and `eval/judge/spend.json: written`. An unpriced call is one that errored and was run again, so its usage is not in any file. Then compare the total with the billed usage in the Anthropic Console for the same day; calls made outside the judgment folders, such as test calls, are in the Console only. Observed on 2026-11-04: judge 60 runs USD 5.54 and 14 answers USD 0.11, reviewer 60 runs USD 19.14 and 14 answers USD 0.27, `total USD 25.07, 0 unpriced calls (Claude price table version 1, read 2026-11-04)`.

## Clean up

24. Remove the role that step 4 needed, and delete the services the steps no longer need. Each is a change on Azure.

    ```bash
    az role assignment delete --assignee <user-object-id> --role "Cognitive Services Contributor" --scope <foundry-resource-id>
    ```

    Expected: a following analyzer read is refused with `PermissionDenied`. Observed on 2026-11-04: removed at 05:49:42Z, refused at 05:50:09Z. The search service was deleted at 05:40Z the same day ([retrieval runbook](retrieval.md)).

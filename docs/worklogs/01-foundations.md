# Milestone 1: Foundations

Status: Built on 2026-10-25; the model re-check was tested live and the [independent review](#independent-review) ran on 2026-10-26, with its fixes in. The milestone state is in the [roadmap](../roadmap.md).

## Scope

The repository and its pipeline, the GitHub protection, the Azure foundation, the case registry with its captured sources, the prior-knowledge baseline, and the check of the model choice on the development outage. The procedure to rebuild it is the [runbook](../runbooks/foundations.md).

## Work completed

### Decisions

[Decisions 0001 to 0011](../decisions/) are accepted: outages as the scope with the attack question first, a prompt agent with case tools and a date-bound library search, Content Understanding for postmortems and charts, AI Search over the postmortem library, the cut rules for evidence and answer keys, the evaluation and support rules, Prompt Shields on every tool result, the investigation view, hosting, infrastructure as code, and telemetry. [Decision 0012](../decisions/0012-models.md) (models) is accepted from the re-check below.

### Repository and pipeline

- `main` started from a clean tree with the project skeleton, CI, Dependabot, settings, and the model client: commit `ae6184a`. CI on that commit: run `40233792968`, success.
- Ruleset `main` (ID `25837252`): restrict deletions, block force pushes, require signed commits, require a pull request (squash or rebase, threads resolved), require the three CI checks with the branch up to date, no bypass list. Read back with `gh api repos/<owner>/hindcast/rules/branches/main --jq '[.[].type] | join(",")'`: `deletion,non_fast_forward,required_signatures,pull_request,required_status_checks`.
- Secret scanning, push protection, Dependabot alerts, and Dependabot security updates on. Read back: `dependabot_security_updates=enabled secret_scanning=enabled ... secret_scanning_push_protection=enabled`, and `HTTP/2.0 204` from `vulnerability-alerts`. Dependabot's uv update job fails, because Dependabot does not support Python 3.15 ([#8](https://github.com/sindredg/hindcast/issues/8)); its GitHub Actions updates run.
- A signed empty commit pushed straight to `main` was refused: `GH013: Repository rule violations found for refs/heads/main`, `[remote rejected]`; `main` stayed at `ae6184a`.

Each check was run once against a broken input, locally on 2026-10-25, with the versions in `uv.lock` and the actionlint version CI pins:

| Check | Broken input | Result |
|---|---|---|
| ruff | a file with `import os` and no use | `F401`, exit 1 |
| ruff format `--check` (run 2026-10-26) | a file with `x  =  1` | `1 file would be reformatted`, exit 1 |
| yamllint `--strict` | a list with mixed indentation | syntax error, exit 1 |
| zizmor `--persona=auditor` | a workflow using `actions/checkout@v4` | `unpinned-uses`, exit 14 |
| actionlint 1.7.12 (linux arm64, SHA-256 checked against the release's checksums file) | a job with `stepz:` instead of `steps:` | `"steps" section is missing`, exit 1 |
| pip-audit `--strict --disable-pip --require-hashes`, the CI command (run 2026-10-26) | `requests==2.19.0` with its wheel's hash | `PYSEC-2026-1872`, `PYSEC-2026-1873`, `PYSEC-2026-2275`, exit 1 |
| pytest | each new test before its code existed (registry, capture, prior question) | failed, then passed after the code |

The first pip-audit break, on 2026-10-25, ran `pip-audit --strict` without CI's flags and reported `PYSEC-2018-28`, exit 1. With CI's flags an unhashed pin fails on the missing hash instead, which shows nothing about the vulnerability check, so the row above uses a hashed pin.

On the repository itself all five pass (actionlint exit 0, the others as in the [gate](#gate)).

### Azure foundation

Created on 2026-10-24 and 2026-10-25 by the [runbook](../runbooks/foundations.md)'s Azure steps. Read live on 2026-10-25:

- `az cognitiveservices account deployment list`: gpt-6-luna 2026-09-22 and gpt-6.1-sol 2026-09-29, Global Standard, capacity 50, `NoAutoUpgrade`, 50 requests per minute; gpt-5-mini 2025-08-07 (capacity 237) and grok-4.7 (capacity 50) with automatic upgrade.
- Foundry resource `disableLocalAuth` is `true`. `az cognitiveservices account keys list` fails: `Failed to list key. disableLocalAuth is set to be true`.
- Storage account: `allowSharedKeyAccess` and `allowBlobPublicAccess` are `false`. A blob listing with the account key fails: `KeyBasedAuthenticationNotPermitted`.
- The code reached the Foundry project with an Entra token (the prior-knowledge and timeline calls below), and the Azure CLI reached Blob Storage with `--auth-mode login` (uploads, listings, downloads below).

### Cases and sources

`hindcast.capture` and the registry (`data/cases.yaml`, `hindcast.cases`): PR #5 commit `877585b`, with a comment fix in PR #5 commit `163ab1c`.

| Case | Role | Status updates | Answer key |
|---|---|---|---|
| `cloudflare-2025-11-18` | showcase | Cloudflare status `8gmgl950y3h7` | Cloudflare blog postmortem |
| `github-2026-08-17` | showcase | GitHub status `zkxwbgr0cnmx` | GitHub availability report, August 2026 |
| `google-cloud-2026-07-14` | showcase | Google Cloud feed entry `T8gmtofFSTGT5tbhyciF` | Google Cloud incident report |
| `cloudflare-2026-02-20` | development | Cloudflare status `kwy3dt82bwbt` | Cloudflare blog postmortem |

The two recent showcase cases began after the training cutoffs that Microsoft's model table states ("Training Data (up to)": May 2026 for gpt-6-luna, April 2026 for gpt-6.1-sol; page updated 2026-10-08).

- Captured on 2026-10-25 between 21:09:30 and 21:09:35 UTC.
- `verify_local_files` returned an empty list for all four cases. After one byte of `github-status-2026-08-17.json` was changed, it returned `['github-status-2026-08-17']`; after the file was restored, an empty list again.
- A second capture of `8gmgl950y3h7` gave the same SHA-256 as the first (`95e7a2ef…`).
- Blob Storage: the eight files uploaded to `sources/<case_id>/`, downloaded again into an empty folder, and `verify_local_files` on the download returned an empty list for all four cases. This was run twice: once with single uploads and once with the runbook's batch commands.
- Cloudflare Radar's About page licenses its downloadable graphs and images under CC BY 4.0: checked by hand in a browser on 2026-10-26. The page refuses scripted reads (HTTP 403), so no copy is kept. Charts are registered, with their attribution, in milestone 2.

### Prior knowledge

PR #5 commit `30c180e` changed the question to name the provider, the incident's public title, and its date, and to ask whether it was an attack. `test_no_key_fact_in_any_question` failed when `sidecar` (a key fact) was added to a case title, and passed after the revert.

Collected on 2026-10-25 from PR #5 commit `30c180e`, effort medium, three showcase cases, committed unread in PR #5 commit `c8ff321`:

| Deployment | Input tokens | Output tokens |
|---|---|---|
| gpt-6-luna 2026-09-22 | 466 | 3,526 |
| gpt-6.1-sol 2026-09-29 | 466 | 2,315 |

The answers are scored with the rubric frozen in milestone 5.

### Model re-check on the development outage

The rule, the five questions, and a hand count of nine timeline events were written before any run: [model selection](../../eval/model-selection/dev-outage-v1/README.md). The timeline calls (live, 2026-10-25) found all nine events for gpt-6-luna at low and medium effort and for gpt-6.1-sol at medium, with nothing added.

The Foundry evaluation ran live on 2026-10-26, one portal run per model, judge gpt-6.1-sol. Results, run records, and log excerpts are committed in the model selection folder; the scores and the rule are in [decision 0012](../decisions/0012-models.md).

- First attempt: every row failed with 401. Cause and fix in [troubleshooting](../troubleshooting.md): the portal calls the models as the user on the resource endpoint once key access is off, and the user needed Cognitive Services OpenAI User on the Foundry resource. Check: `GET <project endpoint>/openai/evals?api-version=v1` returned 400 before the assignment and 200 after.
- Second attempt, both runs completed. Groundedness 5.0 for both; completeness 4.4 for sol and missing for luna on one question, because 2 of luna's 25 judge calls failed with 401 ([#7](https://github.com/sindredg/hindcast/issues/7)). The rule holds for every value the missing score could take, an argument made after the run. Both refused question 5 without naming a cause.
- `check_quotes.py --no-quote-ok 4`: 6 of 6 quotes word for word per run, exit 0; with `--break-row 0`, exit 1 per run.
- `summarise_runs.py` crashed on the failed judge calls, which have no token usage: the tests had no such row. Fixed test first (three tests failed, then passed); it now lists failed calls. `sanitize_results.py` now also sanitizes the run record and keeps the failed-call lines in the log excerpt, each with a test that failed first. `check_quotes.py` gained its first unit tests after the review below. `tests/test_model_selection.py` has 35 tests; the whole suite passes (113, `uv run --frozen pytest -q`).

What the runs showed about the platform: [evaluation findings](../findings/evaluation.md) and [identity findings](../findings/identity-and-access.md).

`sanitize_results.py` prepares a run's downloads for commit and `summarise_runs.py` applies the score part of the rule (commit `07143db`). Tested locally, before any run on this case:

- `tests/test_model_selection.py`, 24 tests. Each of 23 one-line breaks of the two scripts made at least one test fail.
- The downloads of an earlier evaluation run, with this case's status text put in place of that run's context at every encoding level: the leak check flagged 20 fields before sanitizing and none after, with no identifier left. The log excerpt matched one picked by hand for that run, and the summary reproduced the means recorded for it.

### Diagrams

The [architecture page](../architecture/README.md) carries the as-built diagram and the prior-knowledge flow; the README carries the target architecture. Each passed the diagram skill's `self_check.py` and `verify-geometry.py`; `verify-geometry.py` reported a finding on a copy with a label moved onto a later node, so it can fail.

### Findings

[Findings](../findings/) record what the platform and the sources did, with evidence: the status archives and their formats, where the cause leaks into the live record, the models' token use, access for portal evaluations, and what evaluation runs count. Failures with their fix are in [troubleshooting](../troubleshooting.md).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| CI fails on lint, unpinned action, workflow, YAML, and vulnerable-dependency errors; each shown failing once | Tested locally; configured in CI | Break-test table above. CI runs the same checks with the same versions: `.github/workflows/ci.yml`, run `40233792968` |
| `main` takes changes only through a pull request with passing checks and signed commits; secret scanning and push protection on | Tested live | Ruleset read-back, direct push refused with `GH013`, security settings read back |
| Foundry project, deployments, and Blob Storage exist and are reached with Entra tokens; key access off | Tested live; accepted gap for the Log Analytics workspace and for Blob Storage from Hindcast's code | Deployment list; calls through the project; `--auth-mode login` uploads and downloads; key listing and key use refused. The Log Analytics workspace behind Application Insights still accepts its shared keys: nothing uses them, and turning them off waits until traces flow and the change can be checked ([#2](https://github.com/sindredg/hindcast/issues/2)). Blob Storage was reached with the Azure CLI's Entra token, not from Hindcast's code, which has no Blob client yet: reading sources from Blob Storage with an Entra token is milestone 2's first criterion |
| Every source in the registry with URL, licence, attribution, retrieval time, and a matching SHA-256, locally and in Blob Storage | Tested locally and live | `verify_local_files` on the local files and on a fresh download; byte-flip break-test |
| Prior-knowledge answers recorded before any evidence reaches a model | Tested live | Result files committed in PR #5 commit `c8ff321` at 2026-10-25 21:16:40 UTC, collected from PR #5 commit `30c180e`. The first calls that gave a model case evidence, the timeline calls on the development case, wrote their answers at 21:18:18 to 21:18:36 UTC (local file times) |
| The investigator model meets the rule on the development outage | Tested live, 2026-10-26; accepted gap: one luna completeness score is missing, and the rule is decided by a bound worked out after the run | Two Foundry evaluation runs, read with `summarise_runs.py` and `check_quotes.py`: [model selection](../../eval/model-selection/dev-outage-v1/README.md), [decision 0012](../decisions/0012-models.md). One luna completeness score is missing; the rule holds for every value it could take |

## Independent review

A separate agent reviewed the milestone read-only on 2026-10-26, at `b94c2a8`. It checked the claims against the code, CI, the GitHub settings, and the live Azure resources, without opening the prior-knowledge answers. Every finding was checked again before it was acted on; none was rejected.

Fixed in this pull request:

- Three test fixtures held the run and evaluation IDs of a real earlier run; they now use made-up IDs.
- `check_quotes.py` counted a quote that is empty after normalising (an ellipsis, a full stop) as found. Fixed with its first unit tests; the empty-quote test failed before the fix. Both runs still check 6 of 6.
- Gate labels: Blob Storage reached from Hindcast's code, and the bound behind the re-check, are accepted gaps; the prior-knowledge row records the evidence for the order of events.
- Break-test table: a row for `ruff format --check`, and the pip-audit break run with CI's flags.
- A commit reference that is in no branch, and PR #5 commits now named as such.
- Lines that described planned behaviour as built (the case evidence cut, checking every evaluation result), a wrong completeness count in decision 0012, and a pass count that the downloaded rows do not carry.
- The runbook's ruleset step names the two defaults its JSON does not set.

Opened as issues: [#8](https://github.com/sindredg/hindcast/issues/8), [#9](https://github.com/sindredg/hindcast/issues/9), and [#10](https://github.com/sindredg/hindcast/issues/10) (under Follow-up).

Not acted on: gpt-6.1-terra 2026-10-26 became generally available in Sweden Central on the day decision 0012 was accepted (`az cognitiveservices model list`). It is not measured; luna stays on decision 0012's evidence. Four diagram gaps the review confirmed are fixed in this pull request, waiting for a look: the current-architecture diagram now says "status · postmortems" instead of "status APIs · blogs" and shows the portal evaluation path; the prior-knowledge diagram names `pyproject.toml` among the committed inputs and shows the refusal when a showcase case has no date. Both pass `self_check.py` and `verify-geometry.py` with no findings.

## Deviations from the plan

- The ruleset was created through the API from the recorded settings, not copied from an existing ruleset.
- The evidence ends before the update that marks an incident resolved: that update's time and status are kept and its text is withheld, because GitHub and Google Cloud put the cause there ([decision 0005](../decisions/0005-evidence-library-and-answer-key.md)).
- Uploads are checked by downloading and hashing, because the Content-MD5 that `az storage blob show` returns repeats the value the upload sent.
- Charts are registered in milestone 2, with the extraction that reads them.

## Follow-up

- [#1](https://github.com/sindredg/hindcast/issues/1): the newest actionlint release does not know the `ubuntu-26.04` runner label, so CI declares it.
- [#2](https://github.com/sindredg/hindcast/issues/2): Log Analytics workspace keys, milestone 4.
- [#3](https://github.com/sindredg/hindcast/issues/3): settings require search and embedding values before they exist, milestone 2.
- [#4](https://github.com/sindredg/hindcast/issues/4): result files record the requested reasoning effort, not the one the response reports, milestone 5.
- [#7](https://github.com/sindredg/hindcast/issues/7): a few portal evaluation calls failed with 401 an hour after the role assignment; checked again before the milestone 5 runs.
- [#8](https://github.com/sindredg/hindcast/issues/8): Dependabot cannot update the Python dependencies, because it does not support Python 3.15; the pins move by hand.
- [#9](https://github.com/sindredg/hindcast/issues/9): the developer's resource-scope role for portal evaluations also covers the project, so the project-scope least-privilege claim cannot fail while it is assigned. Removed on 2026-10-26 at 19:26 UTC; the evals read returned 400 again and a gpt-6-luna call through the project answered. The runbook now removes it after each portal run.
- [#10](https://github.com/sindredg/hindcast/issues/10): Python 3.15.2 is out; move when uv offers it.

## Not verified

- That the postmortem pages still hash the same when captured again: a page's layout can change around an unchanged article. The registry pins the copy in Blob Storage.
- The CI checks failing on a pull request in this repository: they were broken locally, and run green in CI.
- Why three calls in the evaluation runs failed with 401 after the role assignment ([#7](https://github.com/sindredg/hindcast/issues/7)).

# Milestone 1: Foundations

Status: Verified on 2026-10-26 ([gate](#gate), [independent review](#independent-review)); built on 2026-10-25. Milestone state: [roadmap](../roadmap.md#status).

On this page: [Scope](#scope) · [Work completed](#work-completed) · [Gate](#gate) · [Independent review](#independent-review) · [Deviations from the plan](#deviations-from-the-plan) · [Follow-up](#follow-up) · [Not verified](#not-verified)

## Scope

Repository, pipeline, GitHub protection, Azure foundation, case registry and sources, prior-knowledge baseline, model re-check. Rebuild: [runbook](../runbooks/foundations.md).

## Work completed

### Decisions

[Decisions 0001 to 0011](../decisions/) are accepted. [Decision 0012](../decisions/0012-models.md) (models) is accepted from the re-check below.

### Repository and pipeline

- `main` started from a clean tree: commit `ae6184a`. CI run `40233792968`, success.
- Ruleset `main` (ID `25837252`): no deletions or force pushes, signed commits, pull request required (squash or rebase, threads resolved), three CI checks, branch up to date, no bypass list. Read back with `gh api repos/<owner>/hindcast/rules/branches/main --jq '[.[].type] | join(",")'`: `deletion,non_fast_forward,required_signatures,pull_request,required_status_checks`.
- Secret scanning, push protection, Dependabot alerts and security updates on. Read back: `dependabot_security_updates=enabled secret_scanning=enabled ... secret_scanning_push_protection=enabled`; `HTTP/2.0 204` from `vulnerability-alerts`. Dependabot's uv job fails on Python 3.15 ([#8](https://github.com/sindredg/hindcast/issues/8)); its GitHub Actions updates run.
- A signed empty commit pushed to `main` was refused: `GH013: Repository rule violations found for refs/heads/main`, `[remote rejected]`; `main` stayed at `ae6184a`.

Each check broken once, locally on 2026-10-25, with the `uv.lock` versions and CI's actionlint:

| Check | Broken input | Result |
|---|---|---|
| ruff | `import os`, unused | `F401`, exit 1 |
| ruff format `--check` (run 2026-10-26) | `x  =  1` | `1 file would be reformatted`, exit 1 |
| yamllint `--strict` | mixed list indentation | syntax error, exit 1 |
| zizmor `--persona=auditor` | `actions/checkout@v4` | `unpinned-uses`, exit 14 |
| actionlint 1.7.12 (linux arm64, SHA-256 checked against the release's checksums file) | `stepz:` for `steps:` | `"steps" section is missing`, exit 1 |
| pip-audit `--strict --disable-pip --require-hashes`, the CI command (run 2026-10-26) | `requests==2.19.0` with its wheel's hash | `PYSEC-2026-1872`, `PYSEC-2026-1873`, `PYSEC-2026-2275`, exit 1 |
| pytest | each new test before its code (registry, capture, prior question) | failed, then passed |

A first break (2026-10-25) ran `pip-audit --strict` without CI's flags: `PYSEC-2018-28`, exit 1. With CI's flags an unhashed pin fails on the hash, not the vulnerability, so the row uses a hashed pin.

On the repository all five pass (actionlint exit 0, the others in the [gate](#gate)).

### Azure foundation

Created 2026-10-24 and 2026-10-25 ([runbook](../runbooks/foundations.md)). Read live on 2026-10-25:

- `az cognitiveservices account deployment list`: gpt-6-luna 2026-09-22 and gpt-6.1-sol 2026-09-29, Global Standard, capacity 50, `NoAutoUpgrade`, 50 requests per minute; gpt-5-mini 2025-08-07 (capacity 237) and grok-4.7 (capacity 50) with automatic upgrade.
- Foundry `disableLocalAuth` is `true`; `az cognitiveservices account keys list` fails: `Failed to list key. disableLocalAuth is set to be true`.
- Storage: `allowSharedKeyAccess` and `allowBlobPublicAccess` are `false`; a key-based blob listing fails: `KeyBasedAuthenticationNotPermitted`.
- The code reached the project with an Entra token; the Azure CLI reached Blob Storage with `--auth-mode login`.

### Cases and sources

`hindcast.capture` and the registry (`data/cases.yaml`, `hindcast.cases`): PR #5 commits `877585b` and `163ab1c` (comment fix).

| Case | Role | Status updates | Answer key |
|---|---|---|---|
| `cloudflare-2025-11-18` | showcase | Cloudflare status `8gmgl950y3h7` | Cloudflare blog postmortem |
| `github-2026-08-17` | showcase | GitHub status `zkxwbgr0cnmx` | GitHub availability report, August 2026 |
| `google-cloud-2026-07-14` | showcase | Google Cloud feed entry `T8gmtofFSTGT5tbhyciF` | Google Cloud incident report |
| `cloudflare-2026-02-20` | development | Cloudflare status `kwy3dt82bwbt` | Cloudflare blog postmortem |

The two recent showcase cases began after the training cutoffs in Microsoft's model table: May 2026 (gpt-6-luna), April 2026 (gpt-6.1-sol); page updated 2026-10-08.

- Captured on 2026-10-25, 21:09:30 to 21:09:35 UTC.
- `verify_local_files`: empty list for all four cases; `['github-status-2026-08-17']` after one byte of `github-status-2026-08-17.json` changed; empty again after the restore.
- A second capture of `8gmgl950y3h7` gave the same SHA-256 (`95e7a2ef…`).
- Blob Storage: eight files uploaded to `sources/<case_id>/`, downloaded into an empty folder, `verify_local_files` empty for all four; twice, single uploads and the runbook's batch commands.
- Cloudflare Radar's About page licenses its graphs under CC BY 4.0 (browser, 2026-10-26; scripted reads get HTTP 403, no copy kept). Charts: milestone 2.

### Prior knowledge

PR #5 commit `30c180e`: the question names the provider, the incident's public title and date, and asks whether it was an attack. `test_no_key_fact_in_any_question` failed with `sidecar` in a case title, passed after the revert.

Collected on 2026-10-25 from commit `30c180e`, effort medium, three showcase cases, committed unread in PR #5 commit `c8ff321`:

| Deployment | Input tokens | Output tokens |
|---|---|---|
| gpt-6-luna 2026-09-22 | 466 | 3,526 |
| gpt-6.1-sol 2026-09-29 | 466 | 2,315 |

Scored with the rubric frozen in milestone 5.

### Model re-check on the development outage

Rule, five questions, and a hand count of nine timeline events written before any run: [model selection](../../eval/model-selection/dev-outage-v1/README.md). Timeline calls (live, 2026-10-25): all nine events for gpt-6-luna at low and medium effort and gpt-6.1-sol at medium, nothing added.

Foundry evaluation, live on 2026-10-26, one portal run per model, judge gpt-6.1-sol. Results and records in the model selection folder; scores and rule in [decision 0012](../decisions/0012-models.md).

- First attempt: every row 401 ([troubleshooting](../troubleshooting.md)): the user needed Cognitive Services OpenAI User on the Foundry resource. `GET <project endpoint>/openai/evals?api-version=v1`: 400 before the assignment, 200 after.
- Second attempt: both completed. Groundedness 5.0 for both; completeness 4.4 for sol, missing for luna on one question (2 of 25 judge calls failed with 401, [#7](https://github.com/sindredg/hindcast/issues/7)). The rule holds for every value the missing score could take (argued after the run). Both refused question 5 without naming a cause.
- `check_quotes.py --no-quote-ok 4`: 6 of 6 quotes per run, exit 0; with `--break-row 0`, exit 1 per run.
- `summarise_runs.py` crashed on failed judge calls (no token usage); fixed test first (three failed, then passed). `sanitize_results.py` now sanitizes the run record and keeps failed-call lines, tests first. `check_quotes.py` gained unit tests after the review. `tests/test_model_selection.py`: 35 tests; suite 113 passed (`uv run --frozen pytest -q`).

Platform findings: [evaluation](../findings/evaluation.md), [identity](../findings/identity-and-access.md).

`sanitize_results.py` and `summarise_runs.py` (commit `07143db`), tested locally before any run on this case:

- `tests/test_model_selection.py`, 24 tests; each of 23 one-line breaks failed at least one.
- An earlier run's downloads with this case's status text planted at every encoding level: 20 fields flagged before sanitizing, none after. Log excerpt and summary matched the recorded ones.

### Diagrams

[Architecture page](../architecture/README.md): as-built diagram and prior-knowledge flow; README: target architecture. Each passed `self_check.py` and `verify-geometry.py`; the latter flagged a copy with a moved label.

### Findings

[Findings](../findings/) record what the platform and sources did; failures with their fix: [troubleshooting](../troubleshooting.md).

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| CI fails on lint, unpinned action, workflow, YAML, and vulnerable-dependency errors; each shown failing once | Tested locally; configured in CI | Break-test table above. CI runs the same checks and versions: `.github/workflows/ci.yml`, run `40233792968` |
| `main` takes changes only through a pull request with passing checks and signed commits; secret scanning and push protection on | Tested live | Ruleset read-back, direct push refused with `GH013`, security settings read back |
| Foundry project, deployments, and Blob Storage exist and are reached with Entra tokens; key access off | Tested live; accepted gap for the Log Analytics workspace and for Blob Storage from Hindcast's code | Deployment list; calls through the project; `--auth-mode login` uploads and downloads; key listing and use refused. Log Analytics still accepts shared keys, unused, off once traces flow ([#2](https://github.com/sindredg/hindcast/issues/2)). Blob Storage reached with the CLI's token, not from the code (no Blob client yet): milestone 2's first criterion |
| Every source in the registry with URL, licence, attribution, retrieval time, and a matching SHA-256, locally and in Blob Storage | Tested locally and live | `verify_local_files` on the local files and a fresh download; byte-flip break-test |
| Prior-knowledge answers recorded before any evidence reaches a model | Tested live | Results committed in PR #5 commit `c8ff321` at 2026-10-25 21:16:40 UTC, from commit `30c180e`; the first calls with case evidence (timeline) wrote at 21:18:18 to 21:18:36 UTC (local file times) |
| The investigator model meets the rule on the development outage | Tested live, 2026-10-26; accepted gap: one luna completeness score is missing, and the rule is decided by a bound worked out after the run | Two Foundry evaluation runs, read with `summarise_runs.py` and `check_quotes.py`: [model selection](../../eval/model-selection/dev-outage-v1/README.md), [decision 0012](../decisions/0012-models.md) |

## Independent review

Read-only review from a fresh context, 2026-10-26, at `b94c2a8`: code, CI, GitHub settings, live Azure, prior-knowledge answers unopened. None of its findings was rejected.

Fixed in this pull request:

- Three test fixtures held a real run's IDs; now made-up.
- `check_quotes.py` counted a quote empty after normalising as found. Fixed, test first. Both runs still 6 of 6.
- Gate labels: two accepted gaps; the prior-knowledge row records the order of events.
- Break-test table: a `ruff format --check` row; the pip-audit break with CI's flags.
- A commit reference in no branch; PR #5 commits named as such.
- Planned behaviour written as built, a wrong completeness count in decision 0012, a pass count the rows do not carry.
- The runbook's ruleset step names the two defaults its JSON does not set.

Opened as issues: [#8](https://github.com/sindredg/hindcast/issues/8), [#9](https://github.com/sindredg/hindcast/issues/9), [#10](https://github.com/sindredg/hindcast/issues/10) (under Follow-up).

Not acted on: gpt-6.1-terra 2026-10-26 became generally available in Sweden Central the day decision 0012 was accepted (`az cognitiveservices model list`). Not measured; luna stays. Four diagram gaps fixed: the current-architecture diagram says "status · postmortems" (was "status APIs · blogs") and shows the portal evaluation path; the prior-knowledge diagram names `pyproject.toml` and shows the refusal for a showcase case without a date. Both pass `self_check.py` and `verify-geometry.py`.

## Deviations from the plan

- The ruleset was created through the API from the recorded settings, not copied.
- The resolved update keeps its time and status, its text withheld: GitHub and Google Cloud put the cause there ([decision 0005](../decisions/0005-evidence-library-and-answer-key.md)).
- Uploads are checked by download and hash: `az storage blob show` repeats the Content-MD5 the upload sent.
- Charts are registered in milestone 2, with the extraction that reads them.

## Follow-up

- [#1](https://github.com/sindredg/hindcast/issues/1): actionlint does not know the `ubuntu-26.04` runner label; CI declares it.
- [#2](https://github.com/sindredg/hindcast/issues/2): Log Analytics workspace keys, milestone 4.
- [#3](https://github.com/sindredg/hindcast/issues/3): settings require search and embedding values before they exist, milestone 2.
- [#4](https://github.com/sindredg/hindcast/issues/4): result files record the requested reasoning effort, not the reported one, milestone 5.
- [#7](https://github.com/sindredg/hindcast/issues/7): a few portal evaluation calls failed with 401 an hour after the role assignment; checked again before the milestone 5 runs.
- [#8](https://github.com/sindredg/hindcast/issues/8): Dependabot does not support Python 3.15; pins move by hand.
- [#9](https://github.com/sindredg/hindcast/issues/9): the resource-scope role for portal evaluations masks the project-scope claim. Removed 2026-10-26 at 19:26 UTC: the evals read returned 400 again, a gpt-6-luna call through the project answered. The runbook removes it after each portal run.
- [#10](https://github.com/sindredg/hindcast/issues/10): Python 3.15.2 is out; move when uv offers it.

## Not verified

- A fresh capture of the postmortem pages hashing the same; the registry pins the Blob copy.
- The CI checks failing on a pull request here: broken locally, green in CI.
- Why three evaluation calls failed with 401 after the role assignment ([#7](https://github.com/sindredg/hindcast/issues/7)).

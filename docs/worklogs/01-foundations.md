# Milestone 1: Foundations

Status: Built on 2026-10-25. The model re-check on the development outage and the [independent review](#independent-review) are open; the milestone state is in the [roadmap](../roadmap.md).

## Scope

The repository and its pipeline, the GitHub protection, the Azure foundation, the case registry with its captured sources, the prior-knowledge baseline, and the check of the model choice on the development outage. The procedure to rebuild it is the [runbook](../runbooks/foundations.md).

## Work completed

### Decisions

[Decisions 0001 to 0011](../decisions/) are accepted: outages as the scope with the attack question first, a prompt agent with case tools and a date-bound library search, Content Understanding for postmortems and charts, AI Search over the postmortem library, the cut rules for evidence and answer keys, the evaluation and support rules, Prompt Shields on every tool result, the investigation view, hosting, infrastructure as code, and telemetry. Decision 0012 (models) is written from the re-check below.

### Repository and pipeline

- `main` started from a clean tree with the project skeleton, CI, Dependabot, settings, and the model client: commit `ae6184a`. CI on that commit: run `40233792968`, success.
- Ruleset `main` (ID `25837252`): restrict deletions, block force pushes, require signed commits, require a pull request (squash or rebase, threads resolved), require the three CI checks with the branch up to date, no bypass list. Read back with `gh api repos/<owner>/hindcast/rules/branches/main --jq '[.[].type] | join(",")'`: `deletion,non_fast_forward,required_signatures,pull_request,required_status_checks`.
- Secret scanning, push protection, Dependabot alerts, and Dependabot security updates on. Read back: `dependabot_security_updates=enabled secret_scanning=enabled ... secret_scanning_push_protection=enabled`, and `HTTP/2.0 204` from `vulnerability-alerts`.
- A signed empty commit pushed straight to `main` was refused: `GH013: Repository rule violations found for refs/heads/main`, `[remote rejected]`; `main` stayed at `ae6184a`.

Each check was run once against a broken input, locally on 2026-10-25, with the versions in `uv.lock` and the actionlint version CI pins:

| Check | Broken input | Result |
|---|---|---|
| ruff | a file with `import os` and no use | `F401`, exit 1 |
| yamllint `--strict` | a list with mixed indentation | syntax error, exit 1 |
| zizmor `--persona=auditor` | a workflow using `actions/checkout@v4` | `unpinned-uses`, exit 14 |
| actionlint 1.7.12 (linux arm64, SHA-256 checked against the release's checksums file) | a job with `stepz:` instead of `steps:` | `"steps" section is missing`, exit 1 |
| pip-audit `--strict` | `requests==2.19.0` | `PYSEC-2018-28`, exit 1 |
| pytest | each new test before its code existed (registry, capture, prior question) | failed, then passed after the code |

On the repository itself all five pass (actionlint exit 0, the others as in the [gate](#gate)).

### Azure foundation

Created on 2026-10-24 and 2026-10-25 by the [runbook](../runbooks/foundations.md)'s Azure steps. Read live on 2026-10-25:

- `az cognitiveservices account deployment list`: gpt-6-luna 2026-09-22 and gpt-6.1-sol 2026-09-29, Global Standard, capacity 50, `NoAutoUpgrade`, 50 requests per minute; gpt-5-mini 2025-08-07 (capacity 237) and grok-4.7 (capacity 50) with automatic upgrade.
- Foundry resource `disableLocalAuth` is `true`. `az cognitiveservices account keys list` fails: `Failed to list key. disableLocalAuth is set to be true`.
- Storage account: `allowSharedKeyAccess` and `allowBlobPublicAccess` are `false`. A blob listing with the account key fails: `KeyBasedAuthenticationNotPermitted`.
- The code reached the Foundry project with an Entra token (the prior-knowledge and timeline calls below), and the Azure CLI reached Blob Storage with `--auth-mode login` (uploads, listings, downloads below).

### Cases and sources

`hindcast.capture` and the registry (`data/cases.yaml`, `hindcast.cases`): commit `877585b`, with a comment fix in `163ab1c`.

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

### Prior knowledge

Commit `30c180e` changed the question to name the provider, the incident's public title, and its date, and to ask whether it was an attack. `test_no_key_fact_in_any_question` failed when `sidecar` (a key fact) was added to a case title, and passed after the revert.

Collected on 2026-10-25 from commit `30c180e`, effort medium, three showcase cases, committed unread in `c8ff321`:

| Deployment | Input tokens | Output tokens |
|---|---|---|
| gpt-6-luna 2026-09-22 | 466 | 3,526 |
| gpt-6.1-sol 2026-09-29 | 466 | 2,315 |

The answers are scored with the rubric frozen in milestone 5.

### Model re-check on the development outage

The rule, the five questions, and a hand count of nine timeline events were written before any run: [model selection](../../eval/model-selection/dev-outage-v1/README.md). The timeline calls (live, 2026-10-25) found all nine events for gpt-6-luna at low and medium effort and for gpt-6.1-sol at medium, with nothing added. The Foundry evaluation runs on the five questions are open.

### Diagrams

The [architecture page](../architecture/README.md) carries the as-built diagram and the prior-knowledge flow; the README carries the target architecture. Each passed the diagram skill's `self_check.py` and `verify-geometry.py`; `verify-geometry.py` reported a finding on a copy with a label moved onto a later node, so it can fail.

### Findings

[Findings](../findings/) record what the platform and the sources did, with evidence: the status archives and their formats, where the cause leaks into the live record, and the models' token use.

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| CI fails on lint, unpinned action, workflow, YAML, and vulnerable-dependency errors; each shown failing once | Tested locally; configured in CI | Break-test table above. CI runs the same checks with the same versions: `.github/workflows/ci.yml`, run `40233792968` |
| `main` takes changes only through a pull request with passing checks and signed commits; secret scanning and push protection on | Tested live | Ruleset read-back, direct push refused with `GH013`, security settings read back |
| Foundry project, deployments, and Blob Storage exist and are reached with Entra tokens; key access off | Tested live | Deployment list; calls through the project; `--auth-mode login` uploads and downloads; key listing and key use refused |
| Every source in the registry with URL, licence, attribution, retrieval time, and a matching SHA-256, locally and in Blob Storage | Tested locally and live | `verify_local_files` on the local files and on a fresh download; byte-flip break-test |
| Prior-knowledge answers recorded before any evidence reaches a model | Tested live | Result files in `c8ff321`, collected from `30c180e` |
| The investigator model meets the rule on the development outage | Open | Rule and questions written; Foundry evaluation runs not done yet |

## Independent review

Open.

## Deviations from the plan

- The ruleset was created through the API from the recorded settings, not copied from an existing ruleset.
- The evidence ends before the update that marks an incident resolved: that update's time and status are kept and its text is withheld, because GitHub and Google Cloud put the cause there ([decision 0005](../decisions/0005-evidence-library-and-answer-key.md)).
- Uploads are checked by downloading and hashing, because the Content-MD5 that `az storage blob show` returns repeats the value the upload sent.
- Charts are registered in milestone 2, with the extraction that reads them.

## Not verified

- That Radar's downloadable chart images are licensed CC BY 4.0. Its About page blocks scripted reads; the licence is checked in a browser before any chart is committed.
- That the postmortem pages still hash the same when captured again: a page's layout can change around an unchanged article. The registry pins the copy in Blob Storage.
- The CI checks failing on a pull request in this repository: they were broken locally, and run green in CI.

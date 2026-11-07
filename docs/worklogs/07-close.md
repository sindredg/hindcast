# Worklog 07: Close

Status: Built on 2026-11-07. The checks before the teardown ran with the output below, every open issue has a verdict, and the staleness pass is in. The [teardown](#teardown) and the [independent review](#independent-review) are recorded here as they complete. Milestone state: [roadmap](../roadmap.md#status).

Scope: [milestone 7](../roadmap.md#7-close). The procedure is the [teardown runbook](../runbooks/teardown.md); the order of every runbook is the [reproduce page](../reproduce.md).

## Before the teardown

| Check | How | Result |
| --- | --- | --- |
| Sealed copies match their hashes | Teardown runbook step 1, 2026-11-07: every entry of `eval/sealed/seals.json` hashed under `build/sealed/` and in `~/backups/hindcast/sealed-20261104T1723Z.tgz` | Tested: `16 of 16 match local and backup`. Broken input: a hash of other bytes differs from every seal, so a changed copy would show as a mismatch |
| Every blob has a local copy | Teardown runbook step 2, 2026-11-07: both containers downloaded to a dated folder and compared by hash with `data/sources/` and `build/` | Tested: 39 and 57 blobs, 96 files, 6.9 MB; 91 matched, 0 differed, 5 (`extracted/keys/*-result.json`, the analyzer results) had no local copy and are kept by the download alone |
| Every frozen key passes the leak check offline | `python -m hindcast.leak <case> --snapshot build/sealed-library/github-2026-11-04-actions.json` for each of the six keyed cases, 2026-11-07, after the short-item rule of [#83](https://github.com/sindredg/hindcast/issues/83) went in; the snapshot holds the whole library, filtered by each case's rule in code | Tested: 0 hits for all six (17, 17, 8, 11, 9, and 14 unstated items against 143, 74, 79, 44, 88, and 267 chunks). Broken input: `--plant` on `cloudflare-2025-11-18` reports `root_cause in planted: 20 shared runs`, exit 0; `test_a_key_item_shorter_than_a_run_is_matched_whole` fails on the old rule |

## Teardown

Recorded when the [teardown runbook](../runbooks/teardown.md) steps 3 to 9 have run.

## Issues

Every open issue on 2026-11-07, with its verdict. Fixed items are in this milestone's pull request, each with a test shown failing on the old code.

| Issue | Verdict | Why |
| --- | --- | --- |
| [#1](https://github.com/sindredg/hindcast/issues/1) actionlint lags the runner labels | Closed | No newer release on 2026-11-07 (v1.7.12, last commit 2026-04-19); the label declaration in `.github/actionlint.yaml` stays, and the trigger (each milestone's start) cannot fire again |
| [#4](https://github.com/sindredg/hindcast/issues/4) requested reasoning effort recorded | Closed | The limit is stated in the [prior-knowledge report](../../eval/prior-knowledge/v1/README.md#limits); both collections requested the same effort |
| [#12](https://github.com/sindredg/hindcast/issues/12) draft check accepts a time not in UTC | Fixed | A written time with a zone is converted and compared; keys for the pending reveals are drafted by hand with this check |
| [#14](https://github.com/sindredg/hindcast/issues/14) reused extracts not checked against the registry | Closed | No further capture or extraction runs; the reveal is offline (decision 0022) |
| [#17](https://github.com/sindredg/hindcast/issues/17) chart evidence carries no attribution | Closed | The page shows each chart's attribution and licence from the registry (`_chart_credit` in `hindcast.app`); the design joins the registry instead of copying the fields |
| [#19](https://github.com/sindredg/hindcast/issues/19) add an attack case | Closed | No case was added; the [keys README](../../eval/keys/README.md#limits) records that attack detection is not measured |
| [#42](https://github.com/sindredg/hindcast/issues/42) library day bound assumes UTC days | Closed | Sealing stopped on 2026-11-05 and no document is within a day of a case's start (40 days at the closest); the bound stays a documented rule |
| [#44](https://github.com/sindredg/hindcast/issues/44) seal history test fails on a merge of two seal branches | Closed | The `main` ruleset admits only squash and rebase merges, and sealing stopped |
| [#48](https://github.com/sindredg/hindcast/issues/48) sealed result keeps the raw SDK message | Fixed | The reveal refuses a tool-error reason that names a host, an address, a URL, or an ID, and the sealed ledger keeps the kind of reason only |
| [#50](https://github.com/sindredg/hindcast/issues/50) screens split a long text without overlap | Open, limit | The injection results of [dev-v1](../../eval/injection/dev-v1/README.md) were run under this rule; a change goes with new injection runs |
| [#52](https://github.com/sindredg/hindcast/issues/52) no cost line for search queries | Fixed | The trigger fired with the Cost Management read of 2026-11-07; the [price table](../../data/prices.yaml) says why the line is left out |
| [#66](https://github.com/sindredg/hindcast/issues/66) a stated label on the resolved update's time | Fixed | The [labels README](../../eval/keys/labels/README.md) says the resolved update's time and status count as stated |
| [#69](https://github.com/sindredg/hindcast/issues/69) injection copies show "inject" in their refs | Open, limit | A fix reruns all 16 injection runs; the report states the limit |
| [#71](https://github.com/sindredg/hindcast/issues/71) abstention credit with an unsupported root cause | Open, limit | A rubric change is a new version with new runs; the report lists the case |
| [#72](https://github.com/sindredg/hindcast/issues/72) a partial on a not-inferable factor lowers the score | Open, limit | Same |
| [#82](https://github.com/sindredg/hindcast/issues/82) injection check misses a canary in a rejected citation | Open, limit | A wider match changes what a pass means; it goes with new injection runs |
| [#83](https://github.com/sindredg/hindcast/issues/83) leak check misses items under 8 words | Fixed | A short item is matched whole; every key was checked again offline (above) |
| [#84](https://github.com/sindredg/hindcast/issues/84) per-arm failure count double counts | Open, limit | No scored result changes (no failed attempt in the ledger); the fix belongs with a regenerated report |
| [#88](https://github.com/sindredg/hindcast/issues/88) require SHA-pinned actions in the settings | Open, portal | A repository setting for the owner; zizmor checks the pins in CI meanwhile |
| [#90](https://github.com/sindredg/hindcast/issues/90) root cause names finding IDs first | Closed | A page-order question with no further page change planned |
| [#91](https://github.com/sindredg/hindcast/issues/91) redo the November pin batch | Closed | Landed in [#97](https://github.com/sindredg/hindcast/pull/97); the deployment runbook's expected tool versions now name the run they came from |
| [#99](https://github.com/sindredg/hindcast/issues/99) timeline tolerance credits an announcement | Open, limit | A rubric change is a new version; the sealed report states it |
| [#102](https://github.com/sindredg/hindcast/issues/102) reveal's publication time is the last edit | Fixed | The reveal also checks the sealing-day capture: taken before every seal, resolved text under the placeholder floor, and different from the postmortem's |
| [#103](https://github.com/sindredg/hindcast/issues/103) `keys draft` without `--case` | Fixed | `--case` is required and a non-showcase case is refused |
| [#104](https://github.com/sindredg/hindcast/issues/104) scoring commands compare `--root` as written | Fixed | Both sides are resolved |

## Staleness pass

A read-only pass over every tracked page compared each state-carrying sentence with the code, the registries, the workflow, and the close. It found 78 items: present-tense claims about removed resources, "planned" wording the milestones had overtaken, a diagram label and three definitions that left out the `revealed` role, CI job names that differed from the workflow, two counts, and one defect: since the registry was removed on 2026-11-06, the `Push the image` job failed on every push to `main` (runs for `e12c856`, `e2000d7`, and `9d13be7` on 2026-11-07: `AADSTS700016`). The job is now gated on the repository variable `HINDCAST_PUSH_IMAGE`, which the deployment runbook sets in step 6 and removes in step 18; without it the job is skipped. Finding entries keep their dated text ([findings README](../findings/README.md)), except two whose "For Hindcast" line contradicted the code. Every anchor in the tracked pages resolves (922 links checked).

| Check | How | Result |
| --- | --- | --- |
| The retrieval diagram's label and alt text name both whole-library roles | `docs/diagrams/retrieval.html` against `hindcast.search.WHOLE_LIBRARY_ROLES`; `self_check.py`, `verify-geometry.py`, and the rendered PNG read | Tested: `OK`, 0 findings, the label fits its box |
| The workflow still lints after the gate | `yamllint .github/workflows/ci.yml`; `zizmor .github/workflows/ci.yml` | Tested: no findings |
| The push job is skipped without the variable | The next push to `main` | Configured, not tested: the variable is unset, so the job's `if` is false |

## Gate

| Criterion | Status | Evidence |
| --- | --- | --- |
| Everything built by hand is removed and nothing is left | Pending | [Teardown](#teardown) |
| The sealed copies and every blob were checked before the storage went | Tested | [Before the teardown](#before-the-teardown) |
| Every open issue has a verdict | Tested | [Issues](#issues); `gh issue list --state open` after the batch shows only the seven limits and #88 |
| A reproduce page orders the runbooks | Written | [reproduce](../reproduce.md); not tested from a fork, and the page says so |
| Every state-carrying page matches the code and the close | Tested | [Staleness pass](#staleness-pass) |
| An independent review of the close ran with its fixes in | Pending | [Independent review](#independent-review) |

## Independent review

Recorded when the review has run.

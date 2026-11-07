# 17. Sealed reconstructions: run before the postmortem, publish the hash, reveal after

Status: Accepted (2026-11-01). Changed by [decision 0022](0022-sealed-drop-date-and-offline-reveal.md) and [decision 0030](0030-close-evaluation-with-sealed-addenda.md).

## Context

The [prior-knowledge check](../architecture/README.md#the-prior-knowledge-check) asks each model about each scored case first, and every recent scored case began after both pinned models' cutoffs ([worklog 01](../worklogs/01-foundations.md)). A cutoff is the vendor's statement, and not recalling an answer does not prove never having seen it.

Stronger: while the provider has not published its cause, the answer exists nowhere. A reconstruction made then and later shown unchanged cannot have been helped by it. Two problems: publishing a model's account of a named provider's outage before the provider's own is public speculation, and a private reconstruction can be rerun until it looks right, so "made before the postmortem" needs proof an outsider can check.

## Options considered

| Option | Proves | Cost |
|---|---|---|
| Rely on cutoff dates | What the vendor states | Nothing |
| After-release cases only: outages after the pinned version's release | The version cannot have seen the outage or postmortem | Few cases; the postmortem is public when the case is built |
| Seal by hash: run before the postmortem, commit the SHA-256, keep the file private, reveal after | The answer did not exist when the result was made, and the revealed file is that result | Lost if the provider never publishes; runs before the rubric is frozen |
| Seal in public: commit the result itself | As above, without the reveal | A model's guess about a named provider goes public first |

## Decision

Seal by hash, plus after-release cases where they exist.

1. **A sealable outage** meets the [decision 0001](0001-scope.md) rules checkable before a postmortem (nobody harmed, no data leaked, no attacker named, eight or more updates before resolution) and has no provider text stating its cause when sealed. An outage whose resolved update explains the cause is an after-release case.
2. **Registry role `sealed`.** Needs only its status updates. When the postmortem appears it becomes a `postmortem` source and the role becomes `showcase`. No postmortem by 2026-11-09: dropped, records kept and marked `dropped`.
3. **A sealed run is allowed before the rubric is frozen,** because nothing reads it ([decision 0015](0015-investigation-result-and-citation-policy.md) locks scored cases for the same reason). `python -m hindcast.seal run` prints only counts, usage, and the hash. `python -m hindcast.investigate` refuses a sealed case.
4. **A sealed run refuses a changed tree** under `src/`, `prompts/`, `pyproject.toml`, `uv.lock`, and `data/cases.yaml`.
5. **The seal record** is `eval/sealed/seals.json`, committed, signed, and pushed to a pull request the day it is written; the public time is GitHub's record of that pull request, not the commit date. Each entry holds the case, attempt number, deployment and model version, agent name and version, code commit, evidence SHA-256, library setting, UTC time, file name, result SHA-256, Blob name, and status. The file goes to Blob Storage under `extracted/sealed/<case_id>/`, never overwritten.
6. **One seal per case, deployment, and library setting; every attempt recorded.** An attempt with no model output (a 429, a cut-off response, the time cap on the first call) may be retried, up to three attempts. A result with output, complete or not, is the seal and is never replaced.
7. **Reveal.** After the postmortem and the frozen rubric, the file is copied to `eval/investigations/<case_id>/` and the entry marked `revealed`. A test fails CI when a revealed file does not match its hash.
8. **No prior-knowledge question.** The answers are committed, so asking would publish a guess first. A sealed case began after both pinned versions' release. An exception to the roadmap rule.
9. **No per-case library picks.** Decoys need the cause. A sealed case searches the whole library within its date bound.

## Trade-offs

- The drop rule loses slow providers. GitHub and Google Cloud publish within days; Cloudflare only sometimes, so a Cloudflare seal is the likeliest drop. The rule is fixed before the first seal.
- Sealed cases skip the prior-knowledge check and the single-search baseline, so their scores are not directly comparable with the showcase baseline columns.
- Without picks, a document is a decoy only by chance.
- The hash proves the file is unchanged since GitHub recorded the pull request, not that no other run happened. The refusals and attempt records cover that in committed code; workstation access could bypass them. GitHub's event history is kept for a limited time.
- The rubric is written knowing sealed results exist.

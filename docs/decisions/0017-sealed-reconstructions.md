# 17. Sealed reconstructions: run before the postmortem, publish the hash, reveal after

Status: Accepted (2026-11-01).

## Context

A reconstruction is only worth scoring if the model could not have known the answer. The [prior-knowledge check](../architecture/README.md#the-prior-knowledge-check) asks each model about each scored case before it sees any evidence, and every recent scored case began after both pinned models' training cutoffs ([worklog 01](../worklogs/01-foundations.md)). A cutoff is still the vendor's statement, and a check that a model does not recall an answer cannot prove that it never saw one.

There is a stronger test. When an outage is over and the provider has not yet published its cause, the answer exists nowhere: not in training data, not in this repository, not in a search index. A reconstruction made then and shown later to be unchanged cannot have been helped by the answer.

That test brings two problems:

1. Publishing a model's account of a real company's outage before the company's own account is speculation about a named provider, presented as analysis. It can be wrong in public, and a reader cannot tell it from the provider's statement.
2. A reconstruction kept private can be rerun, edited, or replaced until it looks right. The claim "made before the postmortem" needs proof that an outsider can check.

## Options considered

| Option | Proves | Cost |
|---|---|---|
| Rely on the cutoff dates | Only what the vendor states | Nothing to build; the claim rests on someone else's word |
| After-release cases only: outages that began after the pinned model version was released | The model version cannot have seen the outage, or its postmortem | Few cases, and the postmortem is already public when the case is built |
| Seal by hash: run before the postmortem, commit the SHA-256 publicly, keep the file private, reveal it after the postmortem | The answer did not exist when the result was made, and the revealed file is the one that was made | A sealed case is lost if the provider never publishes; the sealed run happens before the rubric is frozen |
| Seal in public: commit the result itself before the postmortem | Same as sealing by hash, without the reveal step | Problem 1: a model's guess about a named provider is public before the provider's account |

## Decision

Seal by hash, and add after-release cases where they exist.

1. **A sealable outage** meets the [decision 0001](0001-scope.md) rules that can be checked before a postmortem (nobody harmed, no data leaked, no attacker named, eight or more updates before resolution) and has no provider text stating its root cause when it is sealed: not the resolved update, not a blog post, not an incident report. An outage whose resolved update already explains the cause is an after-release case, not a sealed one.
2. **Registry role `sealed`.** A sealed case needs only its status updates. When the postmortem is published, it is added as a `postmortem` source and the role becomes `showcase`. A sealed case without a postmortem by 2026-11-09 is dropped: its registry entry and its seal records stay, marked `dropped`, since history is not rewritten.
3. **A sealed run is allowed before the rubric is frozen,** because nothing reads it. [Decision 0015](0015-investigation-result-and-citation-policy.md) locks scored cases so that no output is read before the rubric exists; `python -m hindcast.seal run` keeps that intent by printing only counts, usage, and the hash. `python -m hindcast.investigate` refuses a sealed case at any time, so every sealed run goes through the seal command and is recorded.
4. **A sealed run refuses a changed tree** under `src/`, `prompts/`, `pyproject.toml`, `uv.lock`, and `data/cases.yaml`, so the recorded commit names the exact prompt, agent definition, code, and case.
5. **The seal record** is `eval/sealed/seals.json`, committed, signed, and pushed the day it is written. Each entry holds the case, the attempt number, the deployment and model version, the agent name and version, the code commit, the evidence SHA-256, whether the investigator had the library, the UTC time, the file name, the result's SHA-256, its Blob name, and the status. The file itself goes to Blob Storage under `extracted/sealed/<case_id>/`, never overwritten.
6. **One seal per case, deployment, and library setting, and every attempt is recorded.** An attempt in which the model produced no output (the run raised, such as on a 429 or a cut-off response, or the time cap ended the first call) may be retried, up to three attempts in all. A result with model output, complete or incomplete, is the seal. It is never rerun or replaced, so a bad answer cannot be swapped for a better one.
7. **Reveal.** After the postmortem is published and the rubric is frozen, the file is copied to `eval/investigations/<case_id>/` and its entry is marked `revealed`. A test fails CI when a revealed file does not match its recorded hash.
8. **No prior-knowledge question for a sealed case.** The prior-knowledge answers are committed, and the question asks for the root cause, so asking it would publish a model's guess before the provider's account. A sealed case began after the release of both pinned model versions, so there is nothing for the check to find. This is an exception to the roadmap rule that every scored case is asked first.
9. **No per-case library picks for a sealed case.** Picks need symptom tags, which are possible, and decoys need the cause, which is not known. A sealed case searches the whole library within its date bound.

## Trade-offs

- The drop rule loses every case whose provider is slow. GitHub writes a root-cause summary into the resolved update within days; Google Cloud publishes incident reports within days; Cloudflare writes a postmortem only for some incidents, so a Cloudflare seal is the most likely to be dropped. Choosing which seals to keep after seeing their scores would undo the point, so the rule is fixed before the first seal.
- Sealed cases skip the prior-knowledge check and the single-search baseline (the comparison model runs in the agent's place instead). Their scores are not directly comparable with the showcase cases' baseline columns, and the report has to say so.
- Without per-case picks, a sealed case tests the library as it stands, decoys included by accident rather than by design.
- The hash proves the file is unchanged after the commit time GitHub shows for the push, not that no other run happened. The refusals and the record of every attempt cover that, in code that is itself committed. Someone with access to the Blob container and the workstation could still run the investigator outside the seal command; the record cannot show a run that never went through it.
- The sealed run happens before the rubric is frozen. Nothing reads the output until then, but the rubric is written knowing that sealed results exist.

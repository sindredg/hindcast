# 28. One template for the whole environment, and a page that investigates

Status: Accepted (2026-11-05).

Answers the question [decision 0016](0016-sign-in-credential-image-build-and-resource-group.md) left open: whether the template owns the hand-built resources. Also decides what the page runs, how a fresh environment gets its data, and what replaces a recorded demo.

The "withheld injection" in section 5 became the injection test's outcome in the roadmap's criterion on 2026-11-06: Prompt Shields does not flag the planted update, so the model ignoring it is the pass ([roadmap](../roadmap.md#6-deployment-and-release)).

## Context

Foundry, the deployments, storage, Application Insights, and search live in a group `azd` never touched (decision 0016, option F), so `azd up` from empty proves the app only. The page renders stored results and calls no model. `build/` and `data/sources/` are not committed; not every source licence allows redistribution. Everything is deleted on 2026-11-09.

Quota, 2026-11-05 (`az cognitiveservices usage list -l swedencentral`): each of the four deployments uses 50 of at least 250 thousand tokens per minute in Global Standard, so a second environment fits.

## Options considered

| Question | Option | Result | Cost |
|---|---|---|---|
| Template | A. Owns everything: Foundry, project, deployments, storage, monitoring, search, registry, app, roles | Rebuild from empty; `azd down` removes all | More Bicep; a second environment to test |
| | B. Keep the split | The app's group only | The rest stays a runbook |
| Page | C. Investigates the development case and injection copies, and challenges, with the app's identity | Agent, screens, search, traces in the cloud | Runtime files, run storage, a paid call per click |
| | D. Live challenges only | One model path | |
| | E. Stored results only | Sign-in and rendering | Nothing for the identity criterion |
| Data | F. One load command: upload, check hashes, build indexes | One step after `azd up` | Needs the operator's local data tree |
| | G. Rerun capture, ingest, extraction | Works from a clean clone | Content Understanding back; re-captured pages may not match frozen hashes; days |
| Demo | H. A screen recording | Strongest single artifact | Not checkable against the repository |
| | I. Screenshots plus each run's trace by query | Every claim has a file or query | No moving picture |

## Decision

A, C, F, and I.

1. **Template.** One `azd` environment builds the Foundry resource (local authentication off) and project, four deployments at pinned versions with upgrade off, storage with shared keys off, Log Analytics and Application Insights, the search service in Switzerland North with local authentication off, the registry, both identities, the Container Apps environment, the app with Entra sign-in, and every role, each naming the call it serves. Content Understanding is out: extraction is finished and loaded.
2. **Page.** With the app's identity, the page investigates the development case and injection copies and challenges any screened result. It refuses scored and sealed cases like the investigate command. On start it downloads the runtime files from Blob Storage, checking each SHA-256 against the load manifest, and writes runs and challenges to a `runs` container, the only one its identity can write.
3. **Provenance.** The image carries its commit, the tree of `src/`, and the Git blob hash of each prompt and registry, written in CI. A page result records them with `"source": "image"`.
4. **Load.** `python -m hindcast.load` uploads every source, refusing one whose SHA-256 differs from its registry entry, uploads the runtime files with their manifest last, and builds the library and injection indexes. It refuses to overwrite a differing blob.
5. **Evidence.** Screenshots of a live investigation, a challenge, and a withheld injection on the deployed page, with each one's trace by query. A recording is optional.
6. **Hand-built resources** stay until teardown and are deleted by hand. The new environment takes its own name.

## Trade-offs

- The rebuild needs the operator's local data tree; a clean clone also needs the capture, ingest, and extraction runbooks and Content Understanding.
- The manifest catches a partial upload, not a writer replacing file and manifest together.
- The `runtime` container holds every case's evidence, readable by the app; no key and no sealed result is in it.
- A click on Investigate is a paid run. One account, one investigation at a time.
- The search service's identity gets Cognitive Services OpenAI User and Cognitive Services User on the Foundry resource, only for the Foundry IQ comparison [decision 0004](0004-retrieval.md) planned.
- After teardown the proof is the worklog.

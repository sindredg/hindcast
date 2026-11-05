# 28. One template for the whole environment, and a page that investigates

Status: Accepted (2026-11-05).

Answers the question [decision 0016](0016-sign-in-credential-image-build-and-resource-group.md) left for the close of milestone 6: whether the template owns the resources built by hand. It also decides what the deployed page runs, how a fresh environment gets its data, and what evidence replaces a recorded demo.

## Context

Foundry, the model deployments, storage, Application Insights, and the search service were built by hand or by a separate template in a resource group `azd` never touched (decision 0016, option F). The `azd` template builds only the app's group. So `azd up` from empty proves the app, not Hindcast.

The deployed page renders stored result files. A challenge runs live only on a developer's machine, with `HINDCAST_CHALLENGE_LIVE=1`. The page calls no model, so "the app reaches every service with its managed identity" has nothing to prove.

The data is local. `build/` and `data/sources/` are not committed, partly because the sources are third-party pages whose licences do not all allow redistribution. Every Azure resource is deleted on 2026-11-09.

Quota read on 2026-11-05 (`az cognitiveservices usage list -l swedencentral`): each of the four model deployments uses 50 of at least 250 thousand tokens per minute in Global Standard, so a second environment fits next to the first.

## Options considered

Template scope:

| Option | What `azd up` proves | Cost |
|---|---|---|
| A. The template owns everything: Foundry, the project, the four deployments, storage, monitoring, search, the registry, the app, and every role | Hindcast can be rebuilt from an empty subscription scope, and `azd down` removes all of it | More Bicep; a second full environment to test it, next to the hand-built one |
| B. Keep decision 0016's split; give the app's identity roles on the hand-built resources | The app's group can be rebuilt | "From empty" covers the app only; the rest stays a runbook of portal and CLI steps |

What the page runs:

| Option | What the page proves | Cost |
|---|---|---|
| C. Investigations of the development case and the injection copies, and challenges, with the app's identity | The product works in the cloud as designed: the agent, the screens, the library search, the traces | The page needs the runtime files and a place to store its runs; a paid call per click |
| D. Live challenges only | One model path in the cloud | The investigation, the screens on case evidence, and the search never run in the cloud |
| E. Stored results only, as now | Sign-in and rendering | The managed-identity criterion has nothing to show |

How a fresh environment gets its data:

| Option | Result | Cost |
|---|---|---|
| F. One load command uploads the local sources, evidence, and library extracts, checks every hash, and builds the indexes | One step after `azd up` | Needs the operator's local data tree |
| G. The capture, ingest, and extraction runbooks, run again | Works from a clean clone | Content Understanding back in the template; re-captured pages may no longer match the frozen keys' hashes; days of steps |

Evidence for the demo criterion:

| Option | Result | Cost |
|---|---|---|
| H. A screen recording | The strongest single artifact | A recording session; nothing in it a reader can check against the repository |
| I. Screenshots from the deployed page plus each run's trace by query, in the worklog | Every claim has a file or a query behind it | No moving picture |

## Decision

A, C, F, and I.

1. **Template.** One `azd` environment builds the Foundry resource (local authentication off) and its project, the four deployments at their pinned versions with automatic upgrade off, storage with shared keys off, Log Analytics and Application Insights, the search service in Switzerland North with local authentication off, the registry, both identities, the Container Apps environment, the app with Entra sign-in, and every role assignment. Each role names the call it serves. Content Understanding is not in the template: extraction is finished, and its outputs are loaded.
2. **Page.** With the app's managed identity, the page investigates the development case and the injection copies, and challenges any screened result. It refuses scored and sealed cases exactly as the investigate command does. On start it downloads the runtime files (evidence, library extracts, the planted pages) from Blob Storage into its own working directory, checking each SHA-256 against the manifest the load command wrote, and writes its runs and challenges to a `runs` container. The app's identity can write to that container only.
3. **Provenance.** The image carries its commit, the tree of `src/`, and the Git blob hash of each prompt and registry, written in CI at build time. A result run from the page records them with `"source": "image"` instead of reading Git.
4. **Load.** `python -m hindcast.load` uploads every case and library source, refusing one whose SHA-256 differs from its registry entry, uploads the runtime files with their manifest last, and builds the library index and the injection index. It refuses to overwrite a blob that differs.
5. **Evidence.** The milestone's demo criterion becomes screenshots from the deployed page of a live investigation, a challenge, and a withheld injection, and each one's trace by query. A recording is optional.
6. **The hand-built resources** stay as they are until teardown and are deleted by hand. The new environment takes a name of its own, so neither template can reach the other's resources.

## Trade-offs

- The rebuild needs the operator's local data tree. A clean clone without it also needs the capture, ingest, and extraction runbooks, and Content Understanding, which this template leaves out.
- The manifest catches a partial or corrupted upload. It does not stop someone with write access to the storage account from replacing a file and its manifest together.
- The `runtime` container holds the evidence of every case, which the app's identity can read, though the page runs only the development case and its copies. The evidence is the providers' public status updates; no answer key and no sealed result is in it.
- A click on Investigate is a paid model run. Sign-in admits one account, and the page runs one investigation at a time.
- The search service's identity gets Cognitive Services OpenAI User and Cognitive Services User on the Foundry resource, only for the Foundry IQ comparison that [decision 0004](0004-retrieval.md) planned: the first for its vectorizer, the second for its query planning. Hindcast's own search embeds its queries in code and does not need it.
- After teardown nothing stays live. The proof is the worklog: the commands, the screenshots, the result files, and the trace queries.

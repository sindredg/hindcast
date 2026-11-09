# OWASP Top 10 for Agentic Applications

OWASP lists ten security risks for AI agents. This page shows where each one applies to Hindcast, what guards against it, and what is still open.

Hindcast's agent only reads: three read-only tools, one outage per run, no actions outside the run. That makes most risks small. The ones that remain are about text: what the agent reads, and what a reader believes.

![Where the OWASP agentic risks sit in Hindcast: status updates, charts, and library postmortems are third-party text; every tool item passes Prompt Shields (ASI01) before the investigator agent reads it through read-only, capped tools (ASI02, ASI05, ASI10). Citation checks flag unsupported items (ASI09); the result file is written once, failed runs too (ASI08). The reader page shows it behind Entra sign-in (ASI09); the challenger agent and the offline judge read the stored result (ASI07, open gaps #109 and #110). The library has an open gap (ASI06, #112). Identity (ASI03, open gap #111) and the supply chain (ASI04) apply across the system.](../diagrams/owasp-agentic.svg)

## Scorecard

| Risk | In plain words | How Hindcast handles it | Status |
|---|---|---|---|
| [ASI01 Agent Goal Hijack](#asi01-agent-goal-hijack) | Text the agent reads tells it to do something else | Every tool result is screened. In planted-instruction tests, none of the 12 runs that saw the instruction followed it | Tested |
| [ASI02 Tool Misuse and Exploitation](#asi02-tool-misuse-and-exploitation) | The agent uses its tools in a harmful way | Three read-only tools, locked to one case, capped at 12 calls and 120 seconds | Tested |
| [ASI03 Identity and Privilege Abuse](#asi03-identity-and-privilege-abuse) | The agent acts with more rights than it needs | Its own managed identity with scoped roles; no service keys except telemetry | Tested, gap [#111](https://github.com/sindredg/hindcast/issues/111) |
| [ASI04 Agentic Supply Chain Vulnerabilities](#asi04-agentic-supply-chain-vulnerabilities) | A package, image, or model is swapped or tampered with | Exact pins with hashes, actions pinned by SHA, model versions pinned, audited in CI | Tested |
| [ASI05 Unexpected Code Execution (RCE)](#asi05-unexpected-code-execution-rce) | Model output gets run as code | Nothing runs model output; it is only parsed as JSON | Tested |
| [ASI06 Memory & Context Poisoning](#asi06-memory--context-poisoning) | Stored or retrieved context is poisoned | No memory between runs; the library is pinned and can never prove a claim alone | Tested, gap [#112](https://github.com/sindredg/hindcast/issues/112) |
| [ASI07 Insecure Inter-Agent Communication](#asi07-insecure-inter-agent-communication) | One agent hands another bad input | The challenger and the judge read the stored answer without a screen | Gaps [#109](https://github.com/sindredg/hindcast/issues/109), [#110](https://github.com/sindredg/hindcast/issues/110) |
| [ASI08 Cascading Failures](#asi08-cascading-failures) | One failure spreads through the system | Any failure stops the run and records why | Tested |
| [ASI09 Human-Agent Trust Exploitation](#asi09-human-agent-trust-exploitation) | A confident answer misleads the reader | Every claim needs a citation; unsupported items are flagged; "cannot tell" is allowed | Tested |
| [ASI10 Rogue Agents](#asi10-rogue-agents) | The agent drifts from its job | One capped, read-only run; nothing it can do outside it | Tested |

**Tested** means a test, CI job, or recorded live run that could fail shows it. Each section below opens to the exact tests and settings.

## Open gaps

| Issue | Gap | Risk |
|---|---|---|
| [#109](https://github.com/sindredg/hindcast/issues/109) | The challenger reads the stored finding without a screen or an integrity check | ASI07 |
| [#110](https://github.com/sindredg/hindcast/issues/110) | The judge reads cited library excerpts without Prompt Shields | ASI07 |
| [#111](https://github.com/sindredg/hindcast/issues/111) | Application Insights accepts key-based ingestion | ASI03 |
| [#112](https://github.com/sindredg/hindcast/issues/112) | A library hit's text is not checked against its pinned extract at query time | ASI06 |

Smaller accepted gaps (no signed manifests, no egress rules, the operator's wider roles) are listed in each section.

## The ten risks

### ASI01 Agent Goal Hijack

A status update, a chart description, or a library page carries an instruction aimed at the investigator: call the outage an attack, leak a code, search for something else.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Every tool item passes Prompt Shields before the model reads it; a flagged item is replaced by a withheld marker and any citation to it is rejected ([decision 0007](../decisions/0007-safety-and-injection.md), [decision 0021](../decisions/0021-screens-pii-and-challenge.md)) | `CaseTools._screen` in [`tools.py`](../../src/hindcast/tools.py); `test_flagged_update_is_withheld_and_the_rest_shown` in [`test_tools.py`](../../tests/test_tools.py); `test_flagged_update_is_withheld_in_the_run_and_its_citation_rejected` and `test_screen_error_ends_run_as_screen_error` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally, with stubs |
| Screens off only for injection copies | `prepare` in [`investigate.py`](../../src/hindcast/investigate.py); `test_screens_off_refused_outside_injection_cases` in [`test_injection.py`](../../tests/test_injection.py) | tested, locally |
| A challenge question is screened as a user prompt; a flagged one gets no model call | `run_challenge` in [`challenge.py`](../../src/hindcast/challenge.py); `test_flagged_question_makes_no_model_call` in [`test_challenge.py`](../../tests/test_challenge.py) | tested, locally, with stubs; live on 2026-11-05: a planted question refused with 0 model calls ([worklog 06](../worklogs/06-deployment.md#slice-2-live-run)) |
| Planted-instruction runs: one instruction in an update, a library section, a library chart, and a case chart; two models; screens on and off | [Injection tests `dev-v1`](../../eval/injection/dev-v1/README.md): 16 live runs on 2026-11-04, 12 pass, 4 not reached, 0 fail | tested, live |
| The prompt is versioned with the agent; a changed prompt is a new agent version | `ensure_agent_version` in [`agent.py`](../../src/hindcast/agent.py); `test_fingerprint_changes_with_the_instructions_and_the_deployment` in [`test_agent.py`](../../tests/test_agent.py) | tested, locally |

**Weak spots.**

- Prompt Shields withheld the planted item in 0 of the 6 screened runs that reached it. The pass rests on the models, not the screen.
- One wording, one run per cell, and the `inject` prefix in the copies' refs is visible to the model ([#69](https://github.com/sindredg/hindcast/issues/69)). The check misses a canary written as a rejected citation ([#82](https://github.com/sindredg/hindcast/issues/82)).
- OWASP's human approval for goal-changing actions (mitigation 2 and 4) has nothing to gate: the agent has no high-impact action.

</details>

### ASI02 Tool Misuse and Exploitation

The tools cannot write or send. Misuse here means reading what the case may not read (its own postmortem, a later document, another case) or burning calls.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Three function tools, strict schemas; `list_updates` and `list_charts` take no arguments, `search_library` takes one query of at most 1,000 characters; anything else is refused | `TOOL_DEFINITIONS`, `MAX_QUERY`, and `CaseTools.call` in [`tools.py`](../../src/hindcast/tools.py); `test_call_refuses_an_unknown_tool_and_arguments` and `test_search_refuses_bad_arguments` in [`test_tools.py`](../../tests/test_tools.py) | tested, locally |
| The case is bound in code, not named by the model; the library filter comes from the case registry and excludes documents published on or after the outage day | the `search_library` binding in `prepare` in [`investigate.py`](../../src/hindcast/investigate.py); `allowed` and the filter in [`search.py`](../../src/hindcast/search.py); `test_allowed_is_the_filter_in_code`, `test_a_document_from_the_start_day_is_not_allowed`, `test_query_never_reaches_the_filter` in [`test_search.py`](../../tests/test_search.py) | tested, locally |
| Every hit is checked again in code; a hit outside the rule raises `LibraryLeak` instead of reaching the model | [`search.py`](../../src/hindcast/search.py); `test_hit_outside_the_filter_raises` and three more in [`test_search.py`](../../tests/test_search.py) | tested, locally |
| The investigator code never opens an answer key or a postmortem | `test_investigator_modules_do_not_import_keys` and `test_investigator_opens_nothing_under_eval_keys_or_a_postmortem` in [`test_boundaries.py`](../../tests/test_boundaries.py) | tested, locally |
| Budgets: 12 tool calls and 120 seconds per investigation, 6 calls and 90 seconds per challenge, no retries inside a run | `TOOL_CAP`, `TIME_CAP` in [`investigate.py`](../../src/hindcast/investigate.py); `CHALLENGE_TOOL_CAP`, `CHALLENGE_TIME_CAP` in [`challenge.py`](../../src/hindcast/challenge.py); `test_thirteenth_tool_call_is_tool_cap`, `test_no_tool_call_starts_after_the_time_cap` in [`test_investigate.py`](../../tests/test_investigate.py); `test_challenge_caps_apply` in [`test_challenge.py`](../../tests/test_challenge.py) | tested, locally |
| Every tool call is recorded in the result file in order, with its masked query, the refs a search showed, and the refs each call withheld | `write_result` in [`investigate.py`](../../src/hindcast/investigate.py); `test_tool_calls_are_recorded_in_order_with_queries_and_refs` and `test_search_queries_are_pii_masked_when_the_run_hits_the_tool_cap` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally |

**Weak spots.** OWASP's sandboxing and egress allowlists (mitigation 3) are not applied as network rules: the tools reach only the endpoints in the configuration, but the container's outbound traffic is not restricted.

</details>

### ASI03 Identity and Privilege Abuse

The deployed page runs the agent as its own user-assigned managed identity. On the command line, the same code runs as the operator's Azure sign-in.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Local auth off on Foundry, Search, and Log Analytics; shared keys and public blob access off on Storage | [`foundry.bicep`](../../infra/modules/foundry.bicep), [`search.bicep`](../../infra/modules/search.bicep), [`monitoring.bicep`](../../infra/modules/monitoring.bicep), [`storage.bicep`](../../infra/modules/storage.bicep); `test_no_service_takes_a_key` in [`test_infra.py`](../../tests/test_infra.py) | tested, template; read live on 2026-11-06 ([worklog 06 review](../worklogs/06-deployment.md#slice-2-independent-review)) |
| Registry admin user off | `adminUserEnabled: false` in [`app.bicep`](../../infra/modules/app.bicep) | configured, not tested |
| The app identity holds data-plane roles to call the models, the screens, and the search; blob read on `runtime` and blob write only on `runs`; Azure AI User on the project, which also lets it create agent versions (`ensure_agent_version`); AcrPull on the registry. A custom role grants exactly the Prompt Shields and PII data actions | [`roles.bicep`](../../infra/modules/roles.bicep), [`app.bicep`](../../infra/modules/app.bicep), the `safetyCaller` role in [`foundry.bicep`](../../infra/modules/foundry.bicep) | configured, not tested by a test; read live on 2026-11-06 ([worklog 06 review](../worklogs/06-deployment.md#slice-2-independent-review)) |
| Result files are written once: uploads use `overwrite=False` and only under the run paths | `store_run` in [`runtime.py`](../../src/hindcast/runtime.py); `test_store_run_refuses_to_overwrite`, `test_store_run_refuses_a_path_outside_the_run_paths` in [`test_runtime.py`](../../tests/test_runtime.py); `test_result_file_is_never_overwritten` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally |
| Entra sign-in on the page, health path excluded | `authConfigs` in [`app.bicep`](../../infra/modules/app.bicep) | tested, live on 2026-11-06: `302`, `401`, `200` ([worklog 06](../worklogs/06-deployment.md#slice-2-rebuild-from-empty)) |
| One allowed user: `allowedPrincipals` names a single object ID | `authConfigs` in [`app.bicep`](../../infra/modules/app.bicep) | configured, not tested: no second account was tried ([worklog 06 gate](../worklogs/06-deployment.md#slice-2-gate)) |
| CI pushes with a federated credential, no stored secret; only the push job gets `id-token: write` | the `image` job in [`ci.yml`](../../.github/workflows/ci.yml), checked by zizmor and actionlint on every pull request | tested as a workflow lint; the push ran live on 2026-11-05 ([worklog 06](../worklogs/06-deployment.md#slice-2-live-run)); the job is skipped while the repository variable `HINDCAST_PUSH_IMAGE` is unset (`gh variable list` empty on 2026-11-09) |

**Weak spots.**

- **accepted gap:** the optional operator roles include Storage Blob Data Contributor on the whole storage account, Search Service Contributor, and Search Index Data Contributor ([`roles.bicep`](../../infra/modules/roles.bicep)), and a command-line run carries those rights. The model cannot reach them: its only actions are the three read-only tools. The operator is a person who loads the data, so the roles stay.
- OWASP's per-action authorization and short-lived task tokens (mitigations 1, 3, 5) are not applied; the managed identity's token lives for its normal lifetime.
- **accepted gap:** Application Insights accepts ingestion with its connection string, which carries the instrumentation key ([`monitoring.bicep`](../../infra/modules/monitoring.bicep) sets no `DisableLocalAuth`; [`app.bicep`](../../infra/modules/app.bicep) passes the string). Anyone holding it can write telemetry ([#111](https://github.com/sindredg/hindcast/issues/111)).

</details>

### ASI04 Agentic Supply Chain Vulnerabilities

Python packages, GitHub Actions, container base images, the model deployments, and the agent's prompt and tool definitions.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Exact package pins, a lock with hashes, `uv sync --locked` in CI, and `pip-audit --strict --require-hashes` | [`pyproject.toml`](../../pyproject.toml), `uv.lock`, the `audit` job in [`ci.yml`](../../.github/workflows/ci.yml) | tested, CI |
| Every action pinned by commit SHA; zizmor and actionlint on the workflow; checkout without stored credentials | [`ci.yml`](../../.github/workflows/ci.yml) | tested, CI |
| Base images pinned by digest; the image runs as UID 10001; hadolint on the Dockerfile; CI pushes the image it tested | [`Dockerfile`](../../Dockerfile); the `infra` and `image` jobs in [`ci.yml`](../../.github/workflows/ci.yml) ([decision 0029](../decisions/0029-push-the-tested-image.md)) | tested, CI |
| Model deployments pinned by version, auto-upgrade off | [`foundry.bicep`](../../infra/modules/foundry.bicep); `test_every_deployment_is_pinned` in [`test_infra.py`](../../tests/test_infra.py) | tested, template |
| The prompt, tools, and schema are in version control; a changed definition gets a new agent version and each result records it | `ensure_agent_version` in [`agent.py`](../../src/hindcast/agent.py); `test_fingerprint_changes_with_the_instructions_and_the_deployment`, `test_prompt_provenance_marks_an_uncommitted_change` in [`test_agent.py`](../../tests/test_agent.py) | tested, locally |
| No MCP server, plug-in, remote prompt, or agent registry | the three tools in [`tools.py`](../../src/hindcast/tools.py) are the whole tool set | tested by `test_definition_offers_the_three_tools` in [`test_agent.py`](../../tests/test_agent.py) |

**Weak spots (accepted gap).** No signed manifests or AI bill of materials, and no kill switch beyond removing the deployment (mitigations 1, 8). Dependabot proposes updates weekly ([`dependabot.yml`](../../.github/dependabot.yml)); the uv version, Python version, actionlint, runner image, and base-image digests move by hand.

</details>

### ASI05 Unexpected Code Execution (RCE)

No tool runs code. Model output is parsed as JSON and validated against a schema, never evaluated.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| No `eval`, `exec`, shell, or deserializer on model output; Ruff's `S` (Bandit) rules fail CI on one | `select` in [`pyproject.toml`](../../pyproject.toml); `ruff check` in [`ci.yml`](../../.github/workflows/ci.yml) | tested, CI |
| Model output is data: strict schema on the service and `jsonschema` locally | `parse_investigation` in [`result.py`](../../src/hindcast/result.py); [`test_result.py`](../../tests/test_result.py) | tested, locally |
| The one model value that names a file, a finding ID, must match a file-safe pattern | `FINDING_ID` in [`result.py`](../../src/hindcast/result.py); `validate` in [`challenge.py`](../../src/hindcast/challenge.py) | tested, locally ([`test_challenge.py`](../../tests/test_challenge.py)) |
| The page renders model text as escaped plain text | [`escape.py`](../../src/hindcast/escape.py); `test_plain_escapes_a_link_and_an_image` in [`test_escape.py`](../../tests/test_escape.py) | tested, locally |
| The container runs as a non-root user | `USER 10001` in [`Dockerfile`](../../Dockerfile); the image check in [`ci.yml`](../../.github/workflows/ci.yml) | tested, CI |

The only `subprocess` calls run `git` with fixed arguments: `_git` in [`provenance.py`](../../src/hindcast/provenance.py) and in [`evaluation/prior.py`](../../src/hindcast/evaluation/prior.py). No model text reaches them.

</details>

### ASI06 Memory & Context Poisoning

No memory carries over between runs: each investigation starts from the same first message. The library of earlier postmortems is the retrieval store, and it is the path a poisoned document would take.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| No cross-run memory: each run starts from `START` with no previous response | `_loop` in [`investigate.py`](../../src/hindcast/investigate.py); `test_tool_calls_are_executed_and_their_outputs_sent_back` in [`test_investigate.py`](../../tests/test_investigate.py) asserts the first turn has no previous response, and `test_agent_turn_references_the_agent_version_and_passes_the_timeout` that such a turn sends no `previous_response_id` | tested, locally |
| The library is curated: each document pinned by SHA-256, dated before every case it serves, and never a case's own source | `load_library` in [`library.py`](../../src/hindcast/library.py); `test_a_date_must_precede_every_served_case`, `test_a_case_postmortem_cannot_be_a_library_document` in [`test_library.py`](../../tests/test_library.py) | tested, locally |
| A library citation alone never supports a claim | `cited` and `backed` in [`result.py`](../../src/hindcast/result.py); `test_library_only_finding_is_unsupported`, `test_library_only_attack_verdict_is_unsupported` in [`test_result.py`](../../tests/test_result.py) | tested, locally |
| A library ref is citable only if a search in this run returned it and it was not withheld | `test_library_citation_from_a_search_is_kept_and_an_unretrieved_one_rejected` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally |
| A run records a digest of every library chunk its filter can reach | `case_chunks` and `contents_digest` in [`search.py`](../../src/hindcast/search.py); `test_contents_digest_changes_with_any_chunk` in [`test_search.py`](../../tests/test_search.py) | tested, locally; the digest is recorded, not compared with an expected value |
| A planted library section was tested live | [Injection tests](../../eval/injection/dev-v1/README.md), library variant: 4 runs, 4 pass | tested, live |

**Weak spot.** The agent's answers are never written back into the library (OWASP mitigation 6), so self-poisoning has no path. Within one run, turns chain by `previous_response_id`, which relies on the Responses service storing the turn server-side.

**accepted gap.** A hit's text is not checked against the pinned extract at query time: the code checks its document, date, and ref, not its content. A chunk rewritten in the index under a valid ref would reach the model, screened only by Prompt Shields ([#112](https://github.com/sindredg/hindcast/issues/112)). Writing the index takes the operator's search roles.

</details>

### ASI07 Insecure Inter-Agent Communication

One agent output feeds another at run time: the challenger reads a stored investigation's finding and the findings it rests on. The judge and the reviewer read run items offline, for scoring only.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| The challenger accepts only a complete, screened result, a file-safe and unique finding ID, and the evidence file whose SHA-256 the result recorded | `validate`, `_findings`, and the evidence check in [`challenge.py`](../../src/hindcast/challenge.py); [`test_challenge.py`](../../tests/test_challenge.py) | tested, locally |
| The challenger's answer goes through its own schema, citation rules, and PII masking | `parse_challenge` in [`result.py`](../../src/hindcast/result.py); [`test_challenge.py`](../../tests/test_challenge.py) | tested, locally |
| The judge's reply is checked by schema and against the code's checks; the reviewer refuses a judgment made on other input | `read_json`, `_check_fits` in [`judge.py`](../../src/hindcast/evaluation/judge.py); `apply_review` in [`reviewer.py`](../../src/hindcast/evaluation/reviewer.py); [`test_judge.py`](../../tests/test_judge.py), [`test_reviewer.py`](../../tests/test_reviewer.py) | tested, locally |
| All calls go over HTTPS to Azure or Anthropic endpoints with token or key authentication; no agent-to-agent protocol, discovery, or registry | [`config.py`](../../src/hindcast/config.py) | configured, not tested |

**Weak spots (accepted gap).**

- The stored finding text reaches the challenger without Prompt Shields, and the result file's own integrity is not checked: a result altered in storage would be read as the investigator wrote it ([#109](https://github.com/sindredg/hindcast/issues/109)). Writing it takes the app identity's write role on the `runs` container or the operator's disk.
- The judge reads third-party evidence excerpts without Prompt Shields; a planted instruction in evidence could steer a score ([#110](https://github.com/sindredg/hindcast/issues/110)).

</details>

### ASI08 Cascading Failures

One agent per run, no delegation, and no agent acts on another's output except the challenger reading a stored result.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Every failure ends the run as `incomplete` with a reason (`time-cap`, `tool-cap`, `model-error`, `screen-error`, `tool-error`, `pii-error`, `empty-result`, `schema`); the model never sees a half answer | `end` inside `_loop` in [`investigate.py`](../../src/hindcast/investigate.py); `test_tool_error_is_incomplete_with_tool_and_message`, `test_schema_failure_is_incomplete_with_the_error`, `test_rate_limit_ends_run_as_model_error` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally |
| No retries inside a run; a batch tries a slot at most three times and stops after two no-results in a row | `max_retries=0` in [`investigate.py`](../../src/hindcast/investigate.py); [`batch.py`](../../src/hindcast/evaluation/batch.py); `test_search_passes_timeout_and_no_retries` in [`test_search.py`](../../tests/test_search.py); [`test_batch.py`](../../tests/test_batch.py) | tested, locally |
| A challenge runs only on a complete result | `_findings` in [`challenge.py`](../../src/hindcast/challenge.py) | tested, locally |

</details>

### ASI09 Human-Agent Trust Exploitation

The reader is the target. A fluent, confident root cause invites trust; the product's job is to show where the evidence stops.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Every citation is resolved against what the run was shown; 11 rejection reasons; a rejected citation is removed and listed, the item stays | `check_citations` in [`result.py`](../../src/hindcast/result.py); `test_bad_citation_is_rejected_with_its_reason` in [`test_result.py`](../../tests/test_result.py) | tested, locally |
| An item with no kept case citation and no supported finding under it is flagged unsupported and stays visible | `backed` in [`result.py`](../../src/hindcast/result.py); `test_attack_without_citation_is_unsupported_not_dropped`, `test_library_citation_with_rests_on_is_supported` in [`test_result.py`](../../tests/test_result.py); [rules](../architecture/investigation-results.md) | tested, locally |
| The attack assessment allows `cannot tell`; the prompt asks for it over a guess | `attack` in the schema in [`result.py`](../../src/hindcast/result.py); [`prompts/investigator.md`](../../prompts/investigator.md) | tested: every showcase run abstained where the evidence could not establish the root cause ([evaluation report](../../eval/reconstruction/showcase-v1/README.md)) |
| A library hit is labelled as a lead to the model and drawn dashed, as a lead, in the evidence graph | `LIBRARY_NOTE` in [`tools.py`](../../src/hindcast/tools.py); `test_search_passes_only_the_query_and_returns_hits_without_scores` in [`test_tools.py`](../../tests/test_tools.py); the graph style in [`views.py`](../../src/hindcast/views.py); `test_evidence_graph_links_claims_to_findings_and_citations` in [`test_views.py`](../../tests/test_views.py) | tested, locally; the graph test checks that amber and `dashed` appear in the graph, not on which node |
| Each result keeps its provenance: agent version, model version, evidence hash, every tool call, usage, and cost | `write_result` in [`investigate.py`](../../src/hindcast/investigate.py); `test_main_writes_the_result_and_prints_counts_never_the_text`, `test_code_provenance_marks_a_change_under_the_code_paths_only` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally |
| Accuracy is measured against the provider's later postmortem, not asserted | [evaluation report](../../eval/reconstruction/showcase-v1/README.md), [sealed report](../../eval/reconstruction/sealed-v1/README.md) | tested, live |

**Weak spots.** No real attack among the cases, so the attack assessment was never shown right on a positive. OWASP's confirmation step for sensitive actions does not apply: the page takes no action on the answer.

</details>

### ASI10 Rogue Agents

An agent that drifts can only produce a wrong answer inside one capped, read-only run, and that answer goes through the same checks.

<details>
<summary>Controls, evidence, and gaps</summary>

| Control | Evidence | Status |
|---|---|---|
| Containment: read-only tools, call and time caps, one page run at a time per process | [ASI02](#asi02-tool-misuse-and-exploitation); `RUN_LOCK` in [`runtime.py`](../../src/hindcast/runtime.py); `test_second_run_is_refused_while_one_runs` in [`test_app.py`](../../tests/test_app.py) | tested, locally |
| Logging: spans for each run, model call, tool call, and PII check, carrying counts and times, never text; screen counts ride on the tool-call span, and a challenge question's screen has its own span; the result file records each tool call | [`telemetry.py`](../../src/hindcast/telemetry.py); `test_spans_carry_no_text` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally; traces read live on 2026-11-06 ([worklog 06](../worklogs/06-deployment.md#slice-2-independent-review)) |
| The page runs only development and injection cases; the command line refuses sealed and revealed cases, which run only through the sealing commands | `LIVE_ROLES` in [`app.py`](../../src/hindcast/app.py); `check_case_allowed` in [`investigate.py`](../../src/hindcast/investigate.py); `test_live_cases_are_development_and_injection_only`, `test_start_run_refuses_a_scored_or_sealed_case` in [`test_app.py`](../../tests/test_app.py); `test_investigate_refuses_a_sealed_case` in [`test_investigate.py`](../../tests/test_investigate.py) | tested, locally |

**Weak spots (accepted gap).** No signed behavioural manifest or attestation per run (OWASP mitigations 5 and 6), and the logs are not tamper-evident: Application Insights and the result files are ordinary stores. With no autonomy past one run, these protect little that the caps and checks do not.

</details>

## About this assessment

| | |
|---|---|
| Framework | [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), Version 2026, December 2025, OWASP GenAI Security Project, Agentic Security Initiative. Licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Entry names are quoted from it; the rest of this page is Hindcast's own text. No newer edition was listed on genai.owasp.org on 2026-11-09. |
| Assessed | The code, tests, and infrastructure template on `main` at `57691f7`, the committed live runs under [`eval/`](../../eval/), and the live checks recorded in the worklogs. Assessed on 2026-11-09. |
| Not assessed | A live system. The Azure environment was removed on 2026-11-07 ([worklog 07](../worklogs/07-close.md)); a live result on this page is the one recorded on its day, not a new check. |
| Labels | **tested**: a test, CI job, or recorded live run that can fail shows it. **configured, not tested**: the setting exists; nothing has shown it holds. **accepted gap**: no control, with the reason. |

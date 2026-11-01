# Sealing: operator procedure

Status: Written on 2026-11-01. Steps 1 to 9 ran on 2026-11-01 with the output shown. [Reveal a seal](#reveal-a-seal) and [Drop a seal](#drop-a-seal) are written, not run: no provider had published a cause for a sealed case by then.

The procedure seals a reconstruction of an outage whose provider has not yet published a cause: it runs the investigator once per deployment, commits the result's SHA-256, and keeps the file in private storage until the postmortem is out ([decision 0017](../decisions/0017-sealed-reconstructions.md)). Each seal makes at most 13 model calls on the deployment it names.

![Sealing a reconstruction: the seal command refuses, before any model call, a case that is not sealed, a case and deployment that already have a seal, or a changed tree; otherwise it investigates once, records an attempt with no model output as no-result, which may be retried up to three attempts in all, and otherwise commits the hash and uploads the file to private storage. If the provider publishes its cause by 2026-11-09, the file is revealed after the rubric is frozen, checked against its hash, and scored; if not, the case is dropped with its record kept](../diagrams/sealing.svg)

## Inputs and access

- The [foundations runbook](foundations.md) completed: `.env` written, with `HINDCAST_CHAT_DEPLOYMENT` (gpt-6-luna) and `HINDCAST_COMPARE_DEPLOYMENT` (gpt-6.1-sol).
- Signed in with `az login` as a user with Foundry User on the project and Storage Blob Data Contributor on the storage account.
- Signed commits, and push access to a branch with an open pull request: the push time is the seal's public timestamp.
- Commands run from the repository root.

## Choose the outages

1. Read the status feeds for incidents that are resolved, have eight or more updates before the resolved one, and harm nobody (the [decision 0001](../decisions/0001-scope.md) rules). Then read each candidate's resolved update.

   ```bash
   curl -s https://www.githubstatus.com/api/v2/incidents/<incident-id>.json | uv run --frozen python -c "import json,sys; i=json.load(sys.stdin)['incident']; print(i['name'], i['status']); [print(u['status'], u['created_at'], u['body'][:200]) for u in i['incident_updates'] if u['status'] in ('resolved','postmortem')]"
   ```

   Use `https://www.cloudflarestatus.com/api/v2/incidents/<incident-id>.json` for Cloudflare. Google Cloud's feed is `https://status.cloud.google.com/incidents.json`; an update that opens with `## Incident Report` or `## Preliminary Incident Report` is a published cause.

   Expected: the resolved update states no cause, and no postmortem entry exists. Observed on 2026-11-01 for GitHub `nms1dpzmh9d9` and `wq8305lppdc2`: "This incident has been resolved. Thank you for your patience and understanding as we addressed this issue. A detailed root cause analysis will be shared as soon as it is available."; for Cloudflare `0eqtn0khkz87`: "This incident has been resolved." Five other October GitHub incidents with eight or more updates, 2026-10-07 among them, already carried GitHub's summary of the cause, and the Google Cloud europe-west2 incident of 2026-10-20 carried its incident report, so none of those is sealable.

## Register the cases

2. Capture each incident.

   ```bash
   PYTHONPATH=src uv run --frozen python -m hindcast.capture status --provider GitHub --incident nms1dpzmh9d9 --out data/sources/github-2026-10-21/github-status-2026-10-21.json
   ```

   Expected: three lines, `url:`, `retrieved_at:`, and `sha256:`. Observed on 2026-11-01: `retrieved_at: "2026-11-01T08:15:51Z"`, `sha256: 3b90d46a…`.

3. Add each case to `data/cases.yaml` with `role: sealed`, the incident's title as the status page shows it, `started_at` as the cut reads it (the earlier of the snapshot's `started_at` and its first update, in UTC to the second; `tests/test_cases.py` fails on a mismatch once the source is local), and one `status-updates` source with the three printed values. Run the registry tests.

   ```bash
   uv run --frozen pytest tests/test_cases.py -q
   ```

   Expected: all pass.

4. Upload each source to Blob Storage under a new name.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "from pathlib import Path; from hindcast.storage import upload_source; c='github-2026-10-21'; f='github-status-2026-10-21.json'; upload_source(c, f, (Path('data/sources')/c/f).read_bytes()); print(c, f, 'uploaded')"
   ```

   Expected: `github-2026-10-21 github-status-2026-10-21.json uploaded`. An existing blob fails with `ResourceExistsError`, and nothing is replaced.

5. Cut the evidence.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence --case github-2026-10-21
   ```

   Expected: the update count including the resolved mark, the resolved time, `dropped 0`, and `blob: uploaded`. Observed on 2026-11-01: 9 updates for `cloudflare-2026-10-20`, 15 for `github-2026-10-21`, 18 for `github-2026-10-22`.

6. Commit the registry. A seal refuses to run while `src/`, `prompts/`, `pyproject.toml`, `uv.lock`, or `data/cases.yaml` differs from the last commit.

   ```bash
   git add data/cases.yaml
   ```

   ```bash
   git commit -m "feat: register <n> outages as sealed cases"
   ```

   Expected: `git status --short -- src prompts pyproject.toml uv.lock data/cases.yaml` prints nothing.

## Seal

7. Seal each case on the investigator deployment.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal run cloudflare-2026-10-20
   ```

   Expected, as observed on 2026-11-01 (the counts and the usage vary per run):

   ```
   complete
   findings 7, timeline events 6, factors 2, open questions 3
   rejected citations 0, unsupported 0
   model calls 2, tool calls 2, seconds 15.661, tokens in 2915 (cached 1049) out 2297
   build/sealed/cloudflare-2026-10-20/20261101T081712Z-v2.json
   sha256 1eaab346304c7de8bb25817a9507de52d7f747f70a1f0a6fa9eba28c42eeec06
   uploaded extracted/sealed/cloudflare-2026-10-20/20261101T081712Z-v2.json
   ```

   The command never prints the investigation, and for an incomplete run it prints only the kind of reason (`schema`, `time-cap`, `tool-cap`, `tool-error`, `empty-result`). If it prints `no-result`, the model produced nothing; run it again, up to three attempts in all. If it prints `upload failed`, the hash is already recorded; upload the same file with `python -m hindcast.seal upload <case_id> <file>`, which checks the file against its hash first.

8. Seal each case with the comparison model in the agent's place.

   ```bash
   HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal run cloudflare-2026-10-20
   ```

   Expected: the same shape. The first run creates agent `hindcast-investigator-gpt-6-1-sol` (Foundry agent names take no dot). Observed on 2026-11-01: six seals, all `complete`, all uploaded.

9. Confirm a second seal is refused.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal run cloudflare-2026-10-20 2>&1 | tail -1
   ```

   Expected, as observed on 2026-11-01: `SealRefused: cloudflare-2026-10-20 is already sealed on gpt-6-luna`, before any cloud call.

10. Commit `eval/sealed/seals.json` and push it the same day. The push time GitHub records is the seal's public timestamp.

    ```bash
    git add eval/sealed/seals.json
    ```

    ```bash
    git commit -m "feat: seal <n> reconstructions"
    ```

    Expected: the branch's pull request shows the commit. Observed on 2026-11-01: pushed at 08:21:55 UTC.

## Reveal a seal

Written, not run.

11. When the provider has published its cause, capture the postmortem, add it to the case as a `postmortem` source, change the role to `showcase`, and draft and freeze its key ([extraction runbook](extraction.md)).

12. After the rubric is frozen (milestone 5), copy the sealed file into the repository and mark its entry in `eval/sealed/seals.json` with `"revealed": true`.

    ```bash
    mkdir -p eval/investigations/<case_id>
    ```

    ```bash
    cp build/sealed/<case_id>/<file> eval/investigations/<case_id>/
    ```

    On another workstation, download it from `extracted/sealed/<case_id>/<file>` instead.

13. Run the reveal check.

    ```bash
    uv run --frozen pytest tests/test_sealed_reveal.py -q
    ```

    Expected (reasoned): `2 passed`. A file that differs from its seal by one byte fails with `<case_id>/<file>: does not match its seal`.

## Drop a seal

Written, not run. A sealed case whose provider has published no cause by 2026-11-09 is dropped.

14. Add `"dropped": true` to each of the case's entries in `eval/sealed/seals.json`, and a comment above the case in `data/cases.yaml` that says it was dropped and when. Keep both: history is not rewritten.

## Remove the agents

15. At teardown, delete the comparison model's agent with the investigator's (investigator runbook, step 6).

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; print(project_client().agents.delete('hindcast-investigator-gpt-6-1-sol'))"
    ```

    Expected (reasoned): `{'object': 'agent.deleted', 'name': 'hindcast-investigator-gpt-6-1-sol', 'deleted': True}`.

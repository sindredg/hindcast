# Sealing: operator procedure

Status: Written on 2026-11-01; the reveal validated on 2026-11-07.

- Steps 1 to 10 ran on 2026-11-01, first series (`library: false`); steps 7 to 10 again on 2026-11-02, second series (`library: true`, [worklog 05](../worklogs/05-sealed-reconstructions.md#second-seals-with-the-library-2026-11-02)); steps 1 to 10 again on 2026-11-04 for two GitHub outages, screens on, four seals `complete` on the first attempt ([worklog 05](../worklogs/05-sealed-reconstructions.md#third-seals-two-github-outages-of-2026-11-04)).
- [Reveal a seal](#reveal-a-seal) ran on 2026-11-07 for `github-2026-11-04-actions`, steps 11 to 24, except step 18 (committed after the reveal; refused since). [Drop a seal](#drop-a-seal) is written, not run: its date is 2026-11-30.
- Since 2026-11-03 a seal runs with Prompt Shields, the PII check, spans, and a cost ([milestone 4, slice 3](../worklogs/04-investigator.md#slice-3-screens-pii-challenge-traces-and-cost)).

One investigator run per deployment, the result's SHA-256 committed, the file in private storage until the postmortem is out ([decision 0017](../decisions/0017-sealed-reconstructions.md)). A seal makes at most 13 model calls plus, in the second series, the calls the [investigator runbook](investigator.md) describes.

![Sealing a reconstruction: the seal command refuses, before any model call, a case that is not sealed, a case and deployment that already have a seal in this series, a changed tree, a seal record that does not extend the committed one, or a library search that does not answer; otherwise it investigates once with the library search, records an attempt with no model output as no-result, which may be retried up to three attempts in all, and otherwise commits the hash and uploads the file to private storage. If the provider publishes its cause by 2026-11-30, the file is revealed after the rubric is frozen, checked against its hash, and scored; if not, the case is dropped with its record kept](../diagrams/sealing.svg)

On this page: [Inputs and access](#inputs-and-access) · [Choose the outages](#choose-the-outages) · [Register the cases](#register-the-cases) · [Seal](#seal) · [Reveal a seal](#reveal-a-seal) · [Drop a seal](#drop-a-seal) · [Remove the agents](#remove-the-agents)

## Inputs and access

- The [foundations runbook](foundations.md) completed: `.env` with `HINDCAST_CHAT_DEPLOYMENT` (gpt-6-luna) and `HINDCAST_COMPARE_DEPLOYMENT` (gpt-6.1-sol); for the second series the [retrieval runbook](retrieval.md) too.
- `az login` with Foundry User on the project and Storage Blob Data Contributor; for the second series also Search Index Data Contributor and Cognitive Services OpenAI User.
- Signed commits and push access to a branch with an open pull request (the push time is the public timestamp).
- Commands run from the repository root.

## Choose the outages

1. Find resolved incidents with eight or more updates before the resolved one that harm nobody ([decision 0001](../decisions/0001-scope.md)); read each resolved update.

   ```bash
   curl -s https://www.githubstatus.com/api/v2/incidents/<incident-id>.json | uv run --frozen python -c "import json,sys; i=json.load(sys.stdin)['incident']; print(i['name'], i['status']); [print(u['status'], u['created_at'], u['body'][:200]) for u in i['incident_updates'] if u['status'] in ('resolved','postmortem')]"
   ```

   Cloudflare: `https://www.cloudflarestatus.com/api/v2/incidents/<incident-id>.json`. Google Cloud: `https://status.cloud.google.com/incidents.json`; an update opening with `## Incident Report` or `## Preliminary Incident Report` is a published cause.

   Expected: the resolved update states no cause, and no postmortem entry exists. Observed on 2026-11-01:

   - GitHub `nms1dpzmh9d9` and `wq8305lppdc2`: "This incident has been resolved. Thank you for your patience and understanding as we addressed this issue. A detailed root cause analysis will be shared as soon as it is available."
   - Cloudflare `0eqtn0khkz87`: "This incident has been resolved."

   Five other October GitHub incidents (2026-10-07 among them) already carried a cause summary, and the Google Cloud europe-west2 incident of 2026-10-20 its incident report: not sealable.

## Register the cases

2. Capture each incident.

   ```bash
   PYTHONPATH=src uv run --frozen python -m hindcast.capture status --provider GitHub --incident nms1dpzmh9d9 --out data/sources/github-2026-10-21/github-status-2026-10-21.json
   ```

   Expected: three lines, `url:`, `retrieved_at:`, and `sha256:`. Observed on 2026-11-01: `retrieved_at: "2026-11-01T08:15:51Z"`, `sha256: 3b90d46a…`.

3. Add each case to `data/cases.yaml`: `role: sealed`, the status page's title, `started_at` (the earlier of the snapshot's `started_at` and its first update, UTC to the second), one `status-updates` source with the three printed values.

   ```bash
   uv run --frozen pytest tests/test_cases.py -q
   ```

   Expected: all pass.

4. Upload each source to Blob Storage under a new name.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "from pathlib import Path; from hindcast.storage import upload_source; c='github-2026-10-21'; f='github-status-2026-10-21.json'; upload_source(c, f, (Path('data/sources')/c/f).read_bytes()); print(c, f, 'uploaded')"
   ```

   Expected: `github-2026-10-21 github-status-2026-10-21.json uploaded`. An existing blob fails with `ResourceExistsError`; nothing is replaced.

5. Cut the evidence.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence --case github-2026-10-21
   ```

   Expected: the update count including the resolved mark, the resolved time, `dropped 0`, and `blob: uploaded`. Observed on 2026-11-01: 9 updates for `cloudflare-2026-10-20`, 15 for `github-2026-10-21`, 18 for `github-2026-10-22`.

6. Commit the registry: a seal refuses uncommitted changes under `src/`, `prompts/`, `pyproject.toml`, `uv.lock`, `data/cases.yaml`, or `data/library.yaml`, and a `seals.json` that does not extend the committed one.

   ```bash
   git add data/cases.yaml
   ```

   ```bash
   git commit -m "feat: register <n> outages as sealed cases"
   ```

   Expected: `git status --short -- src prompts pyproject.toml uv.lock data/cases.yaml data/library.yaml` prints nothing.

## Seal

7. Seal each case on the investigator deployment.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal run cloudflare-2026-10-20
   ```

   Expected, as observed on 2026-11-01 (counts and usage vary per run):

   ```
   complete
   findings 7, timeline events 6, factors 2, open questions 3
   rejected citations 0, unsupported 0
   model calls 2, tool calls 2, seconds 15.661, tokens in 2915 (cached 1049) out 2297
   build/sealed/cloudflare-2026-10-20/20261101T081712Z-v2.json
   sha256 1eaab346304c7de8bb25817a9507de52d7f747f70a1f0a6fa9eba28c42eeec06
   uploaded extracted/sealed/cloudflare-2026-10-20/20261101T081712Z-v2.json
   ```

   For the second series, as observed on 2026-11-02:

   ```
   complete
   findings 6, timeline events 6, factors 2, open questions 3
   rejected citations 0, unsupported 0, searches 1, library citations kept 0
   model calls 3, tool calls 3, seconds 24.617, tokens in 8627 (cached 4633) out 2619
   build/sealed/cloudflare-2026-10-20/20261102T184430Z-v3.json
   sha256 5a492fe38b2bced49a0159ef651f0504c10a1b378db0cfc04a66e7123b9c3e61
   uploaded extracted/sealed/cloudflare-2026-10-20/20261102T184430Z-v3.json
   ```

   While the library search fails, the command refuses before any model call with `SealRefused: the library search did not answer (<error type>); run again later`. One seal per case, deployment, and series. An incomplete run prints only the kind of reason (`schema`, `time-cap`, `tool-cap`, `tool-error`, `screen-error`, `pii-error`, `empty-result`), never the investigation. `no-result`: run again, up to three attempts. `upload failed`: `python -m hindcast.seal upload <case_id> <file>` checks the file against the recorded hash and uploads it, or records an existing blob only when its bytes match (else `upload refused`).

8. Seal each case with the comparison model.

   ```bash
   HINDCAST_CHAT_DEPLOYMENT=gpt-6.1-sol PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal run cloudflare-2026-10-20
   ```

   Expected: the same shape. The first run creates agent `hindcast-investigator-gpt-6-1-sol`. Observed on 2026-11-01: six seals, all `complete`, all uploaded; on 2026-11-02, second series: six more, all `complete` on the first attempt, one search each, all uploaded.

9. Confirm a second seal is refused.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.seal run cloudflare-2026-10-20 2>&1 | tail -1
   ```

   Expected, as observed on 2026-11-01 and on 2026-11-02 for the second series: `SealRefused: cloudflare-2026-10-20 is already sealed on gpt-6-luna`, before any cloud call.

10. Commit `eval/sealed/seals.json` and push it the same day.

    ```bash
    git add eval/sealed/seals.json
    ```

    ```bash
    git commit -m "feat: seal <n> reconstructions"
    ```

    Expected: the pull request shows the commit. Its public time is GitHub's event record, not the commit date:

    ```bash
    gh api repos/<owner>/<repo>/events --jq '.[] | select(.type=="PullRequestEvent" and .payload.action=="opened" and .payload.number==<pr>) | .created_at'
    ```

    Observed on 2026-11-01: pushed at 08:21:55 UTC by the workstation clock; `2026-11-01T08:22:15Z` for #32. GitHub keeps these events for a limited time.

## Reveal a seal

Ran on 2026-11-07 for `github-2026-11-04-actions`, offline except the capture and the Claude API calls ([worklog 05](../worklogs/05-sealed-reconstructions.md#reveal-github-2026-11-04-actions-2026-11-07)). Needs `build/sealed/`, `build/sealed-library/`, `build/evidence/`, and for steps 21 to 23 an Anthropic API key ([evaluation runbook](evaluation.md#inputs-and-access)).

11. Check whether the provider has published a cause. For GitHub or Cloudflare, `<status-host>` is `www.githubstatus.com` or `www.cloudflarestatus.com`:

    ```bash
    curl -s https://<status-host>/api/v2/incidents/<incident_id>.json | python3 -I -c "import json,sys; u=[u for u in json.load(sys.stdin)['incident']['incident_updates'] if u['status']=='resolved'][0]; print(u['updated_at'], len(u['body'].split()), 'words')"
    ```

    Expected: the update's `updated_at` and its length. The placeholder ("A detailed root cause analysis will be shared as soon as it is available") is 31 words; a cause summary runs well over 100. Also check the provider's blog. Observed on 2026-11-07 for `xr3myzj7ms51`: `2026-11-07T01:04:38.642Z 249 words`.

12. Capture the postmortem under a new name (for a status snapshot):

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.capture status --provider GitHub --incident <incident_id> --out data/sources/<case_id>/<summary-file>.json
    ```

    Expected: `url:`, `retrieved_at:`, and `sha256:`. Observed: `retrieved_at: "2026-11-07T10:22:42Z"`, `sha256: 76af8617…`. The `status-updates` source stays as sealed.

13. In `data/cases.yaml`, add the capture as a `postmortem` source, set `role: revealed` ([decision 0030](../decisions/0030-close-evaluation-with-sealed-addenda.md)), and comment when the cause was published.

    ```bash
    uv run --frozen pytest tests/test_cases.py -q
    ```

    Expected: all pass.

14. Draft the key by hand in `build/keys/<case_id>-draft.json` ([fields](../../eval/keys/README.md#fields)), each item quoting the postmortem, and check it:

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.keys check <case_id>
    ```

    Expected: `<case_id>: 0 problems; sheet build/keys/<case_id>-review.md`. A quote off by one word is listed, exit 1. A person reviews the sheet.

15. Freeze the reviewed key.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.keys freeze <case_id>
    ```

    Expected: `<case_id>: frozen, sha256 <hash>`. Observed: `4d3d4633…`.

16. Draft the labels in `build/labels/<case_id>-draft.json` ([decision 0023](../decisions/0023-abstention-and-inferable-labels.md)), write the sheet, approve each label, freeze.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.labels sheet <case_id>
    ```

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.labels freeze <case_id>
    ```

    Expected: `<n> labels; sheet build/labels/<case_id>.md`, then `frozen <case_id> <hash>`. Observed: 11 labels, `57274146…`.

17. Run the leak check against the snapshot, then with a planted chunk.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.leak <case_id> --snapshot build/sealed-library/<case_id>.json
    ```

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.leak <case_id> --snapshot build/sealed-library/<case_id>.json --plant
    ```

    Expected: `0 hits`, then `1 hits` naming the planted chunk. Observed: `14 unstated items, 8 evidence sources, 267 library chunks, 0 hits`; with `--plant`, `root_cause in planted: 15 shared 8-word runs`.

18. Commit the registry, the key, and the labels; the reveal refuses uncommitted changes under `src/`, `data/cases.yaml`, `eval/keys/`, or `eval/sealed/` and records the commit in `reveals.json`.

19. Reveal.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.reveal <case_id>
    ```

    Expected: the publication time, the leak check's counts, and `revealed <n> files`. The command rechecks steps 13 to 17 and refuses before reading a sealed file if one fails or the cause predates a seal. Observed at 10:30:54Z: `cause published 2026-11-07T01:04:38Z`, `revealed 2 files`.

20. Run the reveal check, then commit `eval/investigations/<case_id>/`, `eval/sealed/seals.json`, `eval/sealed/reveals.json`, and `eval/reconstruction/sealed-v1/attempts.json`.

    ```bash
    uv run --frozen pytest tests/test_sealed_reveal.py -q
    ```

    Expected: `4 passed`. A file one byte off its seal fails with `<case_id>/<file>: does not match its seal`.

21. Judge the revealed runs (one Claude API call each).

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge run --root eval/reconstruction/sealed-v1
    ```

    Expected: `judged <n>, errors 0, kept <k>`; runs judged before are kept. Observed: `judged 2, errors 0, kept 0`.

22. Have the reviewer judge them again, and apply its decisions.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.reviewer run --root eval/reconstruction/sealed-v1
    ```

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.reviewer apply --root eval/reconstruction/sealed-v1
    ```

    Expected: `runs: judged <n>, errors 0`, then `runs <n>, decisions <d>, missing 0`. Observed: 2 runs, 22 decisions.

23. Score, and price the Claude calls.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.score --root eval/reconstruction/sealed-v1
    ```

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.spend --sealed
    ```

    Expected: `open review items 0` and `eval/reconstruction/sealed-v1/scores.json: <n> runs`, then a line per stage and `eval/reconstruction/sealed-v1/spend.json: written`. Observed: 2 runs; USD 0.17 and 0.56, total USD 0.73.

24. Add the case as an addendum to the [sealed report](../../eval/reconstruction/sealed-v1/README.md) and commit `eval/reconstruction/sealed-v1/`.

## Drop a seal

Written, not run. No published cause by 2026-11-30: dropped ([decision 0022](../decisions/0022-sealed-drop-date-and-offline-reveal.md)).

25. Add `"dropped": true` to the case's entries in `eval/sealed/seals.json` and a dated comment above the case in `data/cases.yaml`. Keep both.

## Remove the agents

26. At teardown, delete the comparison model's agent with the investigator's (investigator runbook, step 6).

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "from hindcast.models import project_client; print(project_client().agents.delete('hindcast-investigator-gpt-6-1-sol'))"
    ```

    Expected (reasoned): `{'object': 'agent.deleted', 'name': 'hindcast-investigator-gpt-6-1-sol', 'deleted': True}`.

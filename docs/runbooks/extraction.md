# Extraction: operator procedure

Status: Written on 2026-10-27 for [milestone 2](../worklogs/02-extraction.md). Every step ran on 2026-10-27 with the output shown, except where an "Expected:" line is marked as reasoned.

The procedure turns the captured sources into the case evidence, the library extracts, and the answer keys. Content Understanding needs a role on the Foundry resource only while it runs; the last section removes it.

## Inputs and access

- The [foundations runbook](foundations.md) completed: the cases captured, their sources in Blob Storage under `sources/<case_id>/`, and `.env` written.
- Signed in with `az login` as a user with Storage Blob Data Contributor on the storage account and the right to assign roles on the Foundry resource (Owner or User Access Administrator).
- A browser, for the Cloudflare Radar charts.
- Commands run from the repository root. Local values are set once:

```bash
export RG=<resource-group> RESOURCE=<foundry-resource>
```

## Set up Content Understanding

1. Assign Content Understanding Contributor on the Foundry resource to yourself.

   ```bash
   RES_ID=$(az cognitiveservices account show -g "$RG" -n "$RESOURCE" --query id -o tsv)
   ME=$(az ad signed-in-user show --query id -o tsv)
   az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
     --role "Cognitive Services Content Understanding Contributor" --scope "$RES_ID" -o none
   ```

   Expected: no output. Within a few minutes, step 3 can read the service.

2. Deploy the embedding model the document analyzers require, pinned, with automatic upgrade off.

   ```bash
   az rest --method put \
     --url "https://management.azure.com${RES_ID}/deployments/text-embedding-3-large?api-version=2026-09-01" \
     --body '{"sku": {"name": "GlobalStandard", "capacity": 50}, "properties": {"model": {"format": "OpenAI", "name": "text-embedding-3-large", "version": "1"}, "versionUpgradeOption": "NoAutoUpgrade"}}' \
     --query "{state:properties.provisioningState, upgrade:properties.versionUpgradeOption}" -o tsv
   ```

   Expected: `Succeeded	NoAutoUpgrade` (observed as JSON on 2026-10-27). The Azure CLI's `deployment create` cannot set the upgrade option, hence the REST call.

3. Map the models Content Understanding uses to the deployments, and create the three analyzers from [`analyzers/`](../../analyzers/).

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "
   from hindcast.extract import cu_client, ensure_analyzers
   print(cu_client().update_defaults(model_deployments={'gpt-5-mini': 'gpt-5-mini', 'text-embedding-3-large': 'text-embedding-3-large'}).as_dict())
   print('created:', ensure_analyzers())
   print('created:', ensure_analyzers())"
   ```

   Expected: the two mappings, then `created: ['hindcast_postmortem', 'hindcast_chart', 'hindcast_answer_key']` (reasoned: on 2026-10-27 they were created in three runs while the setup was worked out), then `created: []`. `AnalyzerDiffers` means an analyzer in the service differs from its file: recreate it with `hindcast.extract.replace_analyzer("<analyzer_id>")`.

## Describe the charts

4. Download the Radar views in a browser. Radar refuses scripted requests and serves whole UTC days. Open each page, check the chart for any label that names a cause, and download it as PNG into the path shown.

   | Page | Chart | Save as |
   |---|---|---|
   | `https://radar.cloudflare.com/traffic?dateStart=2025-11-18&dateEnd=2025-11-18` | HTTP traffic worldwide | `data/charts/cloudflare-2025-11-18/radar-http-traffic.png` |
   | `https://radar.cloudflare.com/routing/as13335?dateStart=2026-02-20&dateEnd=2026-02-20` | Announced IP address space, IPv4 | `data/charts/cloudflare-2026-02-20/radar-announced-ipv4.png` |
   | same page | BGP announcements | `data/charts/cloudflare-2026-02-20/radar-bgp-announcements.png` |

   The images are committed; on a rebuild they are already there. A new download hashes differently and needs a new registry entry.

5. Check the chart files against the registry.

   ```bash
   PYTHONPATH=src uv run --frozen python -c "
   from pathlib import Path
   from hindcast.cases import load_cases, verify_local_files
   for case in load_cases().values():
       print(case.case_id, verify_local_files(case, Path('data/charts'), kinds=frozenset({'chart'})))"
   ```

   Expected: each case followed by `[]`.

6. Describe each chart once.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest charts
   ```

   Expected: three lines `<case_id>: <doc_id> described`, each followed by `  blob: uploaded` on a first run and `  blob: reused` after. A first run also prints its usage (three charts: 3,000 contextualization tokens).

## Cut the case evidence

7. Run the cut's tests.

   ```bash
   uv run --frozen pytest -q tests/test_evidence.py tests/test_storage.py tests/test_ingest.py
   ```

   Expected: `34 passed`.

8. Ingest every case's evidence from Blob Storage, with the chart descriptions attached.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence; echo "exit $?"
   ```

   Expected:

   ```
   cloudflare-2025-11-18: 22 updates (resolved 2025-11-18T19:28:36Z), dropped 0
     blob: unchanged
   cloudflare-2026-02-20: 10 updates (resolved 2026-02-20T23:50:58Z), dropped 0
     blob: unchanged
   github-2026-08-17: 36 updates (resolved 2026-08-17T21:15:46Z), dropped 0
     blob: unchanged
   google-cloud-2026-07-14: 9 updates (resolved 2026-07-15T05:34:26Z), dropped 2
     report: 2
     blob: unchanged
   exit 0
   ```

   On a first run each case reads `blob: uploaded` (reasoned). `<case_id>: chart <doc_id> has no stored description; run ingest charts first` means step 6 has not run. `<case_id>: evidence in Blob Storage differs; pass --replace to overwrite` means the rules, the sources, or the charts changed; pass `--replace` only then. A line `<case_id>: <doc_id>: downloaded bytes do not match the registry` means the blob is not the captured source, and nothing is written for that case.

9. Check that the Blob copies equal the local ones and that no resolved text was kept.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "
   import json, pathlib
   from hindcast.storage import container
   c = container('extracted')
   for p in sorted(pathlib.Path('build/evidence').glob('*.json')):
       d = json.loads(p.read_bytes())
       print(p.stem, c.download_blob(f'evidence/{p.name}').readall() == p.read_bytes(), d['updates'][-1]['text'], len(d['charts']))"
   ```

   Expected: `True None 1` for `cloudflare-2025-11-18`, `True None 2` for `cloudflare-2026-02-20`, and `True None 0` for the other two.

## Capture the library

10. Check the registry. The picks follow [decision 0013](../decisions/0013-library-selection.md) and are listed in [`data/library.yaml`](../../data/library.yaml).

    ```bash
    uv run --frozen pytest -q tests/test_library.py
    ```

    Expected: `14 passed`. Without the captured status snapshots under `data/sources/`, the quote check is skipped (`13 passed, 1 skipped`, reasoned).

11. Capture each page, unless it is already under `data/sources/library/`.

    ```bash
    PYTHONPATH=src uv run --frozen python -c "
    import subprocess, sys
    from pathlib import Path
    from hindcast.cases import load_cases
    from hindcast.library import load_library
    for d in load_library(Path('data/library.yaml'), load_cases()).values():
        out = Path('data/sources/library') / d.filename
        if not out.exists():
            subprocess.run([sys.executable, '-m', 'hindcast.capture', 'page', '--url', d.url, '--out', str(out)], check=True)
        print(d.doc_id, d.sha256 == __import__('hashlib').sha256(out.read_bytes()).hexdigest())"
    ```

    Expected: one line per document ending in `True`. A page captured again later hashes differently (pages change), and that document cannot be used until it is captured, hashed, and picked again.

12. Upload the pages to Blob Storage. An existing blob is never overwritten.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "
    from pathlib import Path
    from azure.core.exceptions import ResourceExistsError
    from hindcast.cases import load_cases
    from hindcast.library import load_library
    from hindcast.storage import upload_source
    for d in load_library(Path('data/library.yaml'), load_cases()).values():
        try:
            upload_source('library', d.filename, (Path('data/sources/library') / d.filename).read_bytes()); print(d.doc_id, 'uploaded')
        except ResourceExistsError:
            print(d.doc_id, 'already there')"
    ```

    Expected: one line per document, `uploaded` on a first run and `already there` after.

## Extract the library

13. Extract every library page.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest library; echo "exit $?"
    ```

    Expected: one line per document, `<doc_id>: <n> sections, <m> figures, dropped 0`, followed by `  blob: reused` when the extract is already in Blob Storage, then `exit 0`. A first extraction prints `  blob: uploaded` and a `usage:` line; on 2026-10-27 the whole library took 118 minimal pages, 189,000 contextualization tokens, and about 131,000 gpt-5-mini input and 23,000 output tokens. The final library has 176 sections and 65 figures. A page whose title, date, or body its site's rule cannot find is listed with the reason, and the run exits 1.

14. Check the extracts for text that must not be there: a case's report, a case's date, or a byline.

    ```bash
    grep -l -i -E 'availability report: August 2026|2025-11-18|November 18, 2025|18 November 2025|2026-02-20|February 20, 2026|20 February 2026|2026-07-14|July 14, 2026|14 July 2026|2026-08-17|August 17, 2026|17 August 2026' build/extracted/library/*.json; grep -l -i 'written by\|author-bio' build/extracted/library/*.json
    ```

    Expected: no file from the first search, and only `build/extracted/library/cloudflare-2019-07-02.json` from the second, whose text says "code written by customers".

## Draft, review, and freeze the answer keys

15. Draft the four keys.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.keys draft
    ```

    Expected: one line per case with its counts and problems, then `  blob: uploaded` on a first run or `  blob: reused` after, and the stored analysis's `usage:` line either way (together 24 minimal pages). An existing draft is kept: `<case_id>: a draft exists and may hold review edits; kept`. The drafts and review sheets are in `build/keys/`, which Git ignores.

16. Review each sheet against its postmortem, linked at the top of the sheet. Correct the draft in `build/keys/<case_id>-draft.json`: values, missing items, times in UTC, and `stated_during_incident` for what a status update already said. The fields and rules are in the [keys README](../../eval/keys/README.md). The prior-knowledge answers stay unopened.

17. Freeze each reviewed key.

    ```bash
    PYTHONPATH=src uv run --frozen python -m hindcast.keys freeze <case_id>
    ```

    Expected: `<case_id>: frozen, sha256 <hash>`. A second freeze of the same case prints `<case_id>: eval/keys/<case_id>.json is frozen already; a new key needs a new review` and exits 1.

18. Check the frozen keys.

    ```bash
    uv run --frozen pytest -q tests/test_keys.py
    ```

    Expected: `20 passed` with the captured postmortems under `data/sources/` (`19 passed, 1 skipped` without them).

## Remove the Content Understanding role

19. Remove the role and list what is left.

    ```bash
    az role assignment delete --assignee "$ME" --role "Cognitive Services Content Understanding Contributor" --scope "$RES_ID"
    az role assignment list --assignee "$ME" --all --query "[].roleDefinitionName" -o tsv | sort
    ```

    Expected: `Foundry User`, `Owner`, and `Storage Blob Data Contributor`, plus any roles held for other projects.

20. Repeat a Content Understanding read until it is refused. The removal takes about 11 minutes to reach the endpoint.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "
    from hindcast.extract import cu_client
    try:
        cu_client().get_analyzer('hindcast_chart'); print('still allowed')
    except Exception as e:
        print(type(e).__name__, str(e).splitlines()[0][:120])"
    ```

    Expected: `still allowed` for a while, then `ClientAuthenticationError (PermissionDenied) The principal ... lacks the required data action ...analyzers/read`.

21. Check that model calls through the project still work on the project-scope role.

    ```bash
    PYTHONPATH=src uv run --frozen --env-file .env python -c "
    from hindcast.models import ask_model
    print(ask_model('gpt-6-luna', 'Answer in one word.', 'Name the colour of a clear daytime sky.'))"
    ```

    Expected: a one-word answer with its usage, such as `('Blue', TokenUsage(input_tokens=24, cached_input_tokens=0, output_tokens=18))`.

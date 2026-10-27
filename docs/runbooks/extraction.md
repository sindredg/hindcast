# Extraction: operator procedure

Status: Written on 2026-10-27 for [milestone 2](../worklogs/02-extraction.md), evidence part. Every step ran on 2026-10-27 with the output shown, except the `blob: uploaded` line, which is marked as reasoned. The library, extraction, chart, and answer-key steps are added when they are built.

## Inputs and access

- The [foundations runbook](foundations.md) completed: the cases captured, their sources in Blob Storage under `sources/<case_id>/`, and `.env` written.
- Signed in with `az login` as a user with Storage Blob Data Contributor on the storage account.
- Commands run from the repository root.

## Cut the case evidence

1. Run the cut's tests.

   ```bash
   uv run --frozen pytest -q tests/test_evidence.py tests/test_storage.py tests/test_ingest.py
   ```

   Expected: `25 passed`.

2. Ingest every case's evidence from Blob Storage.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence
   ```

   Expected:

   ```
   cloudflare-2025-11-18: 22 updates (resolved 2025-11-18T19:28:36Z), dropped 0
   cloudflare-2026-02-20: 10 updates (resolved 2026-02-20T23:50:58Z), dropped 0
   github-2026-08-17: 36 updates (resolved 2026-08-17T21:15:46Z), dropped 0
   google-cloud-2026-07-14: 9 updates (resolved 2026-07-15T05:34:26Z), dropped 2
     report: 2
   ```

   On a first run each case is followed by `  blob: uploaded` (reasoned from the code and its tests; the run on 2026-10-27 printed the counts before that line existed). A line `<case_id>: <doc_id>: downloaded bytes do not match the registry` means the blob is not the captured source: nothing is written for that case.

3. Run it again to show that existing evidence is kept.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.ingest evidence; echo "exit $?"
   ```

   Expected: the same counts, each case followed by `  blob: unchanged`, then `exit 0`. Evidence that differs from what is in Blob Storage prints `<case_id>: evidence in Blob Storage differs; pass --replace to overwrite` and the run exits 1. Pass `--replace` only after a change to the cut rules or the sources. On a new workstation, this step also writes `build/evidence/` from identical evidence.

4. Check that the Blob copies equal the local ones and that no resolved text was kept.

   ```bash
   PYTHONPATH=src uv run --frozen --env-file .env python -c "
   import json, pathlib
   from hindcast.storage import container
   c = container('extracted')
   for p in sorted(pathlib.Path('build/evidence').glob('*.json')):
       d = json.loads(p.read_bytes())
       print(p.stem, c.download_blob(f'evidence/{p.name}').readall() == p.read_bytes(), d['updates'][-1]['text'])"
   ```

   Expected: one line per case ending in `True None`.

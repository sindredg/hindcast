# Milestone 2: Extraction

Status: Open. The evidence cut and ingestion from Blob Storage were built on 2026-10-27; the library, its extraction, the charts, and the answer keys follow. The milestone state is in the [roadmap](../roadmap.md).

## Scope

Cut each case's status updates into evidence, extract the postmortem library and the answer keys, and describe the charts ([roadmap](../roadmap.md#2-extraction)). The procedure to rebuild it is the [runbook](../runbooks/extraction.md).

## Work completed

### Settings per component

`hindcast.config` loads one section per component (models, storage, extraction, search) instead of every variable at once, so the `.env` the foundations runbook writes, with search and embedding still empty, loads for everything milestone 2 runs. `hindcast.models` now reads its endpoint through the model section. This closes [#3](https://github.com/sindredg/hindcast/issues/3). Tested locally: `tests/test_config.py`, 9 tests, which failed on the missing names before the code existed. Live, 2026-10-27: one `ask_model` call on gpt-6-luna through the project answered after the change.

### Evidence cut

`hindcast.evidence` applies [decision 0005](../decisions/0005-evidence-library-and-answer-key.md) per status format:

| Format | Kept | Resolved mark | Report entries | Unknown |
|---|---|---|---|---|
| Statuspage (Cloudflare, GitHub) | `investigating`, `identified`, `monitoring`, `update` | first `resolved`: time and status, text withheld | `postmortem` | any other status |
| Google Cloud feed entry | `SERVICE_DISRUPTION`, `SERVICE_OUTAGE`, `SERVICE_INFORMATION` | first `AVAILABLE` | any update that opens with a Markdown heading | any other status |

Everything after the resolved mark is dropped as well. Dropped entries are listed with time, status, and reason, never with their text. Times are normalised to UTC and sorted.

Tested locally: `tests/test_evidence.py`, 14 tests. The first 11 ran first against a missing module; the 3 added after the code review below failed on the code before its fix. They include a planted report entry for each format (a `postmortem` update on a Statuspage incident and a `## Mini Incident Report` update before Google's `AVAILABLE`), an unknown status, updates after the first resolved one, mixed time formats out of order, updates in the same second given newest first, an update tied with the resolved mark, a time without a zone, and an incident that never resolved.

The model re-check's dataset builder now calls the same cut. Rebuilt on 2026-10-27, the dataset file is byte for byte the one the evaluation runs used (`cmp` equal, SHA-256 starting `b76a883bd24595a5`), and `check_quotes.py` still finds 6 of 6 quotes in each committed run.

### Blob access from code

`hindcast.storage` reads and writes Blob Storage with `DefaultAzureCredential`. A download is refused unless its SHA-256 matches the registry; an upload never overwrites unless asked. `azure-storage-blob` 12.31.0, the newest stable release on PyPI (released 2026-09-30), is now a direct dependency; it was already in the locked tree through `azure-ai-projects`, so the lock gained no package. `pip-audit --strict --disable-pip --require-hashes` on the exported lock: no known vulnerabilities.

Tested locally: `tests/test_storage.py`, 5 tests with a fake container. Live, 2026-10-27: the development case's status snapshot downloaded from Blob Storage with the Azure CLI sign-in (12,241 bytes, the size of the local copy); the same call with one character of the pinned hash changed raised `SourceMismatch: cloudflare-status-2026-02-20: downloaded bytes do not match the registry`.

### Ingestion

`python -m hindcast.ingest evidence` downloads each case's snapshot, cuts it, and writes the evidence to `build/evidence/` and Blob `extracted/evidence/`. Tested locally: `tests/test_ingest.py`, 6 tests, including that a source failing its hash writes nothing anywhere, that identical evidence already in Blob Storage only writes the local copy, that different evidence is kept and reported, and that one failing case does not stop the others. Live, 2026-10-27, first run:

```
cloudflare-2025-11-18: 22 updates (resolved 2025-11-18T19:28:36Z), dropped 0
cloudflare-2026-02-20: 10 updates (resolved 2026-02-20T23:50:58Z), dropped 0
github-2026-08-17: 36 updates (resolved 2026-08-17T21:15:46Z), dropped 0
google-cloud-2026-07-14: 9 updates (resolved 2026-07-15T05:34:26Z), dropped 2
  report: 2
```

These were the counts expected from the snapshots' structure before the run (update statuses and times, no text). A second run without `--replace` refused all four uploads and exited 1. Each Blob copy equals its local file, every resolved update's text is `null`, and the Google evidence contains no "Incident Report" heading.

After the code review, existing evidence is compared instead of refused. Live, 2026-10-27, with `build/evidence/` moved away: each case reported the same counts and `blob: unchanged`, exit 0, and the four local files were rebuilt byte for byte as before. The cut fix left the four cases' evidence and the dataset hash unchanged.

## Gate

| Criterion | Status | Evidence |
|---|---|---|
| Ingestion reads the sources from Blob Storage with an Entra token | Tested live | The ingestion run above read all four snapshots from Blob Storage with the Azure CLI sign-in's token; a changed hash is refused (`SourceMismatch`, live) |
| The evidence cut, tested per provider with fixed inputs including a planted report entry | Tested locally and live | `tests/test_evidence.py` (14 tests; 11 run first against a missing module, 3 failing on the code before the review fix); live counts above |
| Library postmortems extracted into sections with publish dates; charts described with their source | Open | Follows in the second pull request of this milestone |
| Answer keys extracted, reviewed by a person, and frozen by hash | Open | Follows in the second pull request |
| A third-party chart is shown only under a licence that allows it | Open | Follows in the second pull request |

## Independent review

Open for the milestone; it runs when the second pull request is done.

### Code review of the first pull request

A separate agent reviewed the first pull request read-only on 2026-10-27, against the plan, decision 0005, and the project rules. Each finding was checked again before it was acted on; none was rejected. Fixed in that pull request:

- The cut sorted on times truncated to the second, and providers list updates newest first, so an update posted after the resolved one in the same second was kept with its text. Updates now sort at full precision, and on an exact tie the resolved mark goes first.
- A time without a zone was read as the machine's local time; it is now refused.
- A second workstation with an empty `build/` could not get the evidence without overwriting Blob Storage; identical evidence now writes the local copy.
- A refused cut or a missing blob stopped the whole run; each case now fails on its own.
- A test that matched the case ID too loosely, and two test counts in this worklog.

## Deviations from the plan

- The model re-check scripts that import the dataset builder now import `hindcast`, which is not installed as a package, so their commands in the [foundations runbook](../runbooks/foundations.md#re-check-the-model-choice) gained `PYTHONPATH=src`.

## Follow-up

None new.

## Not verified

- A Statuspage incident with an `update` or `postmortem` status in a real capture: none of the four cases has one, so those rules are tested only on hand-made input.

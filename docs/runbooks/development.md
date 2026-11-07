# Local development

Status: Written on 2026-11-05. The commands are the ones [ci.yml](../../.github/workflows/ci.yml) runs; not validated as a separate procedure.

Requires [uv](https://docs.astral.sh/uv/), which installs the Python version in `.python-version` and the locked tools. The workflow also lints the YAML, audits the dependencies, and builds the image ([ci.yml](../../.github/workflows/ci.yml)).

```bash
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
for f in infra/main.bicep; do az bicep build --file "$f" --stdout > /dev/null && az bicep lint --file "$f"; done
```

The page runs locally with `PYTHONPATH=src uv run --frozen streamlit run src/hindcast/app.py` (the code is not an installed package). Without a connection string it sends no telemetry. With `HINDCAST_LIVE=1` and the `.env` settings, the page investigates the development case and its injection copies, and each finding of a screened result gets a challenge box, with the developer's sign-in. `python -m hindcast.challenge <result file> <finding id> "<question>"` does the same.

hadolint and shellcheck run in CI from their pinned releases; the Dockerfile builds there, since the image is pushed from `main` by the workflow.

Tests that read the captured status pages and postmortems skip when `data/sources/` is absent, as in CI. The [runbooks](../../docs/runbooks/) capture them.

Copy `.env.example` to `.env` and fill in the endpoints. Azure calls use `DefaultAzureCredential`. The judge and reviewer use an Anthropic API key ([evaluation runbook](evaluation.md)).


[Back to the README](../../README.md#development)

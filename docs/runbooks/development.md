# Local development

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the locked tools. These are the checks CI runs on the code; the workflow also lints the YAML, audits the dependencies, and builds the image ([ci.yml](../../.github/workflows/ci.yml)).

```bash
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
for f in infra/main.bicep infra/search.bicep; do az bicep build --file "$f" --stdout > /dev/null && az bicep lint --file "$f"; done
```

The page runs locally with `PYTHONPATH=src uv run --frozen streamlit run src/hindcast/app.py`; the code is not an installed package, so it needs the path. Without a connection string it sends no telemetry. With `HINDCAST_CHALLENGE_LIVE=1` and the `.env` settings, each finding of a screened result gets a box that challenges it with the developer's sign-in. The command `python -m hindcast.challenge <result file> <finding id> "<question>"` does the same.

hadolint and shellcheck run in CI from their pinned releases; the Dockerfile builds there, since the image is pushed from `main` by the workflow, not from a workstation.

The tests that read the captured status pages and postmortems skip when `data/sources/` is absent, which includes CI. The [runbooks](../../docs/runbooks/) capture them.

Copy `.env.example` to `.env` and fill in the endpoints. Azure service calls use `DefaultAzureCredential`. The evaluation judge and reviewer use an Anthropic API key; see the [evaluation runbook](evaluation.md).


[Back to the README](../../README.md#development)

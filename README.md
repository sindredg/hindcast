# Hindcast

Evidence-grounded AI investigations of infrastructure outages.

Given only what an outside engineer could see while an outage was happening, Hindcast reconstructs it: whether it was an attack, a timeline, the most likely root cause, the contributing factors, and the questions the evidence leaves open. Every item cites what it rests on. The provider's own postmortem, published later, is the answer key the reconstruction is scored against; Hindcast never sees it.

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the locked tools.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen pytest
```

Copy `.env.example` to `.env` and fill in the endpoints. No keys: the code signs in with `DefaultAzureCredential`.

## License

[MIT](LICENSE). Status pages and postmortems belong to their publishers and are not redistributed here.

# The web page's image. Built in CI (the registry's remote build is not
# available to this subscription) and pulled by the container app's identity.
# Both base images are pinned by digest; Dependabot does not track them, so
# they move by hand with a check of the publisher's current digest.

# uv 0.13.5, the version pyproject.toml requires. Digest read 2026-10-30.
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

# python:3.14-slim-trixie, pushed 2026-10-28. Digest read 2026-10-30.
FROM python:3.14-slim-trixie@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, on their own layer: a code change does not reinstall
# them. --no-install-project because the project is not a package
# (pyproject.toml: package = false); the code is on PYTHONPATH instead.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra app --no-install-project

# The code and the committed results the page shows.
COPY src ./src
COPY eval/investigations ./eval/investigations
# What a live run reads besides build/ (decision 0028): the prompts, the
# registries, the price table, the injection inputs, and the rubric lock the
# scored-case refusal checks.
COPY prompts ./prompts
COPY data/cases.yaml data/library.yaml data/prices.yaml ./data/
COPY data/injection ./data/injection
COPY eval/rubric ./eval/rubric
# Written in CI by python -m hindcast.provenance before the build: the commit,
# the src/ tree, and the prompts' and registries' blob hashes, since the image
# has no .git. The build fails without it.
COPY provenance.json ./provenance.json

# A fixed UID so the container never runs as root. USER takes the number, not
# the name, so the platform can resolve it without the image's passwd file.
# /app stays owned by root, so the runtime user cannot change its own code or
# the committed results. It owns build/, which takes the runtime files and the
# page's runs, and each case's challenges/ directory under eval/investigations,
# so a challenge of a committed result can be written next to it. The case
# directories stay root's: the owner of a directory can remove or replace any
# file in it, whoever owns the file.
RUN useradd --create-home --uid 10001 app \
    && mkdir build \
    && chown 10001 build \
    && find eval/investigations -mindepth 1 -maxdepth 1 -type d -exec mkdir -p {}/challenges \; \
    && find eval/investigations -mindepth 2 -maxdepth 2 -type d -name challenges -exec chown 10001 {} +
USER 10001

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src \
    HOME=/home/app \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# No HEALTHCHECK: Container Apps probes /_stcore/health itself (infra/app.bicep).
CMD ["streamlit", "run", "src/hindcast/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]

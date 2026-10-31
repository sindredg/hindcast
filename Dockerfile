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

# The code and the one result the page shows.
COPY src ./src
COPY eval/investigations ./eval/investigations

# A fixed UID so the container never runs as root. USER takes the number, not
# the name, so the platform can resolve it without the image's passwd file.
# /app stays owned by root: the page only reads it, and the runtime user
# cannot change its own code.
RUN useradd --create-home --uid 10001 app
USER 10001

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src \
    HOME=/home/app \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# No HEALTHCHECK: Container Apps probes /_stcore/health itself (infra/app.bicep).
CMD ["streamlit", "run", "src/hindcast/app.py", "--server.port", "8502", "--server.address", "0.0.0.0"]

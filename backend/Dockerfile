# syntax=docker/dockerfile:1
#
# The Compass API in one image, one process (the agent's per-session workers and locks live in
# memory, so --workers 1). The build context is backend/ alone: no Node and no UI, which is
# deployed separately (a Render static site, frontend/), so the image serves the API only. No secret
# is ever in the image: the API key and the tokens come from the environment at run time
# (docker-compose.yml: `env_file: backend/.env` for live, demo mode needs none). CI builds this
# image and checks it (scripts/check_image_secrets.py).
#
#   docker build -t compass backend                 (PowerShell, from the repo root)

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.9.13

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- 1. Python dependencies from the lockfile, and the generated data -------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS app
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# dependencies first (a cached layer while only the code changes)
COPY pyproject.toml uv.lock ./
# build_ca (optional): extra CA certificates for a TLS-inspecting network (see docker-compose.yml).
# A build secret, so it is used for the download only and never stored in a layer.
RUN --mount=type=secret,id=build_ca,required=false <<'SH'
set -e
if grep -qs "BEGIN CERTIFICATE" /run/secrets/build_ca; then
  cat /etc/ssl/certs/ca-certificates.crt /run/secrets/build_ca > /tmp/ca.pem
  export SSL_CERT_FILE=/tmp/ca.pem
fi
uv sync --frozen --no-dev --no-install-project
rm -f /tmp/ca.pem
SH
COPY compass/ compass/
COPY scripts/ scripts/
COPY raw/ raw/
COPY data/ data/
# the project itself, editable: compass.config resolves data/ from /app. Then the data scripts,
# in the order `tasks.py data` runs them (tasks.py is at the repo root, outside this context).
RUN uv sync --frozen --no-dev \
    && /app/.venv/bin/python scripts/build_vehicles_db.py \
    && /app/.venv/bin/python scripts/extract_excel.py

# --- 2. the runtime image ---------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm
# gosu: the entrypoint drops from root to the app user with it (docker/entrypoint.sh)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && gosu nobody true
RUN groupadd --system --gid 10001 compass \
    && useradd --system --uid 10001 --gid compass --home-dir /app --no-create-home compass \
    && mkdir /data \
    && chown compass:compass /data
WORKDIR /app
COPY --from=app /app/.venv /app/.venv
COPY --from=app /app/compass /app/compass
COPY --from=app /app/data /app/data
# what judges mode's stats tiles read (compass/api/stats.py)
COPY evals/report.md evals/spend.jsonl /app/evals/
COPY tests/counts.json /app/tests/counts.json

# Sessions live in /data, never in data/ (which holds only the read-only rules, catalog and
# vehicles database). /data is a plain directory owned by the app user unless something is
# mounted there (docker-compose.yml mounts a named volume; Render's free plan mounts nothing,
# so the sessions last until the container restarts). No UI build in the image: API only.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COMPASS_APP_DB=/data/app.db \
    COMPASS_DEMO_DB=/data/demo.db \
    COMPASS_ENV_ONLY=1
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh
# No USER: the entrypoint starts as root only to chown the /data mount, then runs the server as
# `compass` (uid 10001) via gosu. The health check runs as `compass` too.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["gosu", "compass", "python", "-c", "import os, sys, urllib.request; sys.exit(urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT') or 8000}/api/health\", timeout=4).status != 200)"]

# $PORT when the host sets one (Render does), else 8000. One worker, always (see the top).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn compass.api.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1"]

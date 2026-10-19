# syntax=docker/dockerfile:1
#
# Compass in one image: the API and the built UI, one process (the agent's per-session workers
# and locks live in memory, so --workers 1). No secret is ever in the image: the API key and the
# tokens come from the environment at run time (docker-compose.yml: `env_file: .env` for live,
# demo mode needs none). CI builds this image and checks it (scripts/check_image_secrets.py).
#
#   docker compose --profile demo up --build     (PowerShell, from the repo root)

ARG NODE_VERSION=22.19.0
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.9.13

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- 1. the UI: web/dist ----------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
# build_ca (optional): extra CA certificates for a TLS-inspecting network (see docker-compose.yml).
# A build secret, so it is used for the download only and never stored in a layer.
RUN --mount=type=secret,id=build_ca,required=false <<'SH'
set -e
if grep -qs "BEGIN CERTIFICATE" /run/secrets/build_ca; then
  export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca
fi
npm ci --no-audit --no-fund
SH
COPY web/ ./
RUN npm run build

# --- 2. Python dependencies from the lockfile, and the generated data -------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS app
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# dependencies first (a cached layer while only the code changes)
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca,required=false <<'SH'
set -e
if grep -qs "BEGIN CERTIFICATE" /run/secrets/build_ca; then
  cat /etc/ssl/certs/ca-certificates.crt /run/secrets/build_ca > /tmp/ca.pem
  export SSL_CERT_FILE=/tmp/ca.pem
fi
uv sync --frozen --no-dev --no-install-project
rm -f /tmp/ca.pem
SH
COPY README.md tasks.py ./
COPY compass/ compass/
COPY scripts/ scripts/
COPY raw/ raw/
COPY data/ data/
# the project itself, editable: compass.config resolves data/ and web/ from /app
RUN uv sync --frozen --no-dev \
    && /app/.venv/bin/python tasks.py data

# --- 3. the runtime image ---------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm
RUN groupadd --system --gid 10001 compass \
    && useradd --system --uid 10001 --gid compass --home-dir /app --no-create-home compass \
    && mkdir /data \
    && chown compass:compass /data
WORKDIR /app
COPY --from=app /app/.venv /app/.venv
COPY --from=app /app/compass /app/compass
COPY --from=app /app/data /app/data
COPY --from=web /web/dist /app/web/dist
# what judges mode's stats tiles read (compass/api/stats.py)
COPY evals/report.md evals/spend.jsonl /app/evals/
COPY tests/counts.json /app/tests/counts.json

# Sessions live on the /data volume, never in the image (data/ holds only the read-only rules,
# catalog and vehicles database).
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COMPASS_APP_DB=/data/app.db \
    COMPASS_DEMO_DB=/data/demo.db \
    COMPASS_WEB_DIST=/app/web/dist \
    COMPASS_ENV_ONLY=1
USER compass
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import os, sys, urllib.request; sys.exit(urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT') or 8000}/api/health\", timeout=4).status != 200)"]

# $PORT when the host sets one (Render does), else 8000. One worker, always (see the top).
CMD ["sh", "-c", "exec uvicorn compass.api.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1"]

# Compass

Compass is a Hebrew chat assistant for Strauss Group employees. It answers one question:
*"If I switch company car, go electric, or give up the car, how will my monthly net
salary change?"*

**Core principle:** every number shown to a user comes from deterministic code that reads
versioned data files. The same inputs and the same rules always give the same output. Rules
live in config, not in code, so a pilot replaces data files, not code.

Built for the "קוד פתוח" AI Hackathon 2026 (final: Wed 21/10/2026).

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). These commands work on Windows, macOS and Linux:

```sh
uv run python tasks.py install   # create .venv with Python 3.12 and sync uv.lock
uv run python tasks.py data      # rebuild all generated data from raw/ (needs the raw files)
uv run python tasks.py test      # run the tests
uv run python tasks.py lint      # ruff check + ruff format --check
uv run python tasks.py fmt       # apply formatting
```

If you have `make`, `make install|data|test|lint|fmt` does the same.

The raw challenge files are not committed. Put them in `raw/` under the names listed in
[raw/README.md](raw/README.md).

## Project layout

```
compass/        Python package
  config.py     paths, resolved relative to the repo root
  data/         read-only data-access layer
data/           generated + curated data (committed, except *.db)
raw/            raw challenge inputs (git-ignored, except raw/README.md)
scripts/        one-off ETL scripts that turn raw/ into data/
tests/          pytest suite (+ fixtures/)
tasks.py        cross-platform task runner
```

Planned layers, not built yet: `compass/engine/` (deterministic net calculation),
`compass/agent/` (Claude tool-use loop), `api/` (FastAPI + SSE), `web/` (React).

## Data sources

See [raw/README.md](raw/README.md) for the file list, original filenames and checksums.

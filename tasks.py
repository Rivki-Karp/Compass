"""Cross-platform task runner (Windows / macOS / Linux).

Usage:
    uv run python tasks.py install   # sync dependencies (uv.lock)
    uv run python tasks.py data      # rebuild all generated data from raw/
    uv run python tasks.py test      # run the test suite
    uv run python tasks.py lint      # ruff check + ruff format --check
    uv run python tasks.py fmt       # apply ruff formatting and safe fixes
    uv run python tasks.py demo E-001  # Hebrew net breakdown of a golden reference employee
    uv run python tasks.py calc      # interactive calculator: your own profile and scenarios
    uv run python tasks.py serve     # API on http://127.0.0.1:8000 (docs at /docs), auto-reload
    uv run python tasks.py chat      # terminal chat with the agent (ANTHROPIC_API_KEY in .env)
    uv run python tasks.py eval      # agent evals against the real model -> evals/report.md
    uv run python tasks.py eval --only walkthrough,e001_rep_flow --repeat 3 --effort medium
    uv run python tasks.py openapi   # write openapi.json (commit it with API changes)
    uv run python tasks.py ts-types  # write web/src/api/generated.ts (commit it with view changes)
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent

# Order matters: later scripts may read outputs of earlier ones.
DATA_SCRIPTS: list[str] = [
    "scripts/build_vehicles_db.py",
    "scripts/extract_excel.py",
]


def run(*args: str) -> None:
    print("$", " ".join(args), flush=True)
    result = subprocess.run(args, cwd=REPO_ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def install() -> None:
    run("uv", "sync")


def data() -> None:
    for script in DATA_SCRIPTS:
        run(sys.executable, str(REPO_ROOT / script))


def test() -> None:
    run(sys.executable, "-m", "pytest")


def lint() -> None:
    run(sys.executable, "-m", "ruff", "check", ".")
    run(sys.executable, "-m", "ruff", "format", "--check", ".")


def fmt() -> None:
    run(sys.executable, "-m", "ruff", "check", "--fix", ".")
    run(sys.executable, "-m", "ruff", "format", ".")


def demo(*args: str) -> None:
    run(sys.executable, "-m", "compass.demo", *args)


def calc() -> None:
    run(sys.executable, "-m", "compass.calc")


def serve() -> None:
    # One process: the agent's per-session workers and locks live in memory.
    run(
        sys.executable,
        "-m",
        "uvicorn",
        "compass.api.main:app",
        "--reload",
        "--workers",
        "1",
        "--port",
        "8000",
    )


def chat() -> None:
    run(sys.executable, "-m", "compass.agent.chat")


def evals(*args: str) -> None:
    run(sys.executable, "-m", "evals", *args)


def openapi() -> None:
    run(sys.executable, "-m", "compass.api.openapi")


def ts_types() -> None:
    run(sys.executable, "-m", "compass.api.ts_types")


TASKS: dict[str, Callable[..., None]] = {
    "install": install,
    "data": data,
    "test": test,
    "lint": lint,
    "fmt": fmt,
    "demo": demo,
    "calc": calc,
    "serve": serve,
    "openapi": openapi,
    "ts-types": ts_types,
    "chat": chat,
    "eval": evals,
}
TAKES_ARGS: set[str] = {"demo", "eval"}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else None
    if name not in TASKS or (len(sys.argv) > 2 and name not in TAKES_ARGS):
        print(__doc__)
        sys.exit(2)
    TASKS[name](*sys.argv[2:])


if __name__ == "__main__":
    main()

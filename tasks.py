"""Cross-platform task runner (Windows / macOS / Linux).

Usage:
    uv run python tasks.py install   # sync dependencies (uv.lock)
    uv run python tasks.py data      # rebuild all generated data from raw/
    uv run python tasks.py test      # run the test suite
    uv run python tasks.py lint      # ruff check + ruff format --check
    uv run python tasks.py fmt       # apply ruff formatting and safe fixes
    uv run python tasks.py demo E-001  # Hebrew net breakdown of a golden reference employee
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


TASKS: dict[str, Callable[..., None]] = {
    "install": install,
    "data": data,
    "test": test,
    "lint": lint,
    "fmt": fmt,
    "demo": demo,
}
TAKES_ARGS: set[str] = {"demo"}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else None
    if name not in TASKS or (len(sys.argv) > 2 and name not in TAKES_ARGS):
        print(__doc__)
        sys.exit(2)
    TASKS[name](*sys.argv[2:])


if __name__ == "__main__":
    main()

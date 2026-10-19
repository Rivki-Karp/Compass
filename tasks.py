"""Cross-platform task runner (Windows / macOS / Linux).

Usage:
    uv run python tasks.py install   # sync dependencies (uv.lock)
    uv run python tasks.py data      # rebuild all generated data from raw/
    uv run python tasks.py test      # run the test suite
    uv run python tasks.py lint      # ruff check + ruff format --check
    uv run python tasks.py fmt       # apply ruff formatting and safe fixes
    uv run python tasks.py demo      # THE demo: reset, build if needed, serve on :8000 (no key)
    uv run python tasks.py demo E-001  # Hebrew net breakdown of a golden reference employee
    uv run python tasks.py calc      # interactive calculator: your own profile and scenarios
    uv run python tasks.py serve     # API on http://127.0.0.1:8000 (docs at /docs), auto-reload
    uv run python tasks.py demo-reset  # wipe demo mode's database (data/demo.db), never app.db
    uv run python tasks.py build-web # build the UI (web/dist); `serve` then serves it at /
    uv run python tasks.py web       # dev: API :8000 + Vite http://localhost:5173 (Ctrl+C: both)
    uv run python tasks.py chat      # terminal chat with the agent (ANTHROPIC_API_KEY in .env)
    uv run python tasks.py eval      # agent evals against the real model -> evals/report.md
    uv run python tasks.py eval --only walkthrough,e001_rep_flow --repeat 3 --effort medium
    uv run python tasks.py openapi   # write openapi.json (commit it with API changes)
    uv run python tasks.py ts-types  # write web/src/api/generated.ts (commit it with view changes)
    uv run python tasks.py test-counts  # write tests/counts.json (judges mode; pytest checks it)
    uv run python tasks.py record-demo  # the backup video -> docs/video/*.webm (demo mode, no key)
    uv run python tasks.py readme    # regenerate README.md's results block (pytest checks it)
    uv run python tasks.py smoke --url https://compass.onrender.com  # check a deployed server
"""

import subprocess
import sys
import time
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
    """No arguments: the demo (see demo_app). With an employee id: the terminal breakdown."""
    if args:
        run(sys.executable, "-m", "compass.demo", *args)
    else:
        demo_app()


DEMO_TOKENS = {"COMPASS_REP_TOKEN": "rep-demo", "COMPASS_ADMIN_TOKEN": "admin-demo"}


def demo_app() -> None:
    """One command for the demo: demo mode (the scripted model; no API key, no network), an
    empty demo database, the UI built if web/dist is missing or older than its sources, then the
    API and the UI on http://127.0.0.1:8000 until Ctrl+C."""
    import os

    from compass.api.settings import _env

    os.environ["COMPASS_LLM"] = "scripted"
    configured = _env(REPO_ROOT / ".env")
    tokens: dict[str, str] = {}
    for name, default in DEMO_TOKENS.items():
        if configured.get(name):
            tokens[name] = f"from .env / the environment ({name})"
        else:
            os.environ[name] = default
            tokens[name] = default
    _print_token_warnings()
    demo_reset()
    if _web_build_is_stale():
        build_web()
    else:
        print("web/dist is up to date")
    print(
        "\nCompass demo (demo mode: scripted model, no API key, no network)\n"
        "  employee:       http://127.0.0.1:8000/\n"
        "  representative: http://127.0.0.1:8000/rep   token: "
        f"{tokens['COMPASS_REP_TOKEN']}\n"
        "  judges mode:    the toggle on the employee screen   token: "
        f"{tokens['COMPASS_ADMIN_TOKEN']}\n"
        "  API docs:       http://127.0.0.1:8000/docs\n"
        "Ctrl+C stops it.\n",
        flush=True,
    )
    # No --reload: a demo runs what was built and started, nothing changes under it.
    run(sys.executable, "-m", "uvicorn", "compass.api.main:app", "--workers", "1", "--port", "8000")


WEB_SOURCES = ("src", "public", "index.html", "package.json", "package-lock.json", "vite.config.ts")


def _web_build_is_stale() -> bool:
    """Whether web/dist is missing, or older than any file the build reads."""
    index = WEB / "dist" / "index.html"
    if not index.is_file():
        return True
    built = index.stat().st_mtime
    for name in WEB_SOURCES:
        path = WEB / name
        files = path.rglob("*") if path.is_dir() else [path]
        if any(f.is_file() and f.stat().st_mtime > built for f in files):
            return True
    return False


def calc() -> None:
    run(sys.executable, "-m", "compass.calc")


def _print_token_warnings() -> None:
    """An empty rep or admin token (in .env or the environment): say which screen won't work.
    Never prints a token's value."""
    from compass.api.settings import token_warnings_from_env

    for warning in token_warnings_from_env(REPO_ROOT / ".env"):
        print(f"WARNING: {warning}", flush=True)


def serve() -> None:
    from compass.api.settings import Settings, live_token_errors, live_token_message

    errors = live_token_errors(Settings.from_env(REPO_ROOT / ".env"))
    if errors:  # the server would refuse anyway; say it before uvicorn's reloader starts
        sys.exit(live_token_message(errors))
    _print_token_warnings()
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


NPM = "npm.cmd" if sys.platform == "win32" else "npm"
WEB = REPO_ROOT / "web"


def build_web() -> None:
    """Build the UI into web/dist (`npm ci` first when web/node_modules is missing). The API
    serves it at / with an SPA fallback: one URL, http://127.0.0.1:8000."""
    if not (WEB / "node_modules").is_dir():
        run_in(WEB, NPM, "ci")
    run_in(WEB, NPM, "run", "build")
    print("built web/dist: `uv run python tasks.py serve`, then open http://127.0.0.1:8000")


def web() -> None:
    """Development: the API (auto-reload) and Vite (hot reload, proxies /api to the API).
    Ctrl+C stops both, child processes included."""
    if not (WEB / "node_modules").is_dir():
        run_in(WEB, NPM, "ci")
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "compass.api.main:app",
            "--reload",
            "--workers",
            "1",
            "--port",
            "8000",
        ],
        cwd=REPO_ROOT,
    )
    vite = subprocess.Popen([NPM, "run", "dev"], cwd=WEB)
    print("API http://127.0.0.1:8000 · UI http://localhost:5173 · Ctrl+C stops both", flush=True)
    try:
        while api.poll() is None and vite.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (vite, api):
            _stop(process)


def _stop(process: subprocess.Popen[bytes]) -> None:
    """Stop a process and its children (on Windows, npm leaves node running otherwise)."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def run_in(cwd: Path, *args: str) -> None:
    print(f"$ ({cwd.name})", " ".join(args), flush=True)
    result = subprocess.run(args, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def demo_reset() -> None:
    """Demo mode (COMPASS_LLM=scripted) keeps its sessions and tickets in its own database
    (data/demo.db, or COMPASS_DEMO_DB); delete it so the next demo starts empty. Never app.db."""
    from compass.api.settings import SettingsError, demo_db_from_env

    try:
        target = demo_db_from_env()
    except SettingsError as error:
        sys.exit(f"demo-reset: {error}")
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = target.with_name(target.name + suffix)
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            sys.exit(f"demo-reset: {path} is in use. Stop the demo API, then run this again.")
    print(f"demo-reset: cleared {target} (the next demo run starts with an empty one)")


def readme() -> None:
    run(sys.executable, "-m", "compass.readme_numbers")


def record_demo() -> None:
    """The backup demo video, recorded by Playwright at human pace (scripts/record_demo.py)."""
    if _web_build_is_stale():
        build_web()
    run(sys.executable, str(REPO_ROOT / "scripts" / "record_demo.py"))


def chat() -> None:
    run(sys.executable, "-m", "compass.agent.chat")


def evals(*args: str) -> None:
    run(sys.executable, "-m", "evals", *args)


def openapi() -> None:
    run(sys.executable, "-m", "compass.api.openapi")


def ts_types() -> None:
    run(sys.executable, "-m", "compass.api.ts_types")


def test_counts() -> None:
    """Count the pytest and vitest tests and write tests/counts.json, which judges mode shows."""
    import datetime
    import json
    import re
    import subprocess

    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout
    found = re.search(r"(\d+) tests? collected", collected)
    if found is None:
        sys.exit(f"test-counts: unexpected pytest output:\n{collected[-500:]}")
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    report = REPO_ROOT / "web" / "node_modules" / ".vitest-counts.json"
    subprocess.run(
        [npx, "vitest", "run", "--reporter=json", f"--outputFile={report}"],
        capture_output=True,
        check=True,
        cwd=REPO_ROOT / "web",
    )
    listed = subprocess.run(
        [npx, "playwright", "test", "--list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        cwd=REPO_ROOT / "web",
    ).stdout
    e2e = re.search(r"Total: (\d+) tests? in", listed)
    if e2e is None:
        sys.exit(f"test-counts: unexpected playwright output:\n{listed[-500:]}")
    counts = {
        "pytest": int(found.group(1)),
        "vitest": json.loads(report.read_text(encoding="utf-8"))["numTotalTests"],
        "e2e": int(e2e.group(1)),
        "as_of": datetime.date.today().isoformat(),
    }
    path = REPO_ROOT / "tests" / "counts.json"
    path.write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"tests/counts.json: {counts}")


SMOKE_TIMEOUT_SECONDS = 30


def smoke(*args: str) -> None:
    """Check a running server from outside: /api/health answers ok, a session opens, and its
    event stream delivers its first event. Sends no token and prints no secret: only statuses,
    the model mode and the event's type. Exits non-zero on the first failure."""
    import argparse
    import json
    import urllib.error
    import urllib.request

    parser = argparse.ArgumentParser(prog="tasks.py smoke")
    parser.add_argument("--url", required=True, help="the server's base URL")
    base = parser.parse_args(args).url.rstrip("/")

    def fail(step: str, error: object) -> None:
        sys.exit(f"smoke: FAIL at {step}: {error}")

    def call(method: str, path: str) -> tuple[int, dict[str, object]]:
        request = urllib.request.Request(f"{base}{path}", method=method)
        with urllib.request.urlopen(request, timeout=SMOKE_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())

    try:
        status, health = call("GET", "/api/health")
        if status != 200 or health.get("ok") is not True:
            fail("health", f"status {status}")
        print(f"health: ok (llm: {health.get('llm')})")

        status, session = call("POST", "/api/sessions")
        session_id = str(session.get("id", ""))
        if status != 201 or not session_id:
            fail("open a session", f"status {status}")
        print("session: opened")

        request = urllib.request.Request(
            f"{base}/api/sessions/{session_id}/events", headers={"Accept": "text/event-stream"}
        )
        with urllib.request.urlopen(request, timeout=SMOKE_TIMEOUT_SECONDS) as stream:
            kind = stream.headers.get("Content-Type", "")
            if not kind.startswith("text/event-stream"):
                fail("event stream", f"content type {kind!r}")
            event: str | None = None
            for raw in stream:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                elif not line and event:
                    break  # the end of the first event
            if not event:
                fail("event stream", "the stream ended before any event")
            print(f"event stream: first event {event!r}")
            print(f"  Cache-Control: {stream.headers.get('Cache-Control')}")
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        fail("request", error)
    print("smoke: OK")


TASKS: dict[str, Callable[..., None]] = {
    "install": install,
    "data": data,
    "test": test,
    "lint": lint,
    "fmt": fmt,
    "demo": demo,
    "calc": calc,
    "serve": serve,
    "demo-reset": demo_reset,
    "build-web": build_web,
    "web": web,
    "openapi": openapi,
    "ts-types": ts_types,
    "test-counts": test_counts,
    "record-demo": record_demo,
    "readme": readme,
    "chat": chat,
    "eval": evals,
    "smoke": smoke,
}
TAKES_ARGS: set[str] = {"demo", "eval", "smoke"}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else None
    if name not in TASKS or (len(sys.argv) > 2 and name not in TAKES_ARGS):
        print(__doc__)
        sys.exit(2)
    TASKS[name](*sys.argv[2:])


if __name__ == "__main__":
    main()

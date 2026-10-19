"""Record the backup demo video (Day 5 Stage 6): `uv run python tasks.py record-demo`.

1. Seeds the guard-rejection session into a fresh demo database: the walkthrough with a first
   draft that says +2,915, which the real guard rejects (scripts/web_fixtures.py,
   guard_retry_steps; the same fixture judges mode is tested on).
2. Serves that database in demo mode (scripted model, no key, no network) on its own port.
3. Runs the Playwright recorder (web/record/, not part of the test suite) at human pace, 1440x900:
   docs/video/compass-demo-employee.webm and docs/video/compass-demo-rep.webm.
4. Converts both to mp4 when ffmpeg is on PATH, and prints the sizes.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from fastapi.testclient import TestClient

from compass.agent.demo_llm import WALKTHROUGH
from compass.agent.factory import build_claude_runner
from compass.agent.llm import ScriptedClient
from compass.api import Settings, create_app
from compass.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from web_fixtures import guard_retry_steps  # noqa: E402

PORT = 8777
TOKENS = {"COMPASS_REP_TOKEN": "rep-demo", "COMPASS_ADMIN_TOKEN": "admin-demo"}
VIDEO_DIR = REPO_ROOT / "docs" / "video"
VIDEOS = ("compass-demo-employee", "compass-demo-rep")
NPX = "npx.cmd" if sys.platform == "win32" else "npx"
MAX_COMMIT_MB = 25


def seed_guard_session(db: Path) -> str:
    """The walkthrough with a rejected first draft of its last reply, in `db`; its session id."""
    settings = Settings(app_db=db, llm="scripted")
    app = create_app(
        settings,
        agent_factory=lambda s, services, tools: build_claude_runner(
            s, services, llm=ScriptedClient(guard_retry_steps()), tool_runner=tools
        ),
    )
    with TestClient(app) as client:
        sid = client.post("/api/sessions").json()["id"]
        for text in WALKTHROUGH.employee_messages:
            client.post(f"/api/sessions/{sid}/messages", json={"text": text})
            assert app.state.agent.wait_idle(30)
        actions = [
            e.payload["action"]
            for e in app.state.services.store.events_after(sid)
            if e.type == "guard_check"
        ]
    assert actions == ["accept", "retry", "accept_after_retry"], actions
    return str(sid)


def wait_healthy(url: str, server: subprocess.Popen[bytes], seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if server.poll() is not None:
            sys.exit("record-demo: the demo server exited")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    sys.exit(f"record-demo: {url} did not answer in {seconds:.0f} s")


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def to_mp4() -> None:
    ffmpeg = shutil.which("ffmpeg")
    for name in VIDEOS:
        source, target = VIDEO_DIR / f"{name}.webm", VIDEO_DIR / f"{name}.mp4"
        command = [
            "ffmpeg", "-y", "-i", str(source), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(target),
        ]  # fmt: skip
        if ffmpeg:
            subprocess.run(command, check=True, capture_output=True)
            print(f"  {target.relative_to(REPO_ROOT)}")
    if not ffmpeg:
        print("ffmpeg is not on PATH; to make mp4 files later (PowerShell, from the repo root):")
        for name in VIDEOS:
            print(
                f"  ffmpeg -i docs\\video\\{name}.webm -c:v libx264 -pix_fmt yuv420p "
                f"-movflags +faststart docs\\video\\{name}.mp4"
            )


def main() -> int:
    if not (REPO_ROOT / "web" / "dist" / "index.html").is_file():
        sys.exit("record-demo: build the UI first (uv run python tasks.py build-web)")
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "record-demo.db"
        guard_sid = seed_guard_session(db)
        print(f"seeded the guard-rejection session {guard_sid}")

        env = {
            **os.environ,
            "COMPASS_LLM": "scripted",
            "COMPASS_DEMO_DB": str(db),
            "COMPASS_WEB_DIST": str(REPO_ROOT / "web" / "dist"),
            **TOKENS,
        }
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "compass.api.main:app", "--workers", "1",
             "--port", str(PORT)],
            cwd=REPO_ROOT,
            env=env,
        )  # fmt: skip
        try:
            base = f"http://127.0.0.1:{PORT}"
            wait_healthy(f"{base}/api/health", server)
            VIDEO_DIR.mkdir(parents=True, exist_ok=True)
            recorder = subprocess.run(
                [NPX, "playwright", "test", "--config", "record/record.config.ts"],
                cwd=REPO_ROOT / "web",
                env={
                    **os.environ,
                    "RECORD_BASE_URL": base,
                    "RECORD_GUARD_SESSION": guard_sid,
                    "RECORD_OUT": str(VIDEO_DIR),
                    "RECORD_REP_TOKEN": TOKENS["COMPASS_REP_TOKEN"],
                    "RECORD_ADMIN_TOKEN": TOKENS["COMPASS_ADMIN_TOKEN"],
                },
            )
        finally:
            stop(server)
    if recorder.returncode != 0:
        return recorder.returncode

    print("\nvideos:")
    for name in VIDEOS:
        path = VIDEO_DIR / f"{name}.webm"
        mb = path.stat().st_size / 1_000_000
        note = f"  (over {MAX_COMMIT_MB} MB: do not commit)" if mb > MAX_COMMIT_MB else ""
        print(f"  {path.relative_to(REPO_ROOT)}  {mb:.1f} MB{note}")
    to_mp4()
    return 0


if __name__ == "__main__":
    sys.exit(main())

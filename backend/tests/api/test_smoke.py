"""Deployment prep (round 3, item 5): the streams' proxy headers, and `tasks.py smoke`."""

import socket
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import tasks
import yaml
from helpers import ADMIN_TOKEN, REP, REP_TOKEN
from live import live_server

from compass.api import Settings, create_app


def test_streams_are_not_buffered_or_cached_behind_a_proxy(
    make_settings: Callable[..., Settings],
) -> None:
    with (
        live_server(create_app(make_settings())) as base,
        httpx.Client(base_url=base, timeout=10) as http,
    ):
        sid = http.post("/api/sessions").json()["id"]
        for path, headers in ((f"/api/sessions/{sid}/events", {}), ("/api/tickets/events", REP)):
            with http.stream("GET", path, headers=headers) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                assert response.headers["cache-control"] == "no-cache"
                assert response.headers["x-accel-buffering"] == "no"


def test_smoke_passes_against_a_running_server(
    make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    with live_server(create_app(make_settings())) as base:
        tasks.smoke("--url", f"{base}/")
    out = capsys.readouterr().out
    assert "health: ok" in out
    assert "first event 'session_created'" in out
    assert out.rstrip().endswith("smoke: OK")
    assert REP_TOKEN not in out and ADMIN_TOKEN not in out


def test_smoke_fails_when_nothing_answers(capsys: pytest.CaptureFixture[str]) -> None:
    with socket.socket() as free:  # a port nothing listens on
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    with pytest.raises(SystemExit) as failed:
        tasks.smoke("--url", f"http://127.0.0.1:{port}")
    assert str(failed.value).startswith("smoke: FAIL at request")
    assert "smoke: OK" not in capsys.readouterr().out


BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent


def test_render_blueprint() -> None:
    blueprint = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))
    service, web = blueprint["services"]
    assert (service["name"], service["type"], service["runtime"]) == ("compass-api", "web", "docker")
    # with rootDir, Render resolves the Docker paths inside it
    assert service["rootDir"] == "backend"
    assert service["dockerfilePath"] == "./Dockerfile"
    assert service["dockerContext"] == "."
    assert service["plan"] == "free" and "disk" not in service
    assert service["numInstances"] == 1 and "scaling" not in service
    assert service["autoDeployTrigger"] == "off"
    assert service["healthCheckPath"] == "/api/health"
    variables = {v["key"]: v for v in service["envVars"]}
    # the secrets: names only, the values are set in the dashboard
    for secret in ("ANTHROPIC_API_KEY", "COMPASS_REP_TOKEN", "COMPASS_ADMIN_TOKEN"):
        assert variables.pop(secret) == {"key": secret, "sync": False}
    # the rest: set in the file
    assert {k: v["value"] for k, v in variables.items()} == {
        "COMPASS_LLM": "anthropic",
        "COMPASS_DAILY_SPEND_CAP_USD": "5",
        "COMPASS_MESSAGE_RATE_PER_MINUTE": "20",
        "COMPASS_TRUST_PROXY": "1",
        "COMPASS_CORS_ORIGINS": "https://compass-web.onrender.com",
    }

    # the UI: a static site whose CSP and API URL name the backend above
    assert (web["name"], web["type"], web["runtime"]) == ("compass-web", "web", "static")
    assert (web["rootDir"], web["staticPublishPath"]) == ("frontend", "dist")
    assert web["autoDeployTrigger"] == "off"
    built = {v["key"]: v["value"] for v in web["envVars"]}
    assert built["VITE_API_BASE_URL"] == "https://compass-api.onrender.com"
    assert web["routes"] == [{"type": "rewrite", "source": "/*", "destination": "/index.html"}]
    csp = {h["name"]: h["value"] for h in web["headers"]}["Content-Security-Policy"]
    assert "connect-src 'self' https://compass-api.onrender.com;" in csp


def test_the_image_listens_on_port_with_one_worker() -> None:
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert '--port \\"${PORT:-8000}\\" --workers 1' in dockerfile
    assert "os.environ.get('PORT') or 8000" in dockerfile  # the health check follows it


def test_the_image_drops_root_after_the_entrypoint() -> None:
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (BACKEND / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]' in dockerfile
    assert 'CMD ["gosu", "compass", "python"' in dockerfile  # the health check, not as root
    # root only for the chown, then the server via gosu: the only commands run as root
    root_part = entrypoint.split('if [ "$(id -u)" = 0 ]; then', 1)[1].split("\nfi\n", 1)[0]
    commands = [line.strip() for line in root_part.splitlines() if line.strip()]
    commands = [c for c in commands if not c.startswith("#")]
    assert commands == [
        "find /data -xdev ! -user compass -exec chown compass:compass {} +",
        'exec gosu compass "$@"',
    ]

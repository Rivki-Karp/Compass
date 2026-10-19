"""Deployment prep (round 3, item 5): the streams' proxy headers, and `tasks.py smoke`."""

import socket
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import yaml
from helpers import ADMIN_TOKEN, REP, REP_TOKEN
from live import live_server

import tasks
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


REPO = Path(__file__).resolve().parents[2]


def test_render_blueprint() -> None:
    blueprint = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))
    (service,) = blueprint["services"]
    assert (service["type"], service["runtime"]) == ("web", "docker")
    assert service["dockerfilePath"] == "./Dockerfile"
    assert service["numInstances"] == 1 and "scaling" not in service
    assert service["healthCheckPath"] == "/api/health"
    assert service["disk"]["mountPath"] == "/data"
    names = {v["key"] for v in service["envVars"]}
    assert names == {
        "ANTHROPIC_API_KEY",
        "COMPASS_REP_TOKEN",
        "COMPASS_ADMIN_TOKEN",
        "COMPASS_LLM",
        "COMPASS_DAILY_SPEND_CAP_USD",
        "COMPASS_MESSAGE_RATE_PER_MINUTE",
        "COMPASS_TRUST_PROXY",
    }
    # names only: no value in the repo
    assert all(v == {"key": v["key"], "sync": False} for v in service["envVars"])


def test_the_image_listens_on_port_with_one_worker() -> None:
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert '--port \\"${PORT:-8000}\\" --workers 1' in dockerfile
    assert "os.environ.get('PORT') or 8000" in dockerfile  # the health check follows it

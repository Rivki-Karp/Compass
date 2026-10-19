"""Demo mode never touches the network: the walkthrough and E-001 (with the representative's
answer) run through the real app with no API key while every way out is wired to fail."""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from compass.agent import demo_llm
from compass.agent.demo_llm import E001, WALKTHROUGH
from compass.api import Settings, create_app

REP = {"Authorization": "Bearer rep"}
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture
def attempts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Every outbound attempt is recorded and refused. Loopback stays open: asyncio on Windows
    connects a local socket pair to itself."""
    seen: list[str] = []

    def refuse(what: str) -> None:
        seen.append(what)
        raise OSError(f"network access in demo mode: {what}")

    real_connect = socket.socket.connect

    def connect(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in LOOPBACK:
            refuse(f"socket.connect {address!r}")
        return real_connect(self, address)

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        refuse(f"socket.create_connection {address!r}")

    def http(self: Any, request: httpx.Request) -> Any:
        refuse(f"httpx {request.method} {request.url}")

    def anthropic_client(self: Any, *args: Any, **kwargs: Any) -> None:
        refuse("anthropic.Anthropic()")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", http)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", http)
    monkeypatch.setattr(anthropic.Anthropic, "__init__", anthropic_client)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(demo_llm, "DEMO_DELAY_SECONDS", 0)
    yield seen


def test_the_refusals_work(attempts: list[str]) -> None:
    with pytest.raises(OSError):
        httpx.get("https://api.anthropic.com/v1/messages")
    with pytest.raises(OSError):
        anthropic.Anthropic(api_key="x")
    assert len(attempts) == 2


def test_demo_mode_runs_both_scripts_offline(tmp_path: Path, attempts: list[str]) -> None:
    settings = Settings(
        app_db=tmp_path / "demo.db",
        llm="scripted",
        rep_token="rep",
        anthropic_api_key=None,
        web_dist=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["llm"] == "scripted"
        agent = app.state.agent

        def run(texts: list[str]) -> str:
            sid = client.post("/api/sessions").json()["id"]
            for text in texts:
                client.post(f"/api/sessions/{sid}/messages", json={"text": text})
                assert agent.wait_idle(30)
            return sid

        def comparisons(sid: str) -> list[dict[str, Any]]:
            events = app.state.services.store.events_after(sid)
            return [e.payload["view"] for e in events if e.type == "comparison_ready"]

        walkthrough = run(WALKTHROUGH.employee_messages)
        assert comparisons(walkthrough)[-1]["display_diff"] == 2914

        e001 = run(E001.employee_messages)
        assert comparisons(e001)[-1]["display_diff"] == 661
        (ticket,) = client.get("/api/tickets", params={"status": "open"}, headers=REP).json()
        answered = client.post(
            f"/api/tickets/{ticket['id']}/answer",
            json={"values": {"alternative_participation:CAR-10": 350}},
            headers=REP,
        )
        assert answered.status_code == 200
        assert agent.wait_idle(30)
        final = comparisons(e001)[-1]
        assert (final["display_diff"], final["pending"]) == (611, False)

    assert attempts == []

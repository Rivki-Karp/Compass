"""Demo mode (COMPASS_LLM=scripted): only the model is scripted. Tools run for real, the guard
checks every reply, and the representative's answer goes through the real ticket flow."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass.agent import demo_llm
from compass.agent.demo_llm import E001, NO_SCRIPT_HE, WALKTHROUGH, DemoClient, Script, Turn
from compass.agent.factory import build_claude_runner
from compass.api import Settings, create_app
from compass.state import Store
from compass.tools.services import Services

REP_TOKEN = "rep"
REP = {"Authorization": f"Bearer {REP_TOKEN}"}


@pytest.fixture(autouse=True)
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo_llm, "DEMO_DELAY_SECONDS", 0.0)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(app_db=tmp_path / "app.db", llm="scripted", rep_token=REP_TOKEN)
    assert settings.anthropic_api_key is None  # no key, no network
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _say(client: TestClient, sid: str, *texts: str) -> None:
    for text in texts:
        assert client.post(f"/api/sessions/{sid}/messages", json={"text": text}).status_code == 202
    assert client.app.state.agent.wait_idle(20)  # type: ignore[attr-defined]


def _events(client: TestClient, sid: str, kind: str) -> list[dict[str, Any]]:
    store = client.app.state.services.store  # type: ignore[attr-defined]
    return [e.payload for e in store.events_after(sid) if e.type == kind]


def _replies(client: TestClient, sid: str) -> list[str]:
    return [p["text"] for p in _events(client, sid, "assistant_message")]


def _assert_every_reply_passed_the_guard(client: TestClient, sid: str) -> None:
    checks = _events(client, sid, "guard_check")
    assert checks and all(c["action"] == "accept" for c in checks), checks
    assert all(r["ok"] for r in _events(client, sid, "tool_result"))


def test_health_reports_demo_mode(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["llm"] == "scripted"
    assert [s["name"] for s in health["demo_scripts"]] == ["walkthrough", "e001"]
    assert health["demo_scripts"][0]["messages"] == WALKTHROUGH.employee_messages


def test_health_without_demo_mode(tmp_path: Path) -> None:
    for key, mode in ((None, "none"), ("sk-test", "anthropic")):
        settings = Settings(app_db=tmp_path / "app.db", anthropic_api_key=key)
        with TestClient(create_app(settings)) as test_client:
            health = test_client.get("/api/health").json()
        assert (health["llm"], health["demo_scripts"]) == (mode, None)


def test_walkthrough(client: TestClient) -> None:
    sid = client.post("/api/sessions").json()["id"]
    _say(client, sid, *WALKTHROUGH.employee_messages)
    view = _events(client, sid, "comparison_ready")[-1]["view"]
    assert (view["today_net"], view["alternative_net"], view["display_diff"]) == (
        11000,
        13914,
        2914,
    )
    assert [line["net_effect"] for line in view["breakdown"]] == [1500, 802, 180, 132, 300]
    replies = _replies(client, sid)
    assert len(replies) == 2 and "+2,914" in replies[1]
    _assert_every_reply_passed_the_guard(client, sid)
    assert [p["outcome"] for p in _events(client, sid, "agent_finished")] == ["reply", "reply"]


def test_e001_with_the_real_ticket_flow(client: TestClient) -> None:
    sid = client.post("/api/sessions").json()["id"]
    _say(client, sid, *E001.employee_messages)
    pending = _events(client, sid, "comparison_ready")[-1]["view"]
    assert pending["display_diff"] == 661 and pending["pending"]

    (ticket,) = client.get("/api/tickets", params={"status": "open"}, headers=REP).json()
    answer = client.post(
        f"/api/tickets/{ticket['id']}/answer",
        json={"values": {"alternative_participation:CAR-10": 350}},
        headers=REP,
    )
    assert answer.status_code == 200
    assert client.app.state.agent.wait_idle(20)  # type: ignore[attr-defined]

    final = _events(client, sid, "comparison_ready")[-1]["view"]
    assert (final["display_diff"], final["pending"]) == (611, False)
    sources = {i["id"]: i["source"] for i in final["inputs"]}
    assert sources["alternative_participation"] == "representative"
    assert "+611" in _replies(client, sid)[-1]
    _assert_every_reply_passed_the_guard(client, sid)


def test_sessions_run_side_by_side(client: TestClient) -> None:
    first = client.post("/api/sessions").json()["id"]
    second = client.post("/api/sessions").json()["id"]
    _say(client, first, WALKTHROUGH.employee_messages[0])
    _say(client, second, E001.employee_messages[0])
    _say(client, first, WALKTHROUGH.employee_messages[1])
    assert _events(client, first, "comparison_ready")[-1]["view"]["display_diff"] == 2914
    assert "ג׳" in _replies(client, second)[0]


def test_an_unscripted_message_gets_a_reply_without_numbers(client: TestClient) -> None:
    assert re.search(r"\d", NO_SCRIPT_HE) is None
    sid = client.post("/api/sessions").json()["id"]
    _say(client, sid, "ומה אם אעבור לחשמלי?")
    assert _replies(client, sid) == [NO_SCRIPT_HE]


def test_the_guard_catches_a_scripted_number(tmp_path: Path) -> None:
    """A script is not trusted: a number no tool produced is caught like a model's would be."""
    bad = Script(
        name="bad",
        title="bad",
        turns=(Turn(employee="כמה אקבל?", steps=(("text", "הנטו שלך יעלה ב-12,345 ₪."),)),),
    )
    services = Services(Store(tmp_path / "app.db"))
    runner = build_claude_runner(
        Settings(), services, llm=DemoClient([bad], delay=0), background=False
    )
    store = services.store
    sid = store.create_session()
    runner.on_user_message(sid, store.add_message(sid, "user", {"text": "כמה אקבל?"}))
    checks = [e.payload for e in store.events_after(sid) if e.type == "guard_check"]
    assert checks[0]["action"] == "retry" and checks[0]["violations"] == ["12,345"]
    shown = [e.payload["text"] for e in store.events_after(sid) if e.type == "assistant_message"]
    assert shown == [NO_SCRIPT_HE]  # the rewrite; the bad number never reached the employee

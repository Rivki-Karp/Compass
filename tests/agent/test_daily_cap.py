"""Cloud readiness (round 2, item 6): the live server's daily spend cap, the per-IP message
rate limit, and configuration from the environment only."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from compass.agent.factory import build_claude_runner
from compass.agent.llm import ScriptedClient, Usage, text_response, tool_response
from compass.agent.runner import DAILY_CAP_HE, ClaudeAgentRunner
from compass.api import Settings, create_app
from compass.api.ratelimit import RateLimiter, client_ip
from compass.api.settings import SettingsError
from compass.state import Store
from compass.tools import Services

MODEL = "claude-sonnet-5-5"  # priced: each call's cost counts
# 10,000 input tokens at $2 / M = $0.02 a call
CALL = Usage(input_tokens=10_000)


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _runner(services: Services, steps: list[Any], cap: float | None) -> tuple[Any, ScriptedClient]:
    llm = ScriptedClient(steps, model=MODEL)
    runner = ClaudeAgentRunner(services, llm, "SYSTEM", daily_spend_cap_usd=cap, background=False)
    return runner, llm


def _say(services: Services, runner: ClaudeAgentRunner, text: str = "שלום") -> Any:
    sid = services.store.create_session()
    seq = services.store.add_message(sid, "user", {"text": text})
    return sid, runner.process(sid, ("employee_turn", seq))


def test_every_model_call_is_counted(services: Services) -> None:
    steps = [
        replace(tool_response(("get_rule", {"topic": "budgets"})), usage=CALL),
        text_response("תשובה", usage=CALL),
    ]
    runner, _ = _runner(services, steps, cap=5.0)
    _, outcome = _say(services, runner)
    assert outcome.kind == "reply"
    assert services.store.spend_on(_today()) == pytest.approx(0.04)


def test_reaching_the_cap_stops_before_the_next_model_call(services: Services) -> None:
    services.store.add_spend(_today(), 5.0)  # the whole day's budget, across sessions
    runner, llm = _runner(services, [text_response("לא אמור להישלח")], cap=5.0)
    sid, outcome = _say(services, runner)
    assert llm.calls == []  # no model call at all
    assert (outcome.kind, outcome.error, outcome.text) == ("error", "daily_spend_cap", DAILY_CAP_HE)
    shown = [e.payload for e in services.store.events_after(sid) if e.type == "assistant_message"]
    assert shown[-1]["text"] == DAILY_CAP_HE
    errors = [e.payload for e in services.store.events_after(sid) if e.type == "agent_error"]
    assert errors[-1]["kind"] == "daily_spend_cap"


def test_the_cap_applies_mid_run(services: Services) -> None:
    services.store.add_spend(_today(), 4.99)
    first = replace(tool_response(("get_rule", {"topic": "budgets"})), usage=CALL)
    runner, llm = _runner(services, [first, text_response("לא אמור להישלח")], cap=5.0)
    _, outcome = _say(services, runner)
    assert len(llm.calls) == 1  # the first call took the day to $5.01; the second never ran
    assert outcome.text == DAILY_CAP_HE


def test_yesterday_does_not_count(services: Services) -> None:
    services.store.add_spend("2000-01-01", 100.0)
    runner, llm = _runner(services, [text_response("שלום לך")], cap=5.0)
    _, outcome = _say(services, runner)
    assert outcome.kind == "reply" and len(llm.calls) == 1


def test_no_cap_in_demo_mode_and_the_live_default(services: Services, tmp_path: Path) -> None:
    demo = Settings(app_db=tmp_path / "demo.db", llm="scripted")
    assert build_claude_runner(demo, services, llm=ScriptedClient([])).daily_spend_cap_usd is None
    live = Settings(app_db=tmp_path / "a.db")
    assert live.daily_spend_cap_usd == 5.0
    runner = build_claude_runner(live, services, llm=ScriptedClient([]))
    assert runner.daily_spend_cap_usd == 5.0


def test_cap_and_rate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COMPASS_DAILY_SPEND_CAP_USD", "2.5")
    monkeypatch.setenv("COMPASS_MESSAGE_RATE_PER_MINUTE", "7")
    settings = Settings.from_env(env_file=None)
    assert (settings.daily_spend_cap_usd, settings.message_rate_per_minute) == (2.5, 7)
    monkeypatch.setenv("COMPASS_DAILY_SPEND_CAP_USD", "0")
    with pytest.raises(SettingsError):
        Settings.from_env(env_file=None)


def test_the_image_reads_the_environment_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = tmp_path / ".env"
    env.write_text("COMPASS_MODEL=from-a-file\n", encoding="utf-8")
    monkeypatch.delenv("COMPASS_MODEL", raising=False)
    assert Settings.from_env(env_file=env).model == "from-a-file"
    monkeypatch.setenv("COMPASS_ENV_ONLY", "1")  # set in the Dockerfile
    assert Settings.from_env(env_file=env).model != "from-a-file"
    dockerfile = (Path(__file__).parents[2] / "Dockerfile").read_text(encoding="utf-8")
    assert "COMPASS_ENV_ONLY=1" in dockerfile


def test_trust_proxy_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPASS_TRUST_PROXY", raising=False)
    assert Settings.from_env(env_file=None).trust_proxy is False
    monkeypatch.setenv("COMPASS_TRUST_PROXY", "1")
    assert Settings.from_env(env_file=None).trust_proxy is True


def _limited_codes(client: TestClient, headers: list[dict[str, str]]) -> list[int]:
    sid = client.post("/api/sessions").json()["id"]
    url = f"/api/sessions/{sid}/messages"
    return [client.post(url, json={"text": "x"}, headers=h).status_code for h in headers]


def test_behind_a_trusted_proxy_the_rightmost_forwarded_entry_is_the_key(tmp_path: Path) -> None:
    settings = Settings(app_db=tmp_path / "a.db", message_rate_per_minute=1, trust_proxy=True)
    with TestClient(create_app(settings)) as client:
        # two employees behind the same proxy: their own limits
        codes = _limited_codes(
            client,
            [
                {"X-Forwarded-For": "198.51.100.1"},
                {"X-Forwarded-For": "198.51.100.2"},
                {"X-Forwarded-For": "198.51.100.1"},
            ],
        )
        assert codes == [202, 202, 429]
        # a forged entry on the left changes nothing: the proxy's entry (rightmost) counts
        forged = {"X-Forwarded-For": "203.0.113.9, 198.51.100.2"}
        assert _limited_codes(client, [forged]) == [429]


def _request(*forwarded: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request({"type": "http", "headers": headers, "client": ("10.0.0.5", 4000)})


def test_client_ip() -> None:
    assert client_ip(_request("198.51.100.1"), trust_proxy=False) == "10.0.0.5"
    assert client_ip(_request(), trust_proxy=True) == "10.0.0.5"  # no header: the socket
    assert client_ip(_request("1.1.1.1, 198.51.100.1 "), trust_proxy=True) == "198.51.100.1"
    # two headers read as one list; the last one's last entry is the proxy's
    assert client_ip(_request("1.1.1.1", "2.2.2.2, 198.51.100.3"), trust_proxy=True) == (
        "198.51.100.3"
    )
    assert client_ip(_request(" , "), trust_proxy=True) == "10.0.0.5"


def test_without_trust_proxy_forwarded_for_is_ignored(tmp_path: Path) -> None:
    settings = Settings(app_db=tmp_path / "a.db", message_rate_per_minute=1)
    with TestClient(create_app(settings)) as client:
        codes = _limited_codes(
            client,
            [{"X-Forwarded-For": "198.51.100.1"}, {"X-Forwarded-For": "198.51.100.2"}],
        )
        assert codes == [202, 429]  # one socket address, one limit


def test_rate_limiter_window() -> None:
    now = [0.0]
    limiter = RateLimiter(per_minute=2, clock=lambda: now[0])
    assert limiter.check("a") is None and limiter.check("a") is None
    assert limiter.check("a") == 60  # the third within the minute
    assert limiter.check("b") is None  # per key
    now[0] = 59.5
    assert limiter.check("a") == 1
    now[0] = 60.0
    assert limiter.check("a") is None  # the first hit left the window


def test_post_messages_is_rate_limited_per_ip(tmp_path: Path) -> None:
    settings = Settings(app_db=tmp_path / "a.db", message_rate_per_minute=3)
    with TestClient(create_app(settings)) as client:
        sid = client.post("/api/sessions").json()["id"]
        url = f"/api/sessions/{sid}/messages"
        codes = [client.post(url, json={"text": f"הודעה {i}"}).status_code for i in range(4)]
        assert codes == [202, 202, 202, 429]
        refused = client.post(url, json={"text": "עוד"})
        assert refused.status_code == 429 and int(refused.headers["Retry-After"]) >= 1
        # another session from the same IP shares the limit
        other = client.post("/api/sessions").json()["id"]
        assert client.post(f"/api/sessions/{other}/messages", json={"text": "x"}).status_code == 429

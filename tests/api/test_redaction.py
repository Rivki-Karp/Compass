"""Security: judges-only data (tool inputs, full results, rejected drafts, per-number sources,
usage and cost) never reaches a client without the admin token; the admin bearer gets all of it.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from helpers import ADMIN
from live import SSEReader, live_server

from compass.agent.factory import build_claude_runner
from compass.agent.llm import ScriptedClient, Usage, text_response, tool_response
from compass.agent.runner import ClaudeAgentRunner
from compass.api import Settings, create_app
from compass.api.redact import PUBLIC_KEYS, public_payload
from compass.state.store import EVENT_TYPES
from compass.tools import ToolRunner
from compass.tools.services import Services

DEVELOPER = {
    "occupation_query": "מפתח תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
DRAFT = "הנטו יעלה ב-2,915 ₪."  # the old rounding: rejected by the guard, never shown
USAGE = Usage(input_tokens=1000, output_tokens=200, cache_read_input_tokens=5000)


def _script() -> list[Any]:
    return [
        tool_response(
            ("save_profile", DEVELOPER),
            ("set_current_situation", TODAY),
            ("compare", {"alternative": {"kind": "waiver"}}),
        ),
        text_response(DRAFT, USAGE),
        text_response("הפרש של +2,914 ₪ בחודש.", USAGE),
    ]


@pytest.fixture
def run_session(make_settings: Callable[..., Settings]) -> Callable[[], tuple[str, str]]:
    """Start a live server, run one scripted agent turn (with a guard retry), and yield
    (base url, session id)."""
    holder: dict[str, ClaudeAgentRunner] = {}

    def factory(settings: Settings, services: Services, runner: ToolRunner) -> ClaudeAgentRunner:
        llm = ScriptedClient(_script(), model="claude-sonnet-5-5")
        holder["r"] = build_claude_runner(settings, services, llm=llm, tool_runner=runner)
        return holder["r"]

    app = create_app(make_settings(), agent_factory=factory)
    stack: list[Any] = []

    def run() -> tuple[str, str]:
        server = live_server(app)
        base = server.__enter__()
        stack.append(server)
        with httpx.Client(base_url=base, timeout=10) as http:
            sid = http.post("/api/sessions").json()["id"]
            http.post(f"/api/sessions/{sid}/messages", json={"text": "מה אם אוותר על הרכב?"})
        assert holder["r"].wait_idle(20)
        return base, sid

    yield run  # type: ignore[misc]
    for server in stack:
        server.__exit__(None, None, None)


def _stream(base: str, sid: str, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    with SSEReader(f"{base}/api/sessions/{sid}/events", headers=headers) as stream:
        stream.wait_for("agent_finished")
        return list(stream.events)


def _payloads(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e["data"]["payload"] for e in events if e["event"] == kind]


def test_unauthenticated_stream_has_no_judges_data(run_session: Any) -> None:
    base, sid = run_session()
    events = _stream(base, sid)
    raw = json.dumps(events, ensure_ascii=False)

    assert [set(p) for p in _payloads(events, "tool_call")] == [{"tool_use_id", "name"}] * 3
    assert [set(p) for p in _payloads(events, "tool_result")] == [{"tool_use_id", "name", "ok"}] * 3
    assert [p for p in _payloads(events, "guard_check")] == [
        {"passed": False, "action": "retry"},
        {"passed": True, "action": "accept_after_retry"},
    ]
    assert _payloads(events, "agent_finished") == [{"outcome": "reply"}]
    for secret in ("2,915", "rejected_draft", "sources", "cost_usd", "usage", "violations"):
        assert secret not in raw, secret
    # The employee's own comparison is public.
    assert _payloads(events, "comparison_ready")[0]["view"]["display_diff"] == 2914


def test_admin_stream_has_everything(run_session: Any) -> None:
    base, sid = run_session()
    events = _stream(base, sid, ADMIN)

    calls = _payloads(events, "tool_call")
    assert calls[0]["input"] == DEVELOPER
    results = _payloads(events, "tool_result")
    assert results[2]["result"]["comparison"]["display_diff"] == 2914
    retry, accept = _payloads(events, "guard_check")
    assert retry["rejected_draft"] == DRAFT and retry["violations"] == ["2,915"]
    assert accept["sources"] == {"+2,914": "compare"}
    (finished,) = _payloads(events, "agent_finished")
    assert finished["usage"]["input_tokens"] == 2000 and finished["rounds"] == 1
    assert finished["cost_usd"] == pytest.approx(USAGE.cost_usd("claude-sonnet-5-5") * 2)


def test_snapshot_is_redacted_without_the_admin_token(run_session: Any) -> None:
    base, sid = run_session()
    with httpx.Client(base_url=base, timeout=10) as http:
        public = http.get(f"/api/sessions/{sid}").json()
        full = http.get(f"/api/sessions/{sid}", headers=ADMIN).json()
    assert [m["role"] for m in public["messages"]] == ["user", "assistant"]
    assert public["messages"][1]["content"] == {"text": "הפרש של +2,914 ₪ בחודש."}
    raw = json.dumps(public, ensure_ascii=False)
    assert "usage" not in raw and "tool_use" not in raw and "2,915" not in raw
    assert {m["role"] for m in full["messages"]} == {"user", "system_event", "assistant", "tool"}


def test_a_wrong_admin_token_is_refused(run_session: Any) -> None:
    base, sid = run_session()
    wrong = {"Authorization": "Bearer nope"}
    with httpx.Client(base_url=base, timeout=10) as http:
        assert http.get(f"/api/sessions/{sid}", headers=wrong).status_code == 401
        assert http.get(f"/api/sessions/{sid}/events", headers=wrong).status_code == 401


def test_every_event_type_is_classified() -> None:
    assert set(PUBLIC_KEYS) == set(EVENT_TYPES)  # a new event type is a deliberate decision
    assert public_payload("something_new", {"secret": 1}) == {}

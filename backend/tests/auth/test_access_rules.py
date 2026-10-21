"""Stage 3: roles on the rep and admin routes, the static tokens refused, judges mode only for the
admin's own sessions, the per-user limits, and streams that end with the login."""

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from authkit import EMAILS, PASSWORD, STATIC_ADMIN, STATIC_REP
from fastapi.testclient import TestClient
from live import SSEReader, live_server

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner
from compass.api.settings import live_token_errors

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _login(client: TestClient | httpx.Client, who: str) -> dict[str, str]:
    reply = client.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['token']}"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- rep and admin routes ----------------------------------------------------------------------

ADMIN_ROUTES = [("get", "/api/admin/stats", {}), ("post", "/api/admin/reload-rules", {})]


NOA = {  # E-001
    "occupation_query": "מנהלת מוצר",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6,
    "study_fund_percent": 2.5,
    "credit_points": 2.75,
    "children_under_23": 2,
}
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}


def _open_ticket(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    """An employee's session with a ticket waiting for a representative: (session id, ticket id)."""
    sid = client.post("/api/sessions", headers=headers).json()["id"]
    client.post(f"/api/sessions/{sid}/messages", headers=headers, json={"text": "ומה עם ATTO 3?"})
    for name, payload in (
        ("save_profile", NOA),
        ("set_current_situation", TODAY),
        (
            "ask_representative",
            {"question": "?", "blocking_fields": ["alternative_participation:CAR-10"]},
        ),
    ):
        reply = client.post(f"/api/sessions/{sid}/tools/{name}", headers=headers, json=payload)
        assert reply.json()["ok"], reply.json()
    store = client.app.state.services.store  # type: ignore[attr-defined]
    (ticket,) = store.tickets(session_id=sid)
    return sid, ticket.id


def test_rep_routes_are_the_reps_only_and_do_not_exist_for_anyone_else(
    full_client: TestClient,
) -> None:
    """Not even the admin: an employee's tickets carry their profile and comparison."""
    employee = _login(full_client, "employee")
    _, ticket_id = _open_ticket(full_client, employee)
    answer = {"json": {"answer_text": "x"}}
    routes = [
        ("get", "/api/tickets", {}),
        ("get", "/api/tickets/events", {}),
        ("post", f"/api/tickets/{ticket_id}/answer", answer),
    ]
    for method, path, kwargs in routes:

        def call(who: str | None, method: str = method, path: str = path, kwargs=kwargs) -> int:  # type: ignore[no-untyped-def]
            headers = {} if who is None else _login(full_client, who)
            return getattr(full_client, method)(path, headers=headers, **kwargs).status_code

        assert call(None) == 401, path
        assert call("employee") == 404, path
        assert call("admin") == 404, path
    # the admin changed nothing and saw nothing; the rep sees the ticket
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    assert store.ticket(ticket_id).status == "open"
    listed = full_client.get("/api/tickets", headers=_login(full_client, "rep"))
    assert listed.status_code == 200 and [t["id"] for t in listed.json()] == [ticket_id]
    admin_view = full_client.get("/api/tickets", headers=_login(full_client, "admin"))
    assert "ticket" not in admin_view.text and ticket_id not in admin_view.text


def test_the_admin_reaches_no_employee_data(full_client: TestClient) -> None:
    """Every route that could carry an employee's conversation, profile or payslip: 404 or 401."""
    employee = _login(full_client, "employee")
    sid, ticket_id = _open_ticket(full_client, employee)
    admin = _login(full_client, "admin")
    reached = {
        ("get", f"/api/sessions/{sid}"): None,
        ("get", f"/api/sessions/{sid}/events"): None,
        ("post", f"/api/sessions/{sid}/messages"): {"text": "x"},
        ("post", f"/api/sessions/{sid}/tools/save_profile"): {"base_salary": 1},
        ("post", f"/api/sessions/{sid}/payslip/confirm"): {"fields": {}},
        ("post", f"/api/sessions/{sid}/current-car"): {"choice": "no_car"},
        ("get", "/api/tickets"): None,
        ("get", "/api/tickets/events"): None,
        ("post", f"/api/tickets/{ticket_id}/answer"): {"answer_text": "x"},
    }
    for (method, path), body in reached.items():
        kwargs = {} if body is None else {"json": body}
        reply = getattr(full_client, method)(path, headers=admin, **kwargs)
        assert reply.status_code == 404, (path, reply.status_code)
        assert "בקשה" not in reply.text and "18500" not in reply.text
    # what an admin may call on /admin carries no conversation, profile or payslip fields
    stats = full_client.get("/api/admin/stats", headers=admin)
    assert stats.status_code == 200 and "18500" not in stats.text and sid not in stats.text


@pytest.mark.parametrize(("method", "path", "kwargs"), ADMIN_ROUTES)
def test_admin_routes_need_the_admin_role(
    full_client: TestClient, method: str, path: str, kwargs: dict[str, object]
) -> None:
    def call(headers: dict[str, str] | None) -> int:
        return getattr(full_client, method)(path, headers=headers or {}, **kwargs).status_code

    assert call(None) == 401
    for who in ("employee", "rep"):
        assert call(_login(full_client, who)) == 403
    assert call(_login(full_client, "admin")) == 200


def test_the_static_tokens_are_refused(full_client: TestClient) -> None:
    rep, admin = _bearer(STATIC_REP), _bearer(STATIC_ADMIN)
    for method, path, kwargs in (
        ("get", "/api/tickets", {}),
        ("post", "/api/tickets/x/answer", {"json": {"answer_text": "x"}}),
    ):
        for headers in (rep, admin):
            assert getattr(full_client, method)(path, headers=headers, **kwargs).status_code == 401
    for method, path, kwargs in ADMIN_ROUTES:
        for headers in (rep, admin):
            assert getattr(full_client, method)(path, headers=headers, **kwargs).status_code == 401
    # and the admin token gives no judges view of anyone's session
    sid = full_client.post("/api/sessions", headers=_login(full_client, "admin")).json()["id"]
    assert full_client.get(f"/api/sessions/{sid}", headers=admin).status_code == 401


def test_the_same_server_without_the_flag_still_takes_the_static_tokens(
    full_settings: Settings,
) -> None:
    off = replace(full_settings, auth=False, seed_users=())
    with TestClient(create_app(off, agent=NullAgentRunner())) as client:
        assert client.get("/api/tickets", headers=_bearer(STATIC_REP)).status_code == 200
        assert client.get("/api/admin/stats", headers=_bearer(STATIC_ADMIN)).status_code == 200
        assert client.post("/api/sessions").status_code == 201
        health = client.get("/api/health").json()
    assert "accounts" not in health and health["auth"] == {"rep": True, "admin": True}


def test_health_tells_the_ui_accounts_are_on(full_client: TestClient) -> None:
    health = full_client.get("/api/health").json()
    assert health["accounts"] is True
    assert health["auth"] == {"rep": False, "admin": False}  # the static tokens are refused


def test_a_live_server_with_accounts_needs_no_static_tokens(full_settings: Settings) -> None:
    live = replace(full_settings, llm="anthropic", rep_token=None, admin_token=None)
    assert live_token_errors(live) == []
    assert live_token_errors(replace(live, auth=False)) != []


# --- judges mode -------------------------------------------------------------------------------


def _with_engine_room(client: TestClient, sid: str) -> None:
    store = client.app.state.services.store  # type: ignore[attr-defined]
    store.add_message(sid, "user", {"text": "hello"})
    store.add_message(sid, "tool", {"name": "compare", "input": {"secret": "engine"}}, False)
    call = {"tool_use_id": "t1", "name": "compare", "input": "ENGINE"}
    store.append_event(sid, "tool_call", call)


def test_the_engine_room_is_the_admins_own_sessions_only(full_client: TestClient) -> None:
    people = {who: _login(full_client, who) for who in ("employee", "other", "rep", "admin")}
    mine = {
        who: full_client.post("/api/sessions", headers=people[who]).json()["id"]
        for who in ("employee", "admin")
    }
    for sid in mine.values():
        _with_engine_room(full_client, sid)

    def roles(sid: str, who: str) -> list[str]:
        reply = full_client.get(f"/api/sessions/{sid}", headers=people[who])
        assert reply.status_code == 200
        return [m["role"] for m in reply.json()["messages"]]

    assert roles(mine["admin"], "admin") == ["user", "tool"]  # the full view, own session
    assert roles(mine["employee"], "employee") == ["user"]  # an employee: the public part
    # the admin does not get it for an employee's session, nor can anyone read another's
    for owner, outsider in (("employee", "admin"), ("admin", "rep"), ("admin", "employee")):
        reply = full_client.get(f"/api/sessions/{mine[owner]}", headers=people[outsider])
        assert reply.status_code == 404, (owner, outsider)


def test_the_events_stream_is_full_for_the_admin_and_public_for_the_rest(
    full_settings: Settings,
) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        seen = {}
        for who in ("admin", "employee"):
            headers = _login(http, who)
            sid = http.post("/api/sessions", headers=headers).json()["id"]
            app.state.services.store.append_event(
                sid, "tool_call", {"tool_use_id": "t1", "name": "compare", "input": "ENGINE"}
            )
            with SSEReader(f"{base}/api/sessions/{sid}/events", headers=headers) as stream:
                seen[who] = stream.wait_for("tool_call")["data"]["payload"]
    assert seen["admin"] == {"tool_use_id": "t1", "name": "compare", "input": "ENGINE"}
    assert seen["employee"] == {"tool_use_id": "t1", "name": "compare"}


# --- per-user limits ---------------------------------------------------------------------------


def test_messages_are_limited_per_user_as_well_as_per_ip(full_settings: Settings) -> None:
    settings = replace(full_settings, message_rate_per_minute=3, trust_proxy=True)
    with TestClient(create_app(settings, agent=NullAgentRunner())) as client:
        users = {who: _login(client, who) for who in ("employee", "other")}
        sids = {
            who: client.post("/api/sessions", headers=h).json()["id"] for who, h in users.items()
        }
        hits = iter(range(1, 100))

        def post(who: str) -> httpx.Response:
            # a different client address every time: only the per-user limit can answer 429
            headers = {**users[who], "X-Forwarded-For": f"203.0.113.{next(hits)}"}
            return client.post(
                f"/api/sessions/{sids[who]}/messages", headers=headers, json={"text": "hi"}
            )

        assert [post("employee").status_code for _ in range(4)] == [202, 202, 202, 429]
        limited = post("employee")
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
        assert post("other").status_code == 202  # another user's allowance is their own


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> httpx.Response:
    return client.post(
        f"/api/sessions/{sid}/payslip",
        content=PNG,
        headers={**headers, "Content-Type": "image/png"},
    )


def test_payslip_uploads_are_counted_per_user_per_day(full_settings: Settings) -> None:
    settings = replace(full_settings, payslip_per_session=5, payslip_per_user_per_day=3)
    with TestClient(create_app(settings, agent=NullAgentRunner())) as client:
        a, b = _login(client, "employee"), _login(client, "other")
        first = client.post("/api/sessions", headers=a).json()["id"]
        second = client.post("/api/sessions", headers=a).json()["id"]
        theirs = client.post("/api/sessions", headers=b).json()["id"]
        assert [_upload(client, first, a).status_code for _ in range(2)] == [201, 201]
        assert _upload(client, second, a).status_code == 201  # a new conversation, same allowance
        capped = _upload(client, second, a)
        assert capped.status_code == 429 and capped.json()["detail"] == "payslip_per_user_day"
        assert "3" in capped.json()["errors"][0]["message"]
        assert _upload(client, first, a).status_code == 429  # and the first one too
        assert _upload(client, theirs, b).status_code == 201  # not another user's


def test_the_per_session_cap_still_applies(full_settings: Settings) -> None:
    settings = replace(full_settings, payslip_per_session=1, payslip_per_user_per_day=50)
    with TestClient(create_app(settings, agent=NullAgentRunner())) as client:
        a = _login(client, "employee")
        sid = client.post("/api/sessions", headers=a).json()["id"]
        assert _upload(client, sid, a).status_code == 201
        assert _upload(client, sid, a).json()["detail"] == "payslip_per_session"


def test_the_day_count_starts_at_midnight_utc(full_client: TestClient) -> None:
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    a = _login(full_client, "employee")
    sid = full_client.post("/api/sessions", headers=a).json()["id"]
    user = full_client.app.state.accounts.user_by_email(EMAILS["employee"])  # type: ignore[attr-defined]
    store.append_event(sid, "payslip_failed", {"code": "payslip_unreadable"})
    types = ("payslip_extracted", "payslip_failed")
    now = datetime.now(UTC)
    assert store.count_user_events(user.id, types, (now - timedelta(minutes=1)).isoformat()) == 1
    assert store.count_user_events(user.id, types, (now + timedelta(minutes=1)).isoformat()) == 0
    assert store.count_user_events("someone-else", types, "2000-01-01T00:00:00+00:00") == 0


# --- a stream ends with the login --------------------------------------------------------------


def _wait_closed(stream: SSEReader, seconds: float = 8) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not stream._thread.is_alive():
            return True
        time.sleep(0.05)
    return False


@pytest.mark.parametrize("ending", ["logout", "disabled", "expired"])
def test_an_open_event_stream_ends_when_the_login_does(
    full_settings: Settings, ending: str
) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        headers = _login(http, "employee")
        sid = http.post("/api/sessions", headers=headers).json()["id"]
        with SSEReader(f"{base}/api/sessions/{sid}/events", headers=headers) as stream:
            stream.wait_for("session_created")
            if ending == "logout":
                assert http.post("/api/auth/logout", headers=headers).status_code == 204
            elif ending == "disabled":
                with app.state.accounts.store._write() as (conn, _):
                    conn.execute(
                        "UPDATE users SET status = 'disabled' WHERE email = ?",
                        (EMAILS["employee"],),
                    )
            else:
                app.state.accounts.clock = lambda: datetime.now(UTC) + timedelta(hours=9)
            assert _wait_closed(stream), "the stream outlived the login"


def test_the_rep_inbox_stream_ends_with_the_rep_login(full_settings: Settings) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        rep = _login(http, "rep")
        assert http.get("/api/tickets/events").status_code == 401
        assert http.get("/api/tickets/events", headers=_login(http, "employee")).status_code == 404
        assert http.get("/api/tickets/events", headers=_login(http, "admin")).status_code == 404
        with SSEReader(f"{base}/api/tickets/events", headers=rep) as inbox:
            inbox.wait_for("tickets")
            http.post("/api/auth/logout", headers=rep)
            assert _wait_closed(inbox), "the inbox stream outlived the login"


def test_a_conversation_deleted_under_a_stream_ends_it(full_settings: Settings) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        headers = _login(http, "employee")
        sid = http.post("/api/sessions", headers=headers).json()["id"]
        with SSEReader(f"{base}/api/sessions/{sid}/events", headers=headers) as stream:
            stream.wait_for("session_created")
            store = app.state.services.store
            with store._write() as (conn, _):
                for table in ("events", "messages", "scenarios", "profile_slots", "tickets"):
                    conn.execute(f"DELETE FROM {table} WHERE session_id = ?", (sid,))
                conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            assert _wait_closed(stream)

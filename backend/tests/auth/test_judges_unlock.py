"""Judges mode for any logged-in user (COMPASS_JUDGES_UNLOCK): the admin password unlocks the full
engine room for one login session, in that user's own conversations only."""

import logging
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from authkit import DEMO_ADMIN_PASSWORD, DEMO_EMAILS, DEMO_USER_PASSWORD, EMAILS, PASSWORD
from fastapi.testclient import TestClient
from live import SSEReader, live_server

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner

WRONG = "not the admin password"
GENERIC = "הסיסמה שגויה"
UNLOCK = "/api/auth/judges-unlock"
LOCK = "/api/auth/judges-lock"


def _login(
    client: TestClient | httpx.Client, email: str, password: str = PASSWORD
) -> dict[str, str]:
    reply = client.post("/api/auth/login", json={"email": email, "password": password})
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['token']}"}


def _as(client: TestClient | httpx.Client, who: str) -> dict[str, str]:
    return _login(client, EMAILS[who])


def _unlock(
    client: TestClient, headers: dict[str, str], password: str = PASSWORD
) -> httpx.Response:
    return client.post(UNLOCK, headers=headers, json={"password": password})


def _with_engine_room(client: TestClient, sid: str) -> None:
    store = client.app.state.services.store  # type: ignore[attr-defined]
    store.add_message(sid, "user", {"text": "hello"})
    store.add_message(sid, "tool", {"name": "compare", "input": {"secret": "engine"}}, False)
    store.append_event(
        sid, "tool_call", {"tool_use_id": "t1", "name": "compare", "input": "ENGINE"}
    )


def _roles(client: TestClient, sid: str, headers: dict[str, str]) -> list[str]:
    reply = client.get(f"/api/sessions/{sid}", headers=headers)
    assert reply.status_code == 200, reply.text
    return [m["role"] for m in reply.json()["messages"]]


def _me(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    reply = client.get("/api/auth/me", headers=headers)
    assert reply.status_code == 200
    return reply.json()  # type: ignore[no-any-return]


# --- the unlock -----------------------------------------------------------


def test_the_admin_password_unlocks_the_full_engine_room_for_the_owner(
    access_client: TestClient,
) -> None:
    employee = _as(access_client, "employee")
    sid = access_client.post("/api/sessions", headers=employee).json()["id"]
    _with_engine_room(access_client, sid)
    assert _roles(access_client, sid, employee) == ["user"]  # the public part
    assert _me(access_client, employee)["judges_unlocked"] is False

    assert _unlock(access_client, employee).status_code == 204
    assert _roles(access_client, sid, employee) == ["user", "tool"]  # the full view
    assert _me(access_client, employee)["judges_unlocked"] is True


def test_any_active_admins_password_will_do_the_demo_admins_too(access_client: TestClient) -> None:
    for password in (PASSWORD, DEMO_ADMIN_PASSWORD):
        employee = _as(access_client, "employee")
        assert _unlock(access_client, employee, password).status_code == 204
        assert _me(access_client, employee)["judges_unlocked"] is True


@pytest.mark.parametrize("password", [WRONG, DEMO_USER_PASSWORD, ""])
def test_a_wrong_password_is_the_one_generic_error(
    access_client: TestClient, password: str
) -> None:
    """Including a non-admin's own password, and nothing at all."""
    employee = _login(access_client, DEMO_EMAILS["employee"], DEMO_USER_PASSWORD)
    reply = _unlock(access_client, employee, password)
    assert reply.status_code == 401
    assert reply.json() == {"detail": GENERIC}
    assert _me(access_client, employee)["judges_unlocked"] is False


def test_a_disabled_admins_password_no_longer_unlocks(access_client: TestClient) -> None:
    accounts = access_client.app.state.accounts  # type: ignore[attr-defined]
    other_admin = accounts.user_by_email(DEMO_EMAILS["admin"])
    accounts.update_user(other_admin.id, None, "disabled")
    employee = _as(access_client, "employee")
    assert _unlock(access_client, employee, DEMO_ADMIN_PASSWORD).status_code == 401
    assert _unlock(access_client, employee, PASSWORD).status_code == 204


def test_an_admin_made_from_a_demo_session_cannot_set_the_password(
    access_client: TestClient,
) -> None:
    """Anyone could be the demo admin and invite someone: their password is not an admin's."""
    accounts = access_client.app.state.accounts  # type: ignore[attr-defined]
    from compass.auth.passwords import hash_password

    made = accounts.create_user(
        "made@example.com", "Made", "admin", hash_password("made by anyone")
    )
    with accounts.store._write() as (conn, _events):
        conn.execute("UPDATE users SET demo_origin = 1 WHERE id = ?", (made.id,))
    employee = _as(access_client, "employee")
    assert _unlock(access_client, employee, "made by anyone").status_code == 401


def test_login_is_required_and_the_body_is_checked(access_client: TestClient) -> None:
    assert access_client.post(UNLOCK, json={"password": PASSWORD}).status_code == 401
    assert access_client.post(LOCK).status_code == 401
    employee = _as(access_client, "employee")
    for body in ({}, {"password": PASSWORD, "extra": 1}, {"password": "x" * 2000}):
        reply = access_client.post(UNLOCK, headers=employee, json=body)
        assert reply.status_code == 422
        assert PASSWORD not in reply.text and "x" * 50 not in reply.text  # nothing is echoed


def test_an_admin_is_full_as_before_with_or_without_the_unlock(access_client: TestClient) -> None:
    admin = _as(access_client, "admin")
    sid = access_client.post("/api/sessions", headers=admin).json()["id"]
    _with_engine_room(access_client, sid)
    assert _roles(access_client, sid, admin) == ["user", "tool"]


# --- the lock (per user and address, as login's) -----------------------------------------


def _from(ip: str, headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "X-Forwarded-For": ip}


@pytest.fixture
def proxied(access_settings: Settings) -> Settings:
    return replace(access_settings, trust_proxy=True)


def test_five_failures_lock_the_unlock_for_that_user_and_address_only(proxied: Settings) -> None:
    with TestClient(create_app(proxied, agent=NullAgentRunner())) as client:
        dana, avi = _as(client, "employee"), _as(client, "other")
        for _ in range(5):
            reply = client.post(
                UNLOCK, headers=_from("203.0.113.1", dana), json={"password": WRONG}
            )
            assert reply.status_code == 401
        # locked: even the right password is refused, with the same words, and tells nothing more
        locked = client.post(
            UNLOCK, headers=_from("203.0.113.1", dana), json={"password": PASSWORD}
        )
        assert locked.status_code == 429
        assert locked.json()["detail"].startswith(GENERIC)
        assert _me(client, dana)["judges_unlocked"] is False
        # another address, and another user from the same address, are not locked
        other_address = _from("203.0.113.2", dana)
        assert (
            client.post(UNLOCK, headers=other_address, json={"password": PASSWORD}).status_code
            == 204
        )
        assert (
            client.post(
                UNLOCK, headers=_from("203.0.113.1", avi), json={"password": PASSWORD}
            ).status_code
            == 204
        )


def test_the_lock_ends_and_a_wrong_unlock_never_touches_the_logins_count(
    access_settings: Settings,
) -> None:
    clock = [1000.0]
    app = create_app(access_settings, agent=NullAgentRunner())
    with TestClient(app) as client:
        guard = app.state.judges_guard
        guard.clock = lambda: clock[0]
        guard.ips.clock = lambda: clock[0]
        dana = _as(client, "employee")
        for _ in range(5):
            _unlock(client, dana, WRONG)
        assert _unlock(client, dana).status_code == 429
        clock[0] += 15 * 60 + 1
        assert _unlock(client, dana).status_code == 204
        # five wrong unlocks did not count against the login of the same account
        assert (
            client.post(
                "/api/auth/login", json={"email": EMAILS["employee"], "password": PASSWORD}
            ).status_code
            == 200
        )


# --- timing parity -----------------------------------------------------------


def test_every_admin_hash_is_verified_whoever_matches(
    access_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import compass.api.auth as auth_module
    from compass.auth.passwords import hash_password

    accounts = access_client.app.state.accounts  # type: ignore[attr-defined]
    accounts.create_user("third@example.com", "Third", "admin", hash_password("third admin pass"))
    admins = len(accounts.judges_password_hashes())
    assert admins == 3

    calls: list[str] = []
    real = auth_module.verify_password

    def counting(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return real(password_hash, password)

    monkeypatch.setattr(auth_module, "verify_password", counting)
    employee = _as(access_client, "employee")
    results = {}
    for label, password in (
        ("none", WRONG),
        ("first", PASSWORD),
        ("last", "third admin pass"),
        ("middle", DEMO_ADMIN_PASSWORD),
    ):
        calls.clear()
        results[label] = (_unlock(access_client, employee, password).status_code, len(calls))
    assert results == {
        "none": (401, admins),
        "first": (204, admins),
        "last": (204, admins),
        "middle": (204, admins),
    }


# --- the scope -----------------------------------------------------------


def test_the_full_view_is_the_owners_own_sessions_only(access_client: TestClient) -> None:
    employee, other = _as(access_client, "employee"), _as(access_client, "other")
    mine = access_client.post("/api/sessions", headers=employee).json()["id"]
    theirs = access_client.post("/api/sessions", headers=other).json()["id"]
    for sid in (mine, theirs):
        _with_engine_room(access_client, sid)
    assert _unlock(access_client, employee).status_code == 204

    assert _roles(access_client, mine, employee) == ["user", "tool"]
    # someone else's session: the same 404 as ever, unlocked or not, snapshot and stream alike
    unknown = access_client.get("/api/sessions/not-a-session", headers=employee)
    for path in (f"/api/sessions/{theirs}", f"/api/sessions/{theirs}/events"):
        reply = access_client.get(path, headers=employee)
        assert reply.status_code == 404
        assert "ENGINE" not in reply.text and "engine" not in reply.text
    assert unknown.status_code == 404
    # and the unlock is not the other user's: they still see the public part of their own
    assert _roles(access_client, theirs, other) == ["user"]


def test_the_unlock_belongs_to_one_login_session_not_the_account(access_client: TestClient) -> None:
    first, second = _as(access_client, "employee"), _as(access_client, "employee")
    sid = access_client.post("/api/sessions", headers=first).json()["id"]
    _with_engine_room(access_client, sid)
    assert _unlock(access_client, first).status_code == 204
    assert _me(access_client, second)["judges_unlocked"] is False
    assert _roles(access_client, sid, second) == ["user"]


def test_it_ends_on_logout_on_expiry_and_on_disabling(access_client: TestClient) -> None:
    accounts = access_client.app.state.accounts  # type: ignore[attr-defined]
    employee = _as(access_client, "employee")
    assert _unlock(access_client, employee).status_code == 204

    # logout: the token is dead, and a new login starts locked
    assert access_client.post("/api/auth/logout", headers=employee).status_code == 204
    assert access_client.get("/api/auth/me", headers=employee).status_code == 401
    again = _as(access_client, "employee")
    assert _me(access_client, again)["judges_unlocked"] is False

    # disabling the user: every session of theirs ends, the unlock with it, and it does not
    # come back when they are enabled again
    assert _unlock(access_client, again).status_code == 204
    user = accounts.user_by_email(EMAILS["employee"])
    accounts.update_user(user.id, None, "disabled")
    assert access_client.get("/api/auth/me", headers=again).status_code == 401
    accounts.update_user(user.id, None, "active")
    assert access_client.get("/api/auth/me", headers=again).status_code == 401
    fresh = _as(access_client, "employee")
    assert _me(access_client, fresh)["judges_unlocked"] is False

    # the session's absolute expiry
    assert _unlock(access_client, fresh).status_code == 204
    accounts.clock = lambda: datetime.now(UTC) + timedelta(hours=9)
    assert access_client.get("/api/auth/me", headers=fresh).status_code == 401
    assert access_client.get(f"/api/sessions/{'x'}", headers=fresh).status_code == 401


def test_locking_again_turns_it_off(access_client: TestClient) -> None:
    employee = _as(access_client, "employee")
    sid = access_client.post("/api/sessions", headers=employee).json()["id"]
    _with_engine_room(access_client, sid)
    _unlock(access_client, employee)
    assert _roles(access_client, sid, employee) == ["user", "tool"]
    assert access_client.post(LOCK, headers=employee).status_code == 204
    assert _roles(access_client, sid, employee) == ["user"]
    assert _me(access_client, employee)["judges_unlocked"] is False
    assert access_client.post(LOCK, headers=employee).status_code == 204  # idempotent
    assert _unlock(access_client, employee).status_code == 204  # and it can be turned on again


def test_an_open_stream_is_redacted_from_the_next_event_after_a_lock(
    access_settings: Settings,
) -> None:
    app = create_app(access_settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        headers = _as(http, "employee")
        sid = http.post("/api/sessions", headers=headers).json()["id"]
        store = app.state.services.store
        assert http.post(UNLOCK, headers=headers, json={"password": PASSWORD}).status_code == 204
        with SSEReader(f"{base}/api/sessions/{sid}/events", headers=headers) as stream:
            store.append_event(sid, "tool_call", {"tool_use_id": "t1", "name": "c", "input": "A"})
            assert stream.wait_for("tool_call")["data"]["payload"]["input"] == "A"
            assert http.post(LOCK, headers=headers).status_code == 204
            store.append_event(sid, "tool_call", {"tool_use_id": "t2", "name": "c", "input": "B"})
            deadline = time.monotonic() + 10
            while not any(
                e.get("data", {}).get("payload", {}).get("tool_use_id") == "t2"
                for e in stream.events
            ):
                assert time.monotonic() < deadline, stream.events
                time.sleep(0.02)
            last = [e for e in stream.events if e.get("event") == "tool_call"][-1]
            assert last["data"]["payload"] == {"tool_use_id": "t2", "name": "c"}


# --- nothing leaks -----------------------------------------------------------


def test_no_password_reaches_a_log_or_a_response(
    access_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    employee = _as(access_client, "employee")
    bodies = [
        _unlock(access_client, employee, WRONG),
        _unlock(access_client, employee, DEMO_ADMIN_PASSWORD),
        access_client.post(LOCK, headers=employee),
        access_client.get("/api/auth/me", headers=employee),
        access_client.get("/api/health"),
    ]
    text = " ".join(r.text for r in bodies) + caplog.text
    for secret in (WRONG, DEMO_ADMIN_PASSWORD, PASSWORD, DEMO_USER_PASSWORD):
        assert secret not in text
    assert "argon2" not in text


# --- the flag -----------------------------------------------------------


def test_with_the_flag_off_the_routes_do_not_exist(
    access_settings: Settings,
) -> None:
    off = replace(access_settings, judges_unlock=False)
    app = create_app(off, agent=NullAgentRunner())
    with TestClient(app) as client:
        employee = _as(client, "employee")
        assert client.post(UNLOCK, headers=employee, json={"password": PASSWORD}).status_code == 404
        assert client.post(LOCK, headers=employee).status_code == 404
        assert UNLOCK not in app.openapi()["paths"] and LOCK not in app.openapi()["paths"]
        assert "judges_unlock" not in client.get("/api/health").json()
        assert _me(client, employee) == {"name": "Employee", "role": "employee", "demo": False}

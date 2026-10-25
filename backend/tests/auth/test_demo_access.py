"""The demo quick access (COMPASS_DEMO_LOGIN): one-click login to the shared demo accounts, and what
keeps the public from wrecking them or reaching the real users."""

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from authkit import DEMO_ADMIN_PASSWORD, DEMO_EMAILS, DEMO_USER_PASSWORD, EMAILS, PASSWORD
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner

DEMO_LOGIN = "/api/auth/demo-login"
USER_FIELDS = {"id", "email", "name", "role", "status", "created_at", "last_login_at"}
REAL_EMAILS = set(EMAILS.values())


def _demo(client: TestClient, role: str) -> dict[str, str]:
    reply = client.post(DEMO_LOGIN, json={"role": role})
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['token']}"}


def _real(client: TestClient, who: str) -> dict[str, str]:
    reply = client.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['token']}"}


def _listed(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    reply = client.get("/api/admin/users", headers=headers)
    assert reply.status_code == 200, reply.text
    return reply.json()  # type: ignore[no-any-return]


def _uid(client: TestClient, email: str) -> str:
    return client.app.state.accounts.user_by_email(email).id  # type: ignore[attr-defined, no-any-return]


# --- the login -----------------------------------------------------------


@pytest.mark.parametrize("role", ["employee", "rep", "admin"])
def test_each_role_logs_in_with_no_password(access_client: TestClient, role: str) -> None:
    reply = access_client.post(DEMO_LOGIN, json={"role": role})
    assert reply.status_code == 200
    body = reply.json()
    assert set(body) == {"token", "name", "role"} and body["role"] == role
    assert body["name"] == f"Demo {role}"
    headers = {"Authorization": f"Bearer {body['token']}"}
    me = access_client.get("/api/auth/me", headers=headers).json()
    assert me["role"] == role and me["demo"] is True
    # an ordinary login of the same account is not a demo session
    ordinary = (
        access_client.post(
            "/api/auth/login", json={"email": DEMO_EMAILS[role], "password": DEMO_USER_PASSWORD}
        )
        if role != "admin"
        else access_client.post(
            "/api/auth/login", json={"email": DEMO_EMAILS[role], "password": DEMO_ADMIN_PASSWORD}
        )
    )
    token = {"Authorization": f"Bearer {ordinary.json()['token']}"}
    assert access_client.get("/api/auth/me", headers=token).json()["demo"] is False


def test_only_an_active_demo_account_and_a_known_role(access_client: TestClient) -> None:
    assert access_client.post(DEMO_LOGIN, json={"role": "root"}).status_code == 422
    assert access_client.post(DEMO_LOGIN, json={}).status_code == 422
    assert access_client.post(DEMO_LOGIN, json={"role": "rep", "x": 1}).status_code == 422
    accounts = access_client.app.state.accounts  # type: ignore[attr-defined]
    accounts.update_user(_uid(access_client, DEMO_EMAILS["rep"]), None, "disabled")
    assert access_client.post(DEMO_LOGIN, json={"role": "rep"}).status_code == 404
    # a real account is never reachable this way, whatever its role
    only_real = replace(
        access_client.app.state.settings,  # type: ignore[attr-defined]
        app_db=access_client.app.state.settings.app_db.with_name("real-only.db"),  # type: ignore[attr-defined]
        seed_users=tuple(
            u
            for u in access_client.app.state.settings.seed_users
            if not u.demo  # type: ignore[attr-defined]
        ),
    )
    with TestClient(create_app(only_real, agent=NullAgentRunner())) as client:
        assert client.post(DEMO_LOGIN, json={"role": "employee"}).status_code == 404


def test_the_flag_off_means_no_route_and_no_health_key(access_settings: Settings) -> None:
    off = replace(access_settings, demo_login=False)
    app = create_app(off, agent=NullAgentRunner())
    with TestClient(app) as client:
        assert client.post(DEMO_LOGIN, json={"role": "admin"}).status_code == 404
        assert DEMO_LOGIN not in app.openapi()["paths"]
        assert "demo_login" not in client.get("/api/health").json()
    on = TestClient(create_app(access_settings, agent=NullAgentRunner()))
    with on:
        assert on.get("/api/health").json()["demo_login"] is True


def test_demo_login_is_rate_limited_per_ip(access_settings: Settings) -> None:
    limited = replace(access_settings, demo_login_per_ip_per_minute=3, trust_proxy=True)
    with TestClient(create_app(limited, agent=NullAgentRunner())) as client:

        def go(ip: str) -> httpx.Response:
            return client.post(
                DEMO_LOGIN, json={"role": "employee"}, headers={"X-Forwarded-For": ip}
            )

        assert [go("203.0.113.9").status_code for _ in range(4)] == [200, 200, 200, 429]
        assert int(go("203.0.113.9").headers["retry-after"]) >= 1
        assert go("203.0.113.10").status_code == 200  # another address has its own allowance


def test_no_password_is_involved_or_shown_anywhere(
    access_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    texts = []
    for role in ("employee", "rep", "admin"):
        headers = _demo(access_client, role)
        texts.append(access_client.get("/api/auth/me", headers=headers).text)
    admin = _demo(access_client, "admin")
    texts += [
        access_client.get("/api/admin/users", headers=admin).text,
        access_client.get("/api/health").text,
        access_client.get("/openapi.json").text,
    ]
    everything = " ".join(texts) + caplog.text
    for secret in (DEMO_ADMIN_PASSWORD, DEMO_USER_PASSWORD, PASSWORD):
        assert secret not in everything
    assert "argon2" not in everything
    # and the password the body would need does not exist: a password field is refused
    refused = access_client.post(DEMO_LOGIN, json={"role": "admin", "password": "x"})
    assert refused.status_code == 422
    assert "password" not in str(
        access_client.get("/openapi.json").json()["components"]["schemas"].get("DemoLoginBody")
    )


# --- the protections -----------------------------------------------------------


def test_a_demo_account_cannot_be_deleted_disabled_or_demoted_by_anyone(
    access_client: TestClient,
) -> None:
    target = _uid(access_client, DEMO_EMAILS["employee"])
    for admin in (_demo(access_client, "admin"), _real(access_client, "admin")):
        for body in ({"status": "disabled"}, {"role": "rep"}, {"role": "admin"}):
            reply = access_client.patch(f"/api/admin/users/{target}", headers=admin, json=body)
            assert reply.status_code == 409, (body, reply.text)
        assert access_client.delete(f"/api/admin/users/{target}", headers=admin).status_code == 409
    user = access_client.app.state.accounts.user_by_id(target)  # type: ignore[attr-defined]
    assert (user.role, user.status) == ("employee", "active")
    # the same role, or an enable, changes nothing and is allowed
    real = _real(access_client, "admin")
    same = access_client.patch(
        f"/api/admin/users/{target}", headers=real, json={"role": "employee"}
    )
    assert same.status_code == 200 and same.json()["demo"] is True
    # the demo admin's own account is protected too (and, being the caller's own, says so as ever)
    me = _uid(access_client, DEMO_EMAILS["admin"])
    assert (
        access_client.delete(
            f"/api/admin/users/{me}", headers=_real(access_client, "admin")
        ).status_code
        == 409
    )


def test_a_demo_session_sees_and_manages_only_the_demo(access_client: TestClient) -> None:
    demo_admin = _demo(access_client, "admin")
    listed = _listed(access_client, demo_admin)
    assert {u["email"] for u in listed} == set(DEMO_EMAILS.values())
    reply = access_client.get("/api/admin/users", headers=demo_admin)
    for real_email in REAL_EMAILS:
        assert f'"{real_email}"' not in reply.text
    for who in ("Employee", "Other", "Admin"):  # the real accounts' names
        assert f'"name":"{who}"' not in reply.text
    # a real user is not there to touch: 404, the same as an id that does not exist
    real_id = _uid(access_client, EMAILS["employee"])
    nothing = access_client.delete("/api/admin/users/nobody", headers=demo_admin)
    for call in (
        access_client.delete(f"/api/admin/users/{real_id}", headers=demo_admin),
        access_client.patch(
            f"/api/admin/users/{real_id}", headers=demo_admin, json={"status": "disabled"}
        ),
    ):
        assert call.status_code == 404 and call.json() == nothing.json()
    assert access_client.app.state.accounts.user_by_id(real_id).status == "active"  # type: ignore[attr-defined]
    # the real admin sees everyone, the demo flag included
    everyone = _listed(access_client, _real(access_client, "admin"))
    assert {u["email"] for u in everyone} == REAL_EMAILS | set(DEMO_EMAILS.values())
    assert {u["email"] for u in everyone if u["demo"]} == set(DEMO_EMAILS.values())


def test_a_login_of_the_demo_admin_account_is_no_wider_a_view(access_client: TestClient) -> None:
    """The password judges are given opens the account, not a view of the real users."""
    reply = access_client.post(
        "/api/auth/login", json={"email": DEMO_EMAILS["admin"], "password": DEMO_ADMIN_PASSWORD}
    )
    headers = {"Authorization": f"Bearer {reply.json()['token']}"}
    assert {u["email"] for u in _listed(access_client, headers)} == set(DEMO_EMAILS.values())


def test_users_invited_from_a_demo_session_are_the_demos_to_manage(
    access_client: TestClient,
) -> None:
    demo_admin = _demo(access_client, "admin")
    sent = access_client.post(
        "/api/admin/invites",
        headers=demo_admin,
        json={"email": "visitor@example.com", "role": "employee"},
    )
    assert sent.status_code == 201
    code = sent.json()["code"]
    registered = access_client.post(
        "/api/auth/register",
        json={
            "email": "visitor@example.com",
            "code": code,
            "name": "Visitor",
            "password": "a visitor password",
        },
    )
    assert registered.status_code == 201
    accounts = access_client.app.state.accounts  # type: ignore[attr-defined]
    visitor = accounts.user_by_email("visitor@example.com")
    assert visitor.demo_origin is True and visitor.demo is False
    assert "visitor@example.com" in {u["email"] for u in _listed(access_client, demo_admin)}
    # theirs to manage: disable, and delete
    patched = access_client.patch(
        f"/api/admin/users/{visitor.id}", headers=demo_admin, json={"status": "disabled"}
    )
    assert patched.status_code == 200
    assert (
        access_client.delete(f"/api/admin/users/{visitor.id}", headers=demo_admin).status_code
        == 204
    )
    # a user invited by a real admin is not
    real_admin = _real(access_client, "admin")
    code = access_client.post(
        "/api/admin/invites",
        headers=real_admin,
        json={"email": "real@example.com", "role": "employee"},
    ).json()["code"]
    access_client.post(
        "/api/auth/register",
        json={
            "email": "real@example.com",
            "code": code,
            "name": "Real",
            "password": "a real password",
        },
    )
    assert "real@example.com" not in {u["email"] for u in _listed(access_client, demo_admin)}


def test_a_demo_session_cannot_invite_an_admin(access_client: TestClient) -> None:
    reply = access_client.post(
        "/api/admin/invites",
        headers=_demo(access_client, "admin"),
        json={"email": "boss@example.com", "role": "admin"},
    )
    assert reply.status_code == 403
    assert access_client.app.state.accounts.user_by_email("boss@example.com") is None  # type: ignore[attr-defined]


def test_the_invites_of_demo_sessions_are_capped_per_day(access_settings: Settings) -> None:
    capped = replace(access_settings, demo_invites_per_day=2)
    app = create_app(capped, agent=NullAgentRunner())
    with TestClient(app) as client:
        demo_admin = _demo(client, "admin")

        def invite(n: int) -> httpx.Response:
            return client.post(
                "/api/admin/invites",
                headers=demo_admin,
                json={"email": f"v{n}@example.com", "role": "rep"},
            )

        assert [invite(n).status_code for n in (1, 2, 3)] == [201, 201, 429]
        # all demo sessions together: a second demo admin session shares the count
        assert (
            client.post(
                "/api/admin/invites",
                headers=_demo(client, "admin"),
                json={"email": "v4@example.com", "role": "rep"},
            ).status_code
            == 429
        )
        # a real admin is not capped (and not counted)
        real = _real(client, "admin")
        assert (
            client.post(
                "/api/admin/invites", headers=real, json={"email": "v5@example.com", "role": "rep"}
            ).status_code
            == 201
        )
        # tomorrow (UTC) there is room again
        client.app.state.accounts.clock = lambda: datetime.now(UTC) + timedelta(days=1, minutes=1)  # type: ignore[attr-defined]
        assert (
            client.get("/api/auth/me", headers=demo_admin).status_code == 401
        )  # 8 h session ended
        fresh = _demo(client, "admin")
        assert (
            client.post(
                "/api/admin/invites", headers=fresh, json={"email": "v6@example.com", "role": "rep"}
            ).status_code
            == 201
        )


def test_a_demo_invite_tells_nothing_about_the_real_users(access_client: TestClient) -> None:
    demo_admin = _demo(access_client, "admin")
    real_admin = _real(access_client, "admin")
    # a real pending invite, which a demo session must neither replace nor detect
    pending = access_client.post(
        "/api/admin/invites",
        headers=real_admin,
        json={"email": "pending@example.com", "role": "employee"},
    ).json()["code"]

    def attempt(email: str) -> httpx.Response:
        return access_client.post(
            "/api/admin/invites", headers=demo_admin, json={"email": email, "role": "employee"}
        )

    replies = [
        attempt(EMAILS["employee"]),  # a real user
        attempt(DEMO_EMAILS["employee"]),  # a demo user
        attempt("pending@example.com"),  # a real pending invite
    ]
    assert {(r.status_code, r.text) for r in replies} == {(replies[0].status_code, replies[0].text)}
    assert replies[0].status_code == 409
    assert attempt("fresh@example.com").status_code == 201
    # the real pending invite still works
    done = access_client.post(
        "/api/auth/register",
        json={
            "email": "pending@example.com",
            "code": pending,
            "name": "Pending",
            "password": "a pending password",
        },
    )
    assert done.status_code == 201
    # and it left no mark of the demo on that account
    assert (
        access_client.app.state.accounts.user_by_email("pending@example.com").demo_origin is False
    )  # type: ignore[attr-defined]


def test_judges_unlock_in_a_demo_session_still_needs_the_admin_password(
    access_client: TestClient,
) -> None:
    employee = _demo(access_client, "employee")
    sid = access_client.post("/api/sessions", headers=employee).json()["id"]
    store = access_client.app.state.services.store  # type: ignore[attr-defined]
    store.add_message(sid, "tool", {"name": "compare", "input": {"secret": "engine"}}, False)
    for wrong in ("", DEMO_USER_PASSWORD, "judges"):
        reply = access_client.post(
            "/api/auth/judges-unlock", headers=employee, json={"password": wrong}
        )
        assert reply.status_code == 401
    assert [
        m["role"]
        for m in access_client.get(f"/api/sessions/{sid}", headers=employee).json()["messages"]
    ] == []
    unlock = access_client.post(
        "/api/auth/judges-unlock", headers=employee, json={"password": DEMO_ADMIN_PASSWORD}
    )
    assert unlock.status_code == 204
    roles = [
        m["role"]
        for m in access_client.get(f"/api/sessions/{sid}", headers=employee).json()["messages"]
    ]
    assert roles == ["tool"]


# --- the flags off: nothing changes -----------------------------------------------------------


def test_with_both_flags_off_everything_is_as_it_was(access_settings: Settings) -> None:
    """Seed users may carry `demo`; with the flags off it means nothing."""
    off = replace(access_settings, judges_unlock=False, demo_login=False)
    app = create_app(off, agent=NullAgentRunner())
    with TestClient(app) as client:
        admin = _real(client, "admin")
        listed = _listed(client, admin)
        assert all(set(u) == USER_FIELDS for u in listed)  # no `demo` key
        assert {u["email"] for u in listed} == REAL_EMAILS | set(DEMO_EMAILS.values())
        me = client.get("/api/auth/me", headers=admin).json()
        assert me == {"name": "Admin", "role": "admin"}
        health = client.get("/api/health").json()
        assert "demo_login" not in health and "judges_unlock" not in health
        for path in ("/api/auth/demo-login", "/api/auth/judges-unlock", "/api/auth/judges-lock"):
            assert path not in app.openapi()["paths"]
        # a demo-marked account is just an account: it can be disabled, and deleted
        target = _uid(client, DEMO_EMAILS["rep"])
        assert (
            client.patch(
                f"/api/admin/users/{target}", headers=admin, json={"status": "disabled"}
            ).status_code
            == 200
        )
        assert client.delete(f"/api/admin/users/{target}", headers=admin).status_code == 204
        # and an admin sees every user whatever account it is
        demo_admin = client.post(
            "/api/auth/login", json={"email": DEMO_EMAILS["admin"], "password": DEMO_ADMIN_PASSWORD}
        )
        headers = {"Authorization": f"Bearer {demo_admin.json()['token']}"}
        assert len(_listed(client, headers)) == len(REAL_EMAILS) + 2


def test_flags_without_accounts_do_nothing(access_settings: Settings) -> None:
    no_accounts = replace(access_settings, auth=False, seed_users=())
    assert not no_accounts.demo_login_on and not no_accounts.judges_unlock_on
    with TestClient(create_app(no_accounts, agent=NullAgentRunner())) as client:
        assert client.post(DEMO_LOGIN, json={"role": "admin"}).status_code == 404
        assert client.post("/api/auth/judges-unlock", json={"password": "x"}).status_code == 404

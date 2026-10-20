"""/api/auth: register, login, logout, me, and what every failure looks like."""

import logging
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import EMAILS, PASSWORD
from fastapi import Depends
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.auth.codes import hash_secret
from compass.state.accounts import Accounts

REGISTER_ERROR = "הקוד או המייל אינם תקינים"
LOGIN_ERROR = "מייל או סיסמה שגויים"
HINT = "נסו שוב בעוד כמה דקות"
NEW_PASSWORD = "a long new password"


def _register(client: TestClient, **overrides: str) -> httpx.Response:
    body = {
        "email": "new@example.com",
        "code": "",
        "name": "New Person",
        "password": NEW_PASSWORD,
    } | overrides
    return client.post("/api/auth/register", json=body)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- the flag ---------------------------------------------------------------------------------


def test_with_the_flag_off_the_routes_do_not_exist(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings())) as client:
        for method, path in (
            ("post", "/api/auth/register"),
            ("post", "/api/auth/login"),
            ("post", "/api/auth/logout"),
            ("get", "/api/auth/me"),
        ):
            assert getattr(client, method)(path).status_code == 404, path
        assert not [p for p in client.get("/openapi.json").json()["paths"] if "/auth/" in p]


# --- register ---------------------------------------------------------------------------------


def test_register_with_an_invite_logs_in(client: TestClient, accounts: Accounts) -> None:
    code = accounts.create_invite("New@Example.com ", "employee", "admin-id", ttl_hours=48)
    assert len(code) == 11 and code[5] == "-"
    response = _register(client, code=code)
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"token", "name", "role"}
    assert (body["name"], body["role"]) == ("New Person", "employee")

    me = client.get("/api/auth/me", headers=_bearer(body["token"]))
    assert me.status_code == 200 and me.json() == {"name": "New Person", "role": "employee"}
    user = accounts.user_by_email("new@example.com")
    assert user is not None and user.last_login_at is not None and user.status == "active"
    assert user.password_hash.startswith("$argon2id$")


def test_the_invite_decides_the_role(client: TestClient, accounts: Accounts) -> None:
    code = accounts.create_invite("rep2@example.com", "rep", "admin-id", ttl_hours=48)
    body = _register(client, email="rep2@example.com", code=code).json()
    assert body["role"] == "rep"


@pytest.mark.parametrize("spell", [str.lower, lambda c: c.replace("-", ""), lambda c: f" {c} "])
def test_the_code_is_forgiving_about_how_it_is_typed(
    client: TestClient, accounts: Accounts, spell: Callable[[str], str]
) -> None:
    code = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    assert _register(client, code=spell(code)).status_code == 201


def test_a_code_is_single_use(client: TestClient, accounts: Accounts) -> None:
    code = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    assert _register(client, code=code).status_code == 201
    assert _register(client, code=code).status_code == 400


def test_two_registrations_with_one_code_cannot_both_win(
    accounts: Accounts, password_hash: str
) -> None:
    code = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    results: list[object] = []
    barrier = threading.Barrier(6)

    def attempt() -> None:
        barrier.wait()
        results.append(accounts.register("new@example.com", code, "N", password_hash, 8))

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(r is not None for r in results) == 1
    assert accounts.count_users() == 5  # the 4 seeded accounts and one


def test_a_code_expires(client: TestClient, accounts: Accounts) -> None:
    code = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    accounts.clock = lambda: datetime.now(UTC) + timedelta(hours=48, minutes=1)
    assert _register(client, code=code).status_code == 400


def test_a_replaced_invite_voids_the_old_code(client: TestClient, accounts: Accounts) -> None:
    old = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    new = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    assert old != new
    assert _register(client, code=old).status_code == 400
    assert _register(client, code=new).status_code == 201


def test_every_register_failure_is_the_same_response(
    client: TestClient, accounts: Accounts
) -> None:
    good = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    other = accounts.create_invite("other-invitee@example.com", "employee", "admin-id", 48)
    used = accounts.create_invite("used@example.com", "employee", "admin-id", 48)
    assert _register(client, email="used@example.com", code=used).status_code == 201
    # an invite for an address that already has an account
    existing = accounts.create_invite(EMAILS["employee"], "employee", "admin-id", 48)
    failures = {
        "no invite for the email": {"email": "nobody@example.com", "code": good},
        "someone else's code": {"code": other},
        "a wrong code": {"code": "AAAAA-AAAAA"},
        "an empty code": {"code": ""},
        "a used code": {"email": "used@example.com", "code": used},
        "an existing account": {"email": EMAILS["employee"], "code": existing},
        "no name": {"code": good, "name": "  "},
        "a long name": {"code": good, "name": "x" * 61},
        "no @": {"email": "new.example.com", "code": good},
    }
    seen = {}
    for kind, overrides in failures.items():
        response = _register(client, **overrides)
        seen[kind] = (response.status_code, response.json()["detail"])
    assert set(seen.values()) == {(400, REGISTER_ERROR)}, seen
    # none of them used the good code up
    assert _register(client, code=good).status_code == 201


PASSWORD_LENGTH = "הסיסמה צריכה להיות באורך 10 עד 128 תווים"
PASSWORD_EMAIL = "הסיסמה צריכה להיות שונה מהמייל"


def test_a_bad_password_is_told_specifically_and_before_the_invite(
    client: TestClient, accounts: Accounts
) -> None:
    good = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    cases = {
        "short": ("short", PASSWORD_LENGTH),
        "long": ("x" * 129, PASSWORD_LENGTH),
        "the email": ("New@Example.com", PASSWORD_EMAIL),
    }
    for kind, (password, message) in cases.items():
        # with a valid invite, a wrong code, and no invite at all: the same specific answer, so it
        # says nothing about invites
        for overrides in (
            {"code": good},
            {"code": "AAAAA-AAAAA"},
            {"email": "nobody@example.com", "code": "AAAAA-AAAAA"},
        ):
            reply = _register(client, password=password, **overrides)
            if overrides.get("email") == "nobody@example.com" and kind == "the email":
                continue  # (that password is not this email's address)
            assert (reply.status_code, reply.json()["detail"]) == (400, message), (kind, overrides)
    # none of that used the invite up
    assert _register(client, code=good).status_code == 201


def test_register_is_rate_limited_per_ip(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(auth=True, login_per_ip_per_minute=3))) as client:
        statuses = [_register(client, code="AAAAA-AAAAA").status_code for _ in range(5)]
    assert statuses == [400, 400, 400, 429, 429]


# --- login ------------------------------------------------------------------------------------


def test_login_returns_a_token_name_and_role(client: TestClient, accounts: Accounts) -> None:
    response = client.post(
        "/api/auth/login", json={"email": " DANA@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"token", "name", "role"} and body["role"] == "employee"
    user = accounts.user_by_email(EMAILS["employee"])
    assert user is not None and user.last_login_at is not None
    me = client.get("/api/auth/me", headers=_bearer(body["token"]))
    assert me.json() == {"name": "Employee", "role": "employee"}  # no email


def test_every_login_failure_is_the_same_response(client: TestClient, accounts: Accounts) -> None:
    with accounts.store._write() as (conn, _):
        conn.execute("UPDATE users SET status = 'disabled' WHERE email = ?", (EMAILS["other"],))
    attempts = {
        "unknown email": {"email": "nobody@example.com", "password": PASSWORD},
        "wrong password": {"email": EMAILS["employee"], "password": PASSWORD + "x"},
        "a disabled user, right password": {"email": EMAILS["other"], "password": PASSWORD},
        "empty password": {"email": EMAILS["employee"], "password": ""},
    }
    seen = {}
    for kind, body in attempts.items():
        response = client.post("/api/auth/login", json=body)
        seen[kind] = (response.status_code, response.json()["detail"])
    assert set(seen.values()) == {(401, LOGIN_ERROR)}, seen


def test_an_unknown_email_costs_a_verification_too(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from compass.api import auth as auth_module
    from compass.auth.passwords import dummy_hash

    hashes: list[str] = []
    real = auth_module.verify_password

    def spy(password_hash: str, password: str) -> bool:
        hashes.append(password_hash)
        return real(password_hash, password)

    monkeypatch.setattr(auth_module, "verify_password", spy)
    client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert hashes == [dummy_hash()]


def test_five_failures_lock_the_email(client: TestClient) -> None:
    bad = {"email": EMAILS["employee"], "password": "wrong password"}
    assert [client.post("/api/auth/login", json=bad).status_code for _ in range(5)] == [401] * 5
    locked = client.post("/api/auth/login", json=bad)
    assert locked.status_code == 429 and locked.json() == {"detail": f"{LOGIN_ERROR}. {HINT}"}
    assert "retry-after" not in locked.headers  # no lock details
    # even the right password is refused while it is locked
    right = client.post("/api/auth/login", json={**bad, "password": PASSWORD})
    assert right.status_code == 429 and right.json() == locked.json()
    # another account is not affected
    ok = client.post("/api/auth/login", json={"email": EMAILS["rep"], "password": PASSWORD})
    assert ok.status_code == 200


def test_an_invented_email_locks_the_same_way(client: TestClient) -> None:
    """A lock must not tell a real address from an invented one."""
    bodies = []
    for email in (EMAILS["employee"], "nobody@example.com"):
        bad = {"email": email, "password": "wrong password"}
        statuses = [client.post("/api/auth/login", json=bad).status_code for _ in range(7)]
        assert statuses == [401] * 5 + [429] * 2
        bodies.append(client.post("/api/auth/login", json=bad).json())
    assert bodies[0] == bodies[1]


def test_a_success_clears_the_failures(client: TestClient) -> None:
    bad = {"email": EMAILS["employee"], "password": "wrong password"}
    good = {"email": EMAILS["employee"], "password": PASSWORD}
    for _ in range(4):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    assert client.post("/api/auth/login", json=good).status_code == 200
    for _ in range(4):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    assert client.post("/api/auth/login", json=good).status_code == 200


def test_a_lock_from_one_address_does_not_lock_the_email_elsewhere(
    auth_settings: Settings,
) -> None:
    """During the final nobody in the room can lock the judges' demo account out."""
    settings = replace(auth_settings, trust_proxy=True)
    with TestClient(create_app(settings)) as client:

        def login(password: str, ip: str) -> httpx.Response:
            return client.post(
                "/api/auth/login",
                json={"email": EMAILS["employee"], "password": password},
                headers={"X-Forwarded-For": ip},
            )

        assert [login("wrong password", "198.51.100.1").status_code for _ in range(6)] == [
            401,
            401,
            401,
            401,
            401,
            429,
        ]
        assert login(PASSWORD, "198.51.100.1").status_code == 429  # locked for that address
        assert login(PASSWORD, "198.51.100.2").status_code == 200  # not for another


def test_many_addresses_cannot_lock_an_email_out_but_a_flood_ends(
    auth_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    settings = replace(auth_settings, trust_proxy=True, login_email_ceiling=8)
    with TestClient(create_app(settings)) as client:
        caplog.set_level(logging.INFO)

        def login(password: str, n: int) -> httpx.Response:
            return client.post(
                "/api/auth/login",
                json={"email": EMAILS["employee"], "password": password},
                headers={"X-Forwarded-For": f"198.51.100.{n}"},
            )

        assert [login("wrong password", n).status_code for n in range(1, 9)] == [401] * 8
        # eight failures from eight addresses: now the email itself is locked, for everyone
        refused = login(PASSWORD, 200)
        assert refused.status_code == 429 and HINT in refused.json()["detail"]
    assert "ceiling" in caplog.text and EMAILS["employee"] not in caplog.text


def test_the_lock_ends(client: TestClient) -> None:
    guard = client.app.state.login_guard
    now = [1000.0]
    guard.clock = lambda: now[0]
    bad = {"email": EMAILS["employee"], "password": "wrong password"}
    for _ in range(5):
        client.post("/api/auth/login", json=bad)
    good = {"email": EMAILS["employee"], "password": PASSWORD}
    assert client.post("/api/auth/login", json=good).status_code == 429
    now[0] += 15 * 60 - 1
    assert client.post("/api/auth/login", json=good).status_code == 429
    now[0] += 2
    assert client.post("/api/auth/login", json=good).status_code == 200


def test_login_is_limited_per_ip(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(auth=True, login_per_ip_per_minute=4)
    with TestClient(create_app(settings)) as client:
        statuses = [
            client.post(
                "/api/auth/login", json={"email": f"user{i}@example.com", "password": "x"}
            ).status_code
            for i in range(6)
        ]
    assert statuses == [401, 401, 401, 401, 429, 429]


# --- logout, expiry and the guards ------------------------------------------------------------


def test_logout_revokes_the_token(
    client: TestClient, login: Callable[[str], dict[str, str]]
) -> None:
    headers = login("employee")
    other = login("employee")  # a second login session of the same user
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/auth/me", headers=other).status_code == 200  # only this one
    assert client.post("/api/auth/logout", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer not-a-token"},
        {"Authorization": "Basic YTpi"},
        {"Authorization": "Token abc"},
    ],
)
def test_no_valid_token_is_401(client: TestClient, headers: dict[str, str]) -> None:
    for method, path in (("get", "/api/auth/me"), ("post", "/api/auth/logout")):
        response = getattr(client, method)(path, headers=headers)
        assert response.status_code == 401 and response.headers["www-authenticate"] == "Bearer"


def test_a_login_session_ends_after_8_hours_absolute(
    client: TestClient, accounts: Accounts, login: Callable[[str], dict[str, str]]
) -> None:
    start = datetime.now(UTC)
    headers = login("employee")
    accounts.clock = lambda: start + timedelta(hours=7, minutes=59)
    assert client.get("/api/auth/me", headers=headers).status_code == 200  # activity...
    accounts.clock = lambda: start + timedelta(hours=8, minutes=1)
    assert client.get("/api/auth/me", headers=headers).status_code == 401  # ...does not extend it


def test_the_session_ttl_is_a_setting(
    make_settings: Callable[..., Settings], password_hash: str
) -> None:
    from compass.auth.seed import SeedUser

    settings = make_settings(
        auth=True,
        session_ttl_hours=1,
        seed_users=(SeedUser("a@example.com", "A", "employee", password_hash),),
    )
    with TestClient(create_app(settings)) as client:
        token = client.post(
            "/api/auth/login", json={"email": "a@example.com", "password": PASSWORD}
        ).json()["token"]
        accounts: Accounts = client.app.state.accounts
        accounts.clock = lambda: datetime.now(UTC) + timedelta(minutes=61)
        assert client.get("/api/auth/me", headers=_bearer(token)).status_code == 401


def test_a_disabled_user_is_refused_and_all_their_sessions_end(
    client: TestClient, accounts: Accounts, login: Callable[[str], dict[str, str]]
) -> None:
    first, second = login("other"), login("other")
    with accounts.store._write() as (conn, _):
        conn.execute("UPDATE users SET status = 'disabled' WHERE email = ?", (EMAILS["other"],))
    assert client.get("/api/auth/me", headers=first).status_code == 401
    with accounts.store._write() as (conn, _):  # even when switched back on, the sessions are gone
        conn.execute("UPDATE users SET status = 'active' WHERE email = ?", (EMAILS["other"],))
    assert client.get("/api/auth/me", headers=second).status_code == 401


def test_role_guards(auth_settings: Settings, password_hash: str) -> None:
    app = create_app(auth_settings)
    auth = app.state.auth
    # the guards are plain dependencies: mount two probe routes on the real app

    def only_admin(user=Depends(auth.require_role("admin"))) -> dict[str, str]:  # type: ignore[no-untyped-def]  # noqa: B008
        return {"role": user.role}

    def rep_or_admin(user=Depends(auth.require_role("rep", "admin"))) -> dict[str, str]:  # type: ignore[no-untyped-def]  # noqa: B008
        return {"role": user.role}

    app.add_api_route("/api/_probe/admin", only_admin, methods=["GET"])
    app.add_api_route("/api/_probe/rep", rep_or_admin, methods=["GET"])
    with TestClient(app) as client:
        tokens = {
            who: _bearer(
                client.post(
                    "/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD}
                ).json()["token"]
            )
            for who in ("employee", "rep", "admin")
        }
        expected = {
            "/api/_probe/admin": {"employee": 403, "rep": 403, "admin": 200},
            "/api/_probe/rep": {"employee": 403, "rep": 200, "admin": 200},
        }
        for path, by_role in expected.items():
            assert client.get(path).status_code == 401
            for who, status in by_role.items():
                assert client.get(path, headers=tokens[who]).status_code == status, (path, who)


# --- nothing secret is stored, returned or logged ---------------------------------------------


def test_only_hashes_are_stored(client: TestClient, accounts: Accounts) -> None:
    code = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    registered = _register(client, code=code).json()
    logged_in = client.post(
        "/api/auth/login", json={"email": EMAILS["employee"], "password": PASSWORD}
    ).json()
    with accounts.store._read() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE token_hash IN (?, ?)",
                (hash_secret(registered["token"]), hash_secret(logged_in["token"])),
            ).fetchone()[0]
            == 2
        )
        invite = conn.execute("SELECT code_hash FROM invites").fetchone()
    assert invite[0] == hash_secret(code.replace("-", ""))
    # and nowhere in the database file, its write-ahead log included
    raw = b"".join(
        p.read_bytes()
        for p in accounts.store.path.parent.glob(accounts.store.path.name + "*")
        if p.is_file()
    )
    for secret in (
        registered["token"],
        logged_in["token"],
        code,
        code.replace("-", ""),
        PASSWORD,
        NEW_PASSWORD,
    ):
        assert secret.encode() not in raw


def test_nothing_secret_reaches_the_logs(
    client: TestClient, accounts: Accounts, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    code = accounts.create_invite("new@example.com", "employee", "admin-id", ttl_hours=48)
    registered = _register(client, code=code).json()
    logged_in = client.post(
        "/api/auth/login", json={"email": EMAILS["employee"], "password": PASSWORD}
    ).json()
    for _ in range(6):  # failures, then the lock
        client.post("/api/auth/login", json={"email": EMAILS["rep"], "password": "wrong one 123"})
    client.post("/api/auth/logout", headers=_bearer(logged_in["token"]))
    client.get("/api/auth/me", headers=_bearer("bad-token-value"))
    logs = caplog.text
    for secret in (
        registered["token"],
        logged_in["token"],
        code,
        code.replace("-", ""),
        PASSWORD,
        NEW_PASSWORD,
        "wrong one 123",
        "bad-token-value",
        "$argon2id$",
        "new@example.com",
        EMAILS["employee"],
        EMAILS["rep"],
    ):
        assert secret not in logs, secret
    assert "compass.auth" in logs  # it does log, by user id


def test_a_malformed_body_does_not_echo_the_input(client: TestClient) -> None:
    secret = "p" * 2000
    for path, body in (
        ("/api/auth/login", {"email": "a@example.com", "password": secret}),
        ("/api/auth/login", {"email": "a@example.com", "password": "x", "extra": secret}),
        (
            "/api/auth/register",
            {"email": "a@example.com", "code": "x", "name": "n", "password": secret},
        ),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 422
        assert secret not in response.text and "input" not in response.json()["detail"][0]


# --- CORS -------------------------------------------------------------------------------------


def test_authorization_is_allowed_from_the_ui_origin(
    make_settings: Callable[..., Settings], password_hash: str
) -> None:
    origin = "https://compass-web.example.com"
    settings = make_settings(auth=True, cors_origins=(origin,))
    with TestClient(create_app(settings)) as client:
        for path in ("/api/auth/login", "/api/auth/me", "/api/sessions/x/events"):
            preflight = client.options(
                path,
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST" if path.endswith("login") else "GET",
                    "Access-Control-Request-Headers": "authorization,content-type,last-event-id",
                },
            )
            assert preflight.status_code == 200, path
            allowed = preflight.headers["access-control-allow-headers"].lower()
            assert "authorization" in allowed and "last-event-id" in allowed
            assert preflight.headers["access-control-allow-origin"] == origin
        refused = client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert "access-control-allow-origin" not in refused.headers
        actual = client.get("/api/auth/me", headers={"Origin": origin})
        assert actual.status_code == 401
        assert actual.headers["access-control-allow-origin"] == origin

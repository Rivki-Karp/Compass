"""Stage 5: the admin manages access, and only access."""

import logging
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from authkit import EMAILS, PASSWORD, STATIC_ADMIN
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner
from compass.auth.passwords import hash_password
from compass.state.accounts import Accounts, LastAdminError

USER_FIELDS = {"id", "email", "name", "role", "status", "created_at", "last_login_at"}
TODAY = {"kind": "company_car", "car_id": "CAR-09", "participation": 300}
ATTO = "alternative_participation:CAR-10"
NEW = "newhire@example.com"
NEW_PASSWORD = "a long new password"


def _login(client: TestClient, who: str) -> dict[str, str]:
    reply = client.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['token']}"}


@pytest.fixture
def admin(full_client: TestClient) -> dict[str, str]:
    return _login(full_client, "admin")


def _invite(client: TestClient, headers: dict[str, str], email: str = NEW, role: str = "employee"):  # type: ignore[no-untyped-def]
    return client.post("/api/admin/invites", headers=headers, json={"email": email, "role": role})


def _user_id(client: TestClient, who: str) -> str:
    user = client.app.state.accounts.user_by_email(EMAILS[who])  # type: ignore[attr-defined]
    return user.id  # type: ignore[no-any-return]


# --- who may --------------------------------------------------------------------------------

ROUTES = [
    ("get", "/api/admin/users", {}),
    ("post", "/api/admin/invites", {"json": {"email": NEW, "role": "employee"}}),
    ("patch", "/api/admin/users/x", {"json": {"role": "rep"}}),
    ("delete", "/api/admin/users/x", {}),
]


@pytest.mark.parametrize(("method", "path", "kwargs"), ROUTES)
def test_only_an_admin(full_client: TestClient, method: str, path: str, kwargs: Any) -> None:
    def call(headers: dict[str, str]) -> int:
        return getattr(full_client, method)(path, headers=headers, **kwargs).status_code

    assert call({}) == 401
    assert call({"Authorization": f"Bearer {STATIC_ADMIN}"}) == 401
    assert call(_login(full_client, "employee")) == 403
    assert call(_login(full_client, "rep")) == 403
    assert call(_login(full_client, "admin")) in (200, 201, 404)


# --- list and invite ------------------------------------------------------------------------


def test_the_user_list_has_access_fields_only(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    users = full_client.get("/api/admin/users", headers=admin).json()
    assert {u["email"] for u in users} == set(EMAILS.values())
    for user in users:
        assert set(user) == USER_FIELDS
    assert "argon2" not in str(users) and PASSWORD not in str(users)
    me = next(u for u in users if u["email"] == EMAILS["admin"])
    assert me["role"] == "admin" and me["status"] == "active" and me["last_login_at"]


def test_an_invite_shows_its_code_once_and_registers_the_person(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    created = _invite(full_client, admin, " NewHire@Example.com ", "rep")
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"code", "email", "role", "expires_at"}
    assert (body["email"], body["role"]) == (NEW, "rep") and len(body["code"]) == 11
    # the code is not in any later answer, nor stored
    assert body["code"] not in full_client.get("/api/admin/users", headers=admin).text
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    on_disk = b"".join(
        p.read_bytes() for p in store.path.parent.glob(store.path.name + "*") if p.is_file()
    )
    for shown in (body["code"], body["code"].replace("-", "")):
        assert shown.encode() not in on_disk
    # they register with it, as a rep, under their own name
    registered = full_client.post(
        "/api/auth/register",
        json={"email": NEW, "code": body["code"], "name": "Noa Levi", "password": NEW_PASSWORD},
    )
    assert registered.status_code == 201 and registered.json()["role"] == "rep"
    listed = {u["email"]: u for u in full_client.get("/api/admin/users", headers=admin).json()}
    assert listed[NEW]["name"] == "Noa Levi" and listed[NEW]["role"] == "rep"


def test_a_new_invite_replaces_the_old_and_ttl_is_a_setting(
    full_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    settings = Settings(**{**full_settings.__dict__, "invite_ttl_hours": 2})
    caplog.set_level(logging.DEBUG)
    with TestClient(create_app(settings, agent=NullAgentRunner())) as client:
        admin = _login(client, "admin")
        first = _invite(client, admin).json()
        second = _invite(client, admin).json()
        assert first["code"] != second["code"]
        register = {"email": NEW, "name": "N", "password": NEW_PASSWORD}

        def register_with(code: str) -> int:
            return client.post("/api/auth/register", json={**register, "code": code}).status_code

        assert register_with(first["code"]) == 400
        assert register_with(second["code"]) == 201
        gap = datetime.fromisoformat(second["expires_at"]) - datetime.now(UTC)
        assert 1.9 * 3600 < gap.total_seconds() <= 2 * 3600
    assert first["code"] not in caplog.text and second["code"] not in caplog.text
    assert NEW not in caplog.text


def test_inviting_an_existing_user_is_refused_with_a_clear_message(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    reply = _invite(full_client, admin, EMAILS["employee"].upper())
    assert reply.status_code == 409
    assert "מחקו אותו קודם" in reply.json()["detail"]
    assert _invite(full_client, admin, "not-an-email").status_code == 422
    assert _invite(full_client, admin, NEW, "boss").status_code == 422


# --- patch ----------------------------------------------------------------------------------


def test_change_a_role_and_disable_a_user(full_client: TestClient, admin: dict[str, str]) -> None:
    target = _user_id(full_client, "other")
    changed = full_client.patch(f"/api/admin/users/{target}", headers=admin, json={"role": "rep"})
    assert changed.status_code == 200 and changed.json()["role"] == "rep"
    assert set(changed.json()) == USER_FIELDS
    # the new role is in force on their next request
    theirs = _login(full_client, "other")
    assert full_client.get("/api/tickets", headers=theirs).status_code == 200
    # disabling ends their logins at once, and they cannot log in again
    disabled = full_client.patch(
        f"/api/admin/users/{target}", headers=admin, json={"status": "disabled"}
    )
    assert disabled.status_code == 200
    assert full_client.get("/api/auth/me", headers=theirs).status_code == 401
    login = {"email": EMAILS["other"], "password": PASSWORD}
    again = full_client.post("/api/auth/login", json=login)
    assert again.status_code == 401
    full_client.patch(f"/api/admin/users/{target}", headers=admin, json={"status": "active"})
    assert _login(full_client, "other")


def test_a_patch_names_only_known_fields_and_a_known_user(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    target = _user_id(full_client, "other")
    for body in ({"email": "x@example.com"}, {"role": "boss"}, {"status": "gone"}, {"name": "x"}):
        reply = full_client.patch(f"/api/admin/users/{target}", headers=admin, json=body)
        assert reply.status_code == 422
    nobody = full_client.patch("/api/admin/users/nobody", headers=admin, json={"role": "rep"})
    assert nobody.status_code == 404


def test_an_admin_cannot_touch_themselves(full_client: TestClient, admin: dict[str, str]) -> None:
    me = _user_id(full_client, "admin")
    for body in ({"role": "employee"}, {"status": "disabled"}, {"role": "admin"}):
        reply = full_client.patch(f"/api/admin/users/{me}", headers=admin, json=body)
        assert reply.status_code == 409 and "של עצמך" in reply.json()["detail"]
    assert full_client.delete(f"/api/admin/users/{me}", headers=admin).status_code == 409
    assert full_client.get("/api/auth/me", headers=admin).json()["role"] == "admin"


def test_the_last_active_admin_cannot_be_removed(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    accounts: Accounts = full_client.app.state.accounts  # type: ignore[attr-defined]
    me = _user_id(full_client, "admin")
    with pytest.raises(LastAdminError):
        accounts.update_user(me, "employee", None)
    with pytest.raises(LastAdminError):
        accounts.update_user(me, None, "disabled")
    with pytest.raises(LastAdminError):
        accounts.delete_user(me)
    assert accounts.user_by_id(me).role == "admin"  # type: ignore[union-attr]
    # with a second admin the first may go, and then the second is the last
    second = accounts.create_user("two@example.com", "Two", "admin", hash_password(PASSWORD))
    assert accounts.update_user(me, "employee", None) is not None
    with pytest.raises(LastAdminError):
        accounts.update_user(second.id, "rep", None)


def test_two_admins_cannot_remove_each_other(full_client: TestClient) -> None:
    accounts: Accounts = full_client.app.state.accounts  # type: ignore[attr-defined]
    first = _user_id(full_client, "admin")
    second = accounts.create_user("two@example.com", "Two", "admin", hash_password(PASSWORD)).id
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def remove(target: str) -> None:
        barrier.wait()
        try:
            accounts.update_user(target, None, "disabled")
            outcomes.append("removed")
        except LastAdminError:
            outcomes.append("refused")

    threads = [threading.Thread(target=remove, args=(t,)) for t in (first, second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["refused", "removed"] and accounts.count_active_admins() == 1


# --- delete ---------------------------------------------------------------------------------


def test_deleting_a_user_deletes_their_logins_and_conversations(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    theirs = _login(full_client, "other")
    mine = _login(full_client, "employee")
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    their_sessions = [
        full_client.post("/api/sessions", headers=theirs).json()["id"] for _ in range(2)
    ]
    keep = full_client.post("/api/sessions", headers=mine).json()["id"]
    first = their_sessions[0]
    full_client.post(f"/api/sessions/{first}/messages", headers=theirs, json={"text": "סוד"})

    target = _user_id(full_client, "other")
    assert full_client.delete(f"/api/admin/users/{target}", headers=admin).status_code == 204
    assert full_client.get("/api/auth/me", headers=theirs).status_code == 401
    assert (
        full_client.post(
            "/api/auth/login", json={"email": EMAILS["other"], "password": PASSWORD}
        ).status_code
        == 401
    )
    for sid in their_sessions:
        with pytest.raises(LookupError):
            store.session_status(sid)
    assert store.session_status(keep) == "active"  # someone else's, untouched
    users = full_client.get("/api/admin/users", headers=admin).json()
    assert EMAILS["other"] not in {u["email"] for u in users}
    # no reset: invited again, they start with nothing of the old
    code = _invite(full_client, admin, EMAILS["other"]).json()["code"]
    back = full_client.post(
        "/api/auth/register",
        json={"email": EMAILS["other"], "code": code, "name": "Avi", "password": NEW_PASSWORD},
    )
    assert back.status_code == 201
    newcomer = {"Authorization": f"Bearer {back.json()['token']}"}
    assert full_client.get("/api/conversations", headers=newcomer).json() == []


def test_deleting_a_user_clears_their_tickets_from_the_inbox(
    full_client: TestClient, admin: dict[str, str]
) -> None:
    theirs = _login(full_client, "other")
    sid = full_client.post("/api/sessions", headers=theirs).json()["id"]
    full_client.post(f"/api/sessions/{sid}/messages", headers=theirs, json={"text": "ATTO 3?"})
    for name, body in (
        (
            "save_profile",
            {
                "occupation_query": "מנהלת מוצר",
                "base_salary": 18500,
                "commissions": 0,
                "bonus": 0,
                "pension_percent": 6,
                "study_fund_percent": 2.5,
                "credit_points": 2.75,
                "children_under_23": 2,
            },
        ),
        ("set_current_situation", {"today": TODAY}),
        ("ask_representative", {"question": "?", "blocking_fields": [ATTO]}),
    ):
        reply = full_client.post(f"/api/sessions/{sid}/tools/{name}", headers=theirs, json=body)
        assert reply.json()["ok"]
    rep = _login(full_client, "rep")
    assert len(full_client.get("/api/tickets", headers=rep).json()) == 1
    full_client.delete(f"/api/admin/users/{_user_id(full_client, 'other')}", headers=admin)
    assert full_client.get("/api/tickets", headers=rep).json() == []


# --- the privacy rule, in the schemas -------------------------------------------------------

ALLOWED = USER_FIELDS | {"code", "expires_at", "detail"}
FORBIDDEN = (
    "message",
    "profile",
    "slot",
    "payslip",
    "conversation",
    "session",
    "salary",
    "scenario",
    "ticket",
    "event",
    "content",
    "text",
    "hash",
    "password",
    "token",
)


def _property_names(
    node: Any, schemas: dict[str, Any], seen: set[str] | None = None
) -> Iterator[str]:
    seen = set() if seen is None else seen
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            if name not in seen:
                seen.add(name)
                yield from _property_names(schemas[name], schemas, seen)
            return
        for key, value in node.items():
            if key == "properties":
                for prop, sub in value.items():
                    yield prop
                    yield from _property_names(sub, schemas, seen)
            else:
                yield from _property_names(value, schemas, seen)
    elif isinstance(node, list):
        for item in node:
            yield from _property_names(item, schemas, seen)


def test_no_admin_user_route_exposes_conversation_profile_or_payslip_fields(
    full_client: TestClient,
) -> None:
    spec = full_client.app.openapi()  # type: ignore[attr-defined]
    schemas = spec["components"]["schemas"]
    checked = 0
    for path, methods in spec["paths"].items():
        if not path.startswith("/api/admin/users") and path != "/api/admin/invites":
            continue
        for method, operation in methods.items():
            for status, response in operation["responses"].items():
                if not status.startswith("2"):
                    continue
                names = set(_property_names(response, schemas))
                assert names <= ALLOWED, (method, path, names - ALLOWED)
                assert not [n for n in names if any(w in n for w in FORBIDDEN)], (path, names)
                checked += 1
    assert checked >= 3
    # and a request body can set only what the admin is meant to set
    for name in ("InviteBody", "UserPatch"):
        assert set(schemas[name]["properties"]) <= {"email", "role", "status"}

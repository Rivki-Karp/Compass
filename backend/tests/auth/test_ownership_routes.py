"""Stage 3, the security core: every route that names a session goes through one ownership rule.

Two kinds of test. The router is walked (so a new route cannot skip the check unnoticed), and
every session route is called as {anonymous, another user, a rep, an admin, the owner}.
"""

import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from authkit import EMAILS, PASSWORD
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from live import SSEReader, live_server

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner
from compass.api.auth import GUARD_ATTR

# --- the router is enumerated ------------------------------------------------------------------

# Routes that need no login, and why. Everything else under /api must be classified below.
PUBLIC = {
    "/api/health": "liveness and the feature flags the UI reads",
    "/api/rules": "the company rules, not a person's data",
    "/api/catalog": "the car catalog",
    "/api/occupations": "the occupation list",
    "/api/auth/register": "how someone without an account gets one (an invite code is checked)",
    "/api/auth/login": "how someone logs in",
}
LOGIN_ONLY = {
    "/api/sessions": "starts a conversation owned by the caller",
    "/api/auth/logout": "ends the caller's own login",
    "/api/auth/me": "the caller's own name and role",
    "/api/conversations": "the caller's own conversations",
}


def api_routes(app: FastAPI) -> list[tuple[str, str, Any]]:
    """Every /api route, however FastAPI nests the routers: (methods, path, dependant)."""
    found = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        path = context.path or ""
        if isinstance(route, APIRoute) and path.startswith("/api"):
            found.append((str(sorted(route.methods)), path, getattr(context, "dependant", None)))
    return found


def guards(dependant: Any) -> dict[str, set[str]]:
    """The marked guards a route depends on (the whole dependency tree): kind -> details."""
    found: dict[str, set[str]] = {}

    def walk(dependant: Any) -> None:
        mark = getattr(dependant.call, GUARD_ATTR, None)
        if mark is not None:
            found.setdefault(mark[0], set()).update(mark[1])
        for sub in dependant.dependencies:
            walk(sub)

    walk(dependant)
    return found


def problems(app: FastAPI) -> list[str]:
    """Every /api route that is not classified, or lacks the guard its class requires."""
    found = []
    for methods, path, dependant in api_routes(app):
        have = guards(dependant)
        label = f"{methods} {path}"
        if "{session_id}" in path:
            ok = "owner" in have
        elif path in PUBLIC:
            ok = True
        elif path in LOGIN_ONLY:
            ok = "login" in have or "role" in have
        elif path.startswith("/api/tickets"):
            ok = have.get("role") == {"rep"}
        elif path.startswith("/api/admin"):
            ok = have.get("role") == {"admin"}
        else:
            ok = False  # a route nobody classified: decide what guards it, then list it here
        if not ok:
            found.append(label)
    return found


def test_every_route_is_guarded_as_its_class_requires(full_settings: Settings) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())
    assert problems(app) == []
    session_routes = [path for _, path, _ in api_routes(app) if "{session_id}" in path]
    # the six the brief lists, so a rename cannot make the walk above vacuous
    assert {p.removeprefix("/api/sessions/{session_id}") for p in session_routes} >= {
        "",
        "/messages",
        "/events",
        "/tools/{name}",
        "/payslip",
        "/payslip/confirm",
        "/current-car",
    }


def test_the_walk_catches_a_new_route_that_skips_the_check(full_settings: Settings) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())

    async def leak(session_id: str) -> dict[str, str]:
        return {"id": session_id}

    app.add_api_route("/api/sessions/{session_id}/export", leak, methods=["GET"])
    app.add_api_route("/api/something-new", leak, methods=["GET"])
    assert [p for p in problems(app) if "export" in p or "something-new" in p] == [
        "['GET'] /api/sessions/{session_id}/export",
        "['GET'] /api/something-new",
    ]


# --- the matrix --------------------------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
Actor = str  # "anonymous" | "employee" | "other" | "rep" | "admin"


def _upload_first(client: TestClient, sid: str, headers: dict[str, str]) -> None:
    sent = client.post(
        f"/api/sessions/{sid}/payslip",
        content=PNG,
        headers={**headers, "Content-Type": "image/png"},
    )
    assert sent.status_code == 201, sent.text


# name -> (method, path, request kwargs, what the owner gets, what the owner does first)
ROUTES: dict[str, tuple[str, str, dict[str, Any], int, Callable[..., None] | None]] = {
    "snapshot": ("get", "/api/sessions/{sid}", {}, 200, None),
    "message": ("post", "/api/sessions/{sid}/messages", {"json": {"text": "שלום"}}, 202, None),
    "tool": (
        "post",
        "/api/sessions/{sid}/tools/save_profile",
        {"json": {"base_salary": 18000}},
        200,
        None,
    ),
    "payslip": (
        "post",
        "/api/sessions/{sid}/payslip",
        {"content": PNG, "headers": {"Content-Type": "image/png"}},
        201,
        None,
    ),
    "payslip_confirm": (
        "post",
        "/api/sessions/{sid}/payslip/confirm",
        {"json": {"fields": {}}},
        200,
        _upload_first,
    ),
    "current_car": (
        "post",
        "/api/sessions/{sid}/current-car",
        {"json": {"choice": "no_car"}},
        200,
        None,
    ),
}


def _token(client: TestClient, who: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _untouched(client: TestClient, sid: str) -> bool:
    store = client.app.state.services.store  # type: ignore[attr-defined]
    return (
        store.messages(sid) == []
        and store.slots(sid) == {}
        and store.scenarios(sid) == {}
        and store.count_events(sid, ("payslip_extracted", "payslip_failed", "user_message")) == 0
        and store.tickets(session_id=sid) == []
    )


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_session_route_matrix(full_client: TestClient, route: str) -> None:
    method, template, kwargs, owner_status, first = ROUTES[route]
    people = {who: _token(full_client, who) for who in ("employee", "other", "rep", "admin")}
    sid = full_client.post("/api/sessions", headers=people["employee"]).json()["id"]
    path = template.format(sid=sid)

    def call(headers: dict[str, str] | None, where: str = path) -> httpx.Response:
        merged = {**kwargs.get("headers", {}), **(headers or {})}
        return getattr(full_client, method)(where, **{**kwargs, "headers": merged})

    # anonymous: 401, before the session is looked at (so the same for a made-up id)
    assert call(None).status_code == 401
    assert call(None, template.format(sid="not-a-session")).status_code == 401

    # anyone but the owner: 404, a rep and an admin included, and no effect on the session
    def shape(response: httpx.Response, own_id: str) -> str:
        return str(response.json()["detail"]).replace(own_id, "ID")

    shapes = set()
    for who in ("other", "rep", "admin"):
        response = call(people[who])
        assert response.status_code == 404, (who, response.status_code)
        shapes.add(shape(response, sid))
    assert _untouched(full_client, sid)
    # a session that does not exist looks exactly the same as another person's
    unknown = call(people["other"], template.format(sid="not-a-session"))
    assert unknown.status_code == 404
    assert shapes == {shape(unknown, "not-a-session")} == {"session ID not found"}
    # a static rep or admin token is no login
    for token in ("rep-static-token", "admin-static-token"):
        assert call({"Authorization": f"Bearer {token}"}).status_code == 401
    # the owner
    if first is not None:
        first(full_client, sid, people["employee"])
    assert call(people["employee"]).status_code == owner_status


def test_a_session_nobody_owns_is_closed_to_everyone(full_client: TestClient) -> None:
    """Created while accounts were off (no owner), then the flag turned on: fail closed."""
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    orphan = store.create_session()
    for who in ("employee", "rep", "admin"):
        response = full_client.get(f"/api/sessions/{orphan}", headers=_token(full_client, who))
        assert response.status_code == 404


def test_a_new_session_belongs_to_whoever_made_it(full_client: TestClient) -> None:
    assert full_client.post("/api/sessions").status_code == 401
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    for who in ("employee", "rep", "admin"):
        sid = full_client.post("/api/sessions", headers=_token(full_client, who)).json()["id"]
        owner = full_client.app.state.accounts.user_by_email(EMAILS[who])  # type: ignore[attr-defined]
        assert store.session_owner(sid) == owner.id


# --- the event stream, and replay --------------------------------------------------------------


def test_the_event_stream_and_its_replay_are_owned_too(full_settings: Settings) -> None:
    app = create_app(full_settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:

        def login(who: str) -> dict[str, str]:
            reply = http.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
            return {"Authorization": f"Bearer {reply.json()['token']}"}

        owner = login("employee")
        sid = http.post("/api/sessions", headers=owner).json()["id"]
        http.post(f"/api/sessions/{sid}/messages", headers=owner, json={"text": "ויתור על הרכב"})
        url = f"/api/sessions/{sid}/events"

        # not the owner: refused before any stream starts, replay position or not
        assert http.get(url).status_code == 401
        assert http.get(url, headers={"Last-Event-ID": "0"}).status_code == 401
        for who in ("other", "rep", "admin"):
            for extra in ({}, {"Last-Event-ID": "0"}):
                response = http.get(url, headers={**login(who), **extra})
                assert response.status_code == 404, (who, extra)
                assert "session_created" not in response.text and "ויתור" not in response.text
            assert http.get(url + "?after=0", headers=login(who)).status_code == 404

        # the owner: replay from the start, from a position, and the live tail
        full = f"{base}{url}"
        with SSEReader(full, headers={**owner, "Last-Event-ID": "0"}) as stream:
            assert stream.wait_for("session_created")["id"] == 1
            assert stream.wait_for("user_message")["id"] == 2
        with SSEReader(full, headers={**owner, "Last-Event-ID": "1"}) as stream:
            assert stream.wait_for("user_message")["id"] == 2
            assert not [e for e in stream.events if e.get("event") == "session_created"]
            http.post(f"/api/sessions/{sid}/messages", headers=owner, json={"text": "ועוד"})
            deadline = time.monotonic() + 10
            while not any(e.get("id") == 3 for e in stream.events):
                assert time.monotonic() < deadline, stream.events
                time.sleep(0.02)
        with SSEReader(f"{full}?after=2", headers=owner) as stream:
            assert stream.wait_for("user_message")["id"] == 3

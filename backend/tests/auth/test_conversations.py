"""Stage 4: the user's list of conversations, resuming one, and deleting one."""

import time
from dataclasses import replace
from typing import Any

import httpx
import pytest
from authkit import EMAILS, PASSWORD
from fastapi.testclient import TestClient
from live import SSEReader, live_server

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner

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
ATTO = "alternative_participation:CAR-10"


def _login(client: TestClient | httpx.Client, who: str) -> dict[str, str]:
    reply = client.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['token']}"}


def _tool(client: TestClient, sid: str, headers: dict[str, str], name: str, body: Any) -> Any:
    reply = client.post(f"/api/sessions/{sid}/tools/{name}", headers=headers, json=body)
    assert reply.json()["ok"], reply.json()
    return reply.json()


def _new(client: TestClient, headers: dict[str, str]) -> str:
    return client.post("/api/sessions", headers=headers).json()["id"]


def _say(client: TestClient, sid: str, headers: dict[str, str], text: str = "שלום") -> None:
    client.post(f"/api/sessions/{sid}/messages", headers=headers, json={"text": text})


def _profile(client: TestClient, sid: str, headers: dict[str, str]) -> None:
    client.post(f"/api/sessions/{sid}/messages", headers=headers, json={"text": "ומה עם ATTO 3?"})
    _tool(client, sid, headers, "save_profile", NOA)
    _tool(client, sid, headers, "set_current_situation", TODAY)


def _listing(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    reply = client.get("/api/conversations", headers=headers)
    assert reply.status_code == 200, reply.text
    return reply.json()  # type: ignore[no-any-return]


def test_the_list_needs_a_login_and_is_the_users_own(full_client: TestClient) -> None:
    assert full_client.get("/api/conversations").status_code == 401
    a, b = _login(full_client, "employee"), _login(full_client, "other")
    mine = _new(full_client, a)
    _say(full_client, mine, a)
    assert [c["id"] for c in _listing(full_client, a)] == [mine]
    assert _listing(full_client, b) == []
    # a rep and an admin have conversations of their own, and see nobody else's
    for who in ("rep", "admin"):
        assert _listing(full_client, _login(full_client, who)) == []


def test_a_conversation_with_a_message_and_no_comparison_is_new(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    sid = _new(full_client, headers)
    _say(full_client, sid, headers)
    (entry,) = _listing(full_client, headers)
    assert entry["id"] == sid and entry["title"] == "שיחה חדשה"
    assert (entry["status"], entry["diff"]) == ("none", None)
    assert set(entry) == {"id", "title", "updated_at", "status", "diff"}  # no email, no content


def test_a_waiver_is_titled_and_carries_the_diff_from_the_view(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    sid = _new(full_client, headers)
    _profile(full_client, sid, headers)
    result = _tool(full_client, sid, headers, "compare", {"alternative": {"kind": "waiver"}})
    (entry,) = _listing(full_client, headers)
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    view = store.last_comparison(sid)["view"]
    assert entry["title"] == "ויתור על הרכב"
    assert entry["diff"] == view["display_diff"] == result["comparison"]["display_diff"]
    assert entry["status"] == "final"


def test_a_comparison_of_cars_names_both(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    sid = _new(full_client, headers)
    _profile(full_client, sid, headers)
    _tool(
        full_client,
        sid,
        headers,
        "compare",
        {"alternative": {"kind": "car", "car_id": "CAR-10", "participation": 350}},
    )
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    view = store.last_comparison(sid)["view"]
    (entry,) = _listing(full_client, headers)
    assert entry["title"] == f"{view['today_title']} מול {view['alternative_title']}"
    assert "ATTO 3" in entry["title"] and entry["diff"] == view["display_diff"]


def test_pending_comes_from_the_view_and_settles_with_it(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    rep = _login(full_client, "rep")
    sid = _new(full_client, headers)
    _profile(full_client, sid, headers)
    _tool(
        full_client,
        sid,
        headers,
        "compare",
        {"alternative": {"kind": "car", "car_id": "CAR-10"}},
    )
    ask = {"question": "?", "blocking_fields": [ATTO]}
    _tool(full_client, sid, headers, "ask_representative", ask)
    (entry,) = _listing(full_client, headers)
    assert entry["status"] == "pending"
    (ticket,) = full_client.get("/api/tickets", headers=rep).json()
    answered = full_client.post(
        f"/api/tickets/{ticket['id']}/answer", headers=rep, json={"values": {ATTO: 350}}
    )
    assert answered.status_code == 200, answered.text
    (settled,) = _listing(full_client, headers)
    assert settled["status"] == "final"


def test_every_option_is_titled_by_the_group(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    sid = _new(full_client, headers)
    _profile(full_client, sid, headers)
    _tool(full_client, sid, headers, "list_options", {})
    (entry,) = _listing(full_client, headers)
    assert entry["title"].startswith("כל החלופות בקבוצה ")
    assert entry["diff"] is None and entry["status"] in ("final", "pending", "partial")


def test_the_newest_conversation_is_first(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    ids = []
    for _ in range(3):  # (each must have a message, or the next new conversation deletes it)
        ids.append(_new(full_client, headers))
        _say(full_client, ids[-1], headers)
    first, second, third = ids
    time.sleep(0.01)
    _say(full_client, first, headers)
    assert [c["id"] for c in _listing(full_client, headers)] == [first, third, second]


# --- resuming ----------------------------------------------------------------------------------


def test_resume_after_a_restart_and_in_another_browser(full_settings: Settings) -> None:
    """The same database under a new app (a restart in the same process lifetime), opened with a
    second login of the same account: the snapshot and the replay are what they were."""
    first = create_app(full_settings, agent=NullAgentRunner())
    with TestClient(first) as client:
        headers = _login(client, "employee")
        sid = _new(client, headers)
        _profile(client, sid, headers)
        _tool(client, sid, headers, "compare", {"alternative": {"kind": "waiver"}})
        before = client.get(f"/api/sessions/{sid}", headers=headers).json()
        entry_before = _listing(client, headers)

    second = create_app(full_settings, agent=NullAgentRunner())  # a restart: same file
    with live_server(second) as base, httpx.Client(base_url=base, timeout=10) as http:
        browser_two = _login(http, "employee")  # a different browser: a new login
        assert http.get("/api/conversations", headers=browser_two).json() == entry_before
        after = http.get(f"/api/sessions/{sid}", headers=browser_two).json()
        assert after == before
        assert after["last_comparison"] is not None and after["slots"]["base_salary"]
        with SSEReader(
            f"{base}/api/sessions/{sid}/events", headers={**browser_two, "Last-Event-ID": "0"}
        ) as stream:
            stream.wait_for("comparison_ready")
        # and it continues like any live session
        sent = http.post(f"/api/sessions/{sid}/messages", headers=browser_two, json={"text": "עוד"})
        assert sent.status_code == 202


def test_another_account_cannot_resume_it(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    sid = _new(full_client, headers)
    other = _login(full_client, "other")
    assert full_client.get(f"/api/sessions/{sid}", headers=other).status_code == 404


# --- delete ------------------------------------------------------------------------------------

SECRET_WORDS = "מילה-סודית-של-העובדת"


def _loaded(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    sid = _new(client, headers)
    client.post(
        f"/api/sessions/{sid}/messages", headers=headers, json={"text": f"ATTO 3? {SECRET_WORDS}"}
    )
    _tool(client, sid, headers, "save_profile", NOA)
    _tool(client, sid, headers, "set_current_situation", TODAY)
    _tool(client, sid, headers, "ask_representative", {"question": "?", "blocking_fields": [ATTO]})
    client.app.state.services.store.append_event(  # type: ignore[attr-defined]
        sid, "payslip_extracted", {"fields": {"base_salary": {"value": 18500}}, "dropped_keys": 0}
    )
    (ticket,) = client.app.state.services.store.tickets(session_id=sid)  # type: ignore[attr-defined]
    return sid, ticket.id


def test_delete_is_the_owners_only(full_client: TestClient) -> None:
    owner = _login(full_client, "employee")
    sid, _ = _loaded(full_client, owner)
    url = f"/api/conversations/{sid}"
    assert full_client.delete(url).status_code == 401
    for who in ("other", "rep", "admin"):
        assert full_client.delete(url, headers=_login(full_client, who)).status_code == 404
    assert [c["id"] for c in _listing(full_client, owner)] == [sid]  # still there
    assert full_client.delete(url, headers=owner).status_code == 204


def test_a_deleted_conversation_is_gone_everywhere(full_client: TestClient) -> None:
    owner, rep = _login(full_client, "employee"), _login(full_client, "rep")
    keep, _ = _loaded(full_client, owner)
    sid, ticket_id = _loaded(full_client, owner)
    assert len(full_client.get("/api/tickets", headers=rep).json()) == 2
    assert full_client.delete(f"/api/conversations/{sid}", headers=owner).status_code == 204

    # the list, and every route of the conversation: 404, as if it never existed
    assert [c["id"] for c in _listing(full_client, owner)] == [keep]
    gone = [
        ("get", f"/api/sessions/{sid}", {}),
        ("get", f"/api/sessions/{sid}/events", {}),
        ("post", f"/api/sessions/{sid}/messages", {"json": {"text": "x"}}),
        ("post", f"/api/sessions/{sid}/tools/save_profile", {"json": {"base_salary": 1}}),
        ("post", f"/api/sessions/{sid}/payslip/confirm", {"json": {"fields": {}}}),
        ("post", f"/api/sessions/{sid}/current-car", {"json": {"choice": "no_car"}}),
        ("delete", f"/api/conversations/{sid}", {}),
    ]
    for method, path, kwargs in gone:
        reply = getattr(full_client, method)(path, headers=owner, **kwargs)
        assert reply.status_code == 404, path
    # its tickets are gone for the rep, who still sees the other conversation's
    tickets = full_client.get("/api/tickets", headers=rep).json()
    assert [t["session_id"] for t in tickets] == [keep]
    assert full_client.post(
        f"/api/tickets/{ticket_id}/answer", headers=rep, json={"answer_text": "x"}
    ).status_code in (404, 409)


def test_nothing_of_the_content_is_left_in_the_database(full_client: TestClient) -> None:
    owner = _login(full_client, "employee")
    sid, _ = _loaded(full_client, owner)
    store = full_client.app.state.services.store  # type: ignore[attr-defined]

    def on_disk() -> bytes:
        return b"".join(
            p.read_bytes() for p in store.path.parent.glob(store.path.name + "*") if p.is_file()
        )

    assert SECRET_WORDS.encode() in on_disk()  # (so the check below can fail)
    full_client.delete(f"/api/conversations/{sid}", headers=owner)
    left = on_disk()
    assert SECRET_WORDS.encode() not in left and sid.encode() not in left
    with store._read() as conn:
        for table in ("events", "messages", "profile_slots", "scenarios", "tickets"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


def test_delete_logs_no_content(full_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    owner = _login(full_client, "employee")
    sid, _ = _loaded(full_client, owner)
    caplog.set_level("DEBUG")
    full_client.delete(f"/api/conversations/{sid}", headers=owner)
    assert SECRET_WORDS not in caplog.text and EMAILS["employee"] not in caplog.text
    assert "conversation deleted" in caplog.text


def test_deleting_wakes_the_rep_inbox_and_ends_the_conversations_stream(
    full_settings: Settings,
) -> None:
    settings = replace(full_settings, heartbeat_seconds=30.0)  # only a wake-up can be that fast
    app = create_app(settings, agent=NullAgentRunner())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        owner, rep = _login(http, "employee"), _login(http, "rep")
        sid = http.post("/api/sessions", headers=owner).json()["id"]
        http.post(f"/api/sessions/{sid}/messages", headers=owner, json={"text": "ATTO 3?"})
        for name, body in (
            ("save_profile", NOA),
            ("set_current_situation", TODAY),
            ("ask_representative", {"question": "?", "blocking_fields": [ATTO]}),
        ):
            http.post(f"/api/sessions/{sid}/tools/{name}", headers=owner, json=body)
        with (
            SSEReader(f"{base}/api/tickets/events", headers=rep) as inbox,
            SSEReader(f"{base}/api/sessions/{sid}/events", headers=owner) as stream,
        ):
            deadline = time.monotonic() + 10
            while not any(e.get("data", {}).get("tickets") for e in inbox.events):
                assert time.monotonic() < deadline
                time.sleep(0.02)
            assert http.delete(f"/api/conversations/{sid}", headers=owner).status_code == 204
            deadline = time.monotonic() + 8
            while not (inbox.events[-1]["data"]["tickets"] == [] and not stream._thread.is_alive()):
                assert time.monotonic() < deadline, "the inbox or the stream did not notice"
                time.sleep(0.05)


# --- empty conversations -----------------------------------------------------------------------


def _exists(client: TestClient, headers: dict[str, str], sid: str) -> bool:
    return client.get(f"/api/sessions/{sid}", headers=headers).status_code == 200


def test_an_empty_conversation_is_not_listed(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    empty = _new(full_client, headers)
    assert _listing(full_client, headers) == []
    assert _exists(full_client, headers, empty)  # still there, and still opens by its address
    _say(full_client, empty, headers)
    assert [c["id"] for c in _listing(full_client, headers)] == [empty]


def test_a_payslip_upload_makes_a_conversation_not_empty(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    extracted = _new(full_client, headers)
    store.append_event(extracted, "payslip_extracted", {"fields": {}, "dropped_keys": 0})
    cleared = _new(full_client, headers)  # empty: the next new conversation deletes it
    failed = _new(full_client, headers)
    assert not _exists(full_client, headers, cleared)
    assert [c["id"] for c in _listing(full_client, headers)] == [extracted]
    store.append_event(failed, "payslip_failed", {"code": "payslip_unavailable"})
    assert {c["id"] for c in _listing(full_client, headers)} == {extracted, failed}


def test_logout_deletes_the_users_empty_conversations_only(full_client: TestClient) -> None:
    mine, theirs = _login(full_client, "employee"), _login(full_client, "other")
    kept = _new(full_client, mine)
    _say(full_client, kept, mine)
    empty = _new(full_client, mine)
    others_empty = _new(full_client, theirs)
    assert full_client.post("/api/auth/logout", headers=mine).status_code == 204

    again = _login(full_client, "employee")
    assert _exists(full_client, again, kept)  # a conversation with a message survives
    assert not _exists(full_client, again, empty)
    assert _exists(full_client, theirs, others_empty)  # another user's empty one is not touched


def test_a_new_conversation_deletes_the_other_empty_ones(full_client: TestClient) -> None:
    headers, theirs = _login(full_client, "employee"), _login(full_client, "other")
    kept = _new(full_client, headers)
    _say(full_client, kept, headers)
    empty = _new(full_client, headers)
    others_empty = _new(full_client, theirs)
    fresh = _new(full_client, headers)
    assert not _exists(full_client, headers, empty)
    assert _exists(full_client, headers, kept) and _exists(full_client, headers, fresh)
    assert _exists(full_client, theirs, others_empty)
    assert [c["id"] for c in _listing(full_client, headers)] == [kept]  # the new one is empty


def test_the_empty_clean_up_is_the_delete_path(full_client: TestClient) -> None:
    headers = _login(full_client, "employee")
    store = full_client.app.state.services.store  # type: ignore[attr-defined]
    empty = _new(full_client, headers)
    full_client.post("/api/auth/logout", headers=headers)
    with store._read() as conn:
        for table in ("events", "messages", "sessions"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert empty.encode() not in b"".join(
        p.read_bytes() for p in store.path.parent.glob(store.path.name + "*") if p.is_file()
    )

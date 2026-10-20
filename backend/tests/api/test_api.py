import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from helpers import ADMIN, ADMIN_TOKEN, REP, REP_TOKEN

from compass.api import Settings, create_app
from compass.api.openapi import OPENAPI_JSON, render


def tool(client: TestClient, sid: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(f"/api/sessions/{sid}/tools/{name}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- sessions and messages --------------------------------------------------------------------


def test_create_and_snapshot(client: TestClient, sid: str) -> None:
    snapshot = client.get(f"/api/sessions/{sid}").json()
    assert snapshot["id"] == sid and snapshot["status"] == "active"
    assert snapshot["last_event_seq"] == 1 and snapshot["last_comparison"] is None
    assert client.get("/api/sessions/nope").status_code == 404


def test_post_message_is_stored_not_answered(client: TestClient, sid: str) -> None:
    response = client.post(f"/api/sessions/{sid}/messages", json={"text": "שלום, יש לי שאלה"})
    assert response.status_code == 202 and response.json() == {"message_seq": 1}
    snapshot = client.get(f"/api/sessions/{sid}").json()
    assert [m["role"] for m in snapshot["messages"]] == ["user"]  # NullAgentRunner: no reply
    assert snapshot["messages"][0]["content"] == {"text": "שלום, יש לי שאלה"}
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": ""}).status_code == 422
    assert client.post("/api/sessions/nope/messages", json={"text": "x"}).status_code == 404


def test_agent_runner_is_called(make_settings: Callable[..., Settings]) -> None:
    calls: list[tuple[str, object]] = []

    class Recorder:
        def on_user_message(self, session_id: str, message_seq: int) -> None:
            calls.append(("message", message_seq))

        def on_ticket_answered(self, session_id: str, ticket_id: str) -> None:
            calls.append(("ticket", ticket_id))

    with TestClient(create_app(make_settings(), agent=Recorder())) as client:
        sid = client.post("/api/sessions").json()["id"]
        client.post(f"/api/sessions/{sid}/messages", json={"text": "hi"})
        ticket = tool(
            client, sid, "ask_representative", {"question": "?", "blocking_fields": ["bonus"]}
        )["ticket_id"]
        client.post(f"/api/tickets/{ticket}/answer", json={"values": {"bonus": 0}}, headers=REP)
    assert calls == [("message", 1), ("ticket", ticket)]


# --- dev tools --------------------------------------------------------------------------------


def test_dev_tools_disabled_by_default(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(dev_tools=False))) as client:
        sid = client.post("/api/sessions").json()["id"]
        response = client.post(f"/api/sessions/{sid}/tools/get_rule", json={"topic": "budgets"})
        assert response.status_code == 404


def test_dev_tools(client: TestClient, sid: str) -> None:
    result = tool(client, sid, "get_rule", {"topic": "budgets"})
    assert result["ok"] and result["value"]["budgets"]["ב"] == "3700"
    assert tool(client, sid, "nope", {})["error"]["code"] == "not_found"
    assert client.post("/api/sessions/nope/tools/get_rule", json={}).status_code == 404


# --- tickets ----------------------------------------------------------------------------------


def _ticket(client: TestClient, sid: str) -> str:
    return tool(
        client,
        sid,
        "ask_representative",
        {
            "question": "מה אחוז ההפרשה לפנסיה ומה הבונוס?",
            "blocking_fields": ["pension_percent", "bonus"],
            "quick_answers": [
                {
                    "id": "std",
                    "label": "6%, ללא בונוס",
                    "values": {"pension_percent": 6, "bonus": 0},
                }
            ],
        },
    )["ticket_id"]


def test_ticket_inbox(client: TestClient, sid: str) -> None:
    ticket = _ticket(client, sid)
    inbox = client.get("/api/tickets", params={"status": "open"}, headers=REP).json()
    assert [t["id"] for t in inbox] == [ticket]
    assert inbox[0]["blocking_fields"] == ["pension_percent", "bonus"]
    assert client.get("/api/tickets", params={"status": "nope"}, headers=REP).status_code == 422


def test_answer_with_quick_answer(client: TestClient, sid: str) -> None:
    ticket = _ticket(client, sid)
    response = client.post(
        f"/api/tickets/{ticket}/answer", json={"quick_answer_id": "std"}, headers=REP
    )
    assert response.status_code == 200 and response.json()["status"] == "answered"
    slots = client.get(f"/api/sessions/{sid}").json()["slots"]
    assert slots["pension_pct"]["value"] == "0.06" and slots["bonus"]["value"] == "0"
    assert {slots["pension_pct"]["source"], slots["bonus"]["source"]} == {"representative"}


def test_answer_text_only_marks_fields_unknown(client: TestClient, sid: str) -> None:
    ticket = _ticket(client, sid)
    body = {"answer_text": "אין לי את הנתון", "values": {"bonus": 1200}}
    assert client.post(f"/api/tickets/{ticket}/answer", json=body, headers=REP).status_code == 200
    snapshot = client.get(f"/api/sessions/{sid}").json()
    assert snapshot["slots"]["bonus"]["value"] == "1200"
    assert snapshot["slots"]["pension_pct"]["state"] == "unknown"  # answered, but no value
    assert snapshot["status"] == "active" and snapshot["open_tickets"] == []


def test_answer_validation(client: TestClient, sid: str) -> None:
    ticket = _ticket(client, sid)
    answer = f"/api/tickets/{ticket}/answer"
    assert client.post(answer, json={}, headers=REP).status_code == 422
    assert (
        client.post(answer, json={"values": {"pension_percent": 50}}, headers=REP).status_code
        == 422
    )
    assert (
        client.post(answer, json={"values": {"base_salary": 9000}}, headers=REP).status_code == 422
    )
    assert client.post(answer, json={"quick_answer_id": "nope"}, headers=REP).status_code == 422
    assert (
        client.post(answer, json={"values": {"national_id": "1"}}, headers=REP).status_code == 422
    )
    assert (
        client.post("/api/tickets/nope/answer", json={"answer_text": "x"}, headers=REP).status_code
        == 404
    )
    assert client.post(answer, json={"answer_text": "ok"}, headers=REP).status_code == 200
    assert client.post(answer, json={"answer_text": "again"}, headers=REP).status_code == 409


# --- data, health, openapi --------------------------------------------------------------------


def test_data_endpoints(client: TestClient) -> None:
    rules = client.get("/api/rules").json()
    assert rules["rules"]["version"] == "mock-2026-10-12" and len(rules["sha256"]) == 64
    catalog = client.get("/api/catalog").json()
    assert len(catalog) == 20 and catalog[18]["family_track"] is True
    assert catalog[0]["value_of_use"] == "2690"  # Decimal as an exact string
    assert len(client.get("/api/occupations").json()) == 14


def test_health(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["ok"] and health["data"]["vehicles_rows"] == 77988
    assert health["data"]["vehicles_source_sha256"].startswith("fa101574")
    assert (health["data"]["tax_tables_year"], health["data"]["value_of_use_year"]) == (2025, 2026)


def test_health_says_which_tokens_are_set_never_their_values(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.json()["auth"] == {"rep": True, "admin": True}
    assert REP_TOKEN not in health.text and ADMIN_TOKEN not in health.text


def test_an_empty_rep_token_warns_at_startup_and_shows_in_health(
    make_settings: Callable[..., Settings], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="compass.api.app"):
        app = create_app(make_settings(rep_token=None))
    (warning,) = [r.getMessage() for r in caplog.records if r.name == "compass.api.app"]
    assert warning.startswith("COMPASS_REP_TOKEN is empty")
    assert ADMIN_TOKEN not in caplog.text
    with TestClient(app) as client:
        assert client.get("/api/health").json()["auth"] == {"rep": False, "admin": True}
        assert client.get("/api/tickets").status_code == 503


def test_cors_for_vite(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings(cors_origins=("http://localhost:5173",)))
    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_docs_list_every_endpoint(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/api/sessions",
        "/api/sessions/{session_id}",
        "/api/sessions/{session_id}/messages",
        "/api/sessions/{session_id}/events",
        "/api/sessions/{session_id}/tools/{name}",
        "/api/tickets",
        "/api/tickets/events",
        "/api/tickets/{ticket_id}/answer",
        "/api/rules",
        "/api/catalog",
        "/api/occupations",
        "/api/admin/reload-rules",
        "/api/admin/stats",
        "/api/health",
    }


PAYSLIP_PATHS = {"/api/sessions/{session_id}/payslip", "/api/sessions/{session_id}/payslip/confirm"}


def test_the_payslip_routes_are_in_the_schema_only_with_the_flag(
    make_settings: Callable[..., Settings],
) -> None:
    for on in (False, True):
        with TestClient(create_app(make_settings(payslip=on))) as client:
            paths = set(client.get("/openapi.json").json()["paths"])
        assert (paths >= PAYSLIP_PATHS) is on and (PAYSLIP_PATHS & paths == set()) is not on


def test_committed_openapi_is_up_to_date() -> None:
    committed = OPENAPI_JSON.read_text(encoding="utf-8")
    assert committed == render(), "run `uv run python tasks.py openapi` and commit openapi.json"


def test_reload_rules_ok(client: TestClient, rules_copy: Path) -> None:
    before = client.get("/api/health").json()["rules"]["sha256"]
    rules_copy.write_text(
        rules_copy.read_text(encoding="utf-8") + "\n# touched\n", encoding="utf-8"
    )
    response = client.post("/api/admin/reload-rules", headers=ADMIN)
    assert response.status_code == 200
    assert response.json()["sha256"] != before
    assert client.get("/api/health").json()["rules"]["sha256"] == response.json()["sha256"]

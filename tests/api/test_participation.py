"""The challenge brief's scenario: the new car's participation is missing -> ask the
representative -> the representative answers 350 ₪ -> the conversation continues with it."""

from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient
from helpers import REP
from live import SSEReader, live_server

from compass.api import Settings, create_app

ATTO = "alternative_participation:CAR-10"
NOA = {  # E-001
    "display_name": "נועה",
    "occupation_query": "מנהלת מוצר",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6,
    "study_fund_percent": 2.5,
    "credit_points": 2.75,
    "children_under_23": 2,
}
COROLLA_CROSS = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
ATTO_3 = {"alternative": {"kind": "car", "car_id": "CAR-10"}}


def tool(client: TestClient | httpx.Client, sid: str, name: str, payload: dict[str, Any]):  # type: ignore[no-untyped-def]
    response = client.post(f"/api/sessions/{sid}/tools/{name}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _noa(client: TestClient | httpx.Client) -> str:
    sid = client.post("/api/sessions").json()["id"]
    assert tool(client, sid, "save_profile", NOA)["ok"]
    assert tool(client, sid, "set_current_situation", COROLLA_CROSS)["ok"]
    return sid


def test_the_brief_flow(make_settings: Callable[..., Settings]) -> None:
    with (
        live_server(create_app(make_settings())) as base,
        httpx.Client(base_url=base, timeout=10) as http,
    ):
        sid = _noa(http)

        # 1. Without a representative answer: the catalog default, stated as such.
        first = tool(http, sid, "compare", ATTO_3)
        assert first["participation_source"] == "catalog_default"
        assert first["pending_rep"] is False
        assert first["comparison"]["display_diff"] == 661

        # 2. The participation is missing -> ask the representative.
        asked = tool(
            http,
            sid,
            "ask_representative",
            {
                "question": "מה ההשתתפות של נועה ב-ATTO 3?",
                "blocking_fields": [ATTO],
                "quick_answers": [{"id": "350", "label": "350 ₪", "values": {ATTO: 350}}],
            },
        )
        assert asked["ok"], asked
        snapshot = http.get(f"/api/sessions/{sid}").json()
        assert snapshot["slots"][ATTO]["state"] == "pending_rep"
        assert snapshot["status"] == "waiting_for_rep"

        # 3. While the ticket is open: the default is used, but never silently.
        pending = tool(http, sid, "compare", ATTO_3)
        assert pending["participation_source"] == "catalog_default"
        assert pending["pending_rep"] is True
        assert pending["comparison"]["display_diff"] == 661

        # 4. The representative sees the ticket and answers 350 ₪ from 1.11.2026.
        inbox = http.get("/api/tickets", params={"status": "open"}, headers=REP).json()
        assert [t["blocking_fields"] for t in inbox] == [[ATTO]]
        assert inbox[0]["context"]["display_name"] == "נועה"
        assert inbox[0]["context"]["requested_alternative"]["car_id"] == "CAR-10"
        with SSEReader(f"{base}/api/sessions/{sid}/events") as stream:
            stream.wait_for("ticket_opened")
            answered = http.post(
                f"/api/tickets/{asked['ticket_id']}/answer",
                json={"values": {ATTO: 350}, "effective_from": "2026-11-01"},
                headers=REP,
            )
            assert answered.status_code == 200, answered.text
            event = stream.wait_for("ticket_answered")
        assert event["data"]["payload"]["fields"] == {
            ATTO: {"amount": "350", "effective_from": "2026-11-01"}
        }
        slot = http.get(f"/api/sessions/{sid}").json()["slots"][ATTO]
        assert (slot["state"], slot["source"]) == ("filled", "representative")

        # 5. The conversation continues with the representative's 350 ₪.
        after = tool(http, sid, "compare", ATTO_3)
        assert after["participation_source"] == "representative"
        assert after["pending_rep"] is False
        assert after["participation_effective_from"] == "2026-11-01"
        comparison = after["comparison"]
        assert comparison["alternative"]["exact"]["participation"] == "350"
        lines = {line["line"]: line["net_effect"] for line in comparison["display_delta_lines"]}
        assert lines["participation"] == -50  # 300 today -> 350
        assert comparison["display_diff"] == 611  # engine: 661 - 50
        assert http.get(f"/api/sessions/{sid}").json()["status"] == "active"


def test_current_participation_from_the_representative(client: TestClient) -> None:
    sid = client.post("/api/sessions").json()["id"]
    tool(client, sid, "save_profile", NOA)
    tool(
        client, sid, "set_current_situation", {"today": {"kind": "company_car", "car_id": "CAR-09"}}
    )  # participation unknown
    ticket = tool(
        client,
        sid,
        "ask_representative",
        {"question": "?", "blocking_fields": ["current_participation"]},
    )["ticket_id"]
    pending = tool(client, sid, "compare", ATTO_3)
    assert pending["today_participation"] == {
        "source": "catalog_default",
        "pending_rep": True,
        "effective_from": None,
    }
    client.post(
        f"/api/tickets/{ticket}/answer",
        json={"values": {"current_participation": 320}},
        headers=REP,
    )
    after = tool(client, sid, "compare", ATTO_3)
    assert after["today_participation"]["source"] == "representative"
    assert after["comparison"]["today"]["exact"]["participation"] == "320"


def test_explicit_participation_wins(client: TestClient) -> None:
    sid = _noa(client)
    ticket = tool(client, sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]})[
        "ticket_id"
    ]
    client.post(f"/api/tickets/{ticket}/answer", json={"values": {ATTO: 350}}, headers=REP)
    stated = tool(
        client,
        sid,
        "compare",
        {"alternative": {"kind": "car", "car_id": "CAR-10", "participation": 400}},
    )
    assert stated["participation_source"] == "employee_input"
    assert stated["comparison"]["alternative"]["exact"]["participation"] == "400"
    # Another car is not affected by CAR-10's answer.
    other = tool(client, sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-11"}})
    assert other["participation_source"] == "catalog_default" and not other["pending_rep"]


def test_participation_field_validation(client: TestClient) -> None:
    sid = _noa(client)
    bad_car = tool(
        client,
        sid,
        "ask_representative",
        {"question": "?", "blocking_fields": ["alternative_participation:CAR-99"]},
    )
    assert bad_car["error"]["code"] == "invalid_input"
    ticket = tool(
        client, sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO, "bonus"]}
    )["ticket_id"]
    answer = f"/api/tickets/{ticket}/answer"
    assert client.post(answer, json={"values": {ATTO: 25_000}}, headers=REP).status_code == 422
    only_bonus = {"values": {"bonus": 0}, "effective_from": "2026-11-01"}
    assert client.post(answer, json=only_bonus, headers=REP).status_code == 422
    assert (
        client.post(
            answer,
            json={"values": {ATTO: 350, "bonus": 0}, "effective_from": "2026-13-01"},
            headers=REP,
        ).status_code
        == 422
    )
    # save_profile does not take participation: that comes from today's car or a representative
    saved = tool(client, sid, "save_profile", {"current_participation": 300})
    assert saved["error"]["code"] == "invalid_input"

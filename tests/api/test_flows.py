"""End-to-end flows through the HTTP API, scripted (no LLM): the UX walkthrough, the
representative round trip with live SSE, refresh restore and live rules reload."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi.testclient import TestClient
from live import SSEReader, live_server

from compass.api import Settings, create_app


def tool(client: TestClient | httpx.Client, sid: str, name: str, payload: dict[str, Any]):  # type: ignore[no-untyped-def]
    response = client.post(f"/api/sessions/{sid}/tools/{name}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def walkthrough(client: TestClient | httpx.Client, sid: str) -> dict[str, Any]:
    """Our UX walkthrough, step by step; returns the final comparison result."""
    client.post(f"/api/sessions/{sid}/messages", json={"text": "אני גננת"})
    gardener = tool(client, sid, "save_profile", {"occupation_query": "גננות"})
    assert gardener["error"]["code"] == "not_found"

    client.post(f"/api/sessions/{sid}/messages", json={"text": "סליחה, מפתחת תוכנה"})
    saved = tool(
        client,
        sid,
        "save_profile",
        {
            "occupation_query": "מפתח תוכנה",
            "base_salary": 18500,
            "commissions": 0,
            "bonus": 0,
            "pension_percent": 6.5,
            "study_fund_percent": 2.5,
            "credit_points": 3,
        },
    )
    assert saved["ok"] and saved["saved"]["group"] == "ב" and saved["missing"] == []

    car = tool(client, sid, "lookup_vehicle", {"query": "קורולה קורס", "registration_year": 2025})
    assert car["confident"] and car["candidates"][0]["id"] == "CAR-09"
    today = tool(
        client,
        sid,
        "set_current_situation",
        {
            "today": {
                "kind": "company_car",
                "car_id": "CAR-09",
                "registration_year": 2025,
                "participation": 300,
            }
        },
    )
    assert [w["code"] for w in today["warnings"]] == ["current_car_above_group"]

    atto = tool(client, sid, "check_eligibility", {"scenario": {"kind": "car", "car_id": "CAR-10"}})
    assert (atto["error"]["code"], atto["error"]["reason"]) == ("not_eligible", "car_group_higher")

    waiver = tool(client, sid, "compare", {"alternative": {"kind": "waiver"}})
    assert waiver["ok"], waiver
    return waiver


def test_walkthrough(client: TestClient, sid: str) -> None:
    result = walkthrough(client, sid)
    comparison = result["comparison"]
    # Verified against the engine: 10,999.819 -> 11,000 and 13,914.488 -> 13,914, so the
    # displayed diff is 13,914 - 11,000 = +2,914 (the brief's +2,915 rounded the exact diff).
    assert comparison["today"]["display"]["net"] == 11000
    assert comparison["alternative"]["display"]["net"] == 13914
    assert comparison["display_diff"] == 2914
    assert comparison["diff"].startswith("2914.669")
    assert sum(line["net_effect"] for line in comparison["display_delta_lines"]) == 2914
    assert result["eligibility"]["status"] == "eligible" and not result["hypothetical"]


def test_refresh_restore(client: TestClient, sid: str) -> None:
    walkthrough(client, sid)
    ticket = tool(
        client,
        sid,
        "ask_representative",
        {"question": "האם מגיע לי רכב מקבוצה ג?", "blocking_fields": ["group"]},
    )
    snapshot = client.get(f"/api/sessions/{sid}").json()
    assert [m["content"]["text"] for m in snapshot["messages"]] == [
        "אני גננת",
        "סליחה, מפתחת תוכנה",
    ]
    assert snapshot["slots"]["base_salary"]["value"] == "18500"
    assert snapshot["slots"]["group"]["state"] == "pending_rep"
    assert snapshot["scenarios"]["today"]["scenario"]["car_id"] == "CAR-09"
    assert snapshot["scenarios"]["alternative:1"] == {
        "kind": "waiver",
        "maintenance": None,
        "maintenance_source": "occupation",
    }
    assert [t["id"] for t in snapshot["open_tickets"]] == [ticket["ticket_id"]]
    assert snapshot["last_comparison"]["comparison"]["display_diff"] == 2914
    assert snapshot["status"] == "waiting_for_rep"
    # session_created, 2 x user_message, profile_updated (the rejected occupation stored
    # nothing, so no event), current_situation_set, comparison_ready, ticket_opened,
    # session_status
    assert snapshot["last_event_seq"] == 8


def test_representative_round_trip_over_sse(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        sid = http.post("/api/sessions").json()["id"]
        walkthrough(http, sid)
        asked = tool(
            http,
            sid,
            "ask_representative",
            {
                "question": "מה אחוז ההפרשה של העובדת לקרן השתלמות?",
                "blocking_fields": ["study_fund_percent"],
                "quick_answers": [
                    {"id": "std", "label": "2.5%", "values": {"study_fund_percent": 2.5}}
                ],
            },
        )
        ticket_id = asked["ticket_id"]
        inbox = http.get("/api/tickets", params={"status": "open"}).json()
        assert [t["id"] for t in inbox] == [ticket_id]
        assert inbox[0]["context"]["occupation"] == "מפתח/ת תוכנה"

        events_url = f"{base}/api/sessions/{sid}/events"
        with SSEReader(events_url) as stream:
            stream.wait_for("ticket_opened")  # replayed from the events table
            seen = len(stream.events)
            answer = http.post(
                f"/api/tickets/{ticket_id}/answer", json={"values": {"study_fund_percent": 3}}
            )
            assert answer.status_code == 200
            live = stream.wait_for("ticket_answered")  # delivered live
            assert live["data"]["payload"]["fields"] == {"study_fund_pct": "0.03"}
            assert len(stream.events) > seen
        last_seq = live["id"]

        snapshot = http.get(f"/api/sessions/{sid}").json()
        slot = snapshot["slots"]["study_fund_pct"]
        assert (slot["value"], slot["state"], slot["source"]) == (
            "0.03",
            "filled",
            "representative",
        )
        assert snapshot["status"] == "active"

        # Reconnect with Last-Event-ID: only newer events are replayed.
        http.post(f"/api/sessions/{sid}/messages", json={"text": "תודה!"})
        with SSEReader(events_url, headers={"Last-Event-ID": str(last_seq)}) as again:
            again.wait_for("user_message")
            replayed = [e["id"] for e in again.events]
        assert replayed and all(seq > last_seq for seq in replayed)
        assert [e["event"] for e in again.events][0] in ("session_status", "user_message")


def test_sse_heartbeat_and_unknown_session(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings(heartbeat_seconds=1))
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        assert http.get("/api/sessions/nope/events").status_code == 404
        sid = http.post("/api/sessions").json()["id"]
        with SSEReader(f"{base}/api/sessions/{sid}/events?after=1") as stream:
            time.sleep(2.5)
            assert stream.events == []  # nothing after seq 1
            assert stream.comments >= 1  # heartbeat


# --- live rules reload ------------------------------------------------------------------------


def _family_share(client: TestClient, sid: str) -> int:
    result = tool(client, sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-19"}})
    assert result["ok"], result
    return result["comparison"]["alternative"]["display"]["family_employee_share"]


def _e002(client: TestClient, sid: str) -> None:
    tool(
        client,
        sid,
        "save_profile",
        {
            "occupation_query": "נציג מכירות שטח",
            "base_salary": 9800,
            "commissions": 2400,
            "bonus": 0,
            "pension_percent": 6,
            "study_fund_percent": 0,
            "credit_points": 2.25,
            "children_under_23": 5,
        },
    )
    tool(
        client,
        sid,
        "set_current_situation",
        {"today": {"kind": "company_car", "car_id": "CAR-05", "participation": 250}},
    )


def test_reload_rules_changes_the_next_comparison(
    client: TestClient, sid: str, rules_copy: Path
) -> None:
    _e002(client, sid)
    assert _family_share(client, sid) == 1150  # (6,000 - 3,700) x 0.5
    data = yaml.safe_load(rules_copy.read_text(encoding="utf-8"))
    data["budgets"]["ב"] = 4000
    rules_copy.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert client.post("/api/admin/reload-rules").status_code == 200
    assert _family_share(client, sid) == 1000  # (6,000 - 4,000) x 0.5


def test_invalid_rules_are_rejected_and_old_rules_stay(
    client: TestClient, sid: str, rules_copy: Path
) -> None:
    _e002(client, sid)
    before = client.get("/api/health").json()["rules"]["sha256"]
    data = yaml.safe_load(rules_copy.read_text(encoding="utf-8"))
    data["budgets"]["ב"] = 4000  # a valid change that must NOT take effect...
    data["net_method"]["brackets"][2]["rate"] = "1.4"  # ...because this one is invalid
    rules_copy.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    response = client.post("/api/admin/reload-rules")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "net_method.brackets[2].rate: must be between 0 and 1 (got 1.4)" in detail
    assert response.json()["active_rules_sha256"] == before
    assert client.get("/api/health").json()["rules"]["sha256"] == before
    assert _family_share(client, sid) == 1150  # still the old budget

    rules_copy.write_text("budgets: [unclosed\n", encoding="utf-8")
    response = client.post("/api/admin/reload-rules")
    assert response.status_code == 422 and "not valid YAML" in response.json()["detail"]
    assert _family_share(client, sid) == 1150

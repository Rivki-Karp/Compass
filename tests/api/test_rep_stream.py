"""The representative's live inbox: GET /api/tickets/events, and the ticket `view`."""

import time
from collections.abc import Callable
from typing import Any

import httpx
from helpers import REP
from live import SSEReader, live_server

from compass.api import Settings, create_app

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


def _tool(http: httpx.Client, sid: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = http.post(f"/api/sessions/{sid}/tools/{name}", json=payload).json()
    assert result["ok"], result
    return result


def _until(stream: SSEReader, check: Callable[[list[Any]], bool]) -> list[Any]:
    """The latest `tickets` list once `check` accepts it."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        lists = [e["data"]["tickets"] for e in stream.events if e.get("event") == "tickets"]
        if lists and check(lists[-1]):
            return lists[-1]
        time.sleep(0.02)
    raise AssertionError(f"inbox never matched; got {stream.events}")


def test_inbox_needs_the_rep_token(make_settings: Callable[..., Settings]) -> None:
    with (
        live_server(create_app(make_settings())) as base,
        httpx.Client(base_url=base, timeout=10) as http,
    ):
        assert http.get("/api/tickets/events").status_code == 401
        bad = {"Authorization": "Bearer nope"}
        assert http.get("/api/tickets/events", headers=bad).status_code == 401


def test_inbox_updates_live(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings())
    with (
        live_server(app) as base,
        httpx.Client(base_url=base, timeout=10) as http,
        SSEReader(f"{base}/api/tickets/events", headers=REP) as inbox,
    ):
        assert _until(inbox, lambda tickets: tickets == []) == []

        sid = http.post("/api/sessions").json()["id"]
        _tool(http, sid, "save_profile", NOA)
        _tool(http, sid, "set_current_situation", TODAY)
        _tool(http, sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]})
        (opened,) = _until(inbox, lambda tickets: len(tickets) == 1)
        assert opened["view"]["title"] == "השתתפות עצמית · ATTO 3"
        assert opened["view"]["fields"] == [
            {
                "field": ATTO,
                "label": "השתתפות בחלופה",
                "unit": "ils",
                "car_id": "CAR-10",
                "car_name": "ATTO 3",
                "catalog_default": 300,
            }
        ]
        # Since 8b opening the ticket also emits the server's provisional comparison. A snapshot
        # taken between the two has none yet, so wait for it rather than assert on the first.
        (provisional,) = _until(inbox, lambda t: len(t) == 1 and t[0]["view"]["comparison"])
        assert provisional["view"]["comparison"] == {
            "alternative_title": "ATTO 3",
            "display_diff": 661,
            "pending": True,
        }

        # The employee's own comparison: the ticket still shows the provisional diff.
        _tool(http, sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})
        (updated,) = _until(inbox, lambda t: len(t) == 1 and t[0]["view"]["comparison"])
        assert updated["view"]["comparison"] == {
            "alternative_title": "ATTO 3",
            "display_diff": 661,
            "pending": True,
        }

        answer = http.post(
            f"/api/tickets/{opened['id']}/answer", json={"values": {ATTO: 350}}, headers=REP
        )
        assert answer.status_code == 200
        assert _until(inbox, lambda tickets: tickets == []) == []


def test_ticket_list_carries_the_view(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=10) as http:
        sid = http.post("/api/sessions").json()["id"]
        _tool(http, sid, "save_profile", NOA)
        _tool(
            http,
            sid,
            "ask_representative",
            {"question": "?", "blocking_fields": ["study_fund_percent"]},
        )
        (ticket,) = http.get("/api/tickets", headers=REP).json()
        assert ticket["view"]["title"] == "הפרשת עובד לקרן השתלמות"
        assert ticket["view"]["fields"][0]["unit"] == "percent"
        assert ticket["view"]["fields"][0]["catalog_default"] is None

"""Item 6: the employee asked for every option, the request could not be answered yet, and a
representative (or the payslip, or the chat) later supplied what was missing: the server puts the
full option set on screen by itself, as it recomputes a pending comparison.

The incident: list_options failed (nothing was kept of the request), the rep identified today's
car, and only the waiver comparison the agent made on its own was on screen. What the pending
state held: only comparison_set_ready's {stated, today_unknown}, which exists only after a
successful list_options; a refused call left nothing to satisfy. Now every list_options call
records options_requested, and a request with no set after it is pending."""

from pathlib import Path
from typing import Any

import pytest

from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.tickets import answer_ticket

BASE = {
    "occupation_query": "מפתחת תוכנה",
    "base_salary": 7000,
    "study_fund_percent": 2.25,
    "credit_points": 3,
}
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def sets(services: Services, sid: str) -> list[Any]:
    return [e for e in services.store.events_after(sid) if e.type == "comparison_set_ready"]


def start(tools: ToolRunner, profile: dict[str, Any]) -> str:
    sid = tools.services.store.create_session()
    assert tools.run(sid, "save_profile", profile)["ok"]
    return sid


def test_a_request_with_no_amounts_is_satisfied_when_the_profile_is_complete(
    tools: ToolRunner, services: Services
) -> None:
    sid = start(tools, BASE)
    assert tools.run(sid, "list_options", {})["no_amounts"] is True
    assert sets(services, sid) == []
    assert tools.run(sid, "save_profile", {"commissions": 0, "bonus": 0})["ok"]
    # the nets need commissions and bonus; with them the set appears, partial (no pension rate)
    (partial,) = sets(services, sid)
    assert all(o["view"]["alternative_net"] is None for o in partial.payload["options"])
    tools.run(sid, "save_profile", {"pension_percent": 6})  # exactly what the set waited for
    full = sets(services, sid)
    assert len(full) == 2
    assert all(o["view"]["alternative_net"] is not None for o in full[-1].payload["options"])


def test_the_set_gets_its_diffs_when_todays_car_becomes_known(
    tools: ToolRunner, services: Services
) -> None:
    sid = start(tools, {**BASE, "commissions": 0, "bonus": 0, "pension_percent": 6})
    tools.run(sid, "list_options", {})
    assert sets(services, sid)[-1].payload["today_unknown"] is True
    tools.run(sid, "set_current_situation", TODAY)
    last = sets(services, sid)[-1].payload
    assert last["today_unknown"] is False
    assert all(o["view"]["display_diff"] is not None for o in last["options"])


def test_the_incident_a_refused_request_is_answered_when_the_rep_identifies_the_car(
    tools: ToolRunner, services: Services
) -> None:
    sid = start(tools, BASE)
    assert tools.run(sid, "list_options", {})["no_amounts"] is True  # was a refusal
    tools.run(sid, "save_profile", {"commissions": 0, "bonus": 0, "pension_percent": 6})
    ask = {
        "question": "מה הרכב של העובד?",
        "questions": [{"bound_field": "current_car", "car_query": "מאזדה"}],
    }
    ticket = tools.run(sid, "ask_representative", ask)["ticket_id"]
    # only the waiver, which the agent compared itself, would have been on screen
    before = len(sets(services, sid))
    answer_ticket(services, ticket, values={"current_car": "CAR-13"})
    after = sets(services, sid)
    assert len(after) > before or after[-1].payload["today_unknown"] is False
    last = after[-1].payload
    assert last["today_unknown"] is False and len(last["options"]) > 5
    assert all(o["view"]["display_diff"] is not None for o in last["options"])


def test_an_answered_request_is_not_computed_again_by_every_save(
    tools: ToolRunner, services: Services
) -> None:
    sid = start(tools, {**BASE, "commissions": 0, "bonus": 0, "pension_percent": 6})
    tools.run(sid, "list_options", {})
    n = len(sets(services, sid))
    tools.run(sid, "save_profile", {"credit_points": 3.25})
    assert len(sets(services, sid)) == n


def test_no_request_no_set(tools: ToolRunner, services: Services) -> None:
    sid = start(tools, {**BASE, "commissions": 0, "bonus": 0, "pension_percent": 6})
    tools.run(sid, "set_current_situation", TODAY)
    tools.run(sid, "save_profile", {"credit_points": 3.25})
    assert sets(services, sid) == []

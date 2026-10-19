"""A multi-car ticket answered one field at a time: the answered car settles on its own, the
others stay pending and the ticket stays open until the last one is answered."""

import json
from typing import Any

import pytest

from compass.agent.llm import ScriptedClient, text_response
from compass.agent.runner import ClaudeAgentRunner
from compass.agent.transcript import REP_TAG
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.tickets import TicketAnswerError, answer_ticket
from compass.tools.view import build_ticket_view

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
CARS = {"CAR-10": "ATTO 3", "CAR-06": "MG4", "CAR-11": "EV3"}
FIELDS = [f"alternative_participation:{c}" for c in CARS]
ATTO, MG4, EV3 = FIELDS


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


def _three_cars(services: Services) -> tuple[str, str]:
    tools = ToolRunner(services)
    sid = services.store.create_session()
    services.store.add_message(sid, "user", {"text": "ATTO 3, MG4 או EV3: מה ההשתתפות?"})
    assert tools.run(sid, "save_profile", NOA)["ok"]
    assert tools.run(sid, "set_current_situation", TODAY)["ok"]
    result = tools.run(sid, "ask_representative", {"question": "?", "blocking_fields": FIELDS})
    assert result["ok"], result
    return sid, result["ticket_id"]


def _latest(services: Services, sid: str, car_id: str) -> dict[str, Any]:
    events = services.store.events_after(sid)
    return next(
        e.payload
        for e in reversed(events)
        if e.type == "comparison_ready" and e.payload["alternative"].get("car_id") == car_id
    )


def test_the_ticket_view_has_one_section_per_car(services: Services) -> None:
    sid, ticket = _three_cars(services)
    view = build_ticket_view(services, services.store.ticket(ticket))
    assert view["title"] == "השתתפות עצמית · 3 רכבים"
    for field, (car_id, name) in zip(view["fields"], CARS.items(), strict=True):
        assert (field["car_id"], field["car_name"], field["answered"]) == (car_id, name, False)
        # that car's own provisional comparison, never another car's
        assert field["comparison"]["alternative_title"] == name
        assert field["comparison"]["pending"] is True


def test_one_car_answered_the_rest_stay_pending(services: Services) -> None:
    sid, ticket = _three_cars(services)
    mg4_before = _latest(services, sid, "CAR-06")
    answered = answer_ticket(services, ticket, values={ATTO: 350}, partial=True)

    assert answered.status == "open"
    assert services.store.session_status(sid) == "waiting_for_rep"
    slots = services.store.slots(sid)
    assert (slots[ATTO].state, slots[ATTO].source) == ("filled", "representative")
    assert slots[MG4].state == slots[EV3].state == "pending_rep"
    # ATTO 3 settles on its own: final, +611; MG4 is untouched and still pending
    atto = _latest(services, sid, "CAR-10")
    assert (atto["view"]["pending"], atto["comparison"]["display_diff"]) == (False, 611)
    assert atto["answered_field"] == ATTO
    assert _latest(services, sid, "CAR-06") == mg4_before

    (event,) = [e.payload for e in services.store.events_after(sid) if e.type == "ticket_answered"]
    assert event["partial"] is True and event["pending"] == [MG4, EV3]
    view = build_ticket_view(services, services.store.ticket(ticket))
    assert [(f["answered"], f["answer"]) for f in view["fields"]] == [
        (True, 350),
        (False, None),
        (False, None),
    ]
    assert view["fields"][0]["comparison"]["pending"] is False


def test_the_last_part_closes_the_ticket(services: Services) -> None:
    sid, ticket = _three_cars(services)
    answer_ticket(services, ticket, values={ATTO: 350}, partial=True)
    answer_ticket(services, ticket, values={MG4: 250}, partial=True)
    closed = answer_ticket(services, ticket, values={EV3: 300}, partial=True)
    assert closed.status == "answered"
    assert services.store.session_status(sid) == "active"
    assert closed.answer["values"] == {ATTO: 350, MG4: 250, EV3: 300}


def test_a_full_answer_after_a_part_makes_the_rest_unknown(services: Services) -> None:
    sid, ticket = _three_cars(services)
    answer_ticket(services, ticket, values={ATTO: 350}, partial=True)
    closed = answer_ticket(services, ticket, values={MG4: 250})  # not partial: closes
    assert closed.status == "answered"
    assert services.store.slots(sid)[EV3].state == "unknown"
    assert services.store.slots(sid)[ATTO].state == "filled"  # the earlier part stays


def test_a_field_cannot_be_answered_twice_or_empty(services: Services) -> None:
    _, ticket = _three_cars(services)
    answer_ticket(services, ticket, values={ATTO: 350}, partial=True)
    with pytest.raises(TicketAnswerError) as twice:
        answer_ticket(services, ticket, values={ATTO: 400}, partial=True)
    assert [e.code for e in twice.value.errors] == ["field_already_answered"]
    with pytest.raises(TicketAnswerError) as empty:
        answer_ticket(services, ticket, values={}, answer_text="note", partial=True)
    assert [e.code for e in empty.value.errors] == ["empty_answer"]


def test_the_agent_hears_only_this_part_and_what_is_pending(services: Services) -> None:
    sid, ticket = _three_cars(services)
    answer_ticket(services, ticket, values={ATTO: 350}, partial=True)
    llm = ScriptedClient([text_response("הנציג אישר 350 ₪ ל-ATTO 3; MG4 ו-EV3 עדיין ממתינים.")])
    runner = ClaudeAgentRunner(services, llm, "SYSTEM", background=False)
    runner.on_ticket_answered(sid, ticket)
    text = llm.calls[0].messages[-1]["content"][0]["text"]
    assert text.startswith(f"<{REP_TAG} ")
    notification = json.loads(text.split("\n", 1)[1].rsplit("\n", 1)[0])
    assert notification["values"] == {ATTO: 350}
    assert notification["pending_fields"] == [MG4, EV3]
    assert notification["unknown_fields"] == []
    (settled,) = notification["server_comparisons"]  # ATTO 3's settle only
    assert settled["comparison"]["display_diff"] == 611

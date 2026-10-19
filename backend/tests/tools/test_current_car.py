"""The bound current_car question: a representative may know the employee's company car when the
employee cannot name it. The server builds the options (the catalog cars the employee's words may
mean, a search over the whole catalog, "not in the catalog" with a required note) and applies the
answer as today's situation, source representative: eligibility, warnings and what was on screen
are computed again."""

from typing import Any

import pytest

from compass.agent.guard import make_guard
from compass.agent.llm import ScriptedClient, text_response
from compass.agent.runner import ClaudeAgentRunner
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.handlers import settled_compare_results
from compass.tools.tickets import QuestionAnswer, TicketAnswerError, answer_ticket
from compass.tools.view import build_ticket_view

DEVELOPER = {  # group ב
    "occupation_query": "מפתחת תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
ASK_CAR = {
    "question": "העובדת לא יודעת לזהות את הרכב שלה (כתבה 'מאזדה'). איזה רכב צמוד יש לה היום?",
    "questions": [{"bound_field": "current_car", "car_query": "מאזדה"}],
}
MG4 = {"alternative": {"kind": "car", "car_id": "CAR-06"}}


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def err(result: dict[str, Any]) -> str:
    assert result["ok"] is False, result
    return str(result["error"]["message"])


def _asked(tools: ToolRunner) -> tuple[str, str]:
    """A session without today's car: the options on screen, then the ticket."""
    sid = tools.services.store.create_session()
    ok(tools.run(sid, "save_profile", DEVELOPER))
    ok(tools.run(sid, "list_options", {}))
    ok(tools.run(sid, "compare", MG4))
    ticket = ok(tools.run(sid, "ask_representative", ASK_CAR))
    return sid, ticket["ticket_id"]


def _events(services: Services, sid: str, kind: str) -> list[Any]:
    return [e for e in services.store.events_after(sid) if e.type == kind]


# --- asking -----------------------------------------------------------------------------------


def test_the_server_builds_the_options_from_the_employees_words(
    tools: ToolRunner, services: Services
) -> None:
    sid, ticket_id = _asked(tools)
    (question,) = services.store.ticket(ticket_id).questions
    assert question["bound_field"] == "current_car" and question["car_query"] == "מאזדה"
    assert question["answer"] == {
        "type": "choice",
        "options": [
            {"value": "CAR-13", "label": "MAZDA 3 2025 · בנזין · קבוצה ג׳"},
            {"value": "other", "label": "הרכב לא בקטלוג (לפרט בהערה)"},
        ],
    }
    assert services.store.slots(sid)["current_car"].state == "pending_rep"

    view = build_ticket_view(services, services.store.ticket(ticket_id))
    assert view["title"] == "הרכב של היום · מאזדה"
    (shown,) = view["questions"]
    assert shown["options"][0]["detail"] == "בנזין · קבוצה ג׳"
    assert len(shown["search_options"]) == len(services.ctx.catalog)
    assert {"value": "CAR-07", "label": "COROLLA 2026", "detail": "בנזין · קבוצה ב׳"} in shown[
        "search_options"
    ]
    assert shown["note_required_for"] == "other"
    assert shown["search_label"] == "לא ברשימה? חיפוש בקטלוג המלא"
    assert shown["detail_label"] == "הקבוצה וההנעה לפי הבחירה"
    assert shown["facts"] == [{"label": "איך העובד/ת תיאר/ה", "value": "מאזדה"}]


def test_nothing_matching_still_offers_the_search_and_not_in_catalog(
    tools: ToolRunner, services: Services
) -> None:
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", DEVELOPER))
    asked = {"question": "?", "questions": [{"bound_field": "current_car", "car_query": "מציון"}]}
    ticket = services.store.ticket(ok(tools.run(sid, "ask_representative", asked))["ticket_id"])
    assert [o["value"] for o in ticket.questions[0]["answer"]["options"]] == ["other"]
    view = build_ticket_view(services, ticket)
    assert len(view["questions"][0]["search_options"]) == len(services.ctx.catalog)


@pytest.mark.parametrize(
    ("question", "message"),
    [
        ({"bound_field": "current_car"}, "needs car_query"),
        ({"bound_field": "current_car", "car_query": "  "}, "needs car_query"),
        ({"bound_field": "current_car", "car_query": "x", "type": "choice"}, "no type or options"),
        ({"bound_field": "occupation", "occupation_query": "x", "car_query": "x"}, "car_query is"),
        ({"prompt_he": "?", "type": "text", "car_query": "x"}, "car_query needs"),
    ],
)
def test_a_malformed_current_car_question_is_refused(
    tools: ToolRunner, services: Services, question: dict[str, Any], message: str
) -> None:
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", DEVELOPER))
    assert message in err(tools.run(sid, "ask_representative", {"questions": [question]}))


def test_not_asked_once_today_is_recorded(tools: ToolRunner, services: Services) -> None:
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", DEVELOPER))
    ok(tools.run(sid, "set_current_situation", {"today": {"kind": "none"}}))
    assert "already recorded" in err(tools.run(sid, "ask_representative", ASK_CAR))


# --- while the representative is checking -----------------------------------------------------


def test_while_pending_the_screen_waits_for_it_and_the_employee_cannot_set_it(
    tools: ToolRunner, services: Services
) -> None:
    sid, _ = _asked(tools)
    pending = _events(services, sid, "comparison_ready")[-1].payload
    assert pending["origin"] == "server" and pending["pending_field"] == "current_car"
    view = pending["view"]
    assert view["pending"] and view["pending_fields"] == ["current_car"]
    assert view["display_diff"] is None and view["diff_note"] == "חסר הרכב של היום"
    today_car = next(i for i in view["inputs"] if i["id"] == "today_car")
    assert (today_car["value"], today_car["source"]) == (None, "pending_rep")
    shown = _events(services, sid, "comparison_set_ready")[-1].payload
    assert all(o["view"]["pending_fields"] == ["current_car"] for o in shown["options"])

    refused = err(tools.run(sid, "set_current_situation", {"today": {"kind": "none"}}))
    assert "identifying today's car" in refused


# --- the answer -------------------------------------------------------------------------------


def test_a_car_becomes_today_source_representative_and_the_diffs_appear(
    tools: ToolRunner, services: Services
) -> None:
    sid, ticket_id = _asked(tools)
    answer_ticket(services, ticket_id, answers={"q1": QuestionAnswer(value="CAR-13")})
    slots = services.store.slots(sid)
    assert (slots["current_car"].value, slots["current_car"].source) == ("CAR-13", "representative")
    today = services.store.scenarios(sid)["today"]
    assert today["source"] == "representative" and today["label"] == "MAZDA 3"
    assert today["scenario"] == {
        "kind": "company_car",
        "car_id": "CAR-13",
        "participation": None,
        "participation_source": None,
    }

    settled = _events(services, sid, "comparison_ready")[-1].payload
    assert settled["answered_field"] == "current_car" and settled["ticket_id"] == ticket_id
    view = settled["view"]
    assert view["display_diff"] is not None and not view["pending"]
    assert view["today_title"] == "MAZDA 3"
    today_car = next(i for i in view["inputs"] if i["id"] == "today_car")
    assert today_car["source"] == "representative"
    # eligibility and warnings again: MAZDA 3 is in group ג, above the developer's ב
    assert [w["code"] for w in view["warnings"]] == ["current_car_above_group"]

    shown = _events(services, sid, "comparison_set_ready")[-1].payload
    assert shown["today_unknown"] is False
    assert all(o["view"]["display_diff"] is not None for o in shown["options"])
    # the model gets the settled comparison as compare would have returned it
    (result,) = settled_compare_results(services, sid, ticket_id, ["current_car"])
    again = ok(tools.run(sid, "compare", MG4))
    assert result["comparison"]["display_diff"] == again["comparison"]["display_diff"]


def test_not_in_the_catalog_needs_a_note_and_leaves_today_unknown(
    tools: ToolRunner, services: Services
) -> None:
    sid, ticket_id = _asked(tools)
    with pytest.raises(TicketAnswerError) as refused:
        answer_ticket(services, ticket_id, answers={"q1": QuestionAnswer(value="other")})
    assert [e.code for e in refused.value.errors] == ["note_required"]
    answer_ticket(
        services,
        ticket_id,
        answers={"q1": QuestionAnswer(value="other", note="Mazda CX-5 2024, ליסינג פרטי")},
    )
    assert services.store.slots(sid)["current_car"].state == "unknown"
    assert "today" not in services.store.scenarios(sid)
    latest = _events(services, sid, "comparison_ready")[-1].payload["view"]
    assert not latest["pending"] and latest["display_diff"] is None  # the chip is gone
    # the employee may now say it (lookup_vehicle, a car outside the catalog)
    ok(tools.run(sid, "set_current_situation", {"today": {"kind": "none"}}))


def test_a_car_outside_the_catalog_is_refused_as_an_answer(
    tools: ToolRunner, services: Services
) -> None:
    sid, ticket_id = _asked(tools)
    with pytest.raises(TicketAnswerError) as refused:
        answer_ticket(services, ticket_id, answers={"q1": QuestionAnswer(value="CAR-99")})
    assert [e.code for e in refused.value.errors] == ["unknown_car"]
    assert services.store.slots(sid)["current_car"].state == "pending_rep"


def test_the_rep_notification_says_which_car_and_the_guard_allows_it(
    tools: ToolRunner, services: Services
) -> None:
    sid, ticket_id = _asked(tools)
    answer_ticket(services, ticket_id, answers={"q1": QuestionAnswer(value="CAR-13")})
    (result,) = settled_compare_results(services, sid, ticket_id, ["current_car"])
    settled_diff = result["comparison"]["display_diff"]
    reply = f"הנציג זיהה את הרכב שלך: MAZDA 3. ההפרש ב-MG4: {settled_diff:+,} ₪."
    llm = ScriptedClient([text_response(reply)])
    runner = ClaudeAgentRunner(
        services,
        llm,
        "SYSTEM",
        guard=make_guard(services.store),
        template=lambda session_id: "TEMPLATE",
        background=False,
    )
    runner.on_ticket_answered(sid, ticket_id)
    notification = next(
        m.content
        for m in services.store.messages(sid)
        if m.role == "system_event" and m.content.get("kind") == "rep_answer"
    )
    assert notification["values"] == {"current_car": "CAR-13"}
    assert notification["today_after"]["current_situation"] == "MAZDA 3"
    assert notification["today_after"]["source"] == "representative"
    assert [w["code"] for w in notification["today_after"]["warnings"]] == [
        "current_car_above_group"
    ]
    assert notification["server_comparisons"]
    text = llm.calls[0].messages[-1]["content"][0]["text"]
    assert "today_after" in text
    guard = [e.payload for e in services.store.events_after(sid) if e.type == "guard_check"]
    assert guard[-1]["action"] == "accept"

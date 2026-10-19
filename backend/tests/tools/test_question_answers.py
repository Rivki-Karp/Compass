"""Answering a ticket's questions: bound answers change their input (occupation re-derives the
group), free answers never touch a slot and reach the model as data, "needs checking" keeps a
question pending, and every question takes a note."""

from typing import Any

import pytest

from compass.agent.guard import make_guard
from compass.agent.llm import ScriptedClient, text_response
from compass.agent.runner import ClaudeAgentRunner
from compass.agent.transcript import REP_TAG
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.questions import OTHER_OCCUPATION, bound_question, free_question
from compass.tools.tickets import QuestionAnswer, TicketAnswerError, answer_ticket
from compass.tools.view import build_ticket_view

AI_DEVELOPER = {  # no occupation the table recognises
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
COROLLA_CROSS = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
PARKING = "האם החברה מאפשרת חניה בבניין המשרדים?"


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _session(services: Services, profile: dict[str, Any] = AI_DEVELOPER) -> str:
    tools = ToolRunner(services)
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", profile))
    ok(tools.run(sid, "set_current_situation", COROLLA_CROSS))
    return sid


def _open(services: Services, sid: str, *, occupation: bool = True, free: str | None = None):  # type: ignore[no-untyped-def]
    questions = []
    if occupation:
        questions.append(
            bound_question(services, sid, "occupation", qid="q1", occupation_query="מפתח AI")
        )
    if free is not None:
        questions.append(free_question("q2", PARKING, free, ["כן", "לא", "רק לבעלי תפקיד"]))
    fields = ["occupation"] if occupation else []
    return services.store.open_ticket(sid, "?", {}, fields, [], questions=questions)


def _codes(error: TicketAnswerError) -> list[str]:
    return [e.code for e in error.errors]


def test_an_occupation_answer_fills_it_and_derives_the_group(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid)
    assert services.store.slots(sid)["occupation"].state == "pending_rep"
    answered = answer_ticket(
        services, ticket.id, answers={"q1": QuestionAnswer(value="מפתח/ת תוכנה")}, partial=True
    )
    assert answered.status == "answered"
    slots = services.store.slots(sid)
    assert (slots["occupation"].value, slots["occupation"].source) == (
        "מפתח/ת תוכנה",
        "representative",
    )
    assert (slots["group"].value, slots["group"].source) == ("ב", "derived")
    event = [e for e in services.store.events_after(sid) if e.type == "ticket_answered"][-1]
    (shown,) = event.payload["questions"]
    assert shown["answer"] == "מפתח/ת תוכנה · קבוצה ב׳"


def test_an_occupation_answer_keeps_a_group_the_employee_stated(services: Services) -> None:
    sid = _session(services, {**AI_DEVELOPER, "group": "ג"})
    ticket = _open(services, sid)
    answer_ticket(services, ticket.id, answers={"q1": QuestionAnswer(value="מפתח/ת תוכנה")})
    group = services.store.slots(sid)["group"]
    assert (group.value, group.source) == ("ג", "employee")


def test_another_occupation_needs_a_note_and_leaves_it_unknown(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid)
    with pytest.raises(TicketAnswerError) as error:
        answer_ticket(services, ticket.id, answers={"q1": QuestionAnswer(value=OTHER_OCCUPATION)})
    assert _codes(error.value) == ["note_required"]
    answer_ticket(
        services,
        ticket.id,
        answers={"q1": QuestionAnswer(value=OTHER_OCCUPATION, note="תפקיד חדש, בבדיקה מול HR")},
    )
    slots = services.store.slots(sid)
    assert slots["occupation"].state == "unknown"
    assert "group" not in slots


def test_an_occupation_outside_the_table_is_refused(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid)
    with pytest.raises(TicketAnswerError) as error:
        answer_ticket(services, ticket.id, answers={"q1": QuestionAnswer(value="מפתח/ת AI")})
    assert _codes(error.value) == ["unknown_occupation"]


def test_a_free_answer_never_changes_a_slot(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid, occupation=False, free="yes_no")
    before = {f: (s.value, s.state, s.source) for f, s in services.store.slots(sid).items()}
    answered = answer_ticket(
        services,
        ticket.id,
        answers={"q2": QuestionAnswer(value="yes", note="קבוצה ד׳, 500 ₪ בחודש")},
    )
    after = {f: (s.value, s.state, s.source) for f, s in services.store.slots(sid).items()}
    assert after == before
    assert answered.status == "answered"
    assert answered.answer["questions"]["q2"] == {
        "status": "answered",
        "value": "yes",
        "note": "קבוצה ד׳, 500 ₪ בחודש",
    }
    (question,) = build_ticket_view(services, answered)["questions"]
    assert (question["status"], question["answer"]) == ("answered", "כן")


@pytest.mark.parametrize(
    ("kind", "value", "code"),
    [
        ("yes_no", "maybe", "not_an_option"),
        ("choice", "o9", "not_an_option"),
        ("choice", "כן", "not_an_option"),  # a label is not a value
        ("text", "  ", "empty_text"),
    ],
)
def test_a_free_answer_must_fit_its_type(
    services: Services, kind: str, value: Any, code: str
) -> None:
    sid = _session(services)
    ticket = _open(services, sid, occupation=False, free=kind)
    with pytest.raises(TicketAnswerError) as error:
        answer_ticket(services, ticket.id, answers={"q2": QuestionAnswer(value=value)})
    assert _codes(error.value) == [code]


def test_needs_checking_keeps_the_question_pending(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid, free="yes_no")
    part = answer_ticket(
        services,
        ticket.id,
        answers={
            "q1": QuestionAnswer(status="needs_checking", note="בודק מול משאבי אנוש"),
            "q2": QuestionAnswer(value="no"),
        },
        partial=True,
    )
    assert part.status == "open"
    assert services.store.slots(sid)["occupation"].state == "pending_rep"
    view = build_ticket_view(services, part)
    assert [(q["status"], q["note"]) for q in view["questions"]] == [
        ("needs_checking", "בודק מול משאבי אנוש"),
        ("answered", None),
    ]
    with pytest.raises(TicketAnswerError) as error:  # answered already
        answer_ticket(services, ticket.id, answers={"q2": QuestionAnswer(value="yes")})
    assert _codes(error.value) == ["field_already_answered"]
    done = answer_ticket(
        services, ticket.id, answers={"q1": QuestionAnswer(value="מפתח/ת תוכנה")}, partial=True
    )
    assert done.status == "answered"


def test_needs_checking_takes_no_value(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid)
    with pytest.raises(TicketAnswerError) as error:
        answer_ticket(
            services,
            ticket.id,
            answers={"q1": QuestionAnswer(value="מפתח/ת תוכנה", status="needs_checking")},
        )
    assert _codes(error.value) == ["value_with_needs_checking"]


def test_closing_leaves_an_unanswered_free_question_unknown(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid, free="text")
    answered = answer_ticket(
        services, ticket.id, answers={"q1": QuestionAnswer(value="מפתח/ת תוכנה")}
    )
    assert answered.status == "answered"
    assert answered.answer["questions"]["q2"]["status"] == "unknown"


def test_an_unknown_question_id_is_refused(services: Services) -> None:
    sid = _session(services)
    ticket = _open(services, sid)
    with pytest.raises(TicketAnswerError) as error:
        answer_ticket(services, ticket.id, answers={"q7": QuestionAnswer(value="x")})
    assert _codes(error.value) == ["unknown_question"]


def test_an_amount_question_takes_whole_shekels(services: Services) -> None:
    sid = _session(services)
    question = bound_question(services, sid, "current_participation", qid="q1")
    ticket = services.store.open_ticket(
        sid, "?", {}, ["current_participation"], [], questions=[question]
    )
    with pytest.raises(TicketAnswerError) as error:
        answer_ticket(services, ticket.id, answers={"q1": QuestionAnswer(value="350.5")})
    assert _codes(error.value) == ["not_a_whole_amount"]
    answer_ticket(services, ticket.id, answers={"q1": QuestionAnswer(value="350")})
    assert services.store.slots(sid)["current_participation"].value["amount"] == "350"


def test_free_answers_reach_the_model_as_data_and_the_guard_allows_them(
    services: Services,
) -> None:
    sid = _session(services)
    ticket = _open(services, sid, free="yes_no")
    reply = "הנציג אישר חניה: 500 ₪ בחודש, ועיסוק מפתח/ת תוכנה."
    llm = ScriptedClient([text_response(reply)])
    runner = ClaudeAgentRunner(
        services,
        llm,
        "SYSTEM",
        guard=make_guard(services.store),
        template=lambda session_id: "TEMPLATE",
        background=False,
    )
    answer_ticket(
        services,
        ticket.id,
        answers={
            "q1": QuestionAnswer(value="מפתח/ת תוכנה"),
            "q2": QuestionAnswer(value="yes", note="500 ₪ בחודש"),
        },
    )
    runner.on_ticket_answered(sid, ticket.id)
    notification = next(m.content for m in services.store.messages(sid) if m.role == "system_event")
    assert notification["free_answers"] == [
        {"question": PARKING, "answer": "yes", "note": "500 ₪ בחודש"}
    ]
    assert notification["profile_after"]["group"] == "ב"
    assert notification["profile_after"]["occupation_source"] == "representative"
    text = llm.calls[0].messages[-1]["content"][0]["text"]
    assert text.startswith(f"<{REP_TAG}") and PARKING in text
    guard = [e.payload for e in services.store.events_after(sid) if e.type == "guard_check"]
    assert guard[-1]["action"] == "accept"


def test_the_api_takes_answers_by_question_id(tmp_path: Any) -> None:
    from fastapi.testclient import TestClient

    from compass.api import Settings, create_app

    settings = Settings(app_db=tmp_path / "a.db", dev_tools=True, rep_token="r")
    app = create_app(settings)
    with TestClient(app) as client:
        services: Services = app.state.services
        sid = _session(services)
        ticket = _open(services, sid, free="yes_no")
        headers = {"Authorization": "Bearer r"}
        refused = client.post(
            f"/api/tickets/{ticket.id}/answer",
            json={"answers": {"q2": {"value": "maybe"}}, "partial": True},
            headers=headers,
        )
        assert refused.status_code == 422
        assert refused.json()["errors"][0]["code"] == "not_an_option"
        answered = client.post(
            f"/api/tickets/{ticket.id}/answer",
            json={
                "answers": {
                    "q1": {"status": "needs_checking", "note": "בבדיקה"},
                    "q2": {"value": "yes", "note": "רק בחניון B"},
                },
                "partial": True,
            },
            headers=headers,
        )
        assert answered.status_code == 200, answered.json()
        assert answered.json()["status"] == "open"
        inbox = client.get("/api/tickets?status=open", headers=headers).json()
        statuses = [q["status"] for q in inbox[0]["view"]["questions"]]
        assert statuses == ["needs_checking", "answered"]

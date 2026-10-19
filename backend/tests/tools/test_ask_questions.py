"""ask_representative's questions[] input: bound questions get the server's options, free
questions the model's labels; everything else is invalid_input with a message to act on."""

from typing import Any

import pytest

from compass.state import Store
from compass.tools import Services, ToolRunner

AI_DEVELOPER = {
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
COROLLA_CROSS = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
OCCUPATION_Q = {"bound_field": "occupation", "occupation_query": "מפתח AI"}
PARKING = {"prompt_he": "האם יש חניה בבניין?", "type": "yes_no"}


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def _session(services: Services, tools: ToolRunner, profile: dict[str, Any] = AI_DEVELOPER) -> str:
    sid = services.store.create_session()
    assert tools.run(sid, "save_profile", profile)["ok"]
    assert tools.run(sid, "set_current_situation", COROLLA_CROSS)["ok"]
    return sid


def _ask(tools: ToolRunner, sid: str, *questions: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return tools.run(sid, "ask_representative", {"questions": list(questions), **extra})


def test_an_occupation_and_a_free_question(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    result = _ask(tools, sid, OCCUPATION_Q, PARKING, question="העובד/ת מתאר/ת את עצמו כמפתח AI.")
    assert result["ok"] is True, result
    assert [(q["id"], q["bound_field"], q["type"]) for q in result["questions"]] == [
        ("q1", "occupation", "choice"),
        ("q2", None, "yes_no"),
    ]
    assert result["questions"][0]["options"][0] == "מפתח/ת תוכנה · קבוצה ב׳"
    ticket = services.store.ticket(result["ticket_id"])
    assert ticket.blocking_fields == ["occupation"]  # free questions block nothing
    assert ticket.question == "העובד/ת מתאר/ת את עצמו כמפתח AI."
    assert services.store.slots(sid)["occupation"].state == "pending_rep"
    # the employee cannot settle what the representative is reviewing
    again = tools.run(sid, "save_profile", {"occupation_query": "מפתח תוכנה"})
    assert again["ok"] is False and "reviewing the occupation" in again["error"]["message"]


def test_a_free_choice_keeps_the_models_labels_with_server_values(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools)
    choice = {"prompt_he": "איזה סוג חניה?", "type": "choice", "options": ["תת קרקעית", "עילית"]}
    result = _ask(tools, sid, choice)
    assert result["ok"] is True, result
    (question,) = services.store.ticket(result["ticket_id"]).questions
    assert question["answer"]["options"] == [
        {"value": "o1", "label": "תת קרקעית"},
        {"value": "o2", "label": "עילית"},
    ]
    assert services.store.ticket(result["ticket_id"]).question == "איזה סוג חניה?"


@pytest.mark.parametrize(
    ("questions", "extra", "says"),
    [
        ([{"bound_field": "base_salary"}], {}, "unknown bound_field 'base_salary'"),
        ([{"bound_field": "alternative_participation:CAR-99"}], {}, "unknown bound_field"),
        (
            [{**OCCUPATION_Q, "options": ["מפתח/ת תוכנה"]}],
            {},
            "a bound question takes no type or options",
        ),
        ([{**OCCUPATION_Q, "type": "choice"}], {}, "a bound question takes no type or options"),
        ([{"bound_field": "occupation"}], {}, "needs occupation_query"),
        ([{"bound_field": "current_participation", "occupation_query": "x"}], {}, "for bound"),
        ([PARKING, PARKING, PARKING, PARKING], {}, "at most 3 questions"),
        ([{"prompt_he": "  ", "type": "text"}], {}, "needs prompt_he"),
        ([{"prompt_he": "מה?"}], {}, "needs type"),
        ([{"prompt_he": "מה?", "type": "choice", "options": ["רק אחת"]}], {}, "2-6"),
        ([{"prompt_he": "מה?", "type": "choice", "options": ["א", "א"]}], {}, "unique"),
        ([{"prompt_he": "מה?", "type": "yes_no", "options": ["כן", "לא"]}], {}, "choice only"),
        ([{**PARKING, "occupation_query": "x"}], {}, "needs bound_field occupation"),
        ([OCCUPATION_Q, OCCUPATION_Q], {}, "asked twice"),
        ([PARKING], {"blocking_fields": ["current_participation"]}, "questions[] alone"),
        (
            [PARKING],
            {"quick_answers": [{"id": "a", "label": "x", "values": {}}]},
            "questions[] alone",
        ),
    ],
)
def test_invalid_questions_are_refused_with_a_message_to_act_on(
    services: Services,
    tools: ToolRunner,
    questions: list[dict[str, Any]],
    extra: dict[str, Any],
    says: str,
) -> None:
    sid = _session(services, tools)
    result = _ask(tools, sid, *questions, **extra)
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_input"
    assert says in result["error"]["message"]
    assert services.store.tickets("open", sid) == []


def test_a_prompt_over_the_limit_is_invalid_input(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    result = _ask(tools, sid, {"prompt_he": "א" * 301, "type": "text"})
    assert result["ok"] is False and result["error"]["code"] == "invalid_input"


def test_no_group_question_while_the_occupation_is_unknown(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools)  # occupation not recognised: unknown group
    result = _ask(tools, sid, {"bound_field": "group_exception"})
    assert result["ok"] is False
    assert "derives from the occupation" in result["error"]["message"]
    legacy = tools.run(
        sid, "ask_representative", {"question": "?", "blocking_fields": ["group_exception"]}
    )
    assert legacy["ok"] is False


def test_no_group_question_with_an_occupation_question(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools, {**AI_DEVELOPER, "group": "ב"})
    result = _ask(tools, sid, OCCUPATION_Q, {"bound_field": "group_exception"})
    assert result["ok"] is False
    assert "derives from the occupation" in result["error"]["message"]


def test_a_group_question_when_todays_car_is_above_the_occupations_group(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools, {**AI_DEVELOPER, "occupation_query": "מפתחת תוכנה"})
    result = _ask(tools, sid, {"bound_field": "group_exception"})  # COROLLA CROSS is ג, above ב
    assert result["ok"] is True, result
    assert result["questions"][0]["options"][-1] == "לא מאושר"

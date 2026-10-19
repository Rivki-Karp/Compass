"""A ticket asks about the cars the employee is actually considering: at most 3 participations,
each for a car the employee named or that this conversation compared."""

from typing import Any

import pytest

from compass.state import Store
from compass.tools import Services, ToolRunner

NOA = {
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


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def _session(services: Services, tools: ToolRunner, said: str) -> str:
    sid = services.store.create_session()
    services.store.add_message(sid, "user", {"text": said})
    assert tools.run(sid, "save_profile", NOA)["ok"]
    assert tools.run(sid, "set_current_situation", TODAY)["ok"]
    return sid


def _ask(tools: ToolRunner, sid: str, *cars: str) -> dict[str, Any]:
    fields = [f"alternative_participation:{c}" for c in cars]
    return tools.run(sid, "ask_representative", {"question": "?", "blocking_fields": fields})


def test_a_car_the_employee_named_is_accepted(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools, "מה יקרה לנטו אם אעבור לאטו 3? ואולי MG4")
    assert _ask(tools, sid, "CAR-10", "CAR-06")["ok"] is True  # ATTO 3 and MG4


def test_a_car_nobody_mentioned_is_refused(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools, "מה יקרה לנטו אם אעבור ל-ATTO 3?")
    result = _ask(tools, sid, "CAR-10", "CAR-14")  # MODEL 3: never named, never compared
    assert result["ok"] is False
    error = result["error"]
    assert error["code"] == "invalid_input"
    assert error["fields"] == ["alternative_participation:CAR-14"]
    assert "CAR-14 (MODEL 3)" in error["message"]
    assert "actually considering" in error["message"]
    assert services.store.tickets("open", sid) == []  # nothing opened


def test_a_compared_car_is_accepted(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools, "מה האפשרויות שלי?")
    assert _ask(tools, sid, "CAR-11")["ok"] is False
    assert tools.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-11"}})["ok"]
    assert _ask(tools, sid, "CAR-11")["ok"] is True


def test_at_most_three_cars_per_ticket(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools, "אטו 3, MG4, EV3 או קונה, מה ההשתתפות בכל אחד?")
    result = _ask(tools, sid, "CAR-10", "CAR-06", "CAR-11", "CAR-08")
    assert result["ok"] is False
    assert result["error"]["max_cars"] == 3
    assert "at most 3" in result["error"]["message"]
    assert _ask(tools, sid, "CAR-10", "CAR-06", "CAR-11")["ok"] is True


def test_other_fields_are_not_limited(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools, "שאלה")
    fields = ["current_participation", "group_exception", "bonus"]
    result = tools.run(sid, "ask_representative", {"question": "?", "blocking_fields": fields})
    assert result["ok"] is True


@pytest.mark.parametrize(
    ("text", "cars"),
    [
        ("מה עם ATTO 3?", {"CAR-10"}),
        ("לאטו3", {"CAR-10"}),
        ("אם ג'י 4 או טסלה", {"CAR-06", "CAR-14"}),
        ("אני רוצה רכב חשמלי", set()),
        ("מאטואה", set()),  # not a whole word
    ],
)
def test_cars_named_in_text(services: Services, text: str, cars: set[str]) -> None:
    assert services.searcher.cars_named_in(text) == cars

"""Item 5: the employee's catalog picker, built by the server.

Today's car is unknown -> the server offers the catalog itself (manufacturer, model, year, plus
"not in the list" and "no car"). The agent never lists manufacturers or models from its own
knowledge (it once offered Subaru and Nissan, which are not in the catalog); search_catalog with
no query returns the catalog grouped by manufacturer; a model that matches with another year is
"לבדיקת נציג", not "a different car".
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass.agent.factory import build_claude_runner
from compass.agent.guard import allowed_for_session, check_text
from compass.agent.llm import ScriptedClient, text_response
from compass.agent.transcript import CAR_TAG
from compass.api import Settings, create_app
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.car_picker import NOT_IN_LIST, picker

DEVELOPER = {
    "occupation_query": "מפתחת תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
MG4 = {"alternative": {"kind": "car", "car_id": "CAR-06"}}


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def new_session(tools: ToolRunner, profile: dict[str, Any] | None = None) -> str:
    sid = tools.services.store.create_session()
    if profile is not None:
        assert tools.run(sid, "save_profile", profile)["ok"]
    return sid


def events(services: Services, sid: str, kind: str) -> list[Any]:
    return [e for e in services.store.events_after(sid) if e.type == kind]


# --- what the picker offers ------------------------------------------------------------------


def test_the_picker_is_the_catalog_and_only_the_catalog(services: Services) -> None:
    options = picker(services)
    cars = [
        year["car_id"]
        for maker in options["manufacturers"]
        for model in maker["models"]
        for year in model["years"]
    ]
    assert sorted(cars) == sorted(services.ctx.catalog)  # every catalog car once, nothing else
    names = {m["label"] for m in options["manufacturers"]}
    assert not {"סובארו", "ניסאן", "Subaru", "Nissan"} & names
    assert [c["id"] for c in options["extra"]] == ["not_in_list", "no_car"]
    assert [c["label"] for c in options["extra"]] == ["הרכב שלי לא ברשימה", "אין לי רכב היום"]
    assert options["year_check"] == {"id": "check_year", "label": "שנה אחרת — לבדיקת נציג"}


def test_a_model_lists_the_years_the_catalog_has(services: Services) -> None:
    options = picker(services)
    for maker in options["manufacturers"]:
        for model in maker["models"]:
            for year in model["years"]:
                car = services.ctx.catalog[year["car_id"]]
                assert (car.manufacturer_name, car.commercial_name) == (
                    maker["label"],
                    model["label"],
                )
                assert year["year"] == car.registration_year
                assert str(car.registration_year) in year["label"]


# --- when the server offers it -----------------------------------------------------------------


def test_a_comparison_that_waits_for_todays_car_offers_the_picker_once(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools, DEVELOPER)
    assert tools.run(sid, "compare", MG4)["ok"]
    (offer,) = events(services, sid, "current_car_offered")
    assert offer.payload == picker(services)
    assert tools.run(sid, "compare", MG4)["ok"]  # still open: not offered again
    assert len(events(services, sid, "current_car_offered")) == 1


def test_list_options_without_todays_car_offers_it_too(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools, DEVELOPER)
    assert tools.run(sid, "list_options", {})["ok"]
    assert len(events(services, sid, "current_car_offered")) == 1


def test_list_options_without_amounts_and_without_a_car_offers_it_as_well(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools, {"occupation_query": "מפתחת תוכנה", "base_salary": 7000})
    result = tools.run(sid, "list_options", {})
    assert result["no_amounts"] is True
    assert len(events(services, sid, "current_car_offered")) == 1


def test_nothing_is_offered_once_todays_car_is_known(tools: ToolRunner, services: Services) -> None:
    sid = new_session(tools, DEVELOPER)
    assert tools.run(sid, "set_current_situation", {"today": {"kind": "none"}})["ok"]
    assert tools.run(sid, "compare", MG4)["ok"]
    assert events(services, sid, "current_car_offered") == []


def test_nothing_is_offered_while_a_representative_is_asked(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools, DEVELOPER)
    ask = {
        "question": "מה הרכב של העובד?",
        "questions": [{"bound_field": "current_car", "car_query": "יונדאי"}],
    }
    assert tools.run(sid, "ask_representative", ask)["ok"]
    assert tools.run(sid, "compare", MG4)["ok"]
    assert events(services, sid, "current_car_offered") == []


def test_after_not_in_the_list_the_picker_does_not_nag(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools, DEVELOPER)
    assert tools.run(sid, "compare", MG4)["ok"]
    services.store.append_event(sid, "current_car_picked", {"outcome": NOT_IN_LIST})
    assert tools.run(sid, "compare", MG4)["ok"]
    assert len(events(services, sid, "current_car_offered")) == 1


# --- search_catalog ----------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "all", "ALL", "הכל", "  "])
def test_search_catalog_with_no_query_returns_the_catalog_grouped_by_manufacturer(
    tools: ToolRunner, services: Services, query: str
) -> None:
    sid = new_session(tools)
    result = tools.run(sid, "search_catalog", {"query": query})
    assert result["ok"] is True and result["all"] is True and result["cars"] == []
    groups = result["manufacturers"]
    listed = [car["car_id"] for g in groups for car in g["cars"]]
    assert sorted(listed) == sorted(services.ctx.catalog)  # the catalog, all of it
    assert [car["choice"] for g in groups for car in g["cars"]] == list(range(1, len(listed) + 1))
    assert all(g["manufacturer"] and g["cars"] for g in groups)
    first_extra = len(listed) + 1
    assert [(c["choice"], c["id"]) for c in result["other_choices"]] == [
        (first_extra, "not_in_list"),
        (first_extra + 1, "no_car"),
    ]
    assert result["picker_on_screen"] is True
    assert len(events(services, sid, "current_car_offered")) == 1


def test_search_catalog_with_no_query_asked_twice_offers_once(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools)
    tools.run(sid, "search_catalog", {})
    result = tools.run(sid, "search_catalog", {"query": "all"})
    assert result["picker_on_screen"] is True
    assert len(events(services, sid, "current_car_offered")) == 1


def test_a_named_manufacturer_keeps_the_numbered_list_without_the_picker(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools)
    result = tools.run(sid, "search_catalog", {"query": "קיה"})
    assert result["cars"] and result["picker_on_screen"] is False
    assert events(services, sid, "current_car_offered") == []


def test_a_query_that_names_no_catalog_car_puts_the_picker_on_screen(
    tools: ToolRunner, services: Services
) -> None:
    sid = new_session(tools)
    result = tools.run(sid, "search_catalog", {"query": "סובארו"})
    assert result["cars"] == [] and result["picker_on_screen"] is True


def test_a_matching_model_with_another_year_is_for_a_representative_not_a_different_car(
    tools: ToolRunner,
) -> None:
    sid = new_session(tools)
    result = tools.run(sid, "search_catalog", {"query": "מאזדה 3 2024"})
    (mazda,) = result["cars"]
    assert (mazda["car_id"], mazda["registration_year"]) == ("CAR-13", 2025)
    assert mazda["year_differs"] is True and result["stated_year"] == 2024
    assert [c["id"] for c in result["other_choices"]] == [
        "not_in_list",
        "no_car",
        "check_with_rep",
    ]
    assert result["other_choices"][-1]["label_he"] == "לבדיקת נציג"
    same = tools.run(sid, "search_catalog", {"query": "מאזדה 3 2025"})
    assert "year_differs" not in same["cars"][0]
    assert [c["id"] for c in same["other_choices"]] == ["not_in_list", "no_car"]


def test_the_old_year_error_no_longer_says_a_different_car(
    tools: ToolRunner,
) -> None:
    sid = new_session(tools)
    today = {"kind": "company_car", "car_id": "CAR-13", "registration_year": 2024}
    result = tools.run(sid, "set_current_situation", {"today": today})
    assert result["ok"] is False and result["error"]["code"] == "not_found"
    message = result["error"]["message"]
    assert "לבדיקת נציג" in message and "current_car" in message
    assert "lookup_vehicle" not in message


# --- the employee's pick (POST /current-car) -----------------------------------------------------


class App:
    def __init__(self, client: TestClient, llm: ScriptedClient) -> None:
        self.client, self.llm = client, llm
        self.app: Any = client.app
        self.services = self.app.state.services
        self.store = self.services.store
        self.sid = client.post("/api/sessions").json()["id"]

    def run(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.app.state.runner.run(self.sid, tool, payload)
        assert result["ok"] is True, result
        return result

    def pick(self, **body: Any) -> Any:
        return self.client.post(f"/api/sessions/{self.sid}/current-car", json=body)

    def told(self) -> dict[str, Any]:
        text = self.llm.calls[-1].messages[-1]["content"][0]["text"]
        assert text.startswith(f'<{CAR_TAG} label="בחירה מהבורר">')
        return json.loads(text.split("\n", 1)[1].rsplit("\n", 1)[0])  # type: ignore[no-any-return]


@pytest.fixture
def make(tmp_path: Path) -> Iterator[Callable[[], App]]:
    clients: list[TestClient] = []

    def build() -> App:
        llm = ScriptedClient([text_response("רשמתי.")] * 5)

        def factory(settings: Settings, services: Any, runner: Any) -> Any:
            return build_claude_runner(
                settings, services, llm=llm, tool_runner=runner, background=False
            )

        app = create_app(Settings(app_db=tmp_path / "app.db"), agent_factory=factory)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return App(client, llm)

    yield build
    for client in clients:
        client.__exit__(None, None, None)


def test_picking_a_catalog_car_sets_todays_situation_as_the_employees(
    make: Callable[[], App],
) -> None:
    app = make()
    app.run("save_profile", DEVELOPER)
    app.run("compare", MG4)
    before = app.store.scenarios(app.sid).get("today")
    assert before is None
    response = app.pick(choice="car", car_id="CAR-09")
    assert response.status_code == 200 and response.json()["outcome"] == "car"
    today = app.store.scenarios(app.sid)["today"]
    assert today["scenario"]["car_id"] == "CAR-09" and today["source"] == "employee"
    # what is on screen was recomputed by the server, with the diff now
    latest = [e for e in app.store.events_after(app.sid) if e.type == "comparison_ready"][-1]
    assert (
        latest.payload["origin"] == "server" and latest.payload["view"]["display_diff"] is not None
    )
    assert events(app.services, app.sid, "current_car_picked")[-1].payload == {
        "outcome": "car",
        "car_id": "CAR-09",
    }


def test_the_agent_is_told_the_pick_as_data_with_the_recomputed_comparison(
    make: Callable[[], App],
) -> None:
    app = make()
    app.run("save_profile", DEVELOPER)
    app.run("compare", MG4)
    app.pick(choice="car", car_id="CAR-09")
    data = app.told()
    assert data["outcome"] == "car" and data["car_id"] == "CAR-09"
    assert data["today_after"]["car_id"] == "CAR-09" and data["today_after"]["source"] == "employee"
    [comparison] = data["server_comparisons"]
    shown = comparison["comparison"]["display_diff"]
    # the guard allows what the server recomputed, as "server"
    allowed = allowed_for_session(app.store, app.sid)
    assert check_text(f"ההפרש הוא {shown} ₪", allowed).passed


def test_picking_no_car_is_today_without_a_car(make: Callable[[], App]) -> None:
    app = make()
    app.run("save_profile", DEVELOPER)
    app.run("compare", MG4)
    assert app.pick(choice="no_car").status_code == 200
    today = app.store.scenarios(app.sid)["today"]
    assert today["scenario"]["kind"] == "current_maintenance"
    assert app.told()["outcome"] == "no_car"


def test_not_in_the_list_records_nothing_and_the_agent_takes_it_from_there(
    make: Callable[[], App],
) -> None:
    app = make()
    app.run("save_profile", DEVELOPER)
    app.run("compare", MG4)
    assert app.pick(choice="not_in_list").status_code == 200
    assert app.store.scenarios(app.sid).get("today") is None
    assert app.told()["outcome"] == "not_in_list"
    # and the picker does not come back by itself
    app.run("compare", MG4)
    assert len(events(app.services, app.sid, "current_car_offered")) == 1


def test_another_year_opens_a_current_car_ticket_for_a_representative(
    make: Callable[[], App],
) -> None:
    app = make()
    app.run("save_profile", DEVELOPER)
    app.run("compare", MG4)
    response = app.pick(choice="check_year", car_id="CAR-13")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "check_year" and body["ticket_id"]
    [ticket] = app.store.tickets(status="open", session_id=app.sid)
    assert ticket.blocking_fields == ["current_car"]
    assert "MAZDA 3" in ticket.question and "2025" in ticket.question
    [question] = ticket.questions
    assert question["car_query"] == "MAZDA 3"  # the rep's list is that model
    assert app.store.scenarios(app.sid).get("today") is None  # nothing guessed
    assert app.told()["ticket_id"] == body["ticket_id"]


def test_a_pick_is_refused_once_todays_car_is_known_or_asked(make: Callable[[], App]) -> None:
    app = make()
    app.run("save_profile", DEVELOPER)
    app.run("compare", MG4)
    assert app.pick(choice="car", car_id="CAR-09").status_code == 200
    again = app.pick(choice="car", car_id="CAR-07")
    assert again.status_code == 409 and again.json()["detail"] == "current_car_not_needed"
    assert again.json()["errors"][0]["message"] == "הרכב של היום כבר נקבע, או שנציג כבר בודק אותו."
    other = make()
    other.run("save_profile", DEVELOPER)
    assert other.pick(choice="check_year", car_id="CAR-13").status_code == 200
    asked = other.pick(choice="car", car_id="CAR-13")
    assert asked.status_code == 409  # a representative is on it


@pytest.mark.parametrize(
    "body",
    [
        {"choice": "car", "car_id": "CAR-99"},  # not in the catalog
        {"choice": "car"},  # no car
        {"choice": "check_year"},
        {"choice": "no_car", "car_id": "CAR-09"},  # does not fit
    ],
)
def test_a_pick_that_does_not_fit_is_refused(make: Callable[[], App], body: dict[str, Any]) -> None:
    app = make()
    response = app.pick(**body)
    assert response.status_code == 422
    assert app.store.scenarios(app.sid).get("today") is None


def test_an_unknown_choice_is_not_accepted(make: Callable[[], App]) -> None:
    assert make().pick(choice="subaru").status_code == 422


def test_the_pick_needs_the_session(make: Callable[[], App]) -> None:
    app = make()
    response = app.client.post("/api/sessions/nope/current-car", json={"choice": "no_car"})
    assert response.status_code == 404

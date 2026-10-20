"""search_catalog: today's car as a list to pick from, when lookup_vehicle cannot identify it."""

from typing import Any

import pytest

from compass.state import Store
from compass.tools import Services, ToolRunner


@pytest.fixture(scope="module")
def tools(tmp_path_factory: pytest.TempPathFactory) -> ToolRunner:
    return ToolRunner(Services(Store(tmp_path_factory.mktemp("catalog") / "app.db")))


@pytest.fixture
def sid(tools: ToolRunner) -> str:
    return tools.services.store.create_session()


def run(tools: ToolRunner, sid: str, query: str) -> dict[str, Any]:
    result = tools.run(sid, "search_catalog", {"query": query})
    assert result["ok"] is True, result
    return result


def test_a_manufacturer_lists_its_cars_numbered_then_the_two_other_choices(
    tools: ToolRunner, sid: str
) -> None:
    result = run(tools, sid, "טויוטה")
    assert [c["name"] for c in result["cars"]] == [
        "YARIS CROSS HSD",
        "COROLLA",
        "COROLLA CROSS",
        "RAV4",
    ]
    assert [c["choice"] for c in result["cars"]] == [1, 2, 3, 4]
    corolla = result["cars"][1]
    assert corolla == {
        "choice": 2,
        "car_id": "CAR-07",
        "name": "COROLLA",
        "registration_year": 2026,
        "group": "ב",
        "drive": "petrol",
        "details_he": "בנזין · קבוצה ב׳",
    }
    assert result["other_choices"] == [
        {"choice": 5, "id": "not_in_list", "label_he": "הרכב שלי לא ברשימה"},
        {"choice": 6, "id": "no_car", "label_he": "אין לי רכב היום"},
    ]


def test_nothing_matches_still_offers_the_two_other_choices(tools: ToolRunner, sid: str) -> None:
    result = run(tools, sid, "מציון")
    assert result["cars"] == []
    assert [c["id"] for c in result["other_choices"]] == ["not_in_list", "no_car"]
    assert [c["choice"] for c in result["other_choices"]] == [1, 2]


def test_every_registration_year_is_listed(tools: ToolRunner, sid: str) -> None:
    # lookup_vehicle with 2024 finds no catalog car (CAR-13 is the 2025 model); the list does,
    # with its year, so the employee can tell it is not their car
    cars = run(tools, sid, "מאזדה 3 2024")["cars"]
    assert [(c["car_id"], c["registration_year"]) for c in cars] == [("CAR-13", 2025)]


def test_the_list_changes_nothing(tools: ToolRunner, sid: str) -> None:
    store = tools.services.store
    before = len(store.events_after(sid))
    run(tools, sid, "קיה")
    assert store.scenarios(sid) == {} and store.slots(sid) == {}
    assert len(store.events_after(sid)) == before


def test_an_empty_query_is_the_whole_catalog_not_an_error(tools: ToolRunner, sid: str) -> None:
    result = tools.run(sid, "search_catalog", {"query": ""})
    assert result["ok"] is True and result["all"] is True

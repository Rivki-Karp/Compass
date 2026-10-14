"""Every catalog car must exist in the official Tax Authority dataset with identical values."""

import json
from decimal import Decimal

import pytest

from compass.config import FIXTURES_DIR
from compass.data.catalog import CatalogCar, get_car, load_catalog
from compass.data.occupations import get_occupation
from compass.data.vehicles import get_value_of_use

TAX_YEAR = 2026
PRIVATE = 1
CATALOG = load_catalog()


def test_catalog_has_twenty_cars() -> None:
    assert len(CATALOG) == 20


@pytest.mark.parametrize("car", CATALOG, ids=[f"{c.id}-{c.commercial_name}" for c in CATALOG])
def test_catalog_car_matches_official_record(car: CatalogCar) -> None:
    record = get_value_of_use(
        TAX_YEAR, car.registration_year, PRIVATE, car.manufacturer_code, car.model_code
    )
    assert record is not None, f"{car.id} not found in vehicles.db under the official key"
    assert record.value_of_use == car.value_of_use
    assert record.list_price == car.list_price
    assert record.commercial_name == car.commercial_name
    assert record.manufacturer_name == car.manufacturer_name
    assert record.model_description == car.model_description
    assert record.drive == car.drive


# --- golden fixtures agree with the curated datasets ----------------------------------------


def test_reference_fixtures_agree_with_catalog_and_occupations() -> None:
    employees = json.loads((FIXTURES_DIR / "reference_employees.json").read_text("utf-8"))
    results = json.loads((FIXTURES_DIR / "reference_results.json").read_text("utf-8"))
    for emp_id, emp in employees.items():
        occupation = get_occupation(emp["occupation"])
        assert occupation is not None, emp_id
        assert occupation.group == emp["group"], emp_id

        current = emp["current"]
        if current["kind"] == "waiver":
            assert occupation.waiver_allowed, emp_id
            assert Decimal(current["maintenance"]) == occupation.waiver_maintenance, emp_id
        else:
            car = get_car(current["car_id"])
            assert car is not None, emp_id
            assert Decimal(emp["current_participation"]) == car.default_employee_participation

        for scenario in (results[emp_id]["today"], results[emp_id]["alternative"]):
            if scenario["kind"] == "waiver":
                assert Decimal(scenario["maintenance"]) == occupation.waiver_maintenance, emp_id
            else:
                assert get_car(scenario["car_id"]) is not None, emp_id

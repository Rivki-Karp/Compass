from decimal import Decimal

import pytest

from compass.data.catalog import FAMILY_GROUP, cars_for_group, get_car, load_catalog
from compass.rules import Rules, load_rules


@pytest.fixture(scope="module")
def rules() -> Rules:
    return load_rules()


def test_load_catalog() -> None:
    cars = load_catalog()
    assert len(cars) == 20
    assert all(isinstance(car.value_of_use, Decimal) for car in cars)


def test_every_catalog_group_is_known(rules: Rules) -> None:
    assert {car.group for car in load_catalog()} <= {*rules.group_order, FAMILY_GROUP}


def test_get_car() -> None:
    car = get_car("CAR-10")
    assert car is not None
    assert car.commercial_name == "ATTO 3"
    assert (car.manufacturer_code, car.model_code) == ("01014", "00003")
    assert car.drive == "electric"
    assert get_car("CAR-99") is None


def test_group_b_gets_groups_a_and_b_only(rules: Rules) -> None:
    cars = cars_for_group("ב", rules)
    assert len(cars) == 8
    assert {car.group for car in cars} == {"א", "ב"}


def test_lowest_and_highest_group(rules: Rules) -> None:
    assert {car.group for car in cars_for_group("א", rules)} == {"א"}
    assert len(cars_for_group("ד", rules)) == 18


def test_family_cars_only_with_explicit_flag(rules: Rules) -> None:
    assert all(car.group != FAMILY_GROUP for car in cars_for_group("ד", rules))
    with_family = cars_for_group("ב", rules, include_family=True)
    assert len(with_family) == 10
    assert {car.id for car in with_family if car.group == FAMILY_GROUP} == {"CAR-19", "CAR-20"}


def test_family_track_cost_is_per_car() -> None:
    # Organizer decision: family-track car cost = catalog.monthly_company_cost (not one rule value).
    family = {car.commercial_name: car for car in load_catalog() if car.group == FAMILY_GROUP}
    assert family["CARNIVAL"].monthly_company_cost == Decimal(6000)
    assert family["SANTA FE"].monthly_company_cost == Decimal(5600)


def test_unknown_group_is_rejected(rules: Rules) -> None:
    with pytest.raises(ValueError, match="unknown group"):
        cars_for_group(FAMILY_GROUP, rules)

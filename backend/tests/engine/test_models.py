from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from compass.data.catalog import load_catalog
from compass.engine.context import ContextError, build_context
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    MissingInputs,
    Scenario,
    Waiver,
)
from compass.rules import load_rules


def test_profile_defaults_are_unknown_not_typical() -> None:
    profile = EmployeeProfile()
    assert all(value is None for value in profile.model_dump().values())


def test_profile_is_frozen_and_strict() -> None:
    profile = EmployeeProfile(base_salary=Decimal(18500))
    with pytest.raises(ValidationError):
        profile.base_salary = Decimal(1)  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        EmployeeProfile(salary=Decimal(1))  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pension_pct", Decimal("6.5"), "fraction between 0 and 1"),
        ("study_fund_pct", Decimal("-0.01"), "fraction between 0 and 1"),
        ("base_salary", Decimal(-1), "non-negative"),
        ("children_under_23", -1, "greater than or equal to 0"),
    ],
)
def test_profile_rejects_bad_values(field: str, value: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        EmployeeProfile(**{field: value})


def test_scenario_is_a_discriminated_union() -> None:
    adapter = TypeAdapter(Scenario)
    assert adapter.validate_python({"kind": "company_car", "car_id": "CAR-10"}) == CompanyCar(
        car_id="CAR-10"
    )
    assert isinstance(
        adapter.validate_python({"kind": "family_car", "car_id": "CAR-19"}), FamilyCar
    )
    assert adapter.validate_python({"kind": "waiver"}) == Waiver()
    assert adapter.validate_python(
        {"kind": "current_maintenance", "amount": "1500"}
    ) == CurrentMaintenance(amount=Decimal(1500))
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "lease"})


def test_participation_source_only_for_given_values() -> None:
    with pytest.raises(ValidationError):
        CompanyCar(car_id="CAR-10", participation_source="catalog_default")  # type: ignore[arg-type]


def test_missing_inputs_lists_fields_once() -> None:
    error = MissingInputs(["bonus", "pension_pct", "bonus"])
    assert error.fields == ("bonus", "pension_pct")
    assert str(error) == "missing inputs: bonus, pension_pct"


# --- context --------------------------------------------------------------------------------


def test_context_indexes_data(ctx) -> None:  # type: ignore[no-untyped-def]
    assert len(ctx.catalog) == 20
    assert len(ctx.occupations) == 14
    assert ctx.is_family_car("CAR-19") and ctx.is_family_car("CAR-20")
    assert not ctx.is_family_car("CAR-10")


def test_context_rejects_unknown_family_car() -> None:
    rules = load_rules()
    bad = rules.model_copy(
        update={"family_track": rules.family_track.model_copy(update={"cars": ("CAR-19", "X")})}
    )
    with pytest.raises(ContextError, match="family_track.cars: X is not in the catalog"):
        build_context(rules=bad)


def test_context_rejects_regular_car_listed_as_family() -> None:
    rules = load_rules()
    bad = rules.model_copy(
        update={
            "family_track": rules.family_track.model_copy(
                update={"cars": ("CAR-19", "CAR-20", "CAR-10")}
            )
        }
    )
    with pytest.raises(ContextError, match="CAR-10 has catalog group 'ג', expected 'משפחתי'"):
        build_context(rules=bad)


def test_context_rejects_unlisted_family_catalog_car() -> None:
    rules = load_rules()
    bad = rules.model_copy(
        update={"family_track": rules.family_track.model_copy(update={"cars": ("CAR-19",)})}
    )
    with pytest.raises(ContextError, match="CAR-20 is in group 'משפחתי' but not listed"):
        build_context(rules=bad)


def test_context_rejects_unknown_catalog_group() -> None:
    catalog = load_catalog()
    bad = (*catalog[:-1], catalog[-1].model_copy(update={"group": "ה"}))
    with pytest.raises(ContextError, match="unknown group 'ה'"):
        build_context(catalog=bad)

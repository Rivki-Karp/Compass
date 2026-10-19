"""ExternalCar: today's company car when it is not in the catalog (priced from vehicles.db)."""

import sqlite3
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from compass.config import VEHICLES_DB
from compass.data.vehicles import VehicleRecord, get_value_of_use
from compass.engine.compare import compare
from compass.engine.context import EngineContext, build_context
from compass.engine.decimal_math import exact
from compass.engine.eligibility import check_eligibility
from compass.engine.models import CompanyCar, EmployeeProfile, ExternalCar, Waiver
from compass.engine.net import GROSS_UP_TOLERANCE, compute_net
from compass.engine.options import list_options
from compass.engine.serialize import to_api_dict
from compass.search.search import tax_authority_key

PROFILE = EmployeeProfile(
    group="ב",
    occupation="מפתח/ת תוכנה",
    base_salary=D(18500),
    commissions=D(0),
    bonus=D(0),
    pension_pct=D("0.065"),
    study_fund_pct=D("0.025"),
    credit_points=D(3),
    children_under_23=0,
)


def _external(record: VehicleRecord, participation: D = D(300)) -> ExternalCar:
    return ExternalCar(
        vehicle_key=tax_authority_key(record),
        label=f"{record.commercial_name} {record.registration_year}",
        value_of_use=record.value_of_use,
        drive=record.drive,
        participation=participation,
    )


@pytest.fixture(scope="module")
def corolla_cross_2023() -> VehicleRecord:
    record = get_value_of_use(2026, 2023, 1, "00413", "00296")
    assert record is not None and record.commercial_name == "COROLLA CROSS"
    return record


@pytest.fixture(scope="module")
def electric_2024() -> VehicleRecord:
    conn = sqlite3.connect(f"{VEHICLES_DB.as_uri()}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT manufacturer_code, model_code FROM vehicles WHERE tax_year = 2026 AND "
        "registration_year = 2024 AND vehicle_type_code = 1 AND drive_code = 3 "
        "ORDER BY manufacturer_code, model_code LIMIT 1"
    ).fetchone()
    conn.close()
    record = get_value_of_use(2026, 2024, 1, *row)
    assert record is not None and record.drive == "electric"
    return record


def test_priced_from_the_dataset(ctx: EngineContext, corolla_cross_2023: VehicleRecord) -> None:
    today = _external(corolla_cross_2023)
    b = compute_net(PROFILE, today, ctx)
    assert b.value_of_use == corolla_cross_2023.value_of_use
    assert b.car_id is None and b.vehicle_key == "2026-2023-1-00413-00296"
    assert b.participation == D(300) and b.metadata.participation_source == "employee_input"
    assert b.electric_gross == 0
    with exact():
        assert b.taxable_income == D(18500) + corolla_cross_2023.value_of_use


def test_participation_is_required() -> None:
    with pytest.raises(ValidationError, match="participation"):
        ExternalCar(vehicle_key="k", value_of_use=D(4000), drive="petrol")  # type: ignore[call-arg]


def test_electric_external_car_gets_the_gross_up(
    ctx: EngineContext, electric_2024: VehicleRecord
) -> None:
    rules = ctx.rules
    no_bonus = build_context(
        rules=rules.model_copy(
            update={"electric": rules.electric.model_copy(update={"net_bonus": D(0)})}
        )
    )
    today = _external(electric_2024)
    with_g, without = compute_net(PROFILE, today, ctx), compute_net(PROFILE, today, no_bonus)
    assert with_g.electric_gross > 0 and with_g.metadata.electric_method == "gross_up"
    assert with_g.net is not None and without.net is not None
    with exact():
        assert abs(with_g.net - without.net - rules.electric.net_bonus) < GROSS_UP_TOLERANCE


def test_warning_and_no_group_check(ctx: EngineContext, corolla_cross_2023: VehicleRecord):
    result = compare(PROFILE, _external(corolla_cross_2023), Waiver(), ctx)
    assert [(w.code, dict(w.facts)) for w in result.warnings] == [
        (
            "current_car_not_in_catalog",
            {"vehicle_key": "2026-2023-1-00413-00296", "label": "COROLLA CROSS 2023"},
        )
    ]
    facts = [dict(f) for f in result.explanation_facts]
    assert {"kind": "value_of_use_removed", "amount": int(corolla_cross_2023.value_of_use)} in facts
    with exact():
        assert sum(line.net_effect for line in result.delta_lines) == result.diff


def test_today_only(ctx: EngineContext, corolla_cross_2023: VehicleRecord) -> None:
    external = _external(corolla_cross_2023)
    with pytest.raises(ValueError, match="today only"):
        compare(PROFILE, CompanyCar(car_id="CAR-06"), external, ctx)
    verdict = check_eligibility(PROFILE, external, ctx)
    assert (verdict.status, verdict.reason) == ("eligible", "current_arrangement")


def test_options_and_serialization(ctx: EngineContext, corolla_cross_2023: VehicleRecord):
    options = list_options(PROFILE, _external(corolla_cross_2023), ctx)
    assert len(options) == 21  # all 20 catalog cars + the waiver: none of them is "today"
    data = to_api_dict(options[0].comparison, ctx.rules)
    assert data["today"]["vehicle_key"] == "2026-2023-1-00413-00296"
    assert data["today"]["scenario"]["kind"] == "external_car"

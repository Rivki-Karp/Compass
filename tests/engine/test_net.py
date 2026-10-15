from decimal import Decimal as D

import pytest

from compass.engine.context import ContextError, EngineContext, build_context
from compass.engine.decimal_math import to_display
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    MissingInputs,
    Waiver,
)
from compass.engine.net import GROSS_UP_TOLERANCE, compute_net
from compass.reference import ReferenceCase, load_reference_cases
from compass.rules import load_rules

PROFILE = EmployeeProfile(
    group="ג",
    occupation="מנהל/ת מוצר",
    base_salary=D(18500),
    commissions=D(0),
    bonus=D(0),
    pension_pct=D("0.06"),
    study_fund_pct=D("0.025"),
    credit_points=D("2.75"),
    children_under_23=2,
)


@pytest.fixture(scope="module")
def cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    return load_reference_cases(ctx)


def _ctx_with(**electric: object) -> EngineContext:
    rules = load_rules()
    return build_context(
        rules=rules.model_copy(update={"electric": rules.electric.model_copy(update=electric)})
    )


# --- reference values per scenario (the full golden comparison is in test_golden.py) --------


@pytest.mark.parametrize("employee_id", ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"])
def test_reference_nets(cases: dict[str, ReferenceCase], ctx: EngineContext, employee_id: str):
    case = cases[employee_id]
    exp = case.expected
    for side, scenario in (("today", case.today), ("alternative", case.alternative)):
        b = compute_net(case.profile, scenario, ctx)
        assert b.net is not None
        assert to_display(b.net, ctx.rules) == exp[f"net_{side}"]
        assert to_display(b.income_tax, ctx.rules) == exp[f"tax_{side}"]
        assert to_display(b.national_insurance + b.health, ctx.rules) == exp[f"ni_health_{side}"]


def test_gross_up_is_unrounded_and_nets_exactly_250(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    expected = {"E-001": D("439.9085"), "E-004": D("439.9085"), "E-003": D("473.2160")}
    expected["E-006"] = D("473.2160")
    for employee_id, g in expected.items():
        case = cases[employee_id]
        b = compute_net(case.profile, case.alternative, ctx)
        assert b.electric_gross.quantize(D("0.0001")) == g
        assert b.electric_gross != b.electric_gross.to_integral_value()  # not rounded
        no_bonus = compute_net(case.profile, case.alternative, _ctx_with(net_bonus=D(0)))
        assert no_bonus.electric_gross == 0
        assert b.net is not None and no_bonus.net is not None
        assert abs(b.net - no_bonus.net - D(250)) < GROSS_UP_TOLERANCE
        assert b.metadata.electric_method == "gross_up"


def test_gross_up_is_deterministic(ctx: EngineContext) -> None:
    first = compute_net(PROFILE, CompanyCar(car_id="CAR-10"), ctx)
    second = compute_net(PROFILE, CompanyCar(car_id="CAR-10"), ctx)
    assert first.electric_gross == second.electric_gross


def test_gross_up_crossing_the_ni_ceiling(ctx: EngineContext) -> None:
    # taxable just under the NI/health ceiling: the gross-up straddles it.
    profile = PROFILE.model_copy(update={"base_salary": D(50695) - D(3130) - D(100)})
    b = compute_net(profile, CompanyCar(car_id="CAR-10"), ctx)
    assert b.taxable_income - b.electric_gross < D(50695) < b.taxable_income
    zero = compute_net(profile, CompanyCar(car_id="CAR-10"), _ctx_with(net_bonus=D(0)))
    assert b.net is not None and zero.net is not None
    assert abs(b.net - zero.net - D(250)) < GROSS_UP_TOLERANCE


def test_electric_method_gross(ctx: EngineContext) -> None:
    b = compute_net(PROFILE, CompanyCar(car_id="CAR-10"), _ctx_with(method="gross"))
    assert b.electric_gross == D(250)
    assert b.metadata.electric_method == "gross"


@pytest.mark.parametrize("car_id", ["CAR-16", "CAR-09", "CAR-07"])  # plug-in, hybrid, petrol
def test_no_gross_up_unless_fully_electric(ctx: EngineContext, car_id: str) -> None:
    b = compute_net(PROFILE.model_copy(update={"group": "ד"}), CompanyCar(car_id=car_id), ctx)
    assert b.electric_gross == 0
    assert b.metadata.electric_method is None


# --- what is cash, taxable, pensionable --------------------------------------------------------


def test_value_of_use_is_taxable_but_not_cash_or_pensionable(ctx: EngineContext) -> None:
    b = compute_net(PROFILE, CompanyCar(car_id="CAR-09"), ctx)  # COROLLA CROSS, value 4,070
    assert b.value_of_use == D(4070)
    assert b.taxable_income == D(18500) + D(4070)
    assert b.employee_pension == D(18500) * D("0.06")
    assert b.employee_study == D(18500) * D("0.025")
    assert b.net == (
        b.cash_income
        - b.income_tax
        - b.national_insurance
        - b.health
        - b.employee_pension
        - b.employee_study
        - b.participation
    )


def test_maintenance_is_cash_and_taxable_but_not_pensionable(ctx: EngineContext) -> None:
    b = compute_net(PROFILE, CurrentMaintenance(amount=D(1500)), ctx)
    assert b.taxable_income == D(20000)
    assert b.cash_income == D(18500)
    assert b.employee_pension == D(18500) * D("0.06")
    assert b.participation == 0 and b.value_of_use == 0
    assert b.metadata.participation_source is None


def test_waiver_maintenance_comes_from_occupation(ctx: EngineContext) -> None:
    b = compute_net(PROFILE, Waiver(), ctx)
    assert b.maintenance == ctx.occupations["מנהל/ת מוצר"].waiver_maintenance


def test_electric_gross_is_not_pensionable(ctx: EngineContext) -> None:
    b = compute_net(PROFILE, CompanyCar(car_id="CAR-10"), ctx)
    assert b.electric_gross > 0
    assert b.employee_pension == D(18500) * D("0.06")
    assert b.pension_credit == load_rules().net_method.pension_credit.rate * D("0.07") * D(9500)


def test_contributions_include_commissions_and_bonus(ctx: EngineContext) -> None:
    profile = PROFILE.model_copy(update={"commissions": D(2000), "bonus": D(500)})
    b = compute_net(profile, CompanyCar(car_id="CAR-09"), ctx)
    assert b.cash_income == D(21000)
    assert b.employee_pension == D(21000) * D("0.06")


def test_family_share_is_a_net_deduction(ctx: EngineContext) -> None:
    profile = PROFILE.model_copy(update={"group": "ב"})
    b = compute_net(profile, FamilyCar(car_id="CAR-19"), ctx)
    assert b.family_employee_share == (D(6000) - D(3700)) * D("0.5")
    assert b.taxable_income == b.cash_income + b.value_of_use  # share does not reduce taxable
    santa_fe = compute_net(profile, FamilyCar(car_id="CAR-20"), ctx)
    assert santa_fe.family_employee_share == (D(5600) - D(3700)) * D("0.5")
    top = profile.model_copy(update={"group": "ד"})
    top_share = compute_net(top, FamilyCar(car_id="CAR-20"), ctx).family_employee_share
    assert top_share == (D(5600) - D(5200)) * D("0.5")
    # A budget above the car's cost: no share (never negative).
    rules = load_rules()
    rich_ctx = build_context(
        rules=rules.model_copy(update={"budgets": {**rules.budgets, "ד": D(9000)}})
    )
    assert compute_net(top, FamilyCar(car_id="CAR-20"), rich_ctx).family_employee_share == 0


# --- participation and metadata ---------------------------------------------------------------


def test_participation_sources(ctx: EngineContext) -> None:
    default = compute_net(PROFILE, CompanyCar(car_id="CAR-10"), ctx)
    assert default.participation == D(300)
    assert default.metadata.participation_source == "catalog_default"
    given = compute_net(PROFILE, CompanyCar(car_id="CAR-10", participation=D(120)), ctx)
    assert given.participation == D(120)
    assert given.metadata.participation_source == "employee_input"
    rep = CompanyCar(car_id="CAR-10", participation=D(0), participation_source="representative")
    assert compute_net(PROFILE, rep, ctx).metadata.participation_source == "representative"
    # Participation never reduces the taxable value of use.
    assert given.value_of_use == default.value_of_use == D(3130)


def test_metadata_records_both_tax_years(ctx: EngineContext) -> None:
    meta = compute_net(PROFILE, CompanyCar(car_id="CAR-10"), ctx).metadata
    assert (meta.tax_tables_year, meta.value_of_use_year) == (2025, 2026)
    assert meta.rules_version == "mock-2026-10-12"


# --- inputs ---------------------------------------------------------------------------------


def test_missing_inputs_are_listed_all_at_once(ctx: EngineContext) -> None:
    with pytest.raises(MissingInputs) as exc_info:
        compute_net(EmployeeProfile(), Waiver(), ctx)
    assert exc_info.value.fields == (
        "base_salary",
        "commissions",
        "bonus",
        "credit_points",
        "pension_pct",
        "study_fund_pct",
        "occupation",
    )
    with pytest.raises(MissingInputs) as exc_info:
        compute_net(PROFILE.model_copy(update={"group": None}), FamilyCar(car_id="CAR-19"), ctx)
    assert exc_info.value.fields == ("group",)


def test_unknown_occupation_title_is_missing(ctx: EngineContext) -> None:
    with pytest.raises(MissingInputs, match="occupation"):
        compute_net(PROFILE.model_copy(update={"occupation": "אסטרונאוט"}), Waiver(), ctx)


def test_car_kind_must_match_the_catalog(ctx: EngineContext) -> None:
    with pytest.raises(ValueError, match="family-track car; use FamilyCar"):
        compute_net(PROFILE, CompanyCar(car_id="CAR-19"), ctx)
    with pytest.raises(ValueError, match="not a family-track car"):
        compute_net(PROFILE, FamilyCar(car_id="CAR-10"), ctx)
    with pytest.raises(ValueError, match="unknown car id"):
        compute_net(PROFILE, CompanyCar(car_id="CAR-99"), ctx)


def test_ineligible_scenarios_are_still_calculated(ctx: EngineContext) -> None:
    low = PROFILE.model_copy(update={"group": "א", "children_under_23": 0})
    assert compute_net(low, CompanyCar(car_id="CAR-17"), ctx).net is not None  # group ד car
    assert compute_net(low, FamilyCar(car_id="CAR-19"), ctx).net is not None


def test_pensionable_maintenance_is_refused() -> None:
    rules = load_rules()
    bad = rules.model_copy(
        update={"waiver": rules.waiver.model_copy(update={"maintenance_is_pensionable": True})}
    )
    with pytest.raises(ContextError, match="maintenance_is_pensionable"):
        build_context(rules=bad)

from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from compass.engine.compare import compare
from compass.engine.context import EngineContext
from compass.engine.eligibility import check_eligibility
from compass.engine.models import CompanyCar, EmployeeProfile, FamilyCar, MissingInputs, Waiver
from compass.engine.net import compute_net
from compass.engine.options import list_options
from compass.reference import ReferenceCase, load_reference_cases

DEVELOPER_B = EmployeeProfile(
    group="ב",
    occupation="מפתח/ת תוכנה",  # occupation group ב
    base_salary=D(21000),
    commissions=D(0),
    bonus=D(0),
    pension_pct=D("0.065"),
    study_fund_pct=D("0.025"),
    credit_points=D("2.75"),
    children_under_23=0,
)
COROLLA_CROSS = CompanyCar(car_id="CAR-09", participation=D(300))  # group ג


@pytest.fixture(scope="module")
def cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    return load_reference_cases(ctx)


# --- warnings ---------------------------------------------------------------------------------


def test_current_car_above_group(ctx: EngineContext) -> None:
    result = compare(DEVELOPER_B, COROLLA_CROSS, CompanyCar(car_id="CAR-06"), ctx)
    assert [(w.code, dict(w.facts)) for w in result.warnings] == [
        (
            "current_car_above_group",
            {"employee_group": "ב", "car_id": "CAR-09", "car_group": "ג"},
        )
    ]
    # Non-blocking: the comparison is complete, and the group is still the profile's.
    assert result.today.net is not None
    assert check_eligibility(DEVELOPER_B, CompanyCar(car_id="CAR-10"), ctx).reason == (
        "car_group_higher"
    )


def test_group_mismatch_with_occupation(ctx: EngineContext) -> None:
    profile = DEVELOPER_B.model_copy(update={"group": "ד"})
    verdict = check_eligibility(profile, CompanyCar(car_id="CAR-17"), ctx)
    assert verdict.status == "eligible"  # the profile's group decides, the warning only flags
    assert [(w.code, dict(w.facts)) for w in verdict.warnings] == [
        (
            "group_mismatch_with_occupation",
            {"employee_group": "ד", "occupation": "מפתח/ת תוכנה", "occupation_group": "ב"},
        )
    ]
    codes = [w.code for w in compare(profile, COROLLA_CROSS, Waiver(), ctx).warnings]
    assert codes == ["group_mismatch_with_occupation"]  # ג car is not above group ד


def test_both_warnings(ctx: EngineContext) -> None:
    profile = DEVELOPER_B.model_copy(update={"group": "א"})
    codes = [w.code for w in compare(profile, COROLLA_CROSS, Waiver(), ctx).warnings]
    assert codes == ["group_mismatch_with_occupation", "current_car_above_group"]


def test_no_warning_without_the_facts(ctx: EngineContext) -> None:
    unknown = DEVELOPER_B.model_copy(update={"occupation": None})
    assert (
        compare(
            unknown,
            CompanyCar(car_id="CAR-06"),
            Waiver(maintenance=D(1500), maintenance_source="representative"),
            ctx,
        ).warnings
        == ()
    )
    family_today = DEVELOPER_B.model_copy(update={"children_under_23": 5})
    assert compare(family_today, FamilyCar(car_id="CAR-19"), Waiver(), ctx).warnings == ()


@pytest.mark.parametrize("employee_id", ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"])
def test_reference_employees_have_no_warnings(
    cases: dict[str, ReferenceCase], ctx: EngineContext, employee_id: str
) -> None:
    case = cases[employee_id]
    assert compare(case.profile, case.today, case.alternative, ctx).warnings == ()
    assert check_eligibility(case.profile, case.alternative, ctx).warnings == ()


# --- waiver override --------------------------------------------------------------------------


def test_waiver_maintenance_from_occupation_by_default(ctx: EngineContext) -> None:
    b = compute_net(DEVELOPER_B, Waiver(), ctx)
    assert b.maintenance == D(1500)
    assert b.metadata.maintenance_source == "occupation"


def test_waiver_maintenance_quoted_by_representative(ctx: EngineContext) -> None:
    quoted = Waiver(maintenance=D("1750.50"), maintenance_source="representative")
    b = compute_net(DEVELOPER_B, quoted, ctx)
    assert b.maintenance == D("1750.50")
    assert b.metadata.maintenance_source == "representative"
    default = compute_net(DEVELOPER_B, Waiver(), ctx)
    assert b.taxable_income - default.taxable_income == D("250.50")
    facts = compare(DEVELOPER_B, COROLLA_CROSS, quoted, ctx).explanation_facts
    assert {"kind": "maintenance_added", "amount": 1751, "source": "representative"} in [
        dict(f) for f in facts
    ]


def test_quoted_waiver_needs_no_occupation_to_calculate(ctx: EngineContext) -> None:
    profile = DEVELOPER_B.model_copy(update={"occupation": None})
    quoted = Waiver(maintenance=D(2000), maintenance_source="representative")
    assert compute_net(profile, quoted, ctx).maintenance == D(2000)
    with pytest.raises(MissingInputs, match="occupation"):
        compute_net(profile, Waiver(), ctx)
    # Eligibility still depends on the occupation.
    assert check_eligibility(profile, quoted, ctx).reason == "unknown_occupation"


def test_current_maintenance_source(ctx: EngineContext, cases: dict[str, ReferenceCase]) -> None:
    case = cases["E-003"]
    b = compute_net(case.profile, case.today, ctx)
    assert b.metadata.maintenance_source == "employee_input"
    assert compute_net(case.profile, case.alternative, ctx).metadata.maintenance_source is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"maintenance": D(1500)},  # a value without saying who quoted it
        {"maintenance_source": "representative"},  # a representative source without a value
    ],
)
def test_waiver_source_must_match_value(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="maintenance comes from"):
        Waiver(**kwargs)  # type: ignore[arg-type]


def test_quoted_waiver_still_counts_as_waived_today(ctx: EngineContext) -> None:
    today = Waiver(maintenance=D(1500), maintenance_source="representative")
    options = list_options(DEVELOPER_B, today, ctx)
    assert all(not isinstance(o.scenario, Waiver) for o in options)

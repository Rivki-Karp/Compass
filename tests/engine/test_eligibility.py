from decimal import Decimal as D

import pytest

from compass.engine.context import EngineContext
from compass.engine.eligibility import check_eligibility
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    MissingInputs,
    Waiver,
)
from compass.engine.options import list_options
from compass.reference import ReferenceCase, load_reference_cases

GROUP_B = EmployeeProfile(
    group="ב",
    occupation="נציג/ת מכירות שטח",
    base_salary=D(9800),
    commissions=D(2400),
    bonus=D(0),
    pension_pct=D("0.06"),
    study_fund_pct=D(0),
    credit_points=D("2.25"),
    children_under_23=3,
)


@pytest.fixture(scope="module")
def cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    return load_reference_cases(ctx)


# --- regular cars -----------------------------------------------------------------------------


def test_group_b_cannot_take_a_group_c_car(ctx: EngineContext) -> None:
    result = check_eligibility(GROUP_B, CompanyCar(car_id="CAR-10"), ctx)  # ATTO 3, group ג
    assert (result.status, result.reason) == ("not_eligible", "car_group_higher")
    assert result.facts["car_group"] == "ג" and result.facts["employee_group"] == "ב"


@pytest.mark.parametrize("car_id", ["CAR-06", "CAR-03"])  # MG4 (ב), DOLPHIN (א)
def test_own_group_or_lower_is_eligible(ctx: EngineContext, car_id: str) -> None:
    result = check_eligibility(GROUP_B, CompanyCar(car_id=car_id), ctx)
    assert (result.status, result.reason) == ("eligible", "car_group_within")


@pytest.mark.parametrize("group", [None, "ה"])
def test_unknown_group_needs_info(ctx: EngineContext, group: str | None) -> None:
    profile = GROUP_B.model_copy(update={"group": group})
    result = check_eligibility(profile, CompanyCar(car_id="CAR-03"), ctx)
    assert (result.status, result.reason) == ("needs_info", "unknown_group")


def test_group_is_never_inferred_from_the_current_car(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    case = cases["E-001"]  # drives a group ג car today
    profile = case.profile.model_copy(update={"group": None})
    assert check_eligibility(profile, case.alternative, ctx).status == "needs_info"


# --- family track -----------------------------------------------------------------------------


def test_family_track_needs_four_children(ctx: EngineContext) -> None:
    result = check_eligibility(GROUP_B, FamilyCar(car_id="CAR-19"), ctx)  # 3 children
    assert (result.status, result.reason) == ("not_eligible", "family_track_min_children")
    assert result.facts["min_children"] == 4
    four = GROUP_B.model_copy(update={"children_under_23": 4})
    assert check_eligibility(four, FamilyCar(car_id="CAR-19"), ctx).reason == "family_track"


def test_unknown_children_needs_info(ctx: EngineContext) -> None:
    profile = GROUP_B.model_copy(update={"children_under_23": None})
    result = check_eligibility(profile, FamilyCar(car_id="CAR-20"), ctx)
    assert (result.status, result.reason) == ("needs_info", "unknown_children")


# --- waiver -----------------------------------------------------------------------------------


def test_technician_cannot_waive(ctx: EngineContext) -> None:
    profile = GROUP_B.model_copy(update={"occupation": "טכנאי/ת שירות"})
    result = check_eligibility(profile, Waiver(), ctx)
    assert (result.status, result.reason) == ("not_eligible", "car_mandatory")


@pytest.mark.parametrize("occupation", [None, "אסטרונאוט"])
def test_unknown_occupation_needs_info(ctx: EngineContext, occupation: str | None) -> None:
    profile = GROUP_B.model_copy(update={"occupation": occupation})
    result = check_eligibility(profile, Waiver(), ctx)
    assert (result.status, result.reason) == ("needs_info", "unknown_occupation")


def test_waiver_allowed_by_occupation(cases: dict[str, ReferenceCase], ctx: EngineContext):
    case = cases["E-005"]
    result = check_eligibility(case.profile, case.alternative, ctx)
    assert (result.status, result.reason) == ("eligible", "waiver_allowed")
    assert result.facts["waiver_maintenance"] == case.expected["alternative"]["maintenance"]


def test_current_maintenance_is_the_current_arrangement(ctx: EngineContext) -> None:
    result = check_eligibility(GROUP_B, CurrentMaintenance(amount=D(1500)), ctx)
    assert (result.status, result.reason) == ("eligible", "current_arrangement")


@pytest.mark.parametrize("employee_id", ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"])
def test_reference_alternatives_are_eligible(
    cases: dict[str, ReferenceCase], ctx: EngineContext, employee_id: str
) -> None:
    case = cases[employee_id]
    assert case.expected["eligible"] is True
    assert check_eligibility(case.profile, case.alternative, ctx).status == "eligible"


# --- options ----------------------------------------------------------------------------------


def test_list_options_covers_catalog_and_waiver(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    case = cases["E-001"]  # today CAR-09; occupation allows a waiver; group ג; 2 children
    options = list_options(case.profile, case.today, ctx)
    scenarios = [o.scenario for o in options]
    car_ids = {s.car_id for s in scenarios if isinstance(s, CompanyCar | FamilyCar)}
    assert car_ids == set(ctx.catalog) - {"CAR-09"}  # today's car is skipped
    assert Waiver() in scenarios
    assert len(options) == 20

    statuses = [o.eligibility.status for o in options]
    assert statuses == sorted(statuses, key=["eligible", "needs_info", "not_eligible"].index)
    eligible = [o for o in options if o.eligibility.status == "eligible"]
    diffs = [o.comparison.diff for o in eligible]
    assert diffs == sorted(diffs, reverse=True)
    # Group ג: א, ב, ג cars (minus today's) + waiver are eligible; ד and family cars are not.
    assert len(eligible) == 12 + 1  # 4 + 4 + 5 cars, minus CAR-09, plus the waiver
    by_id = {
        o.scenario.car_id: o for o in options if isinstance(o.scenario, CompanyCar | FamilyCar)
    }
    assert by_id["CAR-10"].comparison.display_diff == 661
    assert by_id["CAR-19"].eligibility.reason == "family_track_min_children"
    assert by_id["CAR-14"].eligibility.reason == "car_group_higher"
    # Every option, eligible or not, is calculated.
    assert all(o.comparison.today.net is not None for o in options)


def test_list_options_skips_waiver_when_already_waived(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    case = cases["E-003"]  # today: maintenance 1,500, no car
    options = list_options(case.profile, case.today, ctx)
    assert len(options) == 20
    assert all(isinstance(o.scenario, CompanyCar | FamilyCar) for o in options)


def test_list_options_without_waiver_for_mandatory_car(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    case = cases["E-002"]  # field sales: car mandatory
    options = list_options(case.profile, case.today, ctx)
    assert Waiver() not in [o.scenario for o in options]
    assert len(options) == 19


def test_list_options_partial(cases: dict[str, ReferenceCase], ctx: EngineContext) -> None:
    case = cases["E-001"]
    profile = case.profile.model_copy(update={"pension_pct": None, "study_fund_pct": None})
    options = list_options(profile, case.today, ctx)
    full = list_options(case.profile, case.today, ctx)
    assert all(o.comparison.partial for o in options)
    assert [o.scenario for o in options] == [o.scenario for o in full]
    assert [o.comparison.diff for o in options] == [o.comparison.diff for o in full]


def test_list_options_needs_the_group(cases: dict[str, ReferenceCase], ctx: EngineContext):
    case = cases["E-001"]
    profile = case.profile.model_copy(update={"group": None, "base_salary": None})
    with pytest.raises(MissingInputs) as exc_info:
        list_options(profile, case.today, ctx)
    assert set(exc_info.value.fields) == {"base_salary", "group"}

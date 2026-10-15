"""Monthly net salary for one profile + scenario, with every formula line kept unrounded.

    cash_income        = base_salary + commissions + bonus            (contributions base "gross")
    taxable_income     = cash_income + value_of_use + maintenance + electric_gross
    income_tax         = max(0, brackets(taxable) - credit_points_value - pension_credit)
    national_insurance = two-tier(taxable), health = two-tier(taxable)
    employee_pension   = cash_income * pension_pct,  employee_study = cash_income * study_fund_pct
    net = cash_income + maintenance + electric_gross - income_tax - national_insurance - health
          - employee_pension - employee_study - participation - family_employee_share

Value of use is taxable but never cash. Maintenance and the electric gross-up are cash and
taxable but not pensionable. Nothing is rounded (rules.net_method.rounding.during = none).
"""

from dataclasses import dataclass
from decimal import Decimal

from compass.data.catalog import CatalogCar
from compass.engine import tax
from compass.engine.context import EngineContext
from compass.engine.decimal_math import ZERO, exact
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    Metadata,
    MissingInputs,
    NetBreakdown,
    ParticipationSource,
    Scenario,
    Waiver,
)

# Gross-up solver (numerical settings, not business rules).
GROSS_UP_ITERATIONS = 60  # fixed: same inputs -> same G, digit for digit
GROSS_UP_TOLERANCE = Decimal("0.0001")  # max |net gain - net_bonus| in ILS
_MAX_DOUBLINGS = 64

CONTRIBUTION_FIELDS: tuple[str, ...] = ("pension_pct", "study_fund_pct")
_ALWAYS_REQUIRED: tuple[str, ...] = (
    "base_salary",
    "commissions",
    "bonus",
    "credit_points",
    *CONTRIBUTION_FIELDS,
)


class GrossUpError(ArithmeticError):
    """The gross-up solver could not reach the net bonus (rules make the marginal rate >= 100%)."""


def missing_inputs(profile: EmployeeProfile, scenario: Scenario) -> list[str]:
    """Every profile field the calculation of `scenario` needs but does not have."""
    missing = [name for name in _ALWAYS_REQUIRED if getattr(profile, name) is None]
    if isinstance(scenario, FamilyCar) and profile.group is None:
        missing.append("group")  # the family share is measured against the group budget
    if isinstance(scenario, Waiver) and profile.occupation is None:
        missing.append("occupation")  # the waiver maintenance depends on the occupation
    return missing


@dataclass(frozen=True)
class _Fixed:
    """Everything in a scenario except the electric gross-up and the contribution rates."""

    scenario: Scenario
    car: CatalogCar | None
    cash_income: Decimal
    value_of_use: Decimal
    maintenance: Decimal
    credit_points: Decimal
    participation: Decimal
    participation_source: ParticipationSource | None
    family_employee_share: Decimal


def _car(scenario: CompanyCar | FamilyCar, ctx: EngineContext) -> CatalogCar:
    car = ctx.catalog.get(scenario.car_id)
    if car is None:
        raise ValueError(f"unknown car id {scenario.car_id!r}")
    if isinstance(scenario, FamilyCar) and not ctx.is_family_car(car.id):
        raise ValueError(f"{car.id} is not a family-track car; use CompanyCar")
    if isinstance(scenario, CompanyCar) and ctx.is_family_car(car.id):
        raise ValueError(f"{car.id} is a family-track car; use FamilyCar")
    return car


def _fix(profile: EmployeeProfile, scenario: Scenario, ctx: EngineContext) -> _Fixed:
    rules = ctx.rules
    assert profile.base_salary is not None and profile.commissions is not None
    assert profile.bonus is not None and profile.credit_points is not None
    with exact():
        # contributions_base "gross": the schema allows no other value.
        cash_income = profile.base_salary + profile.commissions + profile.bonus
        car: CatalogCar | None = None
        value_of_use = maintenance = participation = family_share = ZERO
        source: ParticipationSource | None = None

        if isinstance(scenario, CompanyCar | FamilyCar):
            car = _car(scenario, ctx)
            if scenario.participation is None:
                participation, source = car.default_employee_participation, "catalog_default"
            else:
                participation, source = scenario.participation, scenario.participation_source
            value_of_use = car.value_of_use
            if rules.net_method.participation.reduces_value_of_use:  # pragma: no cover
                value_of_use -= participation  # not supported today; the schema forbids it
            if isinstance(scenario, FamilyCar):
                assert profile.group is not None
                if profile.group not in rules.budgets:
                    raise ValueError(f"unknown group {profile.group!r}")
                # price_source "catalogue": the car's own monthly cost.
                gap = max(ZERO, car.monthly_company_cost - rules.budgets[profile.group])
                family_share = rules.family_track.gap_split_employee * gap
        elif isinstance(scenario, Waiver):
            assert profile.occupation is not None
            occupation = ctx.occupations.get(profile.occupation)
            if occupation is None:
                raise MissingInputs(["occupation"])  # not a known title: treat as unknown
            maintenance = occupation.waiver_maintenance
        elif isinstance(scenario, CurrentMaintenance):
            maintenance = scenario.amount

    return _Fixed(
        scenario=scenario,
        car=car,
        cash_income=cash_income,
        value_of_use=value_of_use,
        maintenance=maintenance,
        credit_points=profile.credit_points,
        participation=participation,
        participation_source=source,
        family_employee_share=family_share,
    )


def _breakdown(
    fixed: _Fixed,
    electric_gross: Decimal,
    pension_pct: Decimal | None,
    study_fund_pct: Decimal | None,
    ctx: EngineContext,
) -> NetBreakdown:
    rules = ctx.rules
    nm = rules.net_method
    with exact():
        taxable_maintenance = fixed.maintenance if rules.waiver.maintenance_is_taxable else ZERO
        taxable = fixed.cash_income + fixed.value_of_use + taxable_maintenance + electric_gross
        before = tax.income_tax_before_credits(taxable, nm.brackets)
        points = tax.credit_points_value(fixed.credit_points, nm)
        credit = tax.pension_credit(fixed.cash_income, nm)
        income_tax = max(ZERO, before - points - credit)
        ni = tax.national_insurance(taxable, nm)
        hl = tax.health(taxable, nm)
        pension = None if pension_pct is None else fixed.cash_income * pension_pct
        study = None if study_fund_pct is None else fixed.cash_income * study_fund_pct
        net: Decimal | None = None
        if pension is not None and study is not None:
            # participation.treatment "net_deduction": deducted from net only.
            net = (
                fixed.cash_income
                + fixed.maintenance
                + electric_gross
                - income_tax
                - ni
                - hl
                - pension
                - study
                - fixed.participation
                - fixed.family_employee_share
            )
    electric = fixed.car is not None and fixed.car.drive == "electric"
    return NetBreakdown(
        scenario=fixed.scenario,
        car_id=None if fixed.car is None else fixed.car.id,
        cash_income=fixed.cash_income,
        value_of_use=fixed.value_of_use,
        maintenance=fixed.maintenance,
        electric_gross=electric_gross,
        taxable_income=taxable,
        income_tax_before_credits=before,
        credit_points_value=points,
        pension_credit=credit,
        income_tax=income_tax,
        national_insurance=ni,
        health=hl,
        employee_pension=pension,
        employee_study=study,
        participation=fixed.participation,
        family_employee_share=fixed.family_employee_share,
        net=net,
        metadata=Metadata(
            rules_version=rules.version,
            tax_tables_year=nm.tax_year,
            value_of_use_year=rules.value_of_use.tax_year,
            participation_source=fixed.participation_source,
            electric_method=rules.electric.method if electric else None,
        ),
    )


def solve_gross_up(fixed: _Fixed, ctx: EngineContext) -> Decimal:
    """Smallest-found G with net(G) - net(0) >= net_bonus, within GROSS_UP_TOLERANCE.

    Bisection on the full net function (no marginal-rate shortcut), so G may cross a bracket or
    the NI threshold/ceiling. Contribution rates don't matter: G is not pensionable, so they
    cancel out of net(G) - net(0); they are taken as 0 here.
    """
    target = ctx.rules.electric.net_bonus

    def net_at(g: Decimal) -> Decimal:
        net = _breakdown(fixed, g, ZERO, ZERO, ctx).net
        assert net is not None
        return net

    base = net_at(ZERO)

    def gain(g: Decimal) -> Decimal:
        with exact():
            return net_at(g) - base

    if target == 0:
        return ZERO
    with exact():
        low, high = ZERO, target  # gain(g) <= g, so G >= net_bonus
        for _ in range(_MAX_DOUBLINGS):
            if gain(high) >= target:
                break
            low, high = high, high * 2
        else:
            raise GrossUpError(f"cannot gross up {target}: marginal deductions reach 100%")
        for _ in range(GROSS_UP_ITERATIONS):
            mid = (low + high) / 2
            if gain(mid) < target:
                low = mid
            else:
                high = mid
        error = gain(high) - target
    if not ZERO <= error < GROSS_UP_TOLERANCE:
        raise GrossUpError(f"gross-up did not converge: net gain off by {error}")
    return high


def _electric_gross(fixed: _Fixed, ctx: EngineContext) -> Decimal:
    if fixed.car is None or fixed.car.drive != "electric":  # not plug-in, not hybrid
        return ZERO
    electric = ctx.rules.electric
    if electric.method == "gross":
        return electric.gross_amount
    return solve_gross_up(fixed, ctx)


def compute_with_rates(
    profile: EmployeeProfile,
    scenario: Scenario,
    ctx: EngineContext,
    pension_pct: Decimal | None,
    study_fund_pct: Decimal | None,
) -> NetBreakdown:
    """compute_net with explicit contribution rates (None -> those lines and net are None).

    Used by compare() for the partial diff; checks every other input.
    """
    missing = [f for f in missing_inputs(profile, scenario) if f not in CONTRIBUTION_FIELDS]
    if missing:
        raise MissingInputs(missing)
    fixed = _fix(profile, scenario, ctx)
    return _breakdown(fixed, _electric_gross(fixed, ctx), pension_pct, study_fund_pct, ctx)


def compute_net(profile: EmployeeProfile, scenario: Scenario, ctx: EngineContext) -> NetBreakdown:
    """The full breakdown. Raises MissingInputs listing every unknown input at once."""
    missing = missing_inputs(profile, scenario)
    if missing:
        raise MissingInputs(missing)
    return compute_with_rates(profile, scenario, ctx, profile.pension_pct, profile.study_fund_pct)

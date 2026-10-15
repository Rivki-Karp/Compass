"""Property checks over a salary grid (plain loops, deterministic)."""

import itertools
from decimal import Decimal as D

import pytest

from compass.engine.compare import compare
from compass.engine.context import EngineContext, build_context
from compass.engine.decimal_math import exact
from compass.engine.models import CompanyCar, EmployeeProfile, Waiver
from compass.engine.net import GROSS_UP_TOLERANCE, compute_net

SALARIES = [D(s) for s in range(6000, 60001, 1500)]
TODAY = CompanyCar(car_id="CAR-07", participation=D(250))  # petrol COROLLA


def _profile(salary: D) -> EmployeeProfile:
    return EmployeeProfile(
        group="ד",
        occupation="מנהל/ת מחלקה",
        base_salary=salary,
        commissions=D(0),
        bonus=D(0),
        pension_pct=D("0.06"),
        study_fund_pct=D("0.025"),
        credit_points=D("2.25"),
        children_under_23=1,
    )


@pytest.fixture(scope="module")
def electric_ids(ctx: EngineContext) -> list[str]:
    ids = [car.id for car in ctx.catalog.values() if car.drive == "electric"]
    assert len(ids) == 7
    return ids


@pytest.fixture(scope="module")
def no_bonus_ctx(ctx: EngineContext) -> EngineContext:
    rules = ctx.rules
    electric = rules.electric.model_copy(update={"net_bonus": D(0)})
    return build_context(
        rules=rules.model_copy(update={"electric": electric}),
        catalog=tuple(ctx.catalog.values()),
        occupations=tuple(ctx.occupations.values()),
    )


def test_gross_up_nets_exactly_the_bonus(
    ctx: EngineContext, no_bonus_ctx: EngineContext, electric_ids: list[str]
) -> None:
    for salary in SALARIES:
        for car_id in electric_ids:
            scenario = CompanyCar(car_id=car_id)
            with_g = compute_net(_profile(salary), scenario, ctx)
            without = compute_net(_profile(salary), scenario, no_bonus_ctx)
            assert with_g.net is not None and without.net is not None
            with exact():
                gain = with_g.net - without.net
            assert abs(gain - ctx.rules.electric.net_bonus) < GROSS_UP_TOLERANCE, (salary, car_id)


def test_delta_lines_sum_to_diff(ctx: EngineContext, electric_ids: list[str]) -> None:
    alternatives = [CompanyCar(car_id=car_id) for car_id in electric_ids] + [Waiver()]
    for salary in SALARIES:
        for alternative in alternatives:
            result = compare(_profile(salary), TODAY, alternative, ctx)
            with exact():
                assert sum(line.net_effect for line in result.delta_lines) == result.diff
            shown = sum(line.net_effect for line in result.display_delta_lines)
            assert shown == result.display_diff


def test_net_never_exceeds_cash(ctx: EngineContext, electric_ids: list[str]) -> None:
    for salary in SALARIES:
        for scenario in [*(CompanyCar(car_id=i) for i in electric_ids), Waiver(), TODAY]:
            b = compute_net(_profile(salary), scenario, ctx)
            assert b.net is not None
            with exact():
                assert b.net <= b.cash_income + b.maintenance + b.electric_gross


@pytest.mark.parametrize("car_id", ["CAR-07", "CAR-10"])  # petrol, electric (G changes too)
def test_higher_value_of_use_never_increases_net(ctx: EngineContext, car_id: str) -> None:
    rules, occupations = ctx.rules, tuple(ctx.occupations.values())
    values = [D(v) for v in range(0, 10001, 1000)]
    contexts = []
    for value in values:
        catalog = tuple(
            car.model_copy(update={"value_of_use": value}) if car.id == car_id else car
            for car in ctx.catalog.values()
        )
        contexts.append(build_context(rules=rules, catalog=catalog, occupations=occupations))
    for salary in SALARIES:
        nets = [compute_net(_profile(salary), CompanyCar(car_id=car_id), c).net for c in contexts]
        assert all(a is not None and b is not None and b <= a for a, b in itertools.pairwise(nets))

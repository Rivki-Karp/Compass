"""2,000 seeded random profiles: the exact-Decimal engine may only ever raise MissingInputs.

Inputs look like real ones: amounts with up to 2 decimals, rates with up to 2 decimals as a
percentage (6.25% = 0.0625), credit points in 0.25 steps, every catalog car and the waiver
(from the occupation or quoted). Some inputs are randomly unknown.
"""

import json
import random
from decimal import Decimal as D

from compass.engine.compare import compare
from compass.engine.context import EngineContext
from compass.engine.eligibility import check_eligibility
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    MissingInputs,
    Scenario,
    Waiver,
)
from compass.engine.serialize import to_api_dict

PROFILES = 2000
SEED = 20261015


def _amount(rng: random.Random, high: int) -> D:
    return D(rng.randrange(0, high * 100 + 1)).scaleb(-2)  # up to 2 decimals, exact


def _maybe(rng: random.Random, value: object) -> object:
    return None if rng.random() < 0.04 else value


def _car(rng: random.Random, ctx: EngineContext, car_id: str) -> Scenario:
    participation = None if rng.random() < 0.5 else _amount(rng, 800)
    if ctx.is_family_car(car_id):
        return FamilyCar(car_id=car_id, participation=participation)
    return CompanyCar(car_id=car_id, participation=participation)


def _waiver(rng: random.Random) -> Waiver:
    if rng.random() < 0.5:
        return Waiver()
    return Waiver(maintenance=_amount(rng, 4000), maintenance_source="representative")


def test_engine_only_raises_missing_inputs(ctx: EngineContext) -> None:
    rng = random.Random(SEED)
    car_ids = list(ctx.catalog)
    titles = [*ctx.occupations, "לא ידוע"]
    alternatives: list[str | None] = [*car_ids, None]  # None -> waiver
    outcomes = {"complete": 0, "partial": 0, "missing": 0}

    for index in range(PROFILES):
        profile = EmployeeProfile(
            group=_maybe(rng, rng.choice(ctx.rules.group_order)),
            occupation=_maybe(rng, rng.choice(titles)),
            base_salary=_maybe(rng, _amount(rng, 120_000)),
            commissions=_maybe(rng, _amount(rng, 15_000) if rng.random() < 0.3 else D(0)),
            bonus=_maybe(rng, _amount(rng, 15_000) if rng.random() < 0.2 else D(0)),
            pension_pct=_maybe(rng, D(rng.randrange(0, 1001)).scaleb(-4)),  # 0.00%..10.00%
            study_fund_pct=_maybe(rng, D(rng.randrange(0, 1001)).scaleb(-4)),
            credit_points=_maybe(rng, D(rng.randrange(0, 41)) * D("0.25")),
            children_under_23=_maybe(rng, rng.randrange(0, 8)),
        )
        roll = rng.random()
        if roll < 0.75:
            today: Scenario = _car(rng, ctx, rng.choice(car_ids))
        elif roll < 0.9:
            today = CurrentMaintenance(amount=_amount(rng, 4000))
        else:
            today = _waiver(rng)
        # Cycle through every catalog car and the waiver, so each is hit ~95 times.
        target = alternatives[index % len(alternatives)]
        alternative = _waiver(rng) if target is None else _car(rng, ctx, target)

        check_eligibility(profile, alternative, ctx)
        try:
            result = compare(profile, today, alternative, ctx)
        except MissingInputs as missing:
            assert missing.fields
            outcomes["missing"] += 1
            continue
        outcomes["partial" if result.partial else "complete"] += 1
        assert sum(line.net_effect for line in result.display_delta_lines) == result.display_diff
        json.dumps(to_api_dict(result, ctx.rules), ensure_ascii=False)

    # The random mix really exercised every path.
    assert all(count > 50 for count in outcomes.values()), outcomes

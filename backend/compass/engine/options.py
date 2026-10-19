"""Every alternative an employee could pick, with its eligibility verdict and diff vs today."""

from collections.abc import Callable
from decimal import Decimal

from compass.engine.compare import compare
from compass.engine.context import EngineContext
from compass.engine.eligibility import check_eligibility
from compass.engine.models import (
    CURRENT_SITUATION,
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    MissingInputs,
    Option,
    Scenario,
    Waiver,
)
from compass.engine.net import CONTRIBUTION_FIELDS, missing_inputs

_STATUS_RANK = {"eligible": 0, "needs_info": 1, "not_eligible": 2}


def _is_today(option: Scenario, today: Scenario | None) -> bool:
    if today is None:
        return False
    if isinstance(option, CompanyCar | FamilyCar):
        return isinstance(today, CompanyCar | FamilyCar) and today.car_id == option.car_id
    return isinstance(today, Waiver | CurrentMaintenance)  # option is a Waiver


def _candidates(profile: EmployeeProfile, ctx: EngineContext) -> list[Scenario]:
    candidates: list[Scenario] = [
        FamilyCar(car_id=car_id) if ctx.is_family_car(car_id) else CompanyCar(car_id=car_id)
        for car_id in ctx.catalog
    ]
    occupation = None if profile.occupation is None else ctx.occupations.get(profile.occupation)
    if occupation is not None and occupation.waiver_allowed:
        candidates.append(Waiver())
    return candidates


def list_options(
    profile: EmployeeProfile,
    today: Scenario | None,
    ctx: EngineContext,
    adjust: Callable[[Scenario], Scenario] | None = None,
) -> list[Option]:
    """Every catalog car (all groups + family) and the waiver if the occupation allows it,
    except the option that is today's arrangement. New cars use the catalog participation
    unless `adjust` changes a candidate (the caller's way to apply a stated or confirmed
    participation, so each option is computed exactly as a single compare() of it would be).

    Sorted: eligible by diff (best first), then needs_info, then not_eligible, each by diff;
    ties keep catalog order. With unknown contribution rates the comparisons are partial.
    `today` None (not known yet): every option with its own net and no diff, in the same order
    (by net). Raises MissingInputs (all fields at once) if any option cannot be compared.
    """
    candidates = [c for c in _candidates(profile, ctx) if not _is_today(c, today)]
    if adjust is not None:
        candidates = [adjust(c) for c in candidates]
    missing: list[str] = []
    for candidate in candidates if today is None else [today, *candidates]:
        missing += missing_inputs(profile, candidate)
    if today is None and missing:
        raise MissingInputs([CURRENT_SITUATION, *missing])  # neither a diff nor a net
    if any(field not in CONTRIBUTION_FIELDS for field in missing):
        raise MissingInputs(missing)  # MissingInputs drops duplicates

    options = [
        Option(
            scenario=candidate,
            eligibility=check_eligibility(profile, candidate, ctx),
            comparison=compare(profile, today, candidate, ctx),
        )
        for candidate in candidates
    ]
    # Two stable sorts (no Decimal negation, which would round in the default context).
    by_diff = sorted(options, key=_rank_value, reverse=True)
    return sorted(by_diff, key=lambda o: _STATUS_RANK[o.eligibility.status])


def _rank_value(option: Option) -> Decimal:
    """The diff; with today unknown, the option's own net (the same order: today is common)."""
    comparison = option.comparison
    if comparison.diff is not None:
        return comparison.diff
    assert comparison.alternative.net is not None
    return comparison.alternative.net

"""Eligibility verdicts. Separate from the calculation: an ineligible scenario is still calculated
(shown as "not eligible - hypothetical"); this module only says whether it is allowed.

Reason codes:
    eligible:      car_group_within, family_track, waiver_allowed, current_arrangement
    not_eligible:  car_group_higher, family_track_min_children, car_mandatory, waiver_not_allowed
    needs_info:    unknown_group, unknown_children, unknown_occupation

The group is never inferred (not from the current car, not from the occupation).
"""

from compass.engine.context import EngineContext
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    Eligibility,
    EmployeeProfile,
    FamilyCar,
    Scenario,
    Waiver,
)


def _company_car(profile: EmployeeProfile, scenario: CompanyCar, ctx: EngineContext) -> Eligibility:
    car = ctx.catalog.get(scenario.car_id)
    if car is None:
        raise ValueError(f"unknown car id {scenario.car_id!r}")
    if ctx.is_family_car(car.id):
        raise ValueError(f"{car.id} is a family-track car; use FamilyCar")
    order = ctx.rules.group_order
    facts = {"car_id": car.id, "car_group": car.group, "employee_group": profile.group}
    if profile.group is None or profile.group not in order:
        return Eligibility(status="needs_info", reason="unknown_group", facts=facts)
    # choose_from "own_group_or_lower" (the only value the schema allows)
    if order.index(car.group) <= order.index(profile.group):
        return Eligibility(status="eligible", reason="car_group_within", facts=facts)
    return Eligibility(status="not_eligible", reason="car_group_higher", facts=facts)


def _family_car(profile: EmployeeProfile, scenario: FamilyCar, ctx: EngineContext) -> Eligibility:
    if scenario.car_id not in ctx.catalog:
        raise ValueError(f"unknown car id {scenario.car_id!r}")
    if not ctx.is_family_car(scenario.car_id):
        raise ValueError(f"{scenario.car_id} is not a family-track car; use CompanyCar")
    track = ctx.rules.family_track
    facts = {
        "car_id": scenario.car_id,
        "children_under_23": profile.children_under_23,
        "min_children": track.min_children,
        "child_max_age": track.child_max_age,
    }
    if profile.children_under_23 is None:
        return Eligibility(status="needs_info", reason="unknown_children", facts=facts)
    if profile.children_under_23 < track.min_children:
        return Eligibility(status="not_eligible", reason="family_track_min_children", facts=facts)
    return Eligibility(status="eligible", reason="family_track", facts=facts)


def _waiver(profile: EmployeeProfile, ctx: EngineContext) -> Eligibility:
    # waiver.allowed_by "occupation" (the only value the schema allows)
    occupation = None if profile.occupation is None else ctx.occupations.get(profile.occupation)
    if occupation is None:
        return Eligibility(
            status="needs_info",
            reason="unknown_occupation",
            facts={"occupation": profile.occupation},
        )
    facts = {
        "occupation": occupation.title,
        "car_mandatory": occupation.car_mandatory,
        "waiver_allowed": occupation.waiver_allowed,
        "waiver_maintenance": occupation.waiver_maintenance,
    }
    if occupation.car_mandatory:
        return Eligibility(status="not_eligible", reason="car_mandatory", facts=facts)
    if not occupation.waiver_allowed:
        return Eligibility(status="not_eligible", reason="waiver_not_allowed", facts=facts)
    return Eligibility(status="eligible", reason="waiver_allowed", facts=facts)


def check_eligibility(
    profile: EmployeeProfile, scenario: Scenario, ctx: EngineContext
) -> Eligibility:
    if isinstance(scenario, CompanyCar):
        return _company_car(profile, scenario, ctx)
    if isinstance(scenario, FamilyCar):
        return _family_car(profile, scenario, ctx)
    if isinstance(scenario, Waiver):
        return _waiver(profile, ctx)
    if isinstance(scenario, CurrentMaintenance):
        # What the employee already has today; nothing to qualify for.
        return Eligibility(
            status="eligible", reason="current_arrangement", facts={"amount": scenario.amount}
        )
    raise TypeError(f"unknown scenario {scenario!r}")  # pragma: no cover

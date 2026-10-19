"""Today vs an alternative: exact diff, per-line attribution and structured explanation facts.

delta_lines are the signed effect of each formula line on net; they sum to `diff` exactly.
display_delta_lines are those lines rounded by the largest-remainder method so that they sum to
`display_diff` exactly (the waterfall chart depends on it).
"""

from decimal import Decimal
from typing import Any, get_args

from compass.engine.context import EngineContext
from compass.engine.decimal_math import ZERO, apportion, exact, to_agora, to_display
from compass.engine.eligibility import profile_warnings
from compass.engine.models import (
    CURRENT_SITUATION,
    TODAY_ONLY,
    Comparison,
    DeltaLine,
    DeltaLineName,
    DisplayDeltaLine,
    EmployeeProfile,
    MissingInputs,
    NetBreakdown,
    Scenario,
)
from compass.engine.net import CONTRIBUTION_FIELDS, compute_with_rates, missing_inputs

# Contribution rates tried when the employee's are unknown: the diff is reported only if it is
# the same (to the agora) at both extremes.
PROBE_RATES: tuple[Decimal, Decimal] = (Decimal(0), Decimal("0.2"))

DELTA_LINES: tuple[DeltaLineName, ...] = get_args(DeltaLineName)
_ADDED: frozenset[str] = frozenset({"cash_income", "maintenance", "electric_gross"})


def _line(breakdown: NetBreakdown, name: DeltaLineName) -> Decimal:
    value = getattr(breakdown, name)
    assert value is not None, f"{name} is unknown"
    return value


def delta_lines(today: NetBreakdown, alternative: NetBreakdown) -> tuple[DeltaLine, ...]:
    with exact():
        lines = []
        for name in DELTA_LINES:
            change = _line(alternative, name) - _line(today, name)
            lines.append(DeltaLine(line=name, net_effect=change if name in _ADDED else -change))
    return tuple(lines)


def _has_car(breakdown: NetBreakdown) -> bool:
    return breakdown.car_id is not None or breakdown.vehicle_key is not None


def _facts(today: NetBreakdown, alt: NetBreakdown, ctx: EngineContext) -> list[dict[str, Any]]:
    def show(value: Decimal) -> int:
        return to_display(value, ctx.rules)

    facts: list[dict[str, Any]] = []
    if _has_car(today) and _has_car(alt):
        facts.append(
            {
                "kind": "value_of_use_change",
                "from": show(today.value_of_use),
                "to": show(alt.value_of_use),
            }
        )
    elif _has_car(alt):
        facts.append({"kind": "value_of_use_added", "amount": show(alt.value_of_use)})
    elif _has_car(today):
        facts.append({"kind": "value_of_use_removed", "amount": show(today.value_of_use)})

    if alt.maintenance and not today.maintenance:
        facts.append(
            {
                "kind": "maintenance_added",
                "amount": show(alt.maintenance),
                "source": alt.metadata.maintenance_source,
            }
        )
    elif today.maintenance and not alt.maintenance:
        facts.append({"kind": "maintenance_removed", "amount": show(today.maintenance)})
    elif today.maintenance != alt.maintenance:
        facts.append(
            {
                "kind": "maintenance_change",
                "from": show(today.maintenance),
                "to": show(alt.maintenance),
                "source": alt.metadata.maintenance_source,
            }
        )

    if alt.electric_gross:
        method = alt.metadata.electric_method
        facts.append(
            {
                "kind": "electric_bonus",
                "method": method,
                # gross_up nets exactly net_bonus; a plain gross amount nets whatever is left.
                "net": show(ctx.rules.electric.net_bonus) if method == "gross_up" else None,
                "gross": show(alt.electric_gross),
            }
        )
    elif today.electric_gross:
        facts.append({"kind": "electric_bonus_removed", "gross": show(today.electric_gross)})

    if _has_car(today) or _has_car(alt):
        facts.append(
            {
                "kind": "participation_change",
                "from": show(today.participation),
                "to": show(alt.participation),
                "source": alt.metadata.participation_source,
            }
        )

    if alt.family_employee_share:
        facts.append({"kind": "family_share", "amount": show(alt.family_employee_share)})
    elif today.family_employee_share:
        facts.append({"kind": "family_share_removed", "amount": show(today.family_employee_share)})
    return facts


def _unknown(breakdown: NetBreakdown, missing: list[str]) -> NetBreakdown:
    update: dict[str, None] = {"net": None}
    if "pension_pct" in missing:
        update["employee_pension"] = None
    if "study_fund_pct" in missing:
        update["employee_study"] = None
    return breakdown.model_copy(update=update)


def _build(
    profile: EmployeeProfile,
    today: NetBreakdown,
    alternative: NetBreakdown,
    ctx: EngineContext,
    missing: list[str],
) -> Comparison:
    """`today`/`alternative` are complete breakdowns (probe rates stand in for unknown ones)."""
    assert today.net is not None and alternative.net is not None
    lines = delta_lines(today, alternative)
    with exact():
        diff = alternative.net - today.net
        total = sum((line.net_effect for line in lines), ZERO)
    if total != diff:  # exact arithmetic: any mismatch is a bug, never rounding noise
        raise AssertionError(f"delta lines sum to {total}, diff is {diff}")

    if missing:
        display_diff = to_display(diff, ctx.rules)  # the nets are unknown
        shown_today, shown_alt = _unknown(today, missing), _unknown(alternative, missing)
    else:
        display_diff = to_display(alternative.net, ctx.rules) - to_display(today.net, ctx.rules)
        shown_today, shown_alt = today, alternative
    rounded = apportion([line.net_effect for line in lines], display_diff)
    display_lines = tuple(
        DisplayDeltaLine(line=line.line, net_effect=amount)
        for line, amount in zip(lines, rounded, strict=True)
    )
    assert sum(line.net_effect for line in display_lines) == display_diff

    return Comparison(
        today=shown_today,
        alternative=shown_alt,
        diff=diff,
        display_diff=display_diff,
        delta_lines=lines,
        display_delta_lines=display_lines,
        explanation_facts=tuple(_facts(today, alternative, ctx)),
        warnings=profile_warnings(profile, today.scenario, ctx),
        missing=tuple(missing),
    )


def compare(
    profile: EmployeeProfile,
    today: Scenario | None,
    alternative: Scenario,
    ctx: EngineContext,
) -> Comparison:
    """Compare two scenarios for one profile.

    If only contribution rates are unknown, the diff is still returned when it does not depend
    on them (checked at PROBE_RATES, to the agora): nets are then None and `missing` lists the
    unknown rates. `today` None (not known yet): the alternative's own net and no diff (see
    Comparison). Otherwise raises MissingInputs listing every unknown input.
    """
    if isinstance(alternative, TODAY_ONLY):
        raise ValueError(f"{alternative.kind} describes today only, not an alternative")
    if today is None:
        return _without_today(profile, alternative, ctx)
    missing = list(
        dict.fromkeys(missing_inputs(profile, today) + missing_inputs(profile, alternative))
    )
    if any(field not in CONTRIBUTION_FIELDS for field in missing):
        raise MissingInputs(missing)
    if not missing:
        pension, study = profile.pension_pct, profile.study_fund_pct
        return _build(
            profile,
            compute_with_rates(profile, today, ctx, pension, study),
            compute_with_rates(profile, alternative, ctx, pension, study),
            ctx,
            missing,
        )

    probes = []
    for rate in PROBE_RATES:
        pension = rate if profile.pension_pct is None else profile.pension_pct
        study = rate if profile.study_fund_pct is None else profile.study_fund_pct
        pair = (
            compute_with_rates(profile, today, ctx, pension, study),
            compute_with_rates(profile, alternative, ctx, pension, study),
        )
        probes.append(pair)
    with exact():
        exact_diffs = [_net(alt) - _net(now) for now, alt in probes]
    diffs = {to_agora(d) for d in exact_diffs}
    if len(diffs) != 1:
        raise MissingInputs(missing)  # the diff depends on the unknown rates
    return _build(profile, *probes[0], ctx, missing)


def _without_today(
    profile: EmployeeProfile, alternative: Scenario, ctx: EngineContext
) -> Comparison:
    """The alternative alone: its net needs every input of its own (contribution rates
    included) and none of today's. The diff waits for today."""
    missing = missing_inputs(profile, alternative)
    if missing:
        raise MissingInputs([CURRENT_SITUATION, *missing])
    breakdown = compute_with_rates(
        profile, alternative, ctx, profile.pension_pct, profile.study_fund_pct
    )
    return Comparison(
        today=None,
        alternative=breakdown,
        diff=None,
        display_diff=None,
        delta_lines=(),
        display_delta_lines=(),
        explanation_facts=(),
        warnings=profile_warnings(profile, None, ctx),
        missing=(CURRENT_SITUATION,),
    )


def _net(breakdown: NetBreakdown) -> Decimal:
    assert breakdown.net is not None
    return breakdown.net

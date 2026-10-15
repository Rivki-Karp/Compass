"""The 6 golden reference employees: every value in reference_results.json, exactly.

Values are compared after display rounding (whole ILS, half-up); net_diff is the difference of
the displayed nets.
"""

from decimal import Decimal as D
from pathlib import Path

import pytest
import yaml

from compass.config import RULES_YAML
from compass.engine.compare import compare
from compass.engine.context import EngineContext, build_context
from compass.engine.decimal_math import exact, to_display
from compass.engine.eligibility import check_eligibility
from compass.engine.net import compute_net
from compass.reference import ReferenceCase, load_reference_cases
from compass.rules import load_rules

EMPLOYEES = ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"]


@pytest.fixture(scope="module")
def cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    return load_reference_cases(ctx)


@pytest.mark.parametrize("employee_id", EMPLOYEES)
def test_golden(cases: dict[str, ReferenceCase], ctx: EngineContext, employee_id: str) -> None:
    case = cases[employee_id]
    result = compare(case.profile, case.today, case.alternative, ctx)
    today, alt = result.today, result.alternative
    assert today.net is not None and alt.net is not None

    def show(value: D) -> int:
        return to_display(value, ctx.rules)

    with exact():
        got = {
            "net_today": show(today.net),
            "net_alternative": show(alt.net),
            "net_diff": result.display_diff,
            "tax_today": show(today.income_tax),
            "tax_alternative": show(alt.income_tax),
            "ni_health_today": show(today.national_insurance + today.health),
            "ni_health_alternative": show(alt.national_insurance + alt.health),
            "electric_refund_gross": show(alt.electric_gross),
            "family_track_employee_share": show(alt.family_employee_share),
        }
    assert got == {key: case.expected[key] for key in got}
    assert check_eligibility(case.profile, case.alternative, ctx).status == "eligible"
    assert sum(line.amount for line in result.display_delta_lines) == result.display_diff


def test_waiver_maintenance_matches_the_reference(cases: dict[str, ReferenceCase], ctx):
    case = cases["E-005"]
    breakdown = compute_net(case.profile, case.alternative, ctx)
    assert breakdown.maintenance == case.expected["alternative"]["maintenance"]


def test_partial_diff_e001(cases: dict[str, ReferenceCase], ctx: EngineContext) -> None:
    case = cases["E-001"]
    profile = case.profile.model_copy(update={"pension_pct": None, "study_fund_pct": None})
    result = compare(profile, case.today, case.alternative, ctx)
    assert result.display_diff == 661
    assert result.today.net is None and result.alternative.net is None
    assert result.partial and result.missing == ("pension_pct", "study_fund_pct")


def test_config_is_data(cases: dict[str, ReferenceCase], tmp_path: Path) -> None:
    """Change budget ב in a copy of rules.yaml: E-002's family share follows, no code change."""
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    assert data["budgets"]["ב"] == 3700
    data["budgets"]["ב"] = 4000
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    edited = build_context(rules=load_rules(path))

    case = cases["E-002"]
    breakdown = compute_net(case.profile, case.alternative, edited)
    assert breakdown.family_employee_share == (D(6000) - D(4000)) * D("0.5") == D(1000)

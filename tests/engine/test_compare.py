from decimal import Decimal as D

import pytest

from compass.engine.compare import compare
from compass.engine.context import EngineContext
from compass.engine.decimal_math import apportion, exact
from compass.engine.models import CompanyCar, MissingInputs
from compass.reference import ReferenceCase, load_reference_cases

EMPLOYEES = ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"]


@pytest.fixture(scope="module")
def cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    return load_reference_cases(ctx)


# --- largest remainder ----------------------------------------------------------------------


def test_apportion_keeps_whole_amounts_and_hits_the_total() -> None:
    assert apportion([D("1.4"), D("1.4"), D("1.2")], 4) == [2, 1, 1]
    assert apportion([D(0), D("2.5"), D(-3)], 0) == [0, 3, -3]
    assert apportion([D(0), D("2.5"), D(-3)], -1) == [0, 2, -3]
    assert apportion([D("-0.3"), D("0.3")], 0) == [0, 0]
    assert apportion([D(5), D(-2)], 3) == [5, -2]


def test_apportion_ties_go_to_the_earlier_line() -> None:
    assert apportion([D("0.5"), D("0.5")], 1) == [1, 0]


def test_apportion_refuses_an_unreachable_total() -> None:
    with pytest.raises(ValueError, match="cannot apportion"):
        apportion([D("1.5"), D(2)], 5)
    with pytest.raises(ValueError, match="cannot apportion"):
        apportion([D(1), D(2)], 4)  # no fractional line to absorb the unit


# --- the 12 reference scenarios ---------------------------------------------------------------


@pytest.mark.parametrize("employee_id", EMPLOYEES)
def test_reference_diffs_and_lines(
    cases: dict[str, ReferenceCase], ctx: EngineContext, employee_id: str
) -> None:
    case = cases[employee_id]
    result = compare(case.profile, case.today, case.alternative, ctx)
    assert result.today.net is not None and result.alternative.net is not None
    with exact():  # engine values carry more digits than the default 28-digit context
        assert result.diff == result.alternative.net - result.today.net
        assert sum(line.amount for line in result.delta_lines) == result.diff
    assert result.display_diff == case.expected["net_diff"]
    assert sum(line.amount for line in result.display_delta_lines) == result.display_diff
    for exact_line, shown in zip(result.delta_lines, result.display_delta_lines, strict=True):
        assert shown.line == exact_line.line
        assert abs(D(shown.amount) - exact_line.amount) < 1
    assert not result.partial


def test_display_diff_is_the_difference_of_displayed_nets(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    # E-003: exact diff -1938.681 rounds to -1939, but 13,109 - 15,047 = -1,938 is what is shown.
    case = cases["E-003"]
    result = compare(case.profile, case.today, case.alternative, ctx)
    assert result.diff.quantize(D("0.001")) == D("-1938.681")
    assert result.display_diff == -1938


def test_e001_delta_lines(cases: dict[str, ReferenceCase], ctx: EngineContext) -> None:
    case = cases["E-001"]
    lines = {
        line.line: line.amount
        for line in compare(case.profile, case.today, case.alternative, ctx).delta_lines
    }
    assert lines["cash_income"] == lines["maintenance"] == 0
    assert lines["employee_pension"] == lines["employee_study"] == 0
    assert lines["participation"] == 0  # 300 -> 300
    assert lines["electric_gross"].quantize(D("0.0001")) == D("439.9085")
    assert abs(lines["income_tax"] - (D(3443) - D(3283))) < 1  # less tax: a positive line
    assert lines["family_employee_share"] == 0


# --- explanation facts ------------------------------------------------------------------------


EXPECTED_FACTS = {
    "E-001": [
        {"kind": "value_of_use_change", "from": 4070, "to": 3130},
        {"kind": "electric_bonus", "method": "gross_up", "net": 250, "gross": 440},
        {"kind": "participation_change", "from": 300, "to": 300, "source": "catalog_default"},
    ],
    "E-002": [
        {"kind": "value_of_use_change", "from": 2950, "to": 8120},
        {"kind": "participation_change", "from": 250, "to": 500, "source": "catalog_default"},
        {"kind": "family_share", "amount": 1150},
    ],
    "E-003": [
        {"kind": "value_of_use_added", "amount": 2430},
        {"kind": "maintenance_removed", "amount": 1500},
        {"kind": "electric_bonus", "method": "gross_up", "net": 250, "gross": 473},
        {"kind": "participation_change", "from": 0, "to": 250, "source": "catalog_default"},
    ],
    "E-004": [
        {"kind": "value_of_use_change", "from": 4790, "to": 2930},
        {"kind": "electric_bonus", "method": "gross_up", "net": 250, "gross": 440},
        {"kind": "participation_change", "from": 400, "to": 300, "source": "catalog_default"},
    ],
    "E-005": [
        {"kind": "value_of_use_removed", "amount": 4570},
        {"kind": "maintenance_added", "amount": 2000},
        {"kind": "participation_change", "from": 350, "to": 0, "source": None},
    ],
    "E-006": [
        {"kind": "value_of_use_change", "from": 5150, "to": 4150},
        {"kind": "electric_bonus", "method": "gross_up", "net": 250, "gross": 473},
        {"kind": "participation_change", "from": 500, "to": 500, "source": "catalog_default"},
    ],
}


@pytest.mark.parametrize("employee_id", EMPLOYEES)
def test_explanation_facts(
    cases: dict[str, ReferenceCase], ctx: EngineContext, employee_id: str
) -> None:
    case = cases[employee_id]
    facts = compare(case.profile, case.today, case.alternative, ctx).explanation_facts
    assert [dict(fact) for fact in facts] == EXPECTED_FACTS[employee_id]


# --- partial diff -----------------------------------------------------------------------------


def test_partial_diff_without_contribution_rates(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    case = cases["E-001"]
    profile = case.profile.model_copy(update={"pension_pct": None, "study_fund_pct": None})
    result = compare(profile, case.today, case.alternative, ctx)
    full = compare(case.profile, case.today, case.alternative, ctx)
    assert result.partial and result.missing == ("pension_pct", "study_fund_pct")
    assert result.display_diff == 661
    assert result.diff == full.diff
    assert result.today.net is None and result.alternative.net is None
    assert result.today.employee_pension is None and result.alternative.employee_study is None
    assert result.today.income_tax == full.today.income_tax  # everything else is still known
    assert sum(line.amount for line in result.display_delta_lines) == 661


def test_partial_diff_with_one_rate_known(cases: dict[str, ReferenceCase], ctx: EngineContext):
    case = cases["E-004"]
    profile = case.profile.model_copy(update={"study_fund_pct": None})
    result = compare(profile, case.today, case.alternative, ctx)
    assert result.missing == ("study_fund_pct",)
    assert result.today.employee_pension is not None and result.today.employee_study is None
    assert result.display_diff == 1207


def test_partial_diff_still_requires_other_inputs(
    cases: dict[str, ReferenceCase], ctx: EngineContext
) -> None:
    case = cases["E-001"]
    profile = case.profile.model_copy(update={"pension_pct": None, "bonus": None})
    with pytest.raises(MissingInputs) as exc_info:
        compare(profile, case.today, CompanyCar(car_id="CAR-10"), ctx)
    assert exc_info.value.fields == ("bonus", "pension_pct")

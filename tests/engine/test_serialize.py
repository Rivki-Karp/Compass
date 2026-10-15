import json
from decimal import Context, Decimal, localcontext

import pytest

from compass.engine.compare import compare
from compass.engine.context import EngineContext
from compass.engine.decimal_math import to_display
from compass.engine.eligibility import check_eligibility
from compass.engine.net import compute_net
from compass.engine.options import list_options
from compass.engine.serialize import BREAKDOWN_LINES, to_api_dict
from compass.reference import ReferenceCase, load_reference_cases


@pytest.fixture(scope="module")
def cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    return load_reference_cases(ctx)


@pytest.mark.parametrize(
    "decimal_context",
    [Context(), Context(prec=5)],  # Python's default context, and a hostile one
    ids=["default", "prec5"],
)
@pytest.mark.parametrize("employee_id", ["E-001", "E-003", "E-006"])  # electric: long tails
def test_comparison_round_trips_exactly(
    cases: dict[str, ReferenceCase],
    ctx: EngineContext,
    employee_id: str,
    decimal_context: Context,
) -> None:
    case = cases[employee_id]
    result = compare(case.profile, case.today, case.alternative, ctx)
    with localcontext(decimal_context):
        data = to_api_dict(result, ctx.rules)
        text = json.dumps(data, ensure_ascii=False)
    back = json.loads(text)

    # Exact values: every digit survives (Decimal(str) and == are context-independent).
    assert Decimal(back["diff"]) == result.diff
    assert "E" not in back["diff"]
    for side, breakdown in (("today", result.today), ("alternative", result.alternative)):
        for name in BREAKDOWN_LINES:
            value = getattr(breakdown, name)
            exact_text = back[side]["exact"][name]
            assert Decimal(exact_text) == value and "E" not in exact_text
            assert back[side]["display"][name] == to_display(value, ctx.rules)
        assert back[side]["metadata"]["tax_tables_year"] == 2025
    for shown, line in zip(back["delta_lines"], result.delta_lines, strict=True):
        assert Decimal(shown["net_effect"]) == line.net_effect
    # Display values: plain ints, summing to display_diff.
    assert back["display_diff"] == case.expected["net_diff"]
    assert sum(line["net_effect"] for line in back["display_delta_lines"]) == back["display_diff"]
    assert all(type(line["net_effect"]) is int for line in back["display_delta_lines"])
    assert back["warnings"] == [] and back["partial"] is False


def test_electric_gross_keeps_all_digits(cases: dict[str, ReferenceCase], ctx: EngineContext):
    case = cases["E-001"]
    breakdown = compute_net(case.profile, case.alternative, ctx)
    with localcontext(Context()):
        data = to_api_dict(breakdown, ctx.rules)
    assert data["exact"]["electric_gross"].startswith("439.908499")  # 439.9085 to 4 places
    assert len(data["exact"]["electric_gross"]) > 28  # more than the default context could hold
    assert data["display"]["electric_gross"] == 440


def test_partial_comparison(cases: dict[str, ReferenceCase], ctx: EngineContext) -> None:
    case = cases["E-001"]
    profile = case.profile.model_copy(update={"pension_pct": None, "study_fund_pct": None})
    data = to_api_dict(compare(profile, case.today, case.alternative, ctx), ctx.rules)
    assert data["partial"] is True and data["missing"] == ["pension_pct", "study_fund_pct"]
    assert data["today"]["exact"]["net"] is None and data["today"]["display"]["net"] is None
    assert data["display_diff"] == 661
    json.dumps(data)


def test_eligibility_and_options(cases: dict[str, ReferenceCase], ctx: EngineContext) -> None:
    case = cases["E-005"]
    verdict = to_api_dict(check_eligibility(case.profile, case.alternative, ctx), ctx.rules)
    assert verdict == {
        "status": "eligible",
        "reason": "waiver_allowed",
        "facts": {
            "occupation": "מנהל/ת פיתוח",
            "car_mandatory": False,
            "waiver_allowed": True,
            "waiver_maintenance": "2000",
        },
        "warnings": [],
    }
    options = list_options(case.profile, case.today, ctx)
    with localcontext(Context(prec=5)):
        data = to_api_dict(options, ctx.rules)
    json.dumps(data, ensure_ascii=False)
    assert len(data) == len(options)
    assert data[0]["eligibility"]["status"] == "eligible"
    assert data[0]["comparison"]["display_diff"] == options[0].comparison.display_diff


def test_rejects_unknown_types(ctx: EngineContext) -> None:
    with pytest.raises(TypeError):
        to_api_dict(object(), ctx.rules)  # type: ignore[arg-type]

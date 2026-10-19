"""The eval checks for ticket questions: `ticket`, and `input_sources` on `comparison`."""

from typing import Any

import pytest

from evals.checks import Comparison, Trace, evaluate, parse_check

OCCUPATION_TICKET = {
    "bound_fields": ["occupation"],
    "free_types": [],
    "occupation_options_from_table": True,
}


def _passed(trace: Trace, check: dict[str, Any]) -> bool:
    return evaluate(trace, [check])[0].passed


@pytest.mark.parametrize(
    ("check", "passed"),
    [
        ({"ticket": {"bound_fields": ["occupation"]}}, True),
        ({"ticket": {"bound_fields": ["occupation", "group_exception"]}}, False),
        ({"ticket": {"bound_fields": [], "free_types": ["yes_no"]}}, True),
        ({"ticket": {"free_types": ["text"]}}, False),
        ({"ticket": {"occupation_options_from_table": True}}, True),
    ],
)
def test_ticket(check: dict[str, Any], passed: bool) -> None:
    free = {"bound_fields": [], "free_types": ["yes_no"], "occupation_options_from_table": False}
    trace = Trace(tickets=[OCCUPATION_TICKET, free])
    assert _passed(trace, check) is passed


def test_ticket_bound_fields_in_any_order() -> None:
    both = {**OCCUPATION_TICKET, "bound_fields": ["group_exception", "current_participation"]}
    check = {"ticket": {"bound_fields": ["current_participation", "group_exception"]}}
    assert _passed(Trace(tickets=[both]), check)
    assert not _passed(Trace(), check)  # no ticket at all


def test_unknown_ticket_argument_is_refused() -> None:
    with pytest.raises(ValueError):
        parse_check({"ticket": {"fields": ["occupation"]}})


def test_comparison_input_sources() -> None:
    result = {
        "comparison": {
            "today": {"display": {"net": 11000}},
            "alternative": {"display": {"net": 13914}, "metadata": {"maintenance_source": None}},
            "display_diff": 2914,
            "partial": False,
        },
        "participation_source": None,
        "pending_rep": False,
        "hypothetical": False,
        "view": {
            "inputs": [
                {"id": "occupation", "source": "representative"},
                {"id": "group", "source": "occupation"},
            ]
        },
    }
    trace = Trace(comparisons=[Comparison(1, {"alternative": {"kind": "waiver"}}, result)])
    check = {"comparison": {"input_sources": {"occupation": "representative"}}}
    assert _passed(trace, check)
    wrong = {"comparison": {"input_sources": {"occupation": "employee_input"}}}
    assert not _passed(trace, wrong)

"""The `no_template` eval check, and the payslip_flag_off scenario's shape."""

from evals.checks import Reply, Trace, evaluate, parse_check
from evals.scenario import load_all


def _run(kinds: list[str], check: dict[str, object]) -> bool:
    trace = Trace(replies=[Reply(i, "x", kind) for i, kind in enumerate(kinds)])
    result = next(r for r in evaluate(trace, [{"no_template": check}]) if "no_template" in r.label)
    return result.passed


def test_no_template_passes_on_replies_and_fails_on_a_template() -> None:
    assert _run(["reply", "reply"], {})
    assert not _run(["reply", "template"], {})
    assert _run(["template", "reply"], {"turn": 1})  # only the given turn
    assert not _run(["template", "reply"], {"turn": 0})


def test_the_check_parses_and_the_scenario_runs_with_the_flag_off() -> None:
    assert parse_check({"no_template": {}}) == ("no_template", {})
    scenario = next(s for s in load_all(["payslip_flag_off"]))
    assert not scenario.needs_payslip  # runs in the default (flag off) mode
    assert scenario.checks[0] == {"no_template": {}}

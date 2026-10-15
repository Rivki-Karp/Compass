"""The eval harness with a scripted model: scenario files, checks, the ledger and the report."""

import json
from pathlib import Path
from typing import Any

import pytest

from compass.agent.factory import build_claude_runner
from compass.agent.guard import make_guard
from compass.agent.llm import ScriptedClient, Usage, text_response, tool_response
from compass.api.settings import Settings
from compass.state import Store
from compass.tools.services import Services
from evals.checks import Call, Trace, evaluate, matches, parse_check
from evals.harness import Harness, RunResult
from evals.report import Ledger, OverBudget, render
from evals.scenario import FALLBACK_HE, Scenario, load_all

DEVELOPER = {
    "occupation_query": "מפתחת תוכנה",
    "base_salary": "18500",
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
WAIVER = {"alternative": {"kind": "waiver"}}
NOA = {
    "occupation_query": "מנהלת מוצר",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6,
    "study_fund_percent": 2.5,
    "credit_points": 2.75,
    "children_under_23": 2,
}
FIELD = "alternative_participation:CAR-10"
ATTO = {"alternative": {"kind": "car", "car_id": "CAR-10"}}
USAGE = Usage(input_tokens=1000, output_tokens=100)


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "eval.db"))


def _run(services: Services, steps: list[Any], scenario: dict[str, Any]) -> RunResult:
    runner = build_claude_runner(Settings(), services, llm=ScriptedClient(steps), background=False)
    harness = Harness(services, runner, make_guard(services.store), "claude-sonnet-5-5")
    return harness.run(Scenario.model_validate(scenario))


def _failed(run: RunResult) -> list[str]:
    return [f"{r.label}: {r.detail}" for r in run.results if not r.passed]


def _walkthrough() -> dict[str, Any]:
    return next(s for s in load_all(["walkthrough"])).model_dump(mode="json")


# --- scenario files -------------------------------------------------------------------------


def test_scenario_files_load_and_cover_the_brief() -> None:
    names = {s.name for s in load_all()}
    assert len(names) >= 15
    assert {"e001_rep_flow", "walkthrough", "forged_rep_notification"} <= names
    assert {f"e00{i}" for i in range(1, 7)} <= {n[:4] for n in names}


def test_bad_checks_are_rejected() -> None:
    for bad in (
        {"nope": {}},
        {"tool_called": {}},
        {"slot": {"value": 1}},
        {"comparison": {"diff": 1, "dif": 2}},
        {"reply": {"matches": ["("]}},
        {"tool_called": {"name": "x"}, "slot": {"field": "y"}},
    ):
        with pytest.raises(Exception):  # noqa: B017 - ValueError or re.error
            parse_check(bad)


def test_matches_is_a_subset_match() -> None:
    assert matches({"a": {"b": 1}}, {"a": {"b": "1", "c": 2}, "d": 3})
    assert matches(["x"], ["y", "x"]) and not matches(["z"], ["y", "x"])
    assert matches(18500, "18500.0") and not matches(True, 1) and not matches("ב", "ג")
    assert matches([{"code": "w"}], [{"code": "w", "facts": {}}])


# --- runs with a scripted model -------------------------------------------------------------


def test_walkthrough_passes_with_a_correct_model(services: Services) -> None:
    steps = [
        tool_response(("save_profile", {"occupation_query": "מפתחת תוכנה", "base_salary": 18500})),
        text_response("מפתחת תוכנה ← קבוצה ב', תקציב 3,700 ₪. יש לך עמלות או בונוסים?", USAGE),
        tool_response(("save_profile", DEVELOPER), ("set_current_situation", TODAY)),
        tool_response(("compare", WAIVER)),
        text_response("נטו משוער 13,914 ₪ במקום 11,000 ₪: +2,914 ₪. החישוב על השכר בלבד.", USAGE),
    ]
    run = _run(services, steps, _walkthrough())
    assert run.passed, _failed(run)
    assert (run.turns, run.rounds) == (2, 3)
    assert run.cost_usd == pytest.approx(2 * USAGE.cost_usd("claude-sonnet-5-5"))
    compare = next(c for c in run.trace.calls if c.name == "compare")
    assert compare.turn == 1 and compare.ok and compare.result["comparison"]["display_diff"] == 2914


def test_a_wrong_source_and_a_recommendation_fail(services: Services) -> None:
    # A quoted 1,800 is a representative's maintenance: different numbers, wrong source.
    steps = [
        tool_response(("save_profile", DEVELOPER)),
        text_response("קבוצה ב', 3,700 ₪."),
        tool_response(("set_current_situation", TODAY)),
        tool_response(("compare", {"alternative": {"kind": "waiver", "maintenance": 1800}})),
        text_response("כדאי לך לוותר. החישוב על השכר בלבד."),
    ]
    run = _run(services, steps, _walkthrough())
    failed = _failed(run)
    assert not run.passed
    wrong_source = "maintenance_source=representative"
    assert any(f.startswith("comparison") and wrong_source in f for f in failed)
    assert any("forbidden" in f and "recommendation" in f for f in failed)


def test_until_compare_answers_with_the_fallback(services: Services) -> None:
    steps = [
        text_response("מה התפקיד שלך?"),
        tool_response(("save_profile", DEVELOPER), ("set_current_situation", TODAY)),
        tool_response(("compare", WAIVER)),
        text_response("+2,914 ₪. שכר בלבד."),
    ]
    scenario = {
        "name": "t",
        "description": "d",
        "turns": [{"employee": "שלום"}],
        "until_compare": True,
        "checks": [{"comparison": {"alternative": {"kind": "waiver"}, "diff": 2914}}],
    }
    run = _run(services, steps, scenario)
    assert run.passed, _failed(run)
    assert run.turns == 2
    messages = services.store.messages(run.session_id)
    assert [m.content["text"] for m in messages if m.role == "user"] == ["שלום", FALLBACK_HE]


def test_rep_flow_with_a_scripted_model(services: Services) -> None:
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    ask = {"question": "מה ההשתתפות ב-ATTO 3?", "blocking_fields": [FIELD]}
    steps = [
        tool_response(("save_profile", {"occupation_query": "מנהלת מוצר", "base_salary": 18500})),
        text_response("רשמתי: מנהלת מוצר ← קבוצה ג'. יש לך עמלות?"),
        tool_response(("save_profile", NOA), ("set_current_situation", TODAY)),
        text_response("רשמתי. מה לבדוק?"),
        tool_response(("ask_representative", ask), ("compare", ATTO)),
        text_response("פניתי לנציג. בינתיים: +661 ₪."),
        tool_response(("compare", ATTO)),
        text_response("הנציג אישר 350 ₪: +611 ₪."),
    ]
    run = _run(services, steps, scenario)
    assert run.passed, _failed(run)


def test_a_rep_turn_without_a_ticket_is_a_failure(services: Services) -> None:
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = [text_response("שלום"), text_response("שלום"), text_response("לא פניתי לנציג.")]
    run = _run(services, steps, scenario)
    failed = _failed(run)
    assert any("script ran as written" in f and "found 0" in f for f in failed)


def test_a_number_that_slipped_past_the_guard_is_caught() -> None:
    trace = Trace(guard_rechecks=[(0, ["11,700"])])
    results = evaluate(trace, [{"tool_not_called": {"name": "compare"}}])
    assert [r.passed for r in results] == [True, True, True, False, True]


def test_comparison_check_picks_the_last_matching_compare() -> None:
    def compare(turn: int, diff: int, kind: str) -> Call:
        comparison = {
            "today": {"display": {"net": 1}},
            "alternative": {"display": {"net": 2}, "metadata": {"maintenance_source": None}},
            "display_diff": diff,
            "partial": False,
        }
        result = {
            "comparison": comparison,
            "participation_source": None,
            "pending_rep": False,
            "hypothetical": False,
        }
        return Call(turn, "compare", {"alternative": {"kind": kind}}, True, result)

    trace = Trace(calls=[compare(0, 10, "waiver"), compare(1, 20, "waiver"), compare(2, 30, "car")])
    check = {"comparison": {"alternative": {"kind": "waiver"}, "diff": 20}}
    assert evaluate(trace, [check])[0].passed
    early = {"comparison": {"alternative": {"kind": "waiver"}, "turn": 0, "diff": 10}}
    assert evaluate(trace, [early])[0].passed


# --- ledger and report ----------------------------------------------------------------------


def test_ledger_enforces_the_cap(tmp_path: Path, services: Services) -> None:
    ledger = Ledger(tmp_path / "spend.jsonl", cap_usd=1.0)
    ledger.reserve()  # empty ledger
    run = RunResult("s", [], Trace(), usage=USAGE, cost_usd=0.9)
    ledger.record(run, "low", "claude-sonnet-5-5")
    assert ledger.spent() == pytest.approx(0.9)
    with pytest.raises(OverBudget):
        ledger.reserve()
    entry = json.loads((tmp_path / "spend.jsonl").read_text(encoding="utf-8"))
    assert entry["scenario"] == "s" and entry["effort"] == "low" and entry["passed"] is True


def test_report_renders_the_table_and_failures(services: Services) -> None:
    steps = [
        tool_response(("save_profile", DEVELOPER)),
        text_response("קבוצה ב', 3,700 ₪."),
        text_response("לא חישבתי."),
        text_response("לא חישבתי."),
        text_response("לא חישבתי."),
    ]
    run = _run(services, steps, _walkthrough())
    report = render(
        [run],
        model="claude-sonnet-5-5",
        effort="low",
        repeat=1,
        spent_before=0.1,
        spent_after=0.2,
        cap_usd=30,
    )
    assert "**Scenarios passing (every repeat): 0/1**" in report
    assert "| walkthrough | 0/1 | 4.0 |" in report
    assert "### walkthrough: FAIL" in report and "❌ comparison" in report
    assert "Shown replies failing the guard: 0" in report

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
from evals.checks import (
    Call,
    Comparison,
    Reply,
    Trace,
    evaluate,
    global_checks,
    matches,
    parse_check,
)
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


def _rep_flow_steps(*turn_2: Any) -> list[Any]:
    return [
        tool_response(("save_profile", {"occupation_query": "מנהלת מוצר", "base_salary": 18500})),
        text_response("רשמתי: מנהלת מוצר ← קבוצה ג'. יש לך עמלות?"),
        tool_response(("save_profile", NOA), ("set_current_situation", TODAY)),
        text_response("רשמתי. מה לבדוק?"),
        *turn_2,
        text_response("פניתי לנציג. בינתיים: +661 ₪."),
        tool_response(("compare", ATTO)),
        text_response("הנציג אישר 350 ₪: +611 ₪."),
    ]


ASK_ATTO = {"question": "מה ההשתתפות ב-ATTO 3?", "blocking_fields": [FIELD]}


def test_rep_flow_with_a_scripted_model(services: Services) -> None:
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = _rep_flow_steps(tool_response(("ask_representative", ASK_ATTO), ("compare", ATTO)))
    run = _run(services, steps, scenario)
    assert run.passed, _failed(run)
    # The server's comparisons: the ticket's provisional one (turn 2, pending; 8b) and the
    # settle when the representative answers (turn 3).
    servers = [
        (c.turn, c.result["pending_rep"]) for c in run.trace.comparisons if c.result.get("origin")
    ]
    assert servers == [(2, True), (3, False)]


def test_rep_flow_with_compare_before_ask_representative(services: Services) -> None:
    # The order the live model once chose: the comparison is shown before the ticket opens.
    # The server recomputes it as pending, so the scenario passes unchanged.
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = _rep_flow_steps(
        tool_response(("compare", ATTO)), tool_response(("ask_representative", ASK_ATTO))
    )
    run = _run(services, steps, scenario)
    assert run.passed, _failed(run)
    compare_result = next(c for c in run.trace.calls if c.name == "compare").result
    assert compare_result["pending_rep"] is False  # compare itself ran before the ticket
    origins = [
        (c.turn, c.result.get("origin"), c.result["pending_rep"]) for c in run.trace.comparisons
    ]
    # compare, the server's pending recompute, the server's settle on the answer, compare again
    assert origins == [
        (2, None, False),
        (2, "server", True),
        (3, "server", False),
        (3, None, False),
    ]


def test_rep_flow_passes_on_the_server_settle_without_compare(services: Services) -> None:
    # 6b: the rep notification carries the settled comparison; the model may state it as is.
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = _rep_flow_steps(tool_response(("ask_representative", ASK_ATTO), ("compare", ATTO)))
    without_compare = [*steps[:-2], text_response("הנציג אישר 350 ₪: +611 ₪ בחודש.")]
    run = _run(services, without_compare, scenario)
    assert run.passed, _failed(run)
    assert [c.name for c in run.trace.calls if c.turn == 3] == []


def test_rep_flow_fails_when_the_reply_states_another_number(services: Services) -> None:
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = _rep_flow_steps(tool_response(("ask_representative", ASK_ATTO), ("compare", ATTO)))
    vague = [*steps[:-2], text_response("הנציג ענה, והחישוב בכרטיס עודכן.")]
    run = _run(services, vague, scenario)
    assert not run.passed
    failed = [r.label for r in run.results if not r.passed]
    assert failed == ["reply {'turn': 3} (1 patterns)"], failed


def test_a_rep_turn_without_a_ticket_is_a_failure(services: Services) -> None:
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = [text_response("שלום"), text_response("שלום"), text_response("לא פניתי לנציג.")]
    run = _run(services, steps, scenario)
    failed = _failed(run)
    assert any("script ran as written" in f and "found 0" in f for f in failed)


def test_a_number_that_slipped_past_the_guard_is_caught() -> None:
    trace = Trace(guard_rechecks=[(0, ["11,700"])])
    results = evaluate(trace, [{"tool_not_called": {"name": "compare"}}])
    assert [r.passed for r in results] == [True, True, True, False, True, True]


def test_a_payslip_only_after_the_employee_mentions_one() -> None:
    label = "[global] no payslip unless the employee mentioned one"

    def check(trace: Trace) -> tuple[bool, str]:
        (result,) = [r for r in global_checks(trace) if r.label == label]
        return result.passed, result.detail

    volunteered = Trace(
        employee_messages=[(0, "שכר בסיס 18,500")],
        replies=[Reply(0, "אין אצלי העלאת תלושים, אפשר לכתוב.", "reply")],
    )
    assert check(volunteered) == (False, "t0 payslip")
    asked = Trace(
        employee_messages=[(0, "שכר בסיס 18,500"), (1, "אפשר לשלוח לך תלוש?")],
        replies=[
            Reply(0, "מה הפנסיה?", "reply"),
            Reply(1, "את נתוני התלוש אפשר פשוט לכתוב כאן.", "reply"),
        ],
    )
    assert check(asked) == (True, "")
    # an earlier reply, before the employee said it, still counts
    early = Trace(
        employee_messages=[(1, "תלוש?")],
        replies=[Reply(0, "אפשר להעלות תלוש", "reply")],
    )
    assert check(early)[0] is False


# list_options for E-001 (round 2, all_options repeat 2): best first, the eligible ones first
_OPTIONS = (
    [("waiver", None, "eligible")]
    + [
        ("company_car", name, "eligible")
        for name in ["MG4", "BYD DOLPHIN", "KONA EV", "PICANTO", "EV3", "ATTO 3", "NIRO"]
        + ["YARIS CROSS HSD", "LEON", "COROLLA", "MAZDA 3", "TUCSON"]
    ]
    + [("family_car", name, "not_eligible") for name in ["SANTA FE", "CARNIVAL"]]
)


def _options_trace(reply: str) -> Trace:
    options = [
        {"scenario": {"kind": kind}, "eligibility": {"status": status}}
        | ({"commercial_name": name} if name else {})
        for kind, name, status in _OPTIONS
    ]
    call = Call(0, "list_options", {}, True, {"ok": True, "options": options})
    return Trace(calls=[call], replies=[Reply(0, reply, "reply")])


def _options_reply(reply: str) -> tuple[bool, str]:
    (result,) = evaluate(_options_trace(reply), [{"options_reply": {"top": 3}}])[:1]
    return result.passed, result.detail


def test_options_reply_leads_with_the_top_three_and_may_name_more() -> None:
    # round 2, all_options repeat 2: failed on "TUCSON"/"MAZDA 3", both eligible, numbers from
    # the set; it leads with the top three, so it passes now
    reply = (
        "הרכב של היום: קורולה קרוס 2025. האפשרויות המובילות: - **ויתור על הרכב:** +3,199 ₪. "
        "- **MG4 (חשמלי, קבוצה ב'):** +1,013 ₪. - **BYD DOLPHIN (חשמלי):** +994 ₪. "
        "יש גם KONA EV ו-EV3. ההפרש בחלקם שלילי, למשל MAZDA 3 ו-TUCSON. "
        "המסלול המשפחתי (SANTA FE ו-CARNIVAL) לא זמין לך."
    )
    assert _options_reply(reply)[0] is True
    # in another order is fine; the top three are what it leads with
    assert _options_reply("MG4, BYD DOLPHIN, ויתור על הרכב, ואחר כך TUCSON")[0] is True


def test_options_reply_fails_when_a_worse_option_comes_first() -> None:
    passed, detail = _options_reply("TUCSON, MG4, BYD DOLPHIN ואחר כך ויתור")
    assert passed is False
    assert "TUCSON" in detail
    # an ineligible car before the top three is not leading with them either
    assert _options_reply("SANTA FE לא זמין. ויתור, MG4, BYD DOLPHIN")[0] is False


def test_options_reply_reads_whole_names() -> None:
    # "COROLLA CROSS 2025" is today's car, not the COROLLA option; "ATTO 3 2025" is ATTO 3
    assert _options_reply("היום COROLLA CROSS 2025. ויתור, MG4, BYD DOLPHIN")[0] is True
    assert _options_reply("ATTO 3 2025, ויתור, MG4")[0] is False
    assert _options_reply("no list")[1].startswith("leads with []")
    assert evaluate(Trace(), [{"options_reply": {}}])[0].detail == "no list_options result"


def test_comparison_check_picks_the_last_matching_compare() -> None:
    def compare(turn: int, diff: int, kind: str) -> Comparison:
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
        return Comparison(turn, {"alternative": {"kind": kind}}, result)

    trace = Trace(
        comparisons=[compare(0, 10, "waiver"), compare(1, 20, "waiver"), compare(2, 30, "car")]
    )
    check = {"comparison": {"alternative": {"kind": "waiver"}, "diff": 20}}
    assert evaluate(trace, [check])[0].passed
    early = {"comparison": {"alternative": {"kind": "waiver"}, "turn": 0, "diff": 10}}
    assert evaluate(trace, [early])[0].passed


def test_comparison_check_by_origin() -> None:
    def comparison(turn: int, diff: int, origin: str | None) -> Comparison:
        result: dict[str, Any] = {
            "comparison": {
                "today": {"display": {"net": 1}},
                "alternative": {"display": {"net": 2}, "metadata": {"maintenance_source": None}},
                "display_diff": diff,
                "partial": False,
            },
            "participation_source": "representative",
            "pending_rep": False,
            "hypothetical": False,
        }
        if origin:
            result["origin"] = origin
        return Comparison(turn, {"alternative": {"kind": "car"}}, result)

    settled_only = Trace(comparisons=[comparison(3, 611, "server")])
    with_compare = Trace(comparisons=[comparison(3, 611, "server"), comparison(3, 999, None)])
    server = {"comparison": {"origin": "server", "turn": 3, "diff": 611}}
    tool = {"comparison": {"origin": "tool", "diff": 611}}
    assert evaluate(settled_only, [server])[0].passed  # no compare needed
    assert evaluate(with_compare, [server])[0].passed  # the settle, not the later compare
    assert not evaluate(settled_only, [tool])[0].passed  # no compare: nothing to look at
    assert not evaluate(with_compare, [tool])[0].passed  # compare said 999


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


def test_rep_flow_with_ask_only_passes_on_the_provisional_comparison(services: Services) -> None:
    # 8b: the model only opens the ticket; the server computes the provisional comparison
    # (+661, pending) and settles it on the answer (+611). The model states both, no compare.
    scenario = next(s for s in load_all(["e001_rep_flow"])).model_dump(mode="json")
    steps = [
        *_rep_flow_steps(tool_response(("ask_representative", ASK_ATTO)))[:-2],
        text_response("הנציג אישר 350 ₪: +611 ₪ בחודש."),
    ]
    run = _run(services, steps, scenario)
    assert run.passed, _failed(run)
    assert [c.name for c in run.trace.calls if c.name == "compare"] == []
    shown = [
        (c.turn, c.result.get("origin"), c.result["pending_rep"]) for c in run.trace.comparisons
    ]
    assert shown == [(2, "server", True), (3, "server", False)]

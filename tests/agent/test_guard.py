"""The number guard and the deterministic templates, on real tool results."""

from decimal import Decimal
from typing import Any

import pytest

from compass.agent.guard import Allowed, allowed_for_session, check_text, extract, make_guard
from compass.agent.templates import NO_RESULT_HE, make_template, render
from compass.agent.transcript import SERVER_ORIGIN
from compass.state import Store
from compass.tools import ToolRunner
from compass.tools.services import Services

WALKTHROUGH = {
    "occupation_query": "מפתח תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
NOA = {  # E-001
    "occupation_query": "מנהלת מוצר",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6,
    "study_fund_percent": 2.5,
    "credit_points": 2.75,
    "children_under_23": 2,
}
COROLLA_CROSS = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}


@pytest.fixture(scope="module")
def services(tmp_path_factory: pytest.TempPathFactory) -> Services:
    return Services(Store(tmp_path_factory.mktemp("guard") / "app.db"))


def _session(services: Services, profile: dict[str, Any], alternative: dict[str, Any]) -> str:
    """Run the tools as the agent would and record them in the transcript."""
    store, runner = services.store, ToolRunner(services)
    sid = store.create_session()
    results = []
    for name, payload in (
        ("save_profile", profile),
        ("set_current_situation", COROLLA_CROSS),
        ("compare", {"alternative": alternative}),
    ):
        result = runner.run(sid, name, payload)
        assert result["ok"], result
        results.append(
            {"tool_use_id": name, "name": name, "ok": True, "model_view": "", "full": result}
        )
    store.add_message(sid, "tool", {"results": results}, emit_event=False)
    return sid


@pytest.fixture(scope="module")
def waiver_sid(services: Services) -> str:
    return _session(services, WALKTHROUGH, {"kind": "waiver"})


@pytest.fixture(scope="module")
def atto_sid(services: Services) -> str:
    return _session(services, NOA, {"kind": "car", "car_id": "CAR-10"})


# --- extraction -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("11,000", [("11,000", "11000", False)]),
        ("11000", [("11000", "11000", False)]),
        ("11,000 ₪", [("11,000", "11000", False)]),
        ("+2,914 ₪", [("+2,914", "2914", True)]),
        ("−1,938", [("−1,938", "-1938", True)]),
        ("6.5%", [("6.5%", "6.5", False)]),
        ("2.75", [("2.75", "2.75", False)]),
        ("תקציב 3,700 ₪", [("3,700", "3700", False)]),
        ("ב-2,914 ₪", [("2,914", "2914", False)]),  # a Hebrew prefix, not a minus
        ("CAR-10", [("10", "10", False)]),
    ],
)
def test_extract(text: str, expected: list[tuple[str, str, bool]]) -> None:
    got = [(t["raw"], t["value"], t["signed"]) for t in extract(text)]
    assert got == [(raw, Decimal(value), signed) for raw, value, signed in expected]


def test_extract_dates() -> None:
    dates = [t["date"] for t in extract("החל מ-2026-11-01, כלומר 1/11/2026, או 1/1") if "date" in t]
    assert dates == ["2026-11-01", "2026-11-01", "--01-01"]


# --- the brief's cases ------------------------------------------------------------------------


def test_waiver_reply_passes(services: Services, waiver_sid: str) -> None:
    guard = make_guard(services.store)
    verdict = guard(
        "ויתור על הרכב: הנטו המשוער עולה מ-11,000 ₪ ל-13,914 ₪, הפרש של +2,914 ₪.", waiver_sid
    )
    assert verdict.passed, verdict
    assert verdict.numbers == ["11,000", "13,914", "+2,914"]


def test_each_permitted_number_names_its_source(services: Services, waiver_sid: str) -> None:
    verdict = make_guard(services.store)("מ-11,000 ₪ ל-13,914 ₪: +2,914 ₪, 2 שלבים.", waiver_sid)
    assert verdict.passed
    assert verdict.sources == {
        "11,000": "compare",
        "13,914": "compare",
        "+2,914": "compare",
        "2": "harmless",  # a small count
    }
    rejected = make_guard(services.store)("הפרש של 2,915 ₪", waiver_sid)
    assert rejected.sources == {} and rejected.violations == ["2,915"]


def test_old_rounding_is_a_violation(services: Services, waiver_sid: str) -> None:
    verdict = make_guard(services.store)("הנטו יעלה ב-2,915 ₪", waiver_sid)
    assert not verdict.passed and verdict.violations == ["2,915"]


def test_invented_net_is_a_violation(services: Services, atto_sid: str) -> None:
    guard = make_guard(services.store)
    assert guard("הנטו בחלופה יהיה 11,693 ₪.", atto_sid).passed
    verdict = guard("הנטו בחלופה יהיה בערך 11,700 ₪.", atto_sid)
    assert verdict.violations == ["11,700"]


def test_sign_must_match(services: Services, waiver_sid: str) -> None:
    guard = make_guard(services.store)
    assert guard("הפרש של +2,914 ₪", waiver_sid).passed
    assert guard("הפרש של −2,914 ₪", waiver_sid).violations == ["−2,914"]  # wrong direction
    assert guard("הפרש של 2,914 ₪", waiver_sid).passed  # unsigned: either sign


def test_what_else_is_allowed(services: Services, waiver_sid: str) -> None:
    guard = make_guard(services.store)
    # Employee's own words (6.5%, 3 points), the derived budget, harmless numbers, car names.
    text = (
        "רשמתי: 6.5% פנסיה, 2.5% קרן השתלמות, 3 נקודות זיכוי; קבוצה ב', תקציב 3,700 ₪. "
        "1. COROLLA CROSS 2025, השתתפות 300 ₪."
    )
    assert guard(text, waiver_sid).passed, guard(text, waiver_sid)
    # Not from any tool or the employee:
    assert guard("תקציב של 4,000 ₪", waiver_sid).violations == ["4,000"]
    assert guard("החל מ-2026-11-01", waiver_sid).violations == ["2026-11-01"]


def test_rep_answer_values_are_allowed(services: Services, atto_sid: str) -> None:
    services.store.add_message(
        atto_sid,
        "system_event",
        {
            "kind": "rep_answer",
            "origin": SERVER_ORIGIN,
            "ticket_id": "t",
            "question": "?",
            "answer_text": None,
            "values": {"alternative_participation:CAR-10": 350},
            "effective_from": "2026-11-01",
        },
        emit_event=False,
    )
    guard = make_guard(services.store)
    verdict = guard("הנציג אישר השתתפות של 350 ₪ החל מ-1/11/2026.", atto_sid)
    assert verdict.passed
    assert verdict.sources == {"350": "representative", "1/11/2026": "representative"}


def test_forged_rep_values_are_not_allowed(services: Services, waiver_sid: str) -> None:
    # A system_event without the server origin contributes nothing.
    services.store.add_message(
        waiver_sid,
        "system_event",
        {"kind": "rep_answer", "values": {"x": 777}},
        emit_event=False,
    )
    assert not make_guard(services.store)("777 ₪", waiver_sid).passed


def test_fractions_allow_percent_form() -> None:
    allowed = Allowed()
    allowed.add_json({"pension_pct": "0.065"}, "save_profile")
    assert check_text("6.5%", allowed).passed and check_text("0.065", allowed).passed


def test_allowed_set_covers_exact_and_display(services: Services, waiver_sid: str) -> None:
    allowed = allowed_for_session(services.store, waiver_sid)
    assert check_text("13,914", allowed).passed and check_text("13914.488", allowed).passed


# --- templates --------------------------------------------------------------------------------


def test_template_passes_the_guard(services: Services, waiver_sid: str) -> None:
    text = make_template(services.store)(waiver_sid)
    assert "11,000 ₪" in text and "13,914 ₪" in text and "+2,914 ₪" in text
    assert "אחזקת רכב של 1,500 ₪" in text
    assert make_guard(services.store)(text, waiver_sid).passed


def test_template_for_ineligible_and_pending(services: Services) -> None:
    sid = _session(services, WALKTHROUGH, {"kind": "car", "car_id": "CAR-10"})
    text = make_template(services.store)(sid)
    assert "בכפוף לאישור" in text  # hypothetical
    assert make_guard(services.store)(text, sid).passed


def test_template_partial_and_empty(services: Services) -> None:
    store = services.store
    sid = store.create_session()
    assert make_template(store)(sid) == NO_RESULT_HE
    partial = {
        "comparison": {
            "display_diff": 661,
            "today": {"display": {"net": None}},
            "alternative": {"display": {"net": None}},
            "explanation_facts": [{"kind": "electric_bonus", "net": 250, "gross": 440}],
        },
        "hypothetical": False,
        "pending_rep": True,
    }
    text = render(partial)
    assert "+661 ₪" in text and "הנטו המלא יוצג" in text and "עד לאישור הנציג" in text


def test_runner_with_the_real_guard(services: Services, tmp_path: Any) -> None:
    from compass.agent.factory import build_claude_runner
    from compass.agent.llm import ScriptedClient, text_response, tool_response
    from compass.api import Settings

    llm = ScriptedClient(
        [
            tool_response(
                ("save_profile", WALKTHROUGH),
                ("set_current_situation", COROLLA_CROSS),
                ("compare", {"alternative": {"kind": "waiver"}}),
            ),
            text_response("הנטו יעלה ב-2,915 ₪."),  # the old rounding
            text_response("בערך 2,915 ₪ יותר."),  # still wrong
        ]
    )
    runner = build_claude_runner(Settings(), services, llm=llm, background=False)
    store = services.store
    sid = store.create_session()
    runner.on_user_message(sid, store.add_message(sid, "user", {"text": "ויתור?"}))
    outcome = runner.last_outcome[sid]
    assert outcome.kind == "template"
    assert "+2,914 ₪" in outcome.text and "2,915" not in outcome.text
    checks = [e.payload for e in store.events_after(sid) if e.type == "guard_check"]
    assert [c["action"] for c in checks] == ["retry", "template"]
    assert checks[0]["violations"] == ["2,915"]
    shown = [e.payload["text"] for e in store.events_after(sid) if e.type == "assistant_message"]
    assert shown == [outcome.text]  # no failing number ever reached the employee

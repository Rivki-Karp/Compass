"""The terminal chat, with a scripted model: progress lines, /state, /rep resume, /new."""

from collections.abc import Iterator
from typing import Any

import pytest

from compass.agent.chat import Chat, render_comparison
from compass.agent.factory import build_claude_runner
from compass.agent.llm import ScriptedClient, text_response, tool_response
from compass.api import Settings
from compass.state import Store
from compass.tools.services import Services

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
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
ATTO = {"alternative": {"kind": "car", "car_id": "CAR-10"}}
FIELD = "alternative_participation:CAR-10"


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "chat.db"))


def _chat(services: Services, steps: list[Any], lines: list[str]) -> tuple[Chat, list[str]]:
    runner = build_claude_runner(Settings(), services, llm=ScriptedClient(steps), background=False)
    feed: Iterator[str] = iter(lines)
    out: list[str] = []
    return Chat(services, runner, ask=lambda prompt: next(feed), say=out.append, color=False), out


def test_the_brief_flow_in_the_terminal(services: Services) -> None:
    steps = [
        tool_response(("save_profile", NOA), ("set_current_situation", TODAY), ("compare", ATTO)),
        tool_response(
            (
                "ask_representative",
                {
                    "question": "מה ההשתתפות ב-ATTO 3?",
                    "blocking_fields": [FIELD],
                    "quick_answers": [{"id": "350", "label": "350 ₪", "values": {FIELD: 350}}],
                },
            ),
            ("compare", ATTO),  # shown as pending until the representative answers
        ),
        text_response("לפי ברירת המחדל: +661 ₪. פניתי לנציג."),
        tool_response(("compare", ATTO)),
        text_response("הנציג אישר 350 ₪: עכשיו +611 ₪."),
    ]
    chat, out = _chat(
        services, steps, ["אני נועה, ATTO 3?", "/rep", "1", "350", "", "/state", "/quit"]
    )
    assert chat.run() == 0
    text = "\n".join(out)
    assert "שלום! אני יועץ הרכב של שטראוס" in text  # the fixed opening
    assert "  → save_profile" in text and "  ✓ compare" in text
    assert "guard: accept" in text
    assert "+661  הפרש בנטו" in text and "+611  הפרש בנטו" in text  # the demo table, twice
    assert "השתתפות ממתינה לאישור הנציג" in text  # pending flag before the answer
    assert "יועץ: הנציג אישר 350 ₪: עכשיו +611 ₪." in text
    assert f"{FIELD}: {{'amount': '350', 'effective_from': None}}  [representative]" in text


def test_rep_with_field_values_and_date(services: Services) -> None:
    steps = [
        tool_response(("ask_representative", {"question": "?", "blocking_fields": [FIELD]})),
        text_response("פניתי."),
        text_response("התקבל."),
    ]
    chat, out = _chat(services, steps, ["?", "/rep", "1", f"{FIELD}=350", "2026-11-01", "/quit"])
    chat.run()
    slot = services.store.slots(chat.session_id)[FIELD]
    assert slot.value == {"amount": "350", "effective_from": "2026-11-01"}


def test_commands_without_tickets(services: Services) -> None:
    chat, out = _chat(services, [], ["/rep", "/state", "/new", "/quit"])
    chat.run()
    text = "\n".join(out)
    assert "no open tickets" in text and "(no profile yet)" in text
    assert text.count("[session ") == 2


def test_bad_rep_answer_is_reported(services: Services) -> None:
    steps = [
        tool_response(("ask_representative", {"question": "?", "blocking_fields": [FIELD]})),
        text_response("פניתי."),
    ]
    chat, out = _chat(services, steps, ["?", "/rep", "1", f"{FIELD}=99999", "", "/quit"])
    chat.run()
    assert any("must be 0-20,000" in line for line in out)


def test_render_comparison_partial() -> None:
    result = {
        "comparison": {
            "today": {"display": {"net": None, "cash_income": 18500}},
            "alternative": {"display": {"net": None, "cash_income": 18500}},
            "display_diff": 661,
            "display_delta_lines": [{"line": "electric_gross", "net_effect": 440}],
            "partial": True,
            "missing": ["pension_pct"],
        },
    }
    text = render_comparison(result)
    assert "+661  הפרש בנטו" in text and "חלקי: pension_pct" in text

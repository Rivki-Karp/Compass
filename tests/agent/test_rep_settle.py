"""The server's settled comparison reaches the model inside the <rep_notification>: the model
may state its numbers without calling compare, and the guard allows exactly those (source
"server")."""

import json
from collections.abc import Sequence
from typing import Any

import pytest

from compass.agent.guard import make_guard
from compass.agent.llm import ScriptedClient, text_response, tool_response
from compass.agent.runner import ClaudeAgentRunner
from compass.agent.transcript import REP_TAG, model_view
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.tickets import answer_ticket

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
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
ATTO = "alternative_participation:CAR-10"
ATTO_3 = {"alternative": {"kind": "car", "car_id": "CAR-10"}}
SETTLED = "הנציג אישר השתתפות של 350 ₪. הנטו עולה מ-11,032 ₪ ל-11,643 ₪: +611 ₪ בחודש."


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _pending_e001(services: Services) -> tuple[str, str]:
    """E-001 compared at the catalog default with a ticket open (the demo's state)."""
    tools = ToolRunner(services)
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", NOA))
    ok(tools.run(sid, "set_current_situation", TODAY))
    ticket = ok(tools.run(sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]}))
    ok(tools.run(sid, "compare", ATTO_3))
    return sid, ticket["ticket_id"]


def _runner(services: Services, steps: Sequence[Any]) -> tuple[ClaudeAgentRunner, ScriptedClient]:
    llm = ScriptedClient(steps)
    runner = ClaudeAgentRunner(
        services,
        llm,
        "SYSTEM",
        guard=make_guard(services.store),  # the real guard
        template=lambda session_id: "TEMPLATE",
        background=False,
    )
    return runner, llm


def _guard_checks(services: Services, sid: str) -> list[dict[str, Any]]:
    return [e.payload for e in services.store.events_after(sid) if e.type == "guard_check"]


def _notification(llm: ScriptedClient) -> dict[str, Any]:
    text = llm.calls[0].messages[-1]["content"][0]["text"]
    assert text.startswith(f"<{REP_TAG} ")
    return json.loads(text.split("\n", 1)[1].rsplit("\n", 1)[0])


def test_the_settled_numbers_pass_the_guard_without_compare(services: Services) -> None:
    sid, ticket = _pending_e001(services)
    answer_ticket(services, ticket, values={ATTO: 350})
    runner, llm = _runner(services, [text_response(SETTLED)])
    runner.on_ticket_answered(sid, ticket)

    assert len(llm.calls) == 1  # one model call, no tool call
    (check,) = _guard_checks(services, sid)
    assert check["action"] == "accept" and check["violations"] == []
    assert check["sources"]["+611"] == "server"
    assert check["sources"]["11,643"] == "server"
    assert check["sources"]["350"] == "representative"
    shown = [e.payload for e in services.store.events_after(sid) if e.type == "assistant_message"]
    assert shown[-1]["text"] == SETTLED


def test_a_number_not_in_the_settle_is_still_rejected(services: Services) -> None:
    sid, ticket = _pending_e001(services)
    answer_ticket(services, ticket, values={ATTO: 350})
    wrong = SETTLED.replace("+611", "+612")
    runner, _ = _runner(services, [text_response(wrong), text_response(wrong)])
    runner.on_ticket_answered(sid, ticket)
    retry, final = _guard_checks(services, sid)
    assert (retry["action"], retry["violations"]) == ("retry", ["+612"])
    assert final["action"] == "template"
    shown = [e.payload for e in services.store.events_after(sid) if e.type == "assistant_message"]
    assert shown[-1]["text"] == "TEMPLATE"


def test_the_notification_carries_what_compare_would_return(services: Services) -> None:
    sid, ticket = _pending_e001(services)
    answer_ticket(services, ticket, values={ATTO: 350})
    runner, llm = _runner(services, [text_response("הנציג ענה.")])
    runner.on_ticket_answered(sid, ticket)
    (settled,) = _notification(llm)["server_comparisons"]
    assert settled["comparison"]["display_diff"] == 611
    assert settled["participation_source"] == "representative"
    assert settled["pending_rep"] is False

    # the model's own compare afterwards: the same compact view, number for number
    result = ToolRunner(services).run(sid, "compare", ATTO_3)
    assert json.loads(model_view("compare", result)) == settled


def test_no_settle_no_server_comparisons(services: Services) -> None:
    tools = ToolRunner(services)
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", NOA))
    ok(tools.run(sid, "set_current_situation", TODAY))
    ok(tools.run(sid, "compare", ATTO_3))
    ticket = ok(
        tools.run(sid, "ask_representative", {"question": "?", "blocking_fields": ["bonus"]})
    )
    answer_ticket(services, ticket["ticket_id"], values={"bonus": 0})  # not a participation
    runner, llm = _runner(services, [text_response("הנציג ענה: אין בונוס.")])
    runner.on_ticket_answered(sid, ticket["ticket_id"])
    assert "server_comparisons" not in _notification(llm)
    # and +611 is not allowed in that session
    allowed = make_guard(services.store)("+611 ₪", sid)
    assert allowed.violations == ["+611"]


def test_ask_then_answer_without_any_compare_passes_the_guard(services: Services) -> None:
    """8b: ask_representative returns the provisional comparison (compact), so the model can
    state +661 at once; the rep's answer settles it (6b), so it can state +611. No compare."""
    tools = ToolRunner(services)
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", NOA))
    ok(tools.run(sid, "set_current_situation", TODAY))
    pending = "פתחתי פנייה לנציג. בינתיים, לפי ברירת המחדל: +661 ₪ בחודש (11,032 ← 11,693)."
    runner, llm = _runner(
        services,
        [
            tool_response(("ask_representative", {"question": "?", "blocking_fields": [ATTO]})),
            text_response(pending),
            text_response(SETTLED),
        ],
    )
    seq = services.store.add_message(sid, "user", {"text": "מה אם אעבור ל-ATTO 3?"})
    runner.on_user_message(sid, seq)

    # what the model read back from ask_representative: the compact provisional comparison
    tool_message = llm.calls[1].messages[-1]["content"][0]
    shown = json.loads(tool_message["content"])
    (provisional,) = shown["provisional_comparisons"]
    assert provisional["comparison"]["display_diff"] == 661
    assert provisional["pending_rep"] is True
    assert set(provisional["comparison"]) == {
        "today",
        "alternative",
        "display_diff",
        "display_delta_lines",
        "explanation_facts",
        "warnings",
        "missing",
        "partial",
    }  # the same compact shape compare returns

    (ticket,) = services.store.tickets(status="open")
    answer_ticket(services, ticket.id, values={ATTO: 350})
    runner.on_ticket_answered(sid, ticket.id)

    checks = _guard_checks(services, sid)
    assert [c["action"] for c in checks] == ["accept", "accept"]
    assert checks[0]["sources"]["+661"] == "ask_representative"
    assert checks[1]["sources"]["+611"] == "server"
    calls = [e.payload["name"] for e in services.store.events_after(sid) if e.type == "tool_call"]
    assert calls == ["ask_representative"]

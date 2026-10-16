"""A ticket for a participation turns the comparison shown at the catalog default into a pending
one, whatever order the model called compare and ask_representative in; the representative's
answer settles it on the server, whether or not the model calls compare afterwards."""

from typing import Any

import pytest

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
COROLLA_CROSS = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
ATTO = "alternative_participation:CAR-10"
ATTO_3 = {"alternative": {"kind": "car", "car_id": "CAR-10"}}


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def runner(services: Services) -> ToolRunner:
    return ToolRunner(services)


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _noa(services: Services, runner: ToolRunner, today: dict[str, Any] = COROLLA_CROSS) -> str:
    sid = services.store.create_session()
    ok(runner.run(sid, "save_profile", NOA))
    ok(runner.run(sid, "set_current_situation", today))
    return sid


def _ask(runner: ToolRunner, sid: str, *fields: str) -> str:
    result = ok(runner.run(sid, "ask_representative", {"question": "?", "blocking_fields": fields}))
    return result["ticket_id"]


def _comparisons(services: Services, sid: str) -> list[dict[str, Any]]:
    events = services.store.events_after(sid)
    return [{"seq": e.seq, **e.payload} for e in events if e.type == "comparison_ready"]


def test_compare_then_ask_emits_a_pending_comparison(
    services: Services, runner: ToolRunner
) -> None:
    sid = _noa(services, runner)
    shown = ok(runner.run(sid, "compare", ATTO_3))
    assert shown["pending_rep"] is False and "origin" not in shown  # compare's own contract
    ticket = _ask(runner, sid, ATTO)
    first, recomputed = _comparisons(services, sid)
    assert recomputed["origin"] == "server" and recomputed["recomputed_from"] == first["seq"]
    assert (recomputed["ticket_id"], recomputed["pending_field"]) == (ticket, ATTO)
    assert recomputed["pending_rep"] is True
    assert recomputed["participation_source"] == "catalog_default"
    assert recomputed["comparison"]["display_diff"] == 661
    assert recomputed["alternative_kind"] == first["alternative_kind"]  # the same alternative
    assert recomputed["comparison"] == first["comparison"]  # same inputs, same numbers


def test_ask_then_compare_needs_no_recompute(services: Services, runner: ToolRunner) -> None:
    sid = _noa(services, runner)
    _ask(runner, sid, ATTO)
    result = ok(runner.run(sid, "compare", ATTO_3))
    assert result["pending_rep"] is True and result["comparison"]["display_diff"] == 661
    assert [c.get("origin") for c in _comparisons(services, sid)] == [None]


def test_the_representatives_answer_then_gives_611(services: Services, runner: ToolRunner) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))
    ticket = _ask(runner, sid, ATTO)
    answer_ticket(services, ticket, values={ATTO: 350})
    result = ok(runner.run(sid, "compare", ATTO_3))
    assert result["comparison"]["display_diff"] == 611
    assert result["participation_source"] == "representative" and result["pending_rep"] is False


def test_fields_the_comparison_did_not_use_do_not_recompute(
    services: Services, runner: ToolRunner
) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))
    _ask(runner, sid, "alternative_participation:CAR-11")  # another car
    _ask(runner, sid, "bonus")  # not a participation
    assert len(_comparisons(services, sid)) == 1


def test_a_stated_participation_does_not_recompute(services: Services, runner: ToolRunner) -> None:
    sid = _noa(services, runner)
    stated = {"alternative": {"kind": "car", "car_id": "CAR-10", "participation": 400}}
    ok(runner.run(sid, "compare", stated))  # employee_input, not the catalog default
    _ask(runner, sid, ATTO)
    assert len(_comparisons(services, sid)) == 1


def test_only_the_latest_comparison_of_that_car_counts(
    services: Services, runner: ToolRunner
) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))  # catalog default...
    stated = {"alternative": {"kind": "car", "car_id": "CAR-10", "participation": 400}}
    ok(runner.run(sid, "compare", stated))  # ...superseded by the employee's amount
    _ask(runner, sid, ATTO)
    assert len(_comparisons(services, sid)) == 2


def test_current_participation_at_the_catalog_default(
    services: Services, runner: ToolRunner
) -> None:
    today = {"today": {"kind": "company_car", "car_id": "CAR-09"}}  # participation unknown
    sid = _noa(services, runner, today)
    ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    _ask(runner, sid, "current_participation")
    first, recomputed = _comparisons(services, sid)
    assert first["today_participation"]["source"] == "catalog_default"
    assert recomputed["origin"] == "server"
    assert recomputed["today_participation"]["pending_rep"] is True
    assert recomputed["pending_field"] == "current_participation"


# --- the answer settles it -------------------------------------------------------------------


def _input(view: dict[str, Any], input_id: str) -> dict[str, Any]:
    return next(i for i in view["inputs"] if i["id"] == input_id)


@pytest.mark.parametrize("order", ["ask_then_compare", "compare_then_ask"])
def test_answer_without_a_later_compare_settles_at_611(
    services: Services, runner: ToolRunner, order: str
) -> None:
    sid = _noa(services, runner)
    if order == "ask_then_compare":
        ticket = _ask(runner, sid, ATTO)
        ok(runner.run(sid, "compare", ATTO_3))
    else:
        ok(runner.run(sid, "compare", ATTO_3))
        ticket = _ask(runner, sid, ATTO)
    pending = _comparisons(services, sid)[-1]
    assert pending["view"]["pending"] is True and pending["view"]["display_diff"] == 661

    answer_ticket(services, ticket, values={ATTO: 350})  # and no compare after it

    settled = _comparisons(services, sid)[-1]
    assert settled["origin"] == "server"
    assert settled["recomputed_from"] == pending["seq"]
    assert (settled["ticket_id"], settled["answered_field"]) == (ticket, ATTO)
    assert settled["pending_rep"] is False
    assert settled["participation_source"] == "representative"
    view = settled["view"]
    assert view["pending"] is False and view["pending_fields"] == []
    assert view["display_diff"] == 611
    assert (view["today_net"], view["alternative_net"]) == (11032, 11643)
    participation = _input(view, "alternative_participation")
    assert (participation["value"], participation["source"]) == (350, "representative")
    assert view["alternative_car_id"] == pending["view"]["alternative_car_id"]


def test_answer_then_the_agents_compare_gives_the_same_view(
    services: Services, runner: ToolRunner
) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))
    ticket = _ask(runner, sid, ATTO)
    answer_ticket(services, ticket, values={ATTO: 350})
    ok(runner.run(sid, "compare", ATTO_3))  # the model compares again, as in the demo script
    *_, settled, agents = _comparisons(services, sid)
    assert settled["origin"] == "server" and "origin" not in agents
    assert agents["view"] == settled["view"]
    assert agents["comparison"] == settled["comparison"]


def test_a_field_the_comparison_did_not_use_settles_nothing(
    services: Services, runner: ToolRunner
) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))
    other = _ask(runner, sid, "alternative_participation:CAR-11")  # another car
    before = len(_comparisons(services, sid))
    answer_ticket(services, other, values={"alternative_participation:CAR-11": 500})
    assert len(_comparisons(services, sid)) == before


def test_a_non_participation_answer_settles_nothing(services: Services, runner: ToolRunner) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))
    ticket = _ask(runner, sid, "bonus")
    before = len(_comparisons(services, sid))
    answer_ticket(services, ticket, values={"bonus": 0})
    assert len(_comparisons(services, sid)) == before


def test_a_comparison_that_was_not_pending_is_not_recomputed(
    services: Services, runner: ToolRunner
) -> None:
    sid = _noa(services, runner)
    ticket = _ask(runner, sid, ATTO)
    stated = {"alternative": {"kind": "car", "car_id": "CAR-10", "participation": 400}}
    ok(runner.run(sid, "compare", stated))  # the employee's own amount: never pending
    before = len(_comparisons(services, sid))
    answer_ticket(services, ticket, values={ATTO: 350})
    assert len(_comparisons(services, sid)) == before


def test_an_answer_without_a_value_settles_nothing(services: Services, runner: ToolRunner) -> None:
    sid = _noa(services, runner)
    ok(runner.run(sid, "compare", ATTO_3))
    ticket = _ask(runner, sid, ATTO)
    before = len(_comparisons(services, sid))
    answer_ticket(services, ticket, answer_text="אבדוק ואחזור אליך")  # the field becomes unknown
    assert len(_comparisons(services, sid)) == before


def test_current_participation_answer_settles_today(services: Services, runner: ToolRunner) -> None:
    today = {"today": {"kind": "company_car", "car_id": "CAR-09"}}  # participation unknown
    sid = _noa(services, runner, today)
    ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    ticket = _ask(runner, sid, "current_participation")
    answer_ticket(services, ticket, values={"current_participation": 300})
    settled = _comparisons(services, sid)[-1]
    assert settled["origin"] == "server" and settled["answered_field"] == "current_participation"
    assert settled["today_participation"] == {
        "source": "representative",
        "pending_rep": False,
        "effective_from": None,
    }
    assert settled["view"]["pending"] is False

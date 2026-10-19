"""A ticket for a car's participation, with no comparison of that car yet: the server computes a
provisional one (catalog default, pending, no model call), and the rep's answer settles it."""

import logging
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
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
ATTO = "alternative_participation:CAR-10"
ASK_ATTO = {"question": "?", "blocking_fields": [ATTO]}


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _comparisons(services: Services, sid: str) -> list[dict[str, Any]]:
    events = services.store.events_after(sid)
    return [{"seq": e.seq, **e.payload} for e in events if e.type == "comparison_ready"]


def _session(services: Services, tools: ToolRunner, profile: dict[str, Any] = NOA) -> str:
    sid = services.store.create_session()
    # the employee names the car (a ticket may ask only about such cars)
    services.store.add_message(sid, "user", {"text": "מה יקרה לנטו אם אעבור ל-ATTO 3?"})
    ok(tools.run(sid, "save_profile", profile))
    ok(tools.run(sid, "set_current_situation", TODAY))
    return sid


def test_ask_without_compare_yields_a_pending_661(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    result = ok(tools.run(sid, "ask_representative", ASK_ATTO))

    (shown,) = _comparisons(services, sid)
    assert shown["origin"] == "server" and "recomputed_from" not in shown
    assert (shown["ticket_id"], shown["pending_field"]) == (result["ticket_id"], ATTO)
    assert shown["pending_rep"] is True and shown["participation_source"] == "catalog_default"
    assert shown["view"]["pending"] is True and shown["view"]["display_diff"] == 661
    # the model gets it back from ask_representative, as compare would have returned it
    (provisional,) = result["provisional_comparisons"]
    assert provisional["comparison"]["display_diff"] == 661
    assert provisional["pending_rep"] is True
    assert provisional["alternative_kind"] == shown["alternative_kind"]
    assert "view" not in provisional  # never the UI's labels


def test_then_the_answer_settles_it_at_611(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    ticket = ok(tools.run(sid, "ask_representative", ASK_ATTO))["ticket_id"]
    answer_ticket(services, ticket, values={ATTO: 350})  # no compare anywhere
    provisional, settled = _comparisons(services, sid)
    assert settled["origin"] == "server" and settled["recomputed_from"] == provisional["seq"]
    assert settled["answered_field"] == ATTO
    assert settled["participation_source"] == "representative"
    assert (settled["view"]["display_diff"], settled["view"]["pending"]) == (611, False)


def test_missing_inputs_emit_nothing_and_say_why(
    services: Services, tools: ToolRunner, caplog: pytest.LogCaptureFixture
) -> None:
    no_salary = {k: v for k, v in NOA.items() if k != "base_salary"}
    sid = _session(services, tools, no_salary)
    with caplog.at_level(logging.INFO, logger="compass.tools.handlers"):
        result = ok(tools.run(sid, "ask_representative", ASK_ATTO))
    assert _comparisons(services, sid) == []
    assert "provisional_comparisons" not in result
    assert any("no provisional comparison for CAR-10" in r.getMessage() for r in caplog.records)


def test_no_current_situation_emits_nothing(services: Services, tools: ToolRunner) -> None:
    sid = services.store.create_session()
    # the employee names the car (a ticket may ask only about such cars)
    services.store.add_message(sid, "user", {"text": "מה יקרה לנטו אם אעבור ל-ATTO 3?"})
    ok(tools.run(sid, "save_profile", NOA))  # no set_current_situation
    result = ok(tools.run(sid, "ask_representative", ASK_ATTO))
    assert _comparisons(services, sid) == []
    assert "provisional_comparisons" not in result


def test_ask_after_a_compare_does_not_duplicate(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    ok(tools.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    result = ok(tools.run(sid, "ask_representative", ASK_ATTO))
    compared, recomputed = _comparisons(services, sid)  # 3b50995's pending recompute only
    assert recomputed["recomputed_from"] == compared["seq"]
    assert "provisional_comparisons" not in result


def test_a_second_ticket_for_the_same_car_does_not_duplicate(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools)
    ok(tools.run(sid, "ask_representative", ASK_ATTO))
    ok(tools.run(sid, "ask_representative", ASK_ATTO))
    assert [c["origin"] for c in _comparisons(services, sid)] == ["server", "server"]
    # the second is 3b50995's recompute of the first (still at the catalog default), not a copy
    first, second = _comparisons(services, sid)
    assert second["recomputed_from"] == first["seq"]


def test_only_participation_tickets(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    ok(tools.run(sid, "ask_representative", {"question": "?", "blocking_fields": ["bonus"]}))
    ok(
        tools.run(
            sid,
            "ask_representative",
            {"question": "?", "blocking_fields": ["current_participation"]},
        )
    )
    assert _comparisons(services, sid) == []

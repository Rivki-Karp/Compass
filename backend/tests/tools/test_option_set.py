"""list_options puts every eligible alternative on screen: one comparison_set_ready event, each
option's `view` exactly what compare would show for it, computed by the server (no model)."""

import json
from typing import Any

import pytest

from compass.agent.guard import make_guard
from compass.agent.llm import ScriptedClient, text_response, tool_response
from compass.agent.runner import ClaudeAgentRunner
from compass.agent.transcript import model_view
from compass.state import Store
from compass.tools import Services, ToolRunner

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


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def _session(services: Services, tools: ToolRunner) -> str:
    sid = services.store.create_session()
    services.store.add_message(sid, "user", {"text": "מה כל האפשרויות שלי? ואטו 3?"})
    assert tools.run(sid, "save_profile", NOA)["ok"]
    assert tools.run(sid, "set_current_situation", TODAY)["ok"]
    return sid


def _sets(services: Services, sid: str) -> list[dict[str, Any]]:
    return [e.payload for e in services.store.events_after(sid) if e.type == "comparison_set_ready"]


def _without_origin(view: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in view.items() if k != "computed_by"}


def test_one_event_with_every_eligible_option_best_first(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools)
    result = tools.run(sid, "list_options", {})
    eligible = [o for o in result["options"] if o["eligibility"]["status"] == "eligible"]
    (event,) = _sets(services, sid)
    assert event["origin"] == "server" and event["tool"] == "list_options"
    assert len(event["options"]) == len(eligible) > 2
    diffs = [o["view"]["display_diff"] for o in event["options"]]
    assert diffs == sorted(diffs, reverse=True)
    assert all(o["view"]["computed_by"]["origin"] == "server" for o in event["options"])
    # nothing recorded as a comparison: the model's compare stays the record of what it compared
    assert not [e for e in services.store.events_after(sid) if e.type == "comparison_ready"]


def test_each_option_matches_a_single_compare(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    tools.run(sid, "list_options", {})
    (event,) = _sets(services, sid)
    for option in event["options"]:
        alternative = option["alternative"]
        given = (
            {"kind": "waiver"}
            if alternative["kind"] == "waiver"
            else {
                "kind": "car",
                "car_id": alternative["car_id"],
            }
        )
        assert tools.run(sid, "compare", {"alternative": given})["ok"]
        compared = services.store.last_comparison(sid)
        assert compared is not None
        assert _without_origin(option["view"]) == _without_origin(compared["view"]), given


def test_pending_participation_is_marked_per_car(services: Services, tools: ToolRunner) -> None:
    sid = _session(services, tools)
    ask = {"question": "?", "blocking_fields": ["alternative_participation:CAR-10"]}
    assert tools.run(sid, "ask_representative", ask)["ok"]
    tools.run(sid, "list_options", {})
    (event,) = _sets(services, sid)
    by_car = {o["alternative"].get("car_id"): o["view"] for o in event["options"]}
    assert by_car["CAR-10"]["pending"] is True
    assert by_car["CAR-10"]["pending_fields"] == ["alternative_participation:CAR-10"]
    assert all(not v["pending"] for car, v in by_car.items() if car != "CAR-10")


def test_the_model_reads_compact_numbers_and_the_guard_allows_them(
    services: Services, tools: ToolRunner
) -> None:
    sid = _session(services, tools)
    result = tools.run(sid, "list_options", {})
    compact = json.loads(model_view("list_options", result))
    first = compact["options"][0]
    assert set(first) >= {"commercial_name", "display_diff", "net", "eligibility"}
    assert compact["today_net"] == 11032

    reply = "שלוש המובילות: ויתור +3,199 ₪, MG4 +1,013 ₪, BYD DOLPHIN +994 ₪. השאר מוצגות במסך."
    llm = ScriptedClient([tool_response(("list_options", {})), text_response(reply)])
    runner = ClaudeAgentRunner(
        services, llm, "SYSTEM", guard=make_guard(services.store), background=False
    )
    seq = services.store.add_message(sid, "user", {"text": "מה האפשרויות שלי?"})
    runner.on_user_message(sid, seq)
    (check,) = [e.payload for e in services.store.events_after(sid) if e.type == "guard_check"]
    assert check["action"] == "accept", check

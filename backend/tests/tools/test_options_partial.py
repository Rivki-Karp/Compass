"""Item 4: list_options never refuses for a missing profile input.

The incident (v14-on.db, session 0d26...): after a payslip the employee had a salary, study fund
and credit points; commissions, bonus and the pension rate were missing, and so was today's car.
list_options answered missing_inputs (a red ✕ in the chat). Root cause: the engine's list_options
computed nothing unless EVERY input was known when today's car was unknown ("neither a diff nor a
net"), and nothing at all when commissions or bonus were missing. compare, with today's car
known, already degraded for unknown pension / study fund rates; with today's car unknown it did
not. Now both degrade the same way, and when no net can be computed the options are still listed
with their eligibility, marked partial, with what is missing.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from compass.agent.transcript import model_view
from compass.state import Store
from compass.tools import Services, ToolRunner

BASE = {
    "occupation_query": "מפתחת תוכנה",
    "base_salary": 7000,
    "study_fund_percent": 2.25,
    "credit_points": 3,
}
FULL = {**BASE, "commissions": 0, "bonus": 0, "pension_percent": 6.5}
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def session(tools: ToolRunner, profile: dict[str, Any]) -> str:
    sid = tools.services.store.create_session()
    assert tools.run(sid, "save_profile", profile)["ok"]
    return sid


def sets(services: Services, sid: str) -> list[dict[str, Any]]:
    return [e.payload for e in services.store.events_after(sid) if e.type == "comparison_set_ready"]


def test_the_incident_commissions_bonus_pension_and_today_unknown_is_not_a_refusal(
    tools: ToolRunner, services: Services
) -> None:
    sid = session(tools, BASE)
    result = tools.run(sid, "list_options", {})
    assert result["ok"] is True  # it was missing_inputs
    assert result["partial"] is True and result["no_amounts"] is True
    assert set(result["missing"]) >= {"commissions", "bonus", "pension_percent"}
    assert "current_situation" in result["missing"]
    # every alternative with its eligibility, and no money
    assert len(result["options"]) > 5
    assert all(o["comparison"] is None for o in result["options"])
    assert {o["eligibility"]["status"] for o in result["options"]} >= {"eligible"}
    assert [o for o in result["options"] if o["commercial_name"] == "ATTO 3"]
    # nothing on screen: there is no number to put there
    assert sets(services, sid) == []


def test_the_model_reads_a_list_without_amounts(tools: ToolRunner) -> None:
    sid = session(tools, BASE)
    view = json.loads(model_view("list_options", tools.run(sid, "list_options", {})))
    assert view["partial"] is True and view["no_amounts"] is True
    assert all(o["net"] is None and o["display_diff"] is None for o in view["options"])
    assert all(o["partial"] is True for o in view["options"])
    assert "today_net" not in view and "today_unknown" not in view


def test_only_the_pension_rate_and_today_unknown_lists_every_option_without_a_net(
    tools: ToolRunner, services: Services
) -> None:
    sid = session(tools, {**BASE, "commissions": 0, "bonus": 0})  # pension missing
    result = tools.run(sid, "list_options", {})
    assert result["ok"] is True and result["partial"] is True
    assert "no_amounts" not in result
    assert result["missing"] == ["current_situation", "pension_percent"]
    (event,) = sets(services, sid)
    assert event["today_unknown"] is True
    views = [o["view"] for o in event["options"]]
    assert views and all(v["alternative_net"] is None and v["display_diff"] is None for v in views)
    assert all(v["partial"] is True and v["direction"] == "unknown" for v in views)
    missing = {m["field"] for v in views for m in v["missing"]}
    assert missing == {"current_situation", "pension_percent"}


def test_the_order_does_not_wait_for_the_pension_rate(
    tools: ToolRunner, services: Services
) -> None:
    """Every option pays the same pension, so ranking by the net at zero rates is the order the
    real nets give."""
    unknown = session(tools, {**BASE, "commissions": 0, "bonus": 0})
    known = session(tools, FULL)
    tools.run(unknown, "list_options", {})
    tools.run(known, "list_options", {})
    names = lambda sid: [  # noqa: E731
        o["alternative"].get("car_id") or o["alternative"]["kind"]
        for o in sets(services, sid)[0]["options"]
    ]
    assert names(unknown) == names(known)


def test_today_known_and_the_pension_rate_unknown_keeps_the_diffs(
    tools: ToolRunner, services: Services
) -> None:
    sid = session(tools, {**BASE, "commissions": 0, "bonus": 0})
    assert tools.run(sid, "set_current_situation", TODAY)["ok"]
    result = tools.run(sid, "list_options", {})
    assert result["ok"] is True and result["partial"] is True
    assert result["missing"] == ["pension_percent"]
    (event,) = sets(services, sid)
    assert all(o["view"]["display_diff"] is not None for o in event["options"])


def test_a_full_profile_is_not_partial(tools: ToolRunner) -> None:
    sid = session(tools, FULL)
    assert tools.run(sid, "set_current_situation", TODAY)["ok"]
    result = tools.run(sid, "list_options", {})
    assert result["partial"] is False and result["missing"] == []


def test_compare_without_today_and_the_pension_rate_is_partial_too(
    tools: ToolRunner, services: Services
) -> None:
    sid = session(tools, {**BASE, "commissions": 0, "bonus": 0})
    result = tools.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-06"}})
    assert result["ok"] is True
    comparison = result["comparison"]
    assert comparison["partial"] and comparison["today_unknown"]
    assert comparison["alternative"]["display"]["net"] is None
    assert result["missing"] == ["current_situation", "pension_percent"]


def test_compare_without_commissions_still_refuses_it_has_no_net_to_show(
    tools: ToolRunner,
) -> None:
    sid = session(tools, BASE)
    result = tools.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-06"}})
    assert result["ok"] is False and result["error"]["code"] == "missing_inputs"

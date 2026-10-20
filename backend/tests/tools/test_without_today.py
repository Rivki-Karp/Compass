"""Today's car unknown: every alternative still shows with its own net; the diff waits.

An alternative's net does not depend on today's car, only the difference does. So compare and
list_options answer partially (no diff, "חסר הרכב של היום") instead of refusing, and once today
is known the server computes what is on screen again, with the diffs.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from compass.agent.transcript import model_view
from compass.engine.compare import compare as engine_compare
from compass.engine.context import build_context
from compass.engine.models import CompanyCar, EmployeeProfile, MissingInputs
from compass.engine.options import list_options as engine_options
from compass.state import Store
from compass.tools import Services, ToolRunner

DEVELOPER = {
    "occupation_query": "מפתחת תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
COROLLA_CROSS = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
MG4 = {"alternative": {"kind": "car", "car_id": "CAR-06"}}


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def tools(services: Services) -> ToolRunner:
    return ToolRunner(services)


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _session(tools: ToolRunner, profile: dict[str, Any] = DEVELOPER) -> str:
    sid = tools.services.store.create_session()
    ok(tools.run(sid, "save_profile", profile))
    return sid


def _events(services: Services, sid: str, kind: str) -> list[Any]:
    return [e for e in services.store.events_after(sid) if e.type == kind]


# --- the engine -------------------------------------------------------------------------------


def test_the_engine_gives_the_same_net_with_or_without_today() -> None:
    ctx = build_context()
    profile = EmployeeProfile(
        group="ב",
        occupation="מפתח/ת תוכנה",
        base_salary=Decimal(18500),
        commissions=Decimal(0),
        bonus=Decimal(0),
        pension_pct=Decimal("0.065"),
        study_fund_pct=Decimal("0.025"),
        credit_points=Decimal(3),
    )
    alternative = CompanyCar(car_id="CAR-06")
    known = engine_compare(profile, CompanyCar(car_id="CAR-09"), alternative, ctx)
    alone = engine_compare(profile, None, alternative, ctx)
    assert alone.alternative == known.alternative
    assert alone.today is None and alone.diff is None and alone.display_diff is None
    assert alone.display_delta_lines == () and alone.explanation_facts == ()
    assert alone.missing == ("current_situation",) and alone.today_unknown and alone.partial


def test_without_today_an_unknown_rate_leaves_nothing_to_show() -> None:
    ctx = build_context()
    profile = EmployeeProfile(
        group="ב",
        occupation="מפתח/ת תוכנה",
        base_salary=Decimal(18500),
        commissions=Decimal(0),
        bonus=Decimal(0),
        study_fund_pct=Decimal("0.025"),
        credit_points=Decimal(3),
    )  # the pension rate is unknown: the net is unknown, and there is no diff to fall back on
    with pytest.raises(MissingInputs) as raised:
        engine_compare(profile, None, CompanyCar(car_id="CAR-06"), ctx)
    assert raised.value.fields == ("current_situation", "pension_pct")
    with pytest.raises(MissingInputs):
        engine_options(profile, None, ctx)


# --- compare and list_options -----------------------------------------------------------------


def test_compare_without_today_gives_the_net_and_says_what_the_diff_waits_for(
    tools: ToolRunner, services: Services
) -> None:
    sid = _session(tools)
    result = ok(tools.run(sid, "compare", MG4))
    comparison = result["comparison"]
    assert comparison["today"] is None and comparison["display_diff"] is None
    assert comparison["today_unknown"] and comparison["partial"]
    assert comparison["alternative"]["display"]["net"] > 0
    assert result["missing"] == ["current_situation"]
    (event,) = _events(services, sid, "comparison_ready")
    view = event.payload["view"]
    assert view["display_diff"] is None and view["direction"] == "unknown"
    assert view["diff_note"] == "חסר הרכב של היום"
    assert view["alternative_net"] == comparison["alternative"]["display"]["net"]
    assert view["today_net"] is None and view["breakdown"] == []
    assert [m["field"] for m in view["missing"]] == ["current_situation"]
    assert not any(i["id"].startswith("today") for i in view["inputs"])


def test_list_options_without_today_shows_every_eligible_alternative_by_net(
    tools: ToolRunner, services: Services
) -> None:
    sid = _session(tools)
    options = ok(tools.run(sid, "list_options", {}))["options"]
    assert options and all(o["comparison"]["display_diff"] is None for o in options)
    (shown,) = _events(services, sid, "comparison_set_ready")
    assert shown.payload["today_unknown"] is True
    views = [o["view"] for o in shown.payload["options"]]
    eligible = [o for o in options if o["eligibility"]["status"] == "eligible"]
    assert len(views) == len(eligible) > 2
    nets = [v["alternative_net"] for v in views]
    assert nets == sorted(nets, reverse=True)  # best first, as with the diff
    assert all(v["diff_note"] == "חסר הרכב של היום" and v["display_diff"] is None for v in views)


def test_today_set_later_recomputes_the_set_and_the_latest_comparison(
    tools: ToolRunner, services: Services
) -> None:
    sid = _session(tools)
    ok(tools.run(sid, "list_options", {"participation": {"CAR-06": 250}}))
    ok(tools.run(sid, "compare", MG4))
    (before,) = _events(services, sid, "comparison_set_ready")
    ok(tools.run(sid, "set_current_situation", COROLLA_CROSS))

    _, after = _events(services, sid, "comparison_set_ready")
    assert after.payload["today_unknown"] is False
    assert after.payload["stated"] == {"CAR-06": "250"}  # the same stated participation
    old = {v["view"]["alternative_car_id"]: v["view"] for v in before.payload["options"]}
    new = {v["view"]["alternative_car_id"]: v["view"] for v in after.payload["options"]}
    assert set(new) == set(old) - {"CAR-09"}  # today's own car is no longer an option
    for car, view in new.items():
        assert view["alternative_net"] == old[car]["alternative_net"]  # the net never moved
        assert view["today_net"] + view["display_diff"] == view["alternative_net"]
        assert view["diff_note"] is None and view["breakdown"]
    mg4 = next(v for v in after.payload["options"] if v["view"]["alternative_car_id"] == "CAR-06")
    assert mg4["alternative"]["participation"] == "250"

    shown, recomputed = _events(services, sid, "comparison_ready")
    assert recomputed.payload["origin"] == "server"
    assert recomputed.payload["recomputed_from"] == shown.seq
    assert recomputed.payload["view"]["display_diff"] is not None
    assert recomputed.payload["view"]["today_title"] == "COROLLA CROSS"
    # what compare now returns is what the server put on screen
    again = ok(tools.run(sid, "compare", MG4))
    assert again["comparison"]["display_diff"] == recomputed.payload["view"]["display_diff"]


def test_a_set_with_today_known_is_not_recomputed(tools: ToolRunner, services: Services) -> None:
    sid = _session(tools)
    ok(tools.run(sid, "set_current_situation", COROLLA_CROSS))
    ok(tools.run(sid, "list_options", {}))
    ok(tools.run(sid, "compare", MG4))
    ok(tools.run(sid, "set_current_situation", {"today": {"kind": "none"}}))
    assert len(_events(services, sid, "comparison_set_ready")) == 1
    assert len(_events(services, sid, "comparison_ready")) == 1


def test_the_model_reads_a_partial_list_without_today(tools: ToolRunner) -> None:
    sid = _session(tools)
    result = ok(tools.run(sid, "list_options", {}))
    view = json.loads(model_view("list_options", result))
    assert view["today_unknown"] is True and "today_net" not in view
    assert all(o["display_diff"] is None and o["net"] for o in view["options"])

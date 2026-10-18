"""The display-ready `view` on comparison_ready: labels, sources, provenance and invariants."""

import copy
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from compass.engine.models import CompanyCar, DeltaLineName, FamilyCar, WarningCode
from compass.labels import DELTA_LABELS, FIELD_LABELS, RULE_LABELS, WARNING_MESSAGES
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.profile import PROFILE_FIELDS, REQUIRED_FIELDS
from compass.tools.tickets import answer_ticket
from compass.tools.view import PROVENANCE, ViewInvariantError, build_view

DEVELOPER = {
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
COROLLA_CROSS = {
    "today": {
        "kind": "company_car",
        "car_id": "CAR-09",
        "registration_year": 2025,
        "participation": 300,
    }
}
ATTO = "alternative_participation:CAR-10"


@pytest.fixture
def services(tmp_path: Any) -> Services:
    return Services(Store(tmp_path / "app.db"))


@pytest.fixture
def runner(services: Services) -> ToolRunner:
    return ToolRunner(services)


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _session(services: Services, runner: ToolRunner, profile: dict[str, Any]) -> str:
    sid = services.store.create_session()
    ok(runner.run(sid, "save_profile", profile))
    ok(runner.run(sid, "set_current_situation", COROLLA_CROSS))
    return sid


def _last(services: Services, sid: str) -> dict[str, Any]:
    events = [e for e in services.store.events_after(sid) if e.type == "comparison_ready"]
    return events[-1].payload


def _inputs(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {i["id"]: i for i in view["inputs"]}


def _walkthrough(services: Services, runner: ToolRunner) -> tuple[str, dict[str, Any]]:
    sid = _session(services, runner, DEVELOPER)
    result = ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    assert "view" not in result  # the model never sees the UI's labels
    return sid, _last(services, sid)


def test_walkthrough_view(services: Services, runner: ToolRunner) -> None:
    _, payload = _walkthrough(services, runner)
    view = payload["view"]
    assert (view["today_net"], view["alternative_net"], view["display_diff"]) == (
        11000,
        13914,
        2914,
    )
    assert view["direction"] == "up"
    assert [(line["key"], line["label"], line["net_effect"]) for line in view["breakdown"]] == [
        ("maintenance", "אחזקת רכב", 1500),
        ("income_tax", "מס הכנסה", 802),
        ("national_insurance", "ביטוח לאומי", 180),
        ("health", "מס בריאות", 132),
        ("participation", "השתתפות ברכב", 300),
    ]
    assert view["today_title"] == "COROLLA CROSS 2025"
    assert view["alternative_title"] == "ויתור על הרכב"
    assert (view["group"], view["group_label"], view["group_budget"]) == ("ב", "קבוצה ב׳", 3700)
    assert not view["pending"] and not view["partial"] and not view["hypothetical"]

    inputs = _inputs(view)
    assert {k: (v["value"], v["source"]) for k, v in inputs.items()} == {
        "occupation": ("מפתח/ת תוכנה", "employee_input"),
        "group": ("ב׳", "occupation"),  # with a geresh, like the pill
        "base_salary": (18500, "employee_input"),
        "commissions": (0, "employee_input"),
        "bonus": (0, "employee_input"),
        "pension_percent": ("6.5", "employee_input"),
        "study_fund_percent": ("2.5", "employee_input"),
        "credit_points": ("3", "employee_input"),
        "today_car": ("COROLLA CROSS 2025", "employee_input"),
        "today_participation": (300, "employee_input"),
        "alternative_maintenance": (1500, "occupation"),
    }
    assert [w["code"] for w in view["warnings"]] == ["current_car_above_group"]
    assert "COROLLA CROSS" in view["warnings"][0]["message"]


def test_every_breakdown_line_cites_present_inputs(services: Services, runner: ToolRunner) -> None:
    _, payload = _walkthrough(services, runner)
    view = payload["view"]
    present = set(_inputs(view))
    for line in view["breakdown"]:
        assert line["inputs"] or line["rules"], line["key"]
        assert set(line["inputs"]) <= present
    income_tax = next(line for line in view["breakdown"] if line["key"] == "income_tax")
    assert "credit_points" in income_tax["inputs"]
    assert "מדרגות מס הכנסה" in [r["label"] for r in income_tax["rules"]]


def test_e001_pending_then_final(services: Services, runner: ToolRunner) -> None:
    sid = _session(services, runner, NOA)
    ticket = ok(runner.run(sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]}))
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    pending = _last(services, sid)["view"]
    assert pending["display_diff"] == 661 and pending["alternative_title"] == "ATTO 3"
    assert pending["pending"] and pending["pending_fields"] == [ATTO]
    participation = _inputs(pending)["alternative_participation"]
    assert (participation["value"], participation["source"], participation["ticket_field"]) == (
        300,
        "pending_rep",
        ATTO,
    )
    assert [line["key"] for line in pending["breakdown"]] == [
        "electric_gross",
        "income_tax",
        "national_insurance",
        "health",
    ]

    answer_ticket(services, ticket["ticket_id"], values={ATTO: 350})
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    final = _last(services, sid)["view"]
    assert (final["today_net"], final["alternative_net"], final["display_diff"]) == (
        11032,
        11643,
        611,
    )
    assert not final["pending"] and final["pending_fields"] == []
    assert _inputs(final)["alternative_participation"]["source"] == "representative"
    assert final["breakdown"][-1] == {
        "key": "participation",
        "label": "השתתפות ברכב",
        "net_effect": -50,
        "inputs": ["today_participation", "alternative_participation"],
        "rules": [],
    }


def test_server_recompute_carries_a_pending_view(services: Services, runner: ToolRunner) -> None:
    sid = _session(services, runner, NOA)
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    ok(runner.run(sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]}))
    recomputed = _last(services, sid)
    assert recomputed["origin"] == "server"
    assert recomputed["view"]["pending"] and recomputed["view"]["display_diff"] == 661


def test_invariant_violations_are_never_emitted(services: Services, runner: ToolRunner) -> None:
    sid, payload = _walkthrough(services, runner)
    alternative = payload["alternative"]
    build_view(services, sid, alternative, payload)  # the real payload passes

    lines_off = copy.deepcopy(payload)
    lines_off["comparison"]["display_delta_lines"][1]["net_effect"] += 1
    with pytest.raises(ViewInvariantError, match="lines sum"):
        build_view(services, sid, alternative, lines_off)

    nets_off = copy.deepcopy(payload)
    nets_off["comparison"]["alternative"]["display"]["net"] += 1
    with pytest.raises(ViewInvariantError, match="!="):
        build_view(services, sid, alternative, nets_off)


# --- labels and the provenance map -------------------------------------------------------------


def test_every_delta_line_has_a_label_and_a_provenance() -> None:
    lines = set(get_args(DeltaLineName))
    assert set(DELTA_LABELS) == lines
    assert set(PROVENANCE) == lines
    for key, (inputs, rules) in PROVENANCE.items():
        assert inputs or rules, key
        assert set(inputs) <= set(FIELD_LABELS), key
        assert set(rules) <= set(RULE_LABELS), key


def test_every_warning_code_has_a_message() -> None:
    assert set(WARNING_MESSAGES) == set(get_args(WarningCode))


def test_every_profile_field_has_a_label() -> None:
    assert set(PROFILE_FIELDS) | set(REQUIRED_FIELDS) | {"current_situation"} <= set(FIELD_LABELS)


# --- participation_source is set exactly when the participation is given -----------------------


@pytest.mark.parametrize("cls", [CompanyCar, FamilyCar])
def test_participation_source_follows_the_amount(cls: type[CompanyCar]) -> None:
    assert cls(car_id="CAR-10").participation_source is None
    assert cls(car_id="CAR-10", participation=350).participation_source == "employee_input"
    given = cls(car_id="CAR-10", participation=350, participation_source="representative")
    assert given.participation_source == "representative"
    with pytest.raises(ValidationError):
        cls(car_id="CAR-10", participation_source="representative")


def test_scenarios_stored_before_the_fix_still_load() -> None:
    legacy = {"car_id": "CAR-10", "participation": None, "participation_source": "employee_input"}
    assert CompanyCar.model_validate(legacy).participation_source is None


def test_stored_alternative_has_no_source_without_an_amount(
    services: Services, runner: ToolRunner
) -> None:
    sid = _session(services, runner, NOA)
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    payload = _last(services, sid)
    assert payload["alternative"]["participation"] is None
    assert payload["alternative"]["participation_source"] is None
    assert payload["participation_source"] == "catalog_default"


# --- 1e: honest sources, consistent labels, titles, direction ----------------------------------


def test_unstated_commissions_are_never_assumed_zero(
    services: Services, runner: ToolRunner
) -> None:
    """Zero commissions/bonus reach the view only when saved (the employee said "no"): an
    unstated one stays missing, so compare refuses and no view with a made-up 0 exists."""
    sid = services.store.create_session()
    unstated = {k: v for k, v in DEVELOPER.items() if k not in ("commissions", "bonus")}
    ok(runner.run(sid, "save_profile", unstated))
    ok(runner.run(sid, "set_current_situation", COROLLA_CROSS))
    result = runner.run(sid, "compare", {"alternative": {"kind": "waiver"}})
    assert not result["ok"] and result["error"]["code"] == "missing_inputs"
    assert {"commissions", "bonus"} <= set(result["error"]["fields"])
    assert not [e for e in services.store.events_after(sid) if e.type == "comparison_ready"]


def test_demo_scripts_save_zero_only_when_the_employee_says_so() -> None:
    from compass.agent.demo_llm import SCRIPTS

    for script in SCRIPTS:
        for turn in script.turns:
            for kind, step in turn.steps:
                if kind != "tools":
                    continue
                for name, tool_input in step:
                    zeros = [k for k in ("commissions", "bonus") if tool_input.get(k) == 0]
                    if name == "save_profile" and zeros:
                        assert turn.employee and "אין לי עמלות או בונוסים" in turn.employee


def test_warning_messages_use_the_pill_group_label() -> None:
    import re

    from compass.labels import group_label, warning_message

    facts = {
        "group_mismatch_with_occupation": {
            "employee_group": "ב",
            "occupation": "מפתח/ת תוכנה",
            "occupation_group": "ג",
        },
        "current_car_above_group": {"employee_group": "ב", "car_id": "CAR-09", "car_group": "ג"},
        "current_car_not_in_catalog": {"vehicle_key": "k", "label": "COROLLA CROSS 2023"},
    }
    assert set(facts) == set(get_args(WarningCode))
    for code, code_facts in facts.items():
        message = warning_message(code, code_facts)  # type: ignore[arg-type]
        for key in ("employee_group", "occupation_group", "car_group"):
            if key in code_facts:
                assert group_label(code_facts[key]) in message, (code, message)
        # never a bare letter or an ASCII apostrophe, only the pill's label ("קבוצה ג׳")
        assert not re.search(r"קבוצה [א-ת](?![א-ת׳])", message), message


def test_today_title_has_the_year_only_when_given(services: Services, runner: ToolRunner) -> None:
    sid = services.store.create_session()
    ok(runner.run(sid, "save_profile", DEVELOPER))
    no_year = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
    ok(runner.run(sid, "set_current_situation", no_year))
    ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    assert _last(services, sid)["view"]["today_title"] == "COROLLA CROSS"


def test_direction_is_flat_for_a_zero_diff(services: Services, runner: ToolRunner) -> None:
    sid, payload = _walkthrough(services, runner)
    flat = copy.deepcopy(payload)
    comparison = flat["comparison"]
    comparison["alternative"]["display"]["net"] = comparison["today"]["display"]["net"]
    comparison["display_diff"] = 0
    comparison["display_delta_lines"] = [
        {**line, "net_effect": 0} for line in comparison["display_delta_lines"]
    ]
    view = build_view(services, sid, flat["alternative"], flat)
    assert view["direction"] == "flat" and view["breakdown"] == []


def test_alternative_details_from_the_catalog(services: Services, runner: ToolRunner) -> None:
    sid = _session(services, runner, NOA)
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    assert _last(services, sid)["view"]["alternative_details"] == "חשמלי · קבוצה ג׳"
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-12"}}))
    assert _last(services, sid)["view"]["alternative_details"] == "בנזין · קבוצה ג׳"
    ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    assert _last(services, sid)["view"]["alternative_details"] is None  # nothing for a waiver


def test_alternative_details_for_a_family_track_car() -> None:
    from compass.labels import car_details

    assert car_details("petrol", "משפחתי") == "בנזין · מסלול משפחתי"  # never "קבוצה משפחתי׳"
    assert car_details("plugin", "ד") == "פלאג-אין · קבוצה ד׳"


def test_every_catalog_drive_has_a_label() -> None:
    from compass.data.drive import Drive
    from compass.labels import DRIVE_LABELS

    assert set(DRIVE_LABELS) == set(get_args(Drive))


# --- Day 5 Stage 1: who computed the comparison ------------------------------------------------

TOOL_LABEL = {"origin": "tool", "label": "חושב בכלי", "tool": "compare"}
SERVER_LABEL = {"origin": "server", "label": "חושב מחדש בשרת · בלי מודל", "tool": None}


def _computed_by(services: Services, sid: str) -> list[tuple[Any, dict[str, Any]]]:
    return [
        (e.payload.get("origin"), e.payload["view"]["computed_by"])
        for e in services.store.events_after(sid)
        if e.type == "comparison_ready"
    ]


def test_computed_by_the_tool(services: Services, runner: ToolRunner) -> None:
    _, payload = _walkthrough(services, runner)
    assert "origin" not in payload
    assert payload["view"]["computed_by"] == TOOL_LABEL


def test_computed_by_the_server_for_the_provisional_and_the_settle(
    services: Services, runner: ToolRunner
) -> None:
    """E-001 without a `compare` call: the provisional comparison when the ticket opens, then the
    settle on the rep's answer. Both are the server's, and say so."""
    sid = _session(services, runner, NOA)
    ticket = ok(runner.run(sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]}))
    answer_ticket(services, ticket["ticket_id"], values={ATTO: 350})
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    assert _computed_by(services, sid) == [
        ("server", SERVER_LABEL),  # provisional, +661 pending
        ("server", SERVER_LABEL),  # settle, +611
        (None, TOOL_LABEL),  # the model's own compare
    ]


def test_computed_by_the_server_for_the_pending_recompute(
    services: Services, runner: ToolRunner
) -> None:
    sid = _session(services, runner, NOA)
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    ok(runner.run(sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]}))
    assert _computed_by(services, sid) == [(None, TOOL_LABEL), ("server", SERVER_LABEL)]

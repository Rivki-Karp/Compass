from dataclasses import replace
from typing import Any

import pytest

from compass.state import Store
from compass.tools import REGISTRY, Services, ToolRunner, tool_definitions
from compass.tools.profile import profile_from_slots

DEVELOPER = {
    "occupation_query": "מפתח תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
COROLLA_CROSS_TODAY = {
    "today": {
        "kind": "company_car",
        "car_id": "CAR-09",
        "registration_year": 2025,
        "participation": 300,
    }
}


@pytest.fixture(scope="module")
def services(tmp_path_factory: pytest.TempPathFactory) -> Services:
    return Services(Store(tmp_path_factory.mktemp("tools") / "app.db"))


@pytest.fixture
def runner(services: Services) -> ToolRunner:
    return ToolRunner(services)


@pytest.fixture
def sid(services: Services) -> str:
    return services.store.create_session()


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def err(result: dict[str, Any], code: str) -> dict[str, Any]:
    assert result["ok"] is False and result["error"]["code"] == code, result
    return result["error"]


def _ready(runner: ToolRunner, sid: str) -> None:
    ok(runner.run(sid, "save_profile", DEVELOPER))
    ok(runner.run(sid, "set_current_situation", COROLLA_CROSS_TODAY))


# --- registry ---------------------------------------------------------------------------------


def test_definitions_are_anthropic_format() -> None:
    definitions = tool_definitions()
    assert [d["name"] for d in definitions] == list(REGISTRY)
    assert len(definitions) == 9
    for d in definitions:
        assert set(d) == {"name", "description", "input_schema"}
        assert d["input_schema"]["type"] == "object" and d["description"]
    save = next(d for d in definitions if d["name"] == "save_profile")
    assert "national_id" not in save["input_schema"]["properties"]


def test_unknown_tool_and_bad_input(runner: ToolRunner, sid: str) -> None:
    err(runner.run(sid, "nope", {}), "not_found")
    error = err(runner.run(sid, "get_rule", {"topic": "salaries"}), "invalid_input")
    assert error["errors"][0]["field"] == "topic"
    err(runner.run(sid, "save_profile", {"national_id": "123456789"}), "invalid_input")
    assert ok(runner.run(sid, "save_profile", None))["saved"] == {}  # None = empty input


def test_unknown_session(runner: ToolRunner) -> None:
    err(runner.run("nope", "get_rule", {"topic": "budgets"}), "not_found")


def test_runner_never_raises_on_bugs(
    runner: ToolRunner, sid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object) -> dict[str, Any]:
        raise RuntimeError("bug")

    monkeypatch.setitem(REGISTRY, "get_rule", replace(REGISTRY["get_rule"], handler=boom))
    error = err(runner.run(sid, "get_rule", {"topic": "budgets"}), "internal_error")
    assert "bug" not in error["message"]  # no internals leak to the agent


# --- save_profile -----------------------------------------------------------------------------


def test_save_profile_converts_percent_and_derives_group(
    runner: ToolRunner, services: Services, sid: str
) -> None:
    result = ok(runner.run(sid, "save_profile", DEVELOPER))
    assert result["saved"]["pension_percent"] == "6.5"
    assert result["saved"]["group"] == "ב" and result["missing"] == []
    slots = services.store.slots(sid)
    assert slots["pension_pct"].value == "0.065" and slots["study_fund_pct"].value == "0.025"
    assert (slots["group"].value, slots["group"].source) == ("ב", "derived")
    assert slots["occupation"].value == "מפתח/ת תוכנה"
    profile = profile_from_slots(slots)
    assert str(profile.pension_pct) == "0.065" and profile.group == "ב"


def test_stated_group_wins_over_occupation(
    runner: ToolRunner, services: Services, sid: str
) -> None:
    ok(runner.run(sid, "save_profile", {"group": "ג"}))
    result = ok(runner.run(sid, "save_profile", {"occupation_query": "מפתח תוכנה"}))
    assert services.store.slots(sid)["group"].value == "ג"
    assert [w["code"] for w in result["warnings"]] == ["group_mismatch_with_occupation"]


def test_unknown_fields_and_payslip_hint(runner: ToolRunner, services: Services, sid: str):
    result = ok(
        runner.run(
            sid,
            "save_profile",
            {
                "base_salary": 18500,
                "unknown_fields": ["pension_percent", "credit_points", "children_under_23"],
            },
        )
    )
    assert result["unknown"] == ["pension_percent", "credit_points", "children_under_23"]
    assert result["payslip_fields_unknown"] == ["pension_percent", "credit_points"]
    assert services.store.slots(sid)["pension_pct"].state == "unknown"
    assert "pension_percent" not in result["missing"]  # asked, just unknown


def test_occupation_not_found_and_ambiguous(runner: ToolRunner, services: Services, sid: str):
    error = err(
        runner.run(sid, "save_profile", {"occupation_query": "גננות", "base_salary": 9000}),
        "not_found",
    )
    assert error["field"] == "occupation_query"
    assert error["partial_result"]["saved"] == {"base_salary": "9000"}  # the rest was saved
    assert "occupation" not in services.store.slots(sid)
    error = err(runner.run(sid, "save_profile", {"occupation_query": "מנהל"}), "ambiguous")
    assert len(error["candidates"]) > 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_salary", 0),
        ("base_salary", 500_001),
        ("commissions", -1),
        ("pension_percent", 20.5),
        ("study_fund_percent", -1),
        ("credit_points", 2.3),
        ("credit_points", 15.25),
        ("children_under_23", 21),
        ("group", "ה"),
        ("base_salary", 1000.123),
        ("display_name", "312456783"),
    ],
)
def test_save_profile_validation(runner: ToolRunner, sid: str, field: str, value: Any) -> None:
    error = err(runner.run(sid, "save_profile", {field: value}), "invalid_input")
    assert error["errors"][0]["field"] == field


def test_given_and_unknown_conflict(runner: ToolRunner, sid: str) -> None:
    err(runner.run(sid, "save_profile", {"bonus": 0, "unknown_fields": ["bonus"]}), "invalid_input")
    err(runner.run(sid, "save_profile", {"unknown_fields": ["shoe_size"]}), "invalid_input")


# --- lookups ----------------------------------------------------------------------------------


def test_lookup_occupation(runner: ToolRunner, sid: str) -> None:
    result = ok(runner.run(sid, "lookup_occupation", {"query": "מפתחת תוכנה"}))
    assert result["confident"]
    top = result["candidates"][0]
    assert (top["id"], top["group"], top["waiver_allowed"], top["waiver_maintenance"]) == (
        "מפתח/ת תוכנה",
        "ב",
        True,
        "1500",
    )
    err(runner.run(sid, "lookup_occupation", {"query": "גננות"}), "not_found")


def test_lookup_vehicle(runner: ToolRunner, sid: str) -> None:
    result = ok(runner.run(sid, "lookup_vehicle", {"query": "Atto3"}))
    top = result["candidates"][0]
    assert result["confident"] and top["id"] == "CAR-10"
    assert (top["group"], top["drive"], top["value_of_use"], top["default_participation"]) == (
        "ג",
        "electric",
        "3130",
        "300",
    )
    external = ok(
        runner.run(sid, "lookup_vehicle", {"query": "corolla cross", "registration_year": 2023})
    )
    assert not external["confident"] and external["truncated"]
    assert all(not c["in_catalog"] and c["group"] is None for c in external["candidates"])
    err(runner.run(sid, "lookup_vehicle", {"query": "zzzzqqqq"}), "not_found")


# --- current situation ------------------------------------------------------------------------


def test_set_current_situation_catalog_car(runner: ToolRunner, sid: str) -> None:
    ok(runner.run(sid, "save_profile", DEVELOPER))
    result = ok(runner.run(sid, "set_current_situation", COROLLA_CROSS_TODAY))
    assert [w["code"] for w in result["warnings"]] == ["current_car_above_group"]


def test_set_current_situation_external_car(runner: ToolRunner, sid: str) -> None:
    key = ok(
        runner.run(sid, "lookup_vehicle", {"query": "corolla cross", "registration_year": 2023})
    )["candidates"][0]["id"]
    today = {"today": {"kind": "company_car", "car_id": key}}
    assert err(runner.run(sid, "set_current_situation", today), "missing_inputs")["fields"] == [
        "participation"
    ]
    today["today"]["participation"] = 250
    result = ok(runner.run(sid, "set_current_situation", today))
    assert result["today"]["scenario"]["kind"] == "external_car"
    assert [w["code"] for w in result["warnings"]] == ["current_car_not_in_catalog"]


def test_set_current_situation_errors(runner: ToolRunner, sid: str) -> None:
    wrong_year = {"today": {"kind": "company_car", "car_id": "CAR-09", "registration_year": 2023}}
    err(runner.run(sid, "set_current_situation", wrong_year), "not_found")
    err(
        runner.run(
            sid, "set_current_situation", {"today": {"kind": "company_car", "car_id": "CAR-99"}}
        ),
        "not_found",
    )
    err(runner.run(sid, "set_current_situation", {"today": {"kind": "bike"}}), "invalid_input")
    ok(runner.run(sid, "set_current_situation", {"today": {"kind": "maintenance", "amount": 1500}}))
    ok(runner.run(sid, "set_current_situation", {"today": {"kind": "none"}}))


# --- eligibility and compare ------------------------------------------------------------------


def test_check_eligibility(runner: ToolRunner, sid: str) -> None:
    _ready(runner, sid)
    error = err(
        runner.run(sid, "check_eligibility", {"scenario": {"kind": "car", "car_id": "CAR-10"}}),
        "not_eligible",
    )
    assert error["reason"] == "car_group_higher"
    result = ok(
        runner.run(sid, "check_eligibility", {"scenario": {"kind": "car", "car_id": "CAR-06"}})
    )
    assert result["eligibility"]["reason"] == "car_group_within"
    family = err(
        runner.run(sid, "check_eligibility", {"scenario": {"kind": "car", "car_id": "CAR-19"}}),
        "missing_inputs",
    )
    assert family["fields"] == ["children_under_23"]


def test_compare_walkthrough(runner: ToolRunner, services: Services, sid: str) -> None:
    _ready(runner, sid)
    result = ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    comparison = result["comparison"]
    assert comparison["today"]["display"]["net"] == 11000
    assert comparison["alternative"]["display"]["net"] == 13914
    assert comparison["display_diff"] == 2914
    assert result["hypothetical"] is False and result["alternative_kind"] == "alternative:1"
    snapshot = services.store.snapshot(sid)
    assert snapshot["last_comparison"]["comparison"]["display_diff"] == 2914
    assert services.store.events_after(sid)[-1].type == "comparison_ready"


def test_compare_ineligible_is_hypothetical(runner: ToolRunner, sid: str) -> None:
    _ready(runner, sid)
    result = ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}}))
    assert result["hypothetical"] is True
    assert result["eligibility"]["reason"] == "car_group_higher"


def test_compare_partial_and_missing(runner: ToolRunner, sid: str) -> None:
    err(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}), "missing_inputs")
    profile = {**DEVELOPER}
    del profile["pension_percent"]
    ok(runner.run(sid, "save_profile", {**profile, "unknown_fields": ["pension_percent"]}))
    ok(runner.run(sid, "set_current_situation", COROLLA_CROSS_TODAY))
    result = ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    assert result["comparison"]["partial"] is True and result["missing"] == ["pension_percent"]
    assert result["comparison"]["today"]["display"]["net"] is None


def test_compare_missing_lists_unknown_and_pending(runner: ToolRunner, sid: str) -> None:
    ok(
        runner.run(
            sid,
            "save_profile",
            {**DEVELOPER, "credit_points": None, "unknown_fields": ["credit_points"]},
        )
    )
    ok(runner.run(sid, "set_current_situation", COROLLA_CROSS_TODAY))
    ok(runner.run(sid, "ask_representative", {"question": "בונוס?", "blocking_fields": ["bonus"]}))
    error = err(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}), "missing_inputs")
    assert set(error["fields"]) == {"bonus", "credit_points"}
    assert error["pending_rep"] == ["bonus"] and error["unknown"] == ["credit_points"]


def test_alternative_validation(runner: ToolRunner, sid: str) -> None:
    _ready(runner, sid)
    err(runner.run(sid, "compare", {"alternative": {"kind": "car"}}), "not_found")
    err(
        runner.run(sid, "compare", {"alternative": {"kind": "waiver", "car_id": "CAR-06"}}),
        "invalid_input",
    )
    quoted = ok(
        runner.run(sid, "compare", {"alternative": {"kind": "waiver", "maintenance": 1800}})
    )
    assert quoted["comparison"]["alternative"]["metadata"]["maintenance_source"] == (
        "representative"
    )


def test_waiver_maintenance_equal_to_the_occupation_is_the_occupation(
    runner: ToolRunner, sid: str
) -> None:
    # The live walkthrough: the model copied the developer's 1,500 into compare.
    _ready(runner, sid)
    implicit = ok(runner.run(sid, "compare", {"alternative": {"kind": "waiver"}}))
    explicit = ok(
        runner.run(sid, "compare", {"alternative": {"kind": "waiver", "maintenance": 1500}})
    )
    for result in (implicit, explicit):
        alternative = result["comparison"]["alternative"]
        assert alternative["metadata"]["maintenance_source"] == "occupation"
        assert alternative["display"]["net"] == 13914
    assert explicit["comparison"]["display_diff"] == implicit["comparison"]["display_diff"]
    eligibility = ok(
        runner.run(sid, "check_eligibility", {"scenario": {"kind": "waiver", "maintenance": 1500}})
    )
    assert eligibility["eligibility"]["status"] == "eligible"


def test_waiver_maintenance_without_an_occupation_is_the_representatives(
    runner: ToolRunner, sid: str
) -> None:
    # No occupation to match: an explicit amount can only be a representative's quote.
    profile = {k: v for k, v in DEVELOPER.items() if k != "occupation_query"}
    ok(runner.run(sid, "save_profile", {**profile, "group": "ב"}))
    ok(runner.run(sid, "set_current_situation", COROLLA_CROSS_TODAY))
    result = ok(
        runner.run(sid, "compare", {"alternative": {"kind": "waiver", "maintenance": 1500}})
    )
    assert result["comparison"]["alternative"]["metadata"]["maintenance_source"] == (
        "representative"
    )


def test_list_options(runner: ToolRunner, sid: str) -> None:
    err(runner.run(sid, "list_options", {}), "missing_inputs")
    _ready(runner, sid)
    options = ok(runner.run(sid, "list_options", {}))["options"]
    assert len(options) == 20  # 20 catalog cars minus today's + the waiver
    assert options[0]["eligibility"]["status"] == "eligible"


# --- rules and representative -----------------------------------------------------------------


@pytest.mark.parametrize(
    "topic",
    [
        "budgets",
        "choose_from",
        "unused_budget",
        "electric_bonus",
        "family_track",
        "waiver",
        "participation",
        "value_of_use",
        "tax_tables_year",
    ],
)
def test_get_rule(runner: ToolRunner, sid: str, topic: str) -> None:
    result = ok(runner.run(sid, "get_rule", {"topic": topic}))
    assert result["topic"] == topic and result["value"] is not None


def test_get_rule_values(runner: ToolRunner, sid: str) -> None:
    budgets = ok(runner.run(sid, "get_rule", {"topic": "budgets"}))["value"]["budgets"]
    assert budgets["ב"] == "3700"
    electric = ok(runner.run(sid, "get_rule", {"topic": "electric_bonus"}))
    assert electric["value"]["net_bonus"] == "250" and "250" in electric["note"]
    assert ok(runner.run(sid, "get_rule", {"topic": "tax_tables_year"}))["value"] == 2025


def test_ask_representative(runner: ToolRunner, services: Services, sid: str) -> None:
    _ready(runner, sid)
    ok(runner.run(sid, "save_profile", {"display_name": "נועה"}))
    ok(runner.run(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-06"}}))
    result = ok(
        runner.run(
            sid,
            "ask_representative",
            {
                "question": "מה אחוז ההפרשה לפנסיה?",
                "blocking_fields": ["pension_percent"],
                "quick_answers": [{"id": "six", "label": "6%", "values": {"pension_percent": 6}}],
            },
        )
    )
    context = result["context"]
    assert context["display_name"] == "נועה" and context["group"] == "ב"
    assert context["current_situation"] == "COROLLA CROSS"
    assert context["requested_alternative"]["car_id"] == "CAR-06"
    assert services.store.slots(sid)["pension_pct"].state == "pending_rep"
    assert services.store.session_status(sid) == "waiting_for_rep"
    ticket = services.store.ticket(result["ticket_id"])
    assert ticket.blocking_fields == ["pension_percent"]


def test_ask_representative_validation(runner: ToolRunner, sid: str) -> None:
    err(
        runner.run(sid, "ask_representative", {"question": "?", "blocking_fields": ["shoe"]}),
        "invalid_input",
    )
    bad_quick = {
        "question": "?",
        "blocking_fields": ["pension_percent"],
        "quick_answers": [{"id": "a", "label": "x", "values": {"pension_percent": 50}}],
    }
    err(runner.run(sid, "ask_representative", bad_quick), "invalid_input")


# --- additive fields for the agent ------------------------------------------------------------


def test_save_profile_reports_group_and_budget(runner: ToolRunner, sid: str) -> None:
    result = ok(runner.run(sid, "save_profile", DEVELOPER))
    assert (result["group"], result["group_source"], result["group_budget"]) == (
        "ב",
        "derived",
        "3700",
    )
    stated = ok(runner.run(sid, "save_profile", {"group": "ג"}))
    assert (stated["group"], stated["group_source"], stated["group_budget"]) == (
        "ג",
        "employee",
        "4500",
    )


def test_save_profile_without_group(runner: ToolRunner, sid: str) -> None:
    result = ok(runner.run(sid, "save_profile", {"base_salary": 9000}))
    assert result["group"] is None and result["group_budget"] is None
    assert result["group_source"] is None


def test_list_options_carries_catalog_facts(runner: ToolRunner, sid: str) -> None:
    _ready(runner, sid)
    options = ok(runner.run(sid, "list_options", {}))["options"]
    by_car = {o["scenario"].get("car_id"): o for o in options}
    atto = by_car["CAR-10"]
    assert (atto["commercial_name"], atto["group"], atto["drive"]) == ("ATTO 3", "ג", "electric")
    assert by_car["CAR-19"]["group"] == "משפחתי"
    waiver = by_car[None]
    assert (waiver["commercial_name"], waiver["group"], waiver["drive"]) == (None, None, None)
    # Existing fields are unchanged.
    assert {"scenario", "eligibility", "comparison", "participation_source", "pending_rep"} <= set(
        atto
    )

"""POST /api/sessions/{id}/payslip/confirm: the accepted fields become profile values (source
payslip, or employee when edited), the comparison on screen is recomputed by the server, and the
agent is told the confirmed values as data. Invariants 3 (never occupation, group or a rep's
field), 4 (a representative's value wins) and 5 (only confirmed values are guard sources)."""

import json
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from payslip_files import pdf

from compass.agent.factory import build_claude_runner
from compass.agent.guard import allowed_for_session, check_text
from compass.agent.llm import ScriptedClient, text_response
from compass.api import Settings, create_app
from compass.payslip.extractor import ScriptedExtractor
from compass.payslip.service import PayslipService
from compass.state import SlotUpdate
from compass.tools.handlers import refresh_after_profile_change

NOA = {  # E-001, as the employee said it
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
READ = {  # what the payslip says
    "base_salary": {"value": 20250, "confidence": "high"},
    "bonus": {"value": 777, "confidence": "medium"},
    "pension_percent": {"value": 6.5, "confidence": "high"},
    "credit_points": {"value": 2.25, "confidence": "low"},
    "car_benefit_value": {"value": None, "confidence": "low"},
}


class App:
    def __init__(self, client: TestClient, sid: str, llm: ScriptedClient) -> None:
        self.client, self.sid, self.llm = client, sid, llm
        self.app: Any = client.app
        self.services = self.app.state.services
        self.store = self.services.store

    def run(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.app.state.runner.run(self.sid, tool, payload)
        assert result["ok"] is True, result
        return result

    def upload(self) -> Any:
        return self.client.post(
            f"/api/sessions/{self.sid}/payslip",
            content=pdf(),
            headers={"Content-Type": "application/pdf"},
        )

    def confirm(self, fields: dict[str, Any]) -> Any:
        url = f"/api/sessions/{self.sid}/payslip/confirm"
        return self.client.post(url, json={"fields": fields})

    def comparisons(self) -> list[Any]:
        return [e for e in self.store.events_after(self.sid) if e.type == "comparison_ready"]


@pytest.fixture
def make(tmp_path: Path) -> Callable[..., App]:
    clients: list[TestClient] = []

    def build(read: dict[str, Any] = READ, **overrides: Any) -> App:
        llm = ScriptedClient([text_response("קיבלתי.")] * 5)

        def factory(settings: Settings, services: Any, runner: Any) -> Any:
            return build_claude_runner(
                settings, services, llm=llm, tool_runner=runner, background=False
            )

        values: dict[str, Any] = {"app_db": tmp_path / "app.db", "payslip": True}
        values.update(overrides)
        app = create_app(Settings(**values), agent_factory=factory)
        store = app.state.services.store
        app.state.payslip = PayslipService(
            store, ScriptedExtractor([read], repeat_last=True), count_spend=False
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        sid = client.post("/api/sessions").json()["id"]
        return App(client, sid, llm)

    yield build  # type: ignore[misc]
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def noa(make: Callable[..., App]) -> Iterator[App]:
    app = make()
    app.run("save_profile", NOA)
    app.run("set_current_situation", TODAY)
    app.run("compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})
    yield app


def test_unchanged_is_payslip_edited_is_employee_left_out_is_rejected(noa: App) -> None:
    assert noa.upload().status_code == 201
    response = noa.confirm({"base_salary": "20,250", "pension_percent": 7})  # bonus left out
    assert response.status_code == 200
    assert response.json()["applied"] == {
        "base_salary": {"value": "20250", "source": "payslip"},
        "pension_percent": {"value": "7", "source": "employee"},
    }
    slots = noa.store.slots(noa.sid)
    assert (slots["base_salary"].value, slots["base_salary"].source) == ("20250", "payslip")
    assert (slots["pension_pct"].value, slots["pension_pct"].source) == ("0.07", "employee")
    assert slots["bonus"].value == "0"  # rejected: the employee's earlier value stays


def test_the_server_recomputes_the_comparison_with_the_payslip_chip(noa: App) -> None:
    before = noa.comparisons()
    noa.upload()
    noa.confirm({"base_salary": 20250})
    after = noa.comparisons()
    assert len(after) == len(before) + 1
    latest = after[-1].payload
    assert latest["origin"] == "server" and latest["payslip_seq"] > 0
    assert latest["alternative"] == before[-1].payload["alternative"]
    chips = {i["id"]: i["source"] for i in latest["view"]["inputs"]}
    assert chips["base_salary"] == "payslip"
    assert chips["pension_percent"] == "employee_input"
    # the same numbers compare gives now: the existing calculation path, no new one
    noa.run("compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})
    again = noa.comparisons()[-1].payload
    nets = ("today_net", "alternative_net")
    assert [again["view"][k] for k in nets] == [latest["view"][k] for k in nets]
    assert latest["view"]["today_net"] != before[-1].payload["view"]["today_net"]  # the new pay


def test_the_candidate_is_gone_after_confirming(noa: App) -> None:
    noa.upload()
    noa.confirm({})  # everything rejected: still closes the candidate
    response = noa.confirm({"base_salary": 20250})
    assert response.status_code == 409
    assert response.json()["detail"] == "payslip_nothing_pending"


def test_nothing_to_confirm_before_an_upload(noa: App) -> None:
    assert noa.confirm({"base_salary": 1}).json()["detail"] == "payslip_nothing_pending"


@pytest.mark.parametrize(
    "field",
    ["occupation", "group", "group_exception", "current_car", "display_name", "children_under_23"],
)
def test_a_payslip_never_sets_occupation_group_or_rep_fields(noa: App, field: str) -> None:
    """Invariant 3."""
    noa.upload()
    response = noa.confirm({field: "A", "base_salary": 20250})
    assert response.status_code == 422
    assert response.json()["detail"] == "payslip_field_not_allowed"
    assert response.json()["errors"][0]["field"] == field
    slots = noa.store.slots(noa.sid)
    assert slots["base_salary"].value == "18500"  # nothing applied from a refused request
    assert slots["group"].source == "derived"


def test_a_representatives_value_is_never_overwritten(noa: App) -> None:
    """Invariant 4."""
    noa.store.update_slots(
        noa.sid, {"base_salary": SlotUpdate(value="19000", source="representative")}
    )
    noa.upload()
    body = noa.confirm({"base_salary": 20250, "pension_percent": 6.5}).json()
    assert body["kept_representative"] == ["base_salary"]
    assert set(body["applied"]) == {"pension_percent"}
    slot = noa.store.slots(noa.sid)["base_salary"]
    assert (slot.value, slot.source) == ("19000", "representative")


def test_a_field_waiting_for_a_representative_is_left_alone(noa: App) -> None:
    noa.store.update_slots(
        noa.sid, {"bonus": SlotUpdate(state="pending_rep", source="representative")}
    )
    noa.upload()
    body = noa.confirm({"bonus": 777}).json()
    assert body["waiting_for_rep"] == ["bonus"] and body["applied"] == {}


def test_an_invalid_edit_is_refused_and_nothing_applied(noa: App) -> None:
    noa.upload()
    response = noa.confirm({"base_salary": 20250, "credit_points": "2.3"})
    assert response.status_code == 422 and response.json()["detail"] == "payslip_invalid_value"
    assert response.json()["errors"][0]["field"] == "credit_points"
    assert noa.store.slots(noa.sid)["base_salary"].value == "18500"


def test_the_agent_is_told_only_the_confirmed_values_as_data(noa: App) -> None:
    """Invariant 1: the file and the unconfirmed values (bonus 777) never reach the model."""
    noa.upload()
    noa.confirm({"base_salary": 20250})
    [call] = noa.llm.calls
    last = call.messages[-1]["content"][0]["text"]
    assert last.startswith('<payslip_notification label="לפי התלוש">')
    data = json.loads(last.split("\n", 1)[1].rsplit("\n", 1)[0])
    assert data["confirmed_values"] == {"base_salary": {"value": "20250", "source": "payslip"}}
    assert data["server_comparisons"]  # the recomputed comparison, as compare returns it
    everything = json.dumps([m for c in noa.llm.calls for m in c.messages], ensure_ascii=False)
    assert "777" not in everything and "%PDF" not in everything


def test_the_guard_accepts_confirmed_values_never_pending_ones(noa: App) -> None:
    """Invariant 5."""
    noa.upload()
    pending = allowed_for_session(noa.store, noa.sid)
    assert check_text("לפי התלוש השכר הוא 20,250 ₪", pending).violations == ["20,250"]
    noa.confirm({"base_salary": 20250})
    confirmed = allowed_for_session(noa.store, noa.sid)
    verdict = check_text("לפי התלוש השכר הוא 20,250 ₪", confirmed)
    assert verdict.passed and verdict.sources["20,250"] == "payslip"
    assert check_text("והבונוס 777 ₪", confirmed).violations == ["777"]  # never confirmed


def test_the_car_hint_only_on_a_unique_match(make: Callable[..., App]) -> None:
    app = make()
    catalog = app.services.ctx.catalog.values()
    counts: dict[Decimal, int] = {}
    for car in catalog:
        counts[Decimal(car.value_of_use)] = counts.get(Decimal(car.value_of_use), 0) + 1
    unique = next(c for c in catalog if counts[Decimal(c.value_of_use)] == 1)
    app.upload()
    body = app.confirm({"car_benefit_value": str(unique.value_of_use)}).json()
    assert body["car_hint"] == {"car_id": unique.id, "commercial_name": unique.commercial_name}
    assert app.store.slots(app.sid).get("base_salary") is None  # a hint, never a slot
    data = app.llm.calls[-1].messages[-1]["content"][0]["text"]
    assert unique.id in data  # the agent may ask; it never assumes

    app.upload()
    body = app.confirm({"car_benefit_value": "12345.67"}).json()  # no car has it
    assert body["car_hint"] is None


def test_confirming_off_is_404(make: Callable[..., App]) -> None:
    app = make(payslip=False)
    assert app.confirm({"base_salary": 1}).status_code == 404


def test_refresh_without_a_comparison_is_nothing(make: Callable[..., App]) -> None:
    app = make()
    assert refresh_after_profile_change(app.services, app.sid) == []


def test_one_upload_at_a_time_per_session(make: Callable[..., App]) -> None:
    """A second upload while the first is still being read: 409, and only one extraction."""
    seen: list[int] = []
    app: App | None = None

    def during_the_first(data: bytes, media_type: str) -> None:
        assert app is not None
        second = app.upload()
        seen.append(second.status_code)
        assert second.json()["detail"] == "payslip_in_progress"

    app = make()
    extractor = ScriptedExtractor([READ], repeat_last=True, on_call=during_the_first)
    app.app.state.payslip = PayslipService(app.store, extractor, count_spend=False)
    first = app.upload()
    assert first.status_code == 201 and seen == [409]
    assert len(extractor.calls) == 1


# --- the amounts layout: the percent is derived by the server, and the agent hears what is missing


AMOUNTS = {  # "כלל פנסיה 1,200 / שכר לקופ"ג 20,000", "כלל השתלמות 500 / שכר לקה"ל 20,000"
    "base_salary": {"value": 14000, "confidence": "high"},
    "commissions": {"value": None, "confidence": "high"},
    "bonus": {"value": None, "confidence": "high"},
    "employee_pension_amount": {"value": 1200, "confidence": "high"},
    "pension_wage": {"value": 20000, "confidence": "high"},
    "employee_study_fund_amount": {"value": 500, "confidence": "high"},
    "study_fund_wage": {"value": 20000, "confidence": "high"},
    "credit_points": {"value": 2.75, "confidence": "high"},
}


def told(app: App) -> dict[str, Any]:
    text = app.llm.calls[-1].messages[-1]["content"][0]["text"]
    return json.loads(text.split("\n", 1)[1].rsplit("\n", 1)[0])  # type: ignore[no-any-return]


def test_a_derived_percent_confirmed_unchanged_is_the_payslips(make: Callable[..., App]) -> None:
    app = make(AMOUNTS)
    app.run("save_profile", {"occupation_query": "מנהלת מוצר"})
    app.upload()
    body = app.confirm(
        {"base_salary": "14000", "pension_percent": "6", "study_fund_percent": "2.5"}
    )
    assert body.json()["applied"] == {
        "base_salary": {"value": "14000", "source": "payslip"},
        "pension_percent": {"value": "6", "source": "payslip"},
        "study_fund_percent": {"value": "2.5", "source": "payslip"},
    }
    slots = app.store.slots(app.sid)
    assert (slots["pension_pct"].value, slots["pension_pct"].source) == ("0.06", "payslip")
    assert (slots["study_fund_pct"].value, slots["study_fund_pct"].source) == ("0.025", "payslip")


def test_an_edited_derived_percent_is_the_employees(make: Callable[..., App]) -> None:
    app = make(AMOUNTS)
    app.run("save_profile", {"occupation_query": "מנהלת מוצר"})
    app.upload()
    body = app.confirm({"pension_percent": "6.5"}).json()
    assert body["applied"]["pension_percent"] == {"value": "6.5", "source": "employee"}


def test_a_printed_and_a_derived_percent_that_differ_are_both_the_payslips(
    make: Callable[..., App],
) -> None:
    read = {**AMOUNTS, "pension_percent": {"value": 6.5, "confidence": "high"}}
    app = make(read)
    app.run("save_profile", {"occupation_query": "מנהלת מוצר"})
    fields = app.upload().json()["fields"]
    assert fields["pension_percent"]["value"] == "6.5"
    assert fields["pension_percent_derived"]["value"] == "6"
    assert app.confirm({"pension_percent": "6"}).json()["applied"]["pension_percent"]["source"] == (
        "payslip"
    )
    app.upload()
    assert app.confirm({"pension_percent": "6.5"}).json()["applied"]["pension_percent"][
        "source"
    ] == ("payslip")


def test_the_agent_hears_which_fields_the_payslip_did_not_give(make: Callable[..., App]) -> None:
    """Why pension was never filled in the incident: the payslip printed amounts, the schema
    asked for percents. Now the model reads the amounts and the server derives; and whatever is
    still missing is listed, so the agent can say what happened instead of "no access"."""
    read = {**AMOUNTS, "credit_points": {"value": 2.3, "confidence": "low"}}  # printed, not valid
    app = make(read)
    app.run("save_profile", {"occupation_query": "מנהלת מוצר"})
    app.upload()
    body = app.confirm({"base_salary": "14000", "study_fund_percent": "2.5"}).json()
    # commissions and bonus: not on the payslip; credit points: read but not a valid value;
    # pension: read and derived but left out of the confirmation by the employee
    assert body["not_in_payslip"] == ["commissions", "bonus"]
    assert body["unreadable"] == ["credit_points"]
    assert body["removed_by_employee"] == ["pension_percent"]
    data = told(app)
    assert data["not_in_payslip"] == ["commissions", "bonus"]
    assert data["unreadable"] == ["credit_points"]
    assert data["removed_by_employee"] == ["pension_percent"]


def test_a_field_the_employee_answered_is_not_listed_as_missing(make: Callable[..., App]) -> None:
    """Commissions and bonus the payslip does not show: one tap on "אין" sends 0, which is the
    employee's own answer (source employee), and the agent is not told they are missing."""
    app = make(AMOUNTS)
    app.run("save_profile", {"occupation_query": "מנהלת מוצר"})
    app.upload()
    body = app.confirm(
        {"base_salary": "14000", "commissions": "0", "bonus": "0", "pension_percent": "6"}
    ).json()
    assert body["applied"]["commissions"] == {"value": "0", "source": "employee"}
    assert body["applied"]["bonus"] == {"value": "0", "source": "employee"}
    assert "commissions" not in body["not_in_payslip"] and "bonus" not in body["not_in_payslip"]
    assert told(app)["confirmed_values"]["bonus"]["source"] == "employee"

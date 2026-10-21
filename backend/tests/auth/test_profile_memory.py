"""Remembered details (COMPASS_PROFILE_MEMORY=1, with accounts), Stage 1: the saved profile, the
offer of it in a new conversation (a pending candidate), apply / dismiss / delete, and the
invariants: nothing is used silently, anything new in the conversation wins, only personal facts
are saved, the group is never stored, the profile is private, and with the flag off nothing
changes."""

import json
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from authkit import EMAILS, PASSWORD
from fastapi.testclient import TestClient
from payslip_files import pdf

from compass.agent.factory import build_claude_runner
from compass.agent.guard import allowed_for_session, check_text
from compass.agent.llm import ScriptedClient, text_response
from compass.agent.transcript import build_model_messages
from compass.api import Settings, create_app
from compass.api.redact import public_payload
from compass.payslip.extractor import ScriptedExtractor
from compass.payslip.service import PayslipService
from compass.profile_memory import build_offer
from compass.state import Store

NOA = {  # E-001, as the employee said it
    "occupation_query": "מנהלת מוצר",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6,
    "study_fund_percent": 2.5,
    "credit_points": 2.75,
}
TODAY = {"today": {"kind": "company_car", "car_id": "CAR-09"}}
OCCUPATION = "מנהל/ת מוצר"  # as the catalog spells it: read from the saved profile in the tests
READ = {  # what a payslip says
    "base_salary": {"value": 20250, "confidence": "high"},
    "pension_percent": {"value": 6.5, "confidence": "high"},
    "car_benefit_value": {"value": None, "confidence": "low"},
}


class World:
    def __init__(self, client: TestClient, llm: ScriptedClient) -> None:
        self.client, self.llm = client, llm
        self.app: Any = client.app
        self.services = self.app.state.services
        self.store: Store = self.services.store
        self._tokens: dict[str, dict[str, str]] = {}

    def who(self, key: str) -> dict[str, str]:
        if key not in self._tokens:
            reply = self.client.post(
                "/api/auth/login", json={"email": EMAILS[key], "password": PASSWORD}
            )
            assert reply.status_code == 200, reply.text
            self._tokens[key] = {"Authorization": f"Bearer {reply.json()['token']}"}
        return self._tokens[key]

    def user_id(self, key: str = "employee") -> str:
        user = self.app.state.accounts.user_by_email(EMAILS[key])
        return str(user.id)

    def new(self, key: str = "employee") -> str:
        return str(self.client.post("/api/sessions", headers=self.who(key)).json()["id"])

    def tool(self, sid: str, name: str, body: dict[str, Any], key: str = "employee") -> Any:
        reply = self.client.post(
            f"/api/sessions/{sid}/tools/{name}", headers=self.who(key), json=body
        )
        assert reply.status_code == 200, reply.text
        return reply.json()

    def events(self, sid: str, *types: str) -> list[Any]:
        return [e for e in self.store.events_after(sid) if not types or e.type in types]

    def profile(self, key: str = "employee") -> dict[str, Any]:
        found = self.store.profile(self.user_id(key))
        return {} if found is None else found["fields"]

    def apply(self, sid: str, fields: list[dict[str, Any]], key: str = "employee") -> Any:
        return self.client.post(
            f"/api/sessions/{sid}/profile/apply", headers=self.who(key), json={"fields": fields}
        )

    def dismiss(self, sid: str, key: str = "employee") -> Any:
        return self.client.post(f"/api/sessions/{sid}/profile/dismiss", headers=self.who(key))

    def offer(self, sid: str) -> dict[str, Any]:
        (event,) = self.events(sid, "profile_offer")
        return dict(event.payload)

    def keep_all(self, sid: str) -> Any:
        names = [f["name"] for f in self.offer(sid)["fields"]]
        return self.apply(sid, [{"name": n, "action": "keep"} for n in names])

    def slot(self, sid: str, name: str) -> Any:
        return self.store.slots(sid).get(name)


@pytest.fixture
def make(auth_settings: Settings, tmp_path: Path) -> Iterator[Callable[..., World]]:
    clients: list[TestClient] = []

    def build(**overrides: Any) -> World:
        llm = ScriptedClient([text_response("קיבלתי.")] * 8)

        def factory(settings: Settings, services: Any, runner: Any) -> Any:
            return build_claude_runner(
                settings, services, llm=llm, tool_runner=runner, background=False
            )

        values = {"profile_memory": True, "dev_tools": True, "payslip": True} | overrides
        app = create_app(replace(auth_settings, **values), agent_factory=factory)
        app.state.payslip = PayslipService(
            app.state.services.store, ScriptedExtractor([READ], repeat_last=True), count_spend=False
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return World(client, llm)

    yield build
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def world(make: Callable[..., World]) -> World:
    return make()


def saved_world(world: World) -> World:
    """The employee told the bot their details and car in one conversation."""
    first = world.new()
    world.tool(first, "save_profile", NOA)
    world.tool(first, "set_current_situation", TODAY)
    return world


# --- saving: only what is confirmed or settled ---------------------------------------------------


def test_employee_stated_details_are_saved_with_their_source_and_time(world: World) -> None:
    sid = world.new()
    world.tool(sid, "save_profile", NOA)
    fields = world.profile()
    assert set(fields) == {
        "occupation",
        "base_salary",
        "commissions",
        "bonus",
        "pension_percent",
        "study_fund_percent",
        "credit_points",
    }
    assert fields["base_salary"]["value"] == "18500"
    assert fields["pension_percent"]["value"] == "0.06"  # the slot's own unit, a fraction
    assert {f["source"] for f in fields.values()} == {"employee"}
    assert all(f["from_session"] == sid and f["saved_at"] for f in fields.values())
    assert "group" not in fields  # the group is derived again, never stored


def test_a_confirmed_payslip_value_is_saved_as_payslip(world: World) -> None:
    sid = world.new()
    world.tool(sid, "save_profile", NOA)
    reply = world.client.post(
        f"/api/sessions/{sid}/payslip",
        content=pdf(),
        headers={**world.who("employee"), "Content-Type": "application/pdf"},
    )
    assert reply.status_code == 201, reply.text
    # the candidate alone saves nothing
    assert world.profile()["base_salary"]["source"] == "employee"
    confirmed = world.client.post(
        f"/api/sessions/{sid}/payslip/confirm",
        headers=world.who("employee"),
        json={"fields": {"base_salary": 20250, "pension_percent": 6.5}},
    )
    assert confirmed.status_code == 200, confirmed.text
    fields = world.profile()
    assert (fields["base_salary"]["value"], fields["base_salary"]["source"]) == ("20250", "payslip")
    assert fields["pension_percent"]["source"] == "payslip"
    assert fields["bonus"]["source"] == "employee"  # what the payslip did not touch


def test_a_representative_settled_value_is_saved_as_representative(world: World) -> None:
    sid = world.new()
    world.client.post(
        f"/api/sessions/{sid}/messages", headers=world.who("employee"), json={"text": "שלום"}
    )
    world.tool(sid, "save_profile", {"occupation_query": "מנהלת מוצר"})
    asked = world.tool(
        sid, "ask_representative", {"question": "מה השכר?", "blocking_fields": ["base_salary"]}
    )
    assert asked["ok"], asked
    assert "base_salary" not in world.profile()  # pending: never saved
    ticket = world.store.tickets("open", sid)[0]
    answer = world.client.post(
        f"/api/tickets/{ticket.id}/answer",
        headers=world.who("rep"),
        json={"values": {"base_salary": 21000}},
    )
    assert answer.status_code == 200, answer.text
    field = world.profile()["base_salary"]
    assert (field["value"], field["source"]) == ("21000", "representative")


def test_pending_unknown_derived_and_default_values_are_never_saved(world: World) -> None:
    sid = world.new()
    world.tool(sid, "save_profile", {"occupation_query": "מנהלת מוצר", "unknown_fields": ["bonus"]})
    fields = world.profile()
    assert "bonus" not in fields  # "לא יודע" saves nothing (and removes nothing)
    assert "group" not in fields  # derived
    # today's car with the catalog's default participation: the car, not the participation
    world.tool(sid, "set_current_situation", TODAY)
    assert world.profile()["today_car"]["value"] == "CAR-09"
    assert "today_participation" not in world.profile()
    saved = {k: v for k, v in fields.items() if k != "occupation"}
    assert saved == {}
    # a car outside the catalog, a maintenance amount and "no car" are not saved
    other = world.new()
    world.tool(other, "set_current_situation", {"today": {"kind": "none"}})
    assert world.profile()["today_car"]["from_session"] == sid  # unchanged by the other one


def test_a_value_the_employee_does_not_know_removes_nothing(world: World) -> None:
    sid = world.new()
    world.tool(sid, "save_profile", {"base_salary": 18500})
    other = world.new()
    world.tool(other, "save_profile", {"unknown_fields": ["base_salary"]})
    assert world.profile()["base_salary"]["value"] == "18500"


def test_rep_answers_about_participation_or_a_group_exception_are_never_saved(
    world: World,
) -> None:
    sid = world.new()
    world.client.post(
        f"/api/sessions/{sid}/messages",
        headers=world.who("employee"),
        json={"text": "ומה עם ATTO 3?"},
    )
    world.tool(sid, "save_profile", {"occupation_query": "מנהלת מוצר", "base_salary": 18500})
    world.tool(
        sid,
        "ask_representative",
        {
            "question": "?",
            "blocking_fields": ["alternative_participation:CAR-10", "current_participation"],
        },
    )
    ticket = world.store.tickets("open", sid)[0]
    answered = world.client.post(
        f"/api/tickets/{ticket.id}/answer",
        headers=world.who("rep"),
        json={"values": {"alternative_participation:CAR-10": 350, "current_participation": 300}},
    )
    assert answered.status_code == 200, answered.text
    assert set(world.profile()) == {"occupation", "base_salary"}
    assert world.slot(sid, "group").source == "derived"


# --- the offer: a pending candidate, once per new conversation ------------------------------------


def test_a_new_conversation_gets_one_offer_with_the_original_sources(world: World) -> None:
    saved_world(world)
    sid = world.new()
    (event,) = world.events(sid, "profile_offer")
    offer = event.payload
    by_name = {f["name"]: f for f in offer["fields"]}
    assert list(by_name) == [
        "occupation",
        "base_salary",
        "commissions",
        "bonus",
        "pension_percent",
        "study_fund_percent",
        "credit_points",
        "today_car",
    ]
    assert by_name["base_salary"]["value"] == "18500"
    assert by_name["base_salary"]["label"] == "שכר בסיס"
    assert by_name["pension_percent"]["value"] == "6"  # the employee's unit, not the fraction
    assert by_name["today_car"]["value"] == "CAR-09" and by_name["today_car"]["display"]
    assert {f["source"] for f in offer["fields"]} == {"employee"}
    assert by_name["base_salary"]["source_label"] == "לפי דבריך"
    assert offer["age_days"] == 0 and offer["stale"] is False and offer["stale_note"] is None
    # once: reading the session again, or resuming it, does not make another
    world.client.get(f"/api/sessions/{sid}", headers=world.who("employee"))
    assert len(world.events(sid, "profile_offer")) == 1


def test_no_profile_no_offer_and_each_new_conversation_gets_its_own(world: World) -> None:
    empty = world.new()
    assert world.events(empty, "profile_offer") == []  # nothing is saved yet
    saved_world(world)
    two = world.new()
    assert len(world.events(two, "profile_offer")) == 1
    # an empty conversation is replaced by the next one, which is offered the profile as well
    three = world.new()
    assert len(world.events(three, "profile_offer")) == 1
    assert world.events(three, "profile_offer")[0].payload == world.offer(three)


def test_the_offer_is_the_owners_and_reaches_the_public_stream_in_full(world: World) -> None:
    saved_world(world)
    sid = world.new()
    event = world.events(sid, "profile_offer")[0]
    assert public_payload("profile_offer", event.payload) == event.payload
    other = world.new("other")
    assert world.events(other, "profile_offer") == []  # someone else's profile is not mine


def test_an_offer_alone_leaves_the_conversation_empty(world: World) -> None:
    saved_world(world)
    sid = world.new()
    token = world.who("employee")["Authorization"].removeprefix("Bearer ")
    from compass.auth.codes import hash_secret

    assert sid in world.store.empty_session_ids(world.user_id(), hash_secret(token))
    listed = world.client.get("/api/conversations", headers=world.who("employee")).json()
    assert sid not in [c["id"] for c in listed]
    assert world.keep_all(sid).status_code == 200  # applying is activity
    assert sid not in world.store.empty_session_ids(world.user_id(), hash_secret(token))
    listed = world.client.get("/api/conversations", headers=world.who("employee")).json()
    assert sid in [c["id"] for c in listed]


def test_an_offered_value_is_not_in_the_agent_input_and_not_a_guard_source(world: World) -> None:
    saved_world(world)
    sid = world.new()
    rendered = json.dumps(build_model_messages(world.store.messages(sid)), ensure_ascii=False)
    assert "18500" not in rendered and "18,500" not in rendered and "CAR-09" not in rendered
    assert world.store.slots(sid) == {}  # nothing applied
    # a draft quoting an offered value is rejected until the employee applies it
    draft = "שכר הבסיס שלך הוא 18,500 ₪."
    assert not check_text(draft, allowed_for_session(world.store, sid)).passed
    assert world.keep_all(sid).status_code == 200
    verdict = check_text(draft, allowed_for_session(world.store, sid))
    assert verdict.passed and verdict.sources["18,500"] == "previous"


# --- apply: keep / edit / drop through the slot path ---------------------------------------------


def test_keep_edit_and_drop_go_through_the_slot_path_with_the_right_sources(world: World) -> None:
    saved_world(world)
    sid = world.new()
    reply = world.apply(
        sid,
        [
            {"name": "occupation", "action": "keep"},
            {"name": "base_salary", "action": "edit", "value": 19000},
            {"name": "bonus", "action": "drop"},
            {"name": "pension_percent", "action": "keep"},
            {"name": "today_car", "action": "keep"},
        ],
    )
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["values"]["base_salary"] == {"value": "19000", "source": "employee"}
    assert body["values"]["occupation"]["source"] == "previous"
    assert body["dropped"] == ["bonus"] and body["kept_current"] == []
    slots = world.store.slots(sid)
    first_saved = world.offer(sid)["fields"][0]["saved_at"]
    assert (slots["occupation"].source, slots["occupation"].previous_from) == (
        "previous",
        first_saved,
    )
    assert slots["base_salary"].source == "employee" and slots["base_salary"].value == "19000"
    assert slots["base_salary"].previous_from is None
    assert slots["pension_pct"].source == "previous" and slots["pension_pct"].value == "0.06"
    assert "bonus" not in slots  # dropped: skipped
    assert "commissions" not in slots  # left out: not used
    assert slots["group"].source == "derived"  # re-derived from the occupation, never stored
    today = world.store.scenarios(sid)["today"]
    assert today["source"] == "previous" and today["previous_from"]
    # the events: the slot path's profile_updated, then profile_applied
    assert [e.type for e in world.events(sid, "profile_updated", "profile_applied")] == [
        "profile_updated",
        "profile_applied",
    ]
    updated = world.events(sid, "profile_updated")[0].payload["fields"]
    assert updated["occupation"]["previous_from"] == first_saved


def test_the_view_shows_the_previous_chip_and_its_date(world: World) -> None:
    saved_world(world)
    sid = world.new()
    assert world.keep_all(sid).status_code == 200
    world.tool(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})
    view = world.events(sid, "comparison_ready")[-1].payload["view"]
    inputs = {i["id"]: i for i in view["inputs"]}
    assert inputs["base_salary"]["source"] == "previous" and inputs["base_salary"]["previous_from"]
    assert inputs["today_car"]["source"] == "previous" and inputs["today_car"]["previous_from"]
    assert inputs["today_participation"]["source"] == "catalog_default"
    assert "previous_from" not in inputs["group"]  # only a previous value has the date


def test_the_agent_is_told_the_confirmed_values_as_data(world: World) -> None:
    saved_world(world)
    sid = world.new()
    assert world.keep_all(sid).status_code == 200
    sent = json.dumps(world.llm.calls[-1].messages, ensure_ascii=False)
    assert "profile_notification" in sent and "משיחה קודמת" in sent
    assert '\\"source\\": \\"previous\\"' in sent


def test_apply_refuses_what_was_not_offered_and_what_is_invalid(world: World) -> None:
    saved_world(world)
    sid = world.new()
    nothing = world.apply(sid, [{"name": "group", "action": "keep"}])
    assert nothing.status_code == 422 and nothing.json()["detail"] == "profile_field_not_allowed"
    twice = world.apply(
        sid, [{"name": "bonus", "action": "keep"}, {"name": "bonus", "action": "drop"}]
    )
    assert twice.status_code == 422
    bad = world.apply(sid, [{"name": "base_salary", "action": "edit", "value": "abc"}])
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "base_salary"
    no_value = world.apply(sid, [{"name": "base_salary", "action": "edit"}])
    assert no_value.status_code == 422
    assert world.store.slots(sid) == {}  # a refusal changes nothing
    assert world.apply(sid, [{"name": "bonus", "action": "wipe"}]).status_code == 422
    assert world.keep_all(sid).status_code == 200
    again = world.keep_all(sid)
    assert again.status_code == 409 and again.json()["detail"] == "profile_nothing_pending"


# --- precedence, in both directions ---------------------------------------------------------------


def test_what_was_said_in_this_conversation_wins_over_a_kept_value(world: World) -> None:
    saved_world(world)
    sid = world.new()
    world.tool(sid, "save_profile", {"base_salary": 25000})  # said first, in this conversation
    body = world.apply(
        sid,
        [
            {"name": "base_salary", "action": "keep"},
            {"name": "bonus", "action": "keep"},
        ],
    ).json()
    assert body["kept_current"] == ["base_salary"]
    assert world.slot(sid, "base_salary").value == "25000"
    assert world.slot(sid, "base_salary").source == "employee"
    assert world.slot(sid, "bonus").source == "previous"
    # an explicit edit is the employee's newest word
    sid2 = world.new()
    world.tool(sid2, "save_profile", {"base_salary": 25000})
    world.apply(sid2, [{"name": "base_salary", "action": "edit", "value": 26000}])
    assert world.slot(sid2, "base_salary").value == "26000"


def test_a_representatives_value_wins_over_both_keep_and_edit(world: World) -> None:
    saved_world(world)

    def asked_about_salary() -> tuple[str, str]:
        sid = world.new()
        world.client.post(
            f"/api/sessions/{sid}/messages", headers=world.who("employee"), json={"text": "שלום"}
        )
        world.tool(sid, "ask_representative", {"question": "?", "blocking_fields": ["base_salary"]})
        return sid, world.store.tickets("open", sid)[0].id

    # still pending: neither keep nor edit touches the field a representative is answering
    waiting, _ticket = asked_about_salary()
    reply = world.apply(
        waiting,
        [
            {"name": "base_salary", "action": "edit", "value": 1000},
            {"name": "bonus", "action": "keep"},
        ],
    ).json()
    assert reply["waiting_for_rep"] == ["base_salary"]
    assert world.slot(waiting, "base_salary").state == "pending_rep"
    assert world.slot(waiting, "bonus").source == "previous"
    # answered: the representative's value is kept against keep and edit alike
    for action, extra in (("keep", {}), ("edit", {"value": 1000})):
        sid, ticket = asked_about_salary()
        answer = world.client.post(
            f"/api/tickets/{ticket}/answer",
            headers=world.who("rep"),
            json={"values": {"base_salary": 22000}},
        )
        assert answer.status_code == 200, answer.text
        reply = world.apply(sid, [{"name": "base_salary", "action": action, **extra}]).json()
        assert reply["kept_current"] == ["base_salary"], action
        assert (world.slot(sid, "base_salary").value, world.slot(sid, "base_salary").source) == (
            "22000",
            "representative",
        )


def test_a_kept_value_gives_way_to_anything_new_afterwards(world: World) -> None:
    saved_world(world)
    sid = world.new()
    assert world.keep_all(sid).status_code == 200
    assert world.slot(sid, "base_salary").source == "previous"
    world.tool(sid, "save_profile", {"base_salary": 30000})
    assert (world.slot(sid, "base_salary").source, world.slot(sid, "base_salary").value) == (
        "employee",
        "30000",
    )
    assert world.slot(sid, "base_salary").previous_from is None
    world.tool(sid, "set_current_situation", {"today": {"kind": "company_car", "car_id": "CAR-10"}})
    assert world.store.scenarios(sid)["today"]["source"] == "employee"
    # a payslip replaces a kept value too
    world.client.post(
        f"/api/sessions/{sid}/payslip",
        content=pdf(),
        headers={**world.who("employee"), "Content-Type": "application/pdf"},
    )
    world.client.post(
        f"/api/sessions/{sid}/payslip/confirm",
        headers=world.who("employee"),
        json={"fields": {"pension_percent": 6.5}},
    )
    assert world.slot(sid, "pension_pct").source == "payslip"


def test_a_value_that_came_from_the_profile_is_not_saved_again(world: World) -> None:
    saved_world(world)
    before = world.profile()
    sid = world.new()
    assert world.keep_all(sid).status_code == 200
    assert world.profile() == before  # same values, same dates, same sessions


def test_an_edit_is_the_employees_new_word_and_is_saved(world: World) -> None:
    saved_world(world)
    sid = world.new()
    world.apply(sid, [{"name": "base_salary", "action": "edit", "value": 19000}])
    saved = world.profile()["base_salary"]
    assert (saved["value"], saved["source"], saved["from_session"]) == ("19000", "employee", sid)


# --- dismiss, delete, staleness -------------------------------------------------------------------


def test_dismiss_is_for_this_conversation_only_and_deletes_nothing(world: World) -> None:
    saved_world(world)
    before = world.profile()
    sid = world.new()
    assert world.dismiss(sid).status_code == 204
    assert world.profile() == before
    assert world.store.slots(sid) == {}
    assert len(world.events(sid, "profile_dismissed")) == 1
    assert world.dismiss(sid).status_code == 409  # nothing waits any more
    assert (
        world.keep_all.__func__
        and world.apply(sid, [{"name": "bonus", "action": "keep"}]).status_code == 409
    )
    nxt = world.new()
    assert len(world.events(nxt, "profile_offer")) == 1  # the next conversation is offered again


def test_deleting_the_profile_means_no_offer_next_time(world: World) -> None:
    saved_world(world)
    assert world.client.delete("/api/profile", headers=world.who("employee")).status_code == 204
    assert world.profile() == {}
    assert world.events(world.new(), "profile_offer") == []
    # deleting twice is fine
    assert world.client.delete("/api/profile", headers=world.who("employee")).status_code == 204


def test_deleting_the_account_deletes_the_profile(world: World) -> None:
    saved_world(world)
    admin = world.who("admin")
    reply = world.client.delete(f"/api/admin/users/{world.user_id('employee')}", headers=admin)
    assert reply.status_code == 204, reply.text
    assert world.store.profile(world.user_id("admin")) is None
    with sqlite3.connect(world.store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0] == 0


def test_an_old_profile_says_the_details_may_have_changed(world: World) -> None:
    saved_world(world)
    now = datetime.now(UTC) + timedelta(days=45)
    offer = build_offer(world.services, world.user_id(), now=now)
    assert offer is not None
    assert offer["age_days"] == 45 and offer["stale"] is True
    assert offer["stale_note"] == "ייתכן שהפרטים השתנו"
    soon = build_offer(world.services, world.user_id(), now=datetime.now(UTC) + timedelta(days=30))
    assert soon is not None and soon["stale"] is False


def test_what_the_rules_no_longer_hold_is_not_offered(world: World) -> None:
    saved_world(world)
    with sqlite3.connect(world.store.path) as conn:
        row = conn.execute("SELECT fields_json FROM user_profiles").fetchone()
        fields = json.loads(row[0])
        fields["occupation"]["value"] = "תפקיד שלא קיים"
        fields["today_car"]["year"] = 1999  # the catalog's year is another
        conn.execute("UPDATE user_profiles SET fields_json = ?", (json.dumps(fields),))
    offer = build_offer(world.services, world.user_id())
    assert offer is not None
    assert {f["name"] for f in offer["fields"]} == {
        "base_salary",
        "commissions",
        "bonus",
        "pension_percent",
        "study_fund_percent",
        "credit_points",
    }


def test_the_group_is_derived_again_so_a_rules_change_applies(world: World) -> None:
    saved_world(world)
    sid = world.new()
    world.apply(sid, [{"name": "occupation", "action": "keep"}])
    title = world.slot(sid, "occupation").value
    assert world.slot(sid, "group").value == world.services.ctx.occupations[title].group
    assert "group" not in json.dumps(world.profile())


# --- who may see or touch it ----------------------------------------------------------------------


@pytest.mark.parametrize("actor", ["other", "rep", "admin"])
def test_only_the_owner_can_apply_dismiss_or_see_it(world: World, actor: str) -> None:
    saved_world(world)
    sid = world.new()
    url = f"/api/sessions/{sid}/profile"
    headers = world.who(actor)
    body = {"fields": [{"name": "bonus", "action": "keep"}]}
    assert world.client.post(f"{url}/apply", headers=headers, json=body).status_code == 404
    assert world.client.post(f"{url}/dismiss", headers=headers).status_code == 404
    assert (
        world.client.get(
            f"{url.removesuffix('/profile')}/events?after=0", headers=headers
        ).status_code
        == 404
    )
    assert world.slot(sid, "bonus") is None  # nothing happened
    assert len(world.profile()) == 8


def test_anonymous_gets_401_and_the_delete_only_touches_the_callers_profile(world: World) -> None:
    saved_world(world)
    sid = world.new()
    url = f"/api/sessions/{sid}/profile"
    assert world.client.post(f"{url}/dismiss").status_code == 401
    assert world.client.delete("/api/profile").status_code == 401
    other = world.new("other")
    world.tool(other, "save_profile", {"base_salary": 9000}, key="other")
    assert world.client.delete("/api/profile", headers=world.who("other")).status_code == 204
    assert world.profile("other") == {} and len(world.profile()) == 8


# --- the flag ---------------------------------------------------------------------------


def test_with_the_flag_off_nothing_is_saved_offered_or_reachable(
    make: Callable[..., World],
) -> None:
    world = make(profile_memory=False)
    saved_world(world)
    assert world.profile() == {}
    sid = world.new()
    assert world.events(sid, "profile_offer") == []
    for call in (
        world.apply(sid, [{"name": "bonus", "action": "keep"}]),
        world.dismiss(sid),
        world.client.delete("/api/profile", headers=world.who("employee")),
        world.client.delete("/api/profile"),  # 404 before the login is even asked for
    ):
        assert call.status_code == 404
    types = {e.type for e in world.events(sid)}
    assert not any(t.startswith("profile_") and t != "profile_updated" for t in types)
    # a view and a snapshot are what they always were: no previous_from key anywhere
    world.tool(sid, "save_profile", NOA)
    world.tool(sid, "set_current_situation", TODAY)
    world.tool(sid, "compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})
    assert "previous" not in json.dumps([e.payload for e in world.events(sid)])
    snapshot = world.client.get(f"/api/sessions/{sid}", headers=world.who("employee")).json()
    assert all("previous_from" not in slot for slot in snapshot["slots"].values())
    schema = world.client.get("/openapi.json").json()
    assert not [p for p in schema["paths"] if "profile" in p]


def test_the_flag_without_accounts_is_inert(tmp_path: Path) -> None:
    settings = Settings(app_db=tmp_path / "a.db", profile_memory=True, dev_tools=True)
    assert settings.profile_memory_on is False
    with TestClient(create_app(settings)) as client:
        sid = client.post("/api/sessions").json()["id"]
        store = client.app.state.services.store  # type: ignore[attr-defined]
        assert store.memory is None
        assert client.post(f"/api/sessions/{sid}/profile/dismiss").status_code == 404
        assert client.delete("/api/profile").status_code == 404


# --- storage ---------------------------------------------------------------------------------

OLD_SLOTS = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    status TEXT NOT NULL);
CREATE TABLE profile_slots (
    session_id TEXT NOT NULL REFERENCES sessions (id), field TEXT NOT NULL,
    value_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('filled','unknown','pending_rep')),
    source TEXT NOT NULL CHECK (source IN ('employee','payslip','representative','derived')),
    updated_at TEXT NOT NULL, PRIMARY KEY (session_id, field));
"""


def test_a_file_from_before_previous_is_rebuilt_once_and_keeps_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SLOTS)
    conn.execute("INSERT INTO sessions VALUES ('s','t','t','active')")
    conn.execute(
        "INSERT INTO profile_slots VALUES ('s','base_salary','\"18500\"','filled','employee','t')"
    )
    conn.commit()
    conn.close()
    store = Store(path)
    slots = store.slots("s")
    assert slots["base_salary"].value == "18500" and slots["base_salary"].previous_from is None
    from compass.state import SlotUpdate

    store.update_slots("s", {"bonus": SlotUpdate(value="0", source="previous", previous_from="t")})
    assert store.slots("s")["bonus"].source == "previous"
    Store(path)  # a second start changes nothing
    assert set(store.slots("s")) == {"base_salary", "bonus"}


def test_a_number_from_a_previous_conversation_says_so(world: World) -> None:
    from compass.agent.number_sources import audit, build_number_sources, session_context

    saved_world(world)
    sid = world.new()
    assert world.keep_all(sid).status_code == 200
    text = "שכר הבסיס שלך הוא 18,500 ₪."
    verdict = check_text(text, allowed_for_session(world.store, sid))
    sources = build_number_sources(
        text,
        verdict.spans,
        world.store.events_after(sid),
        0,
        session_context(world.services, sid),
    )
    (source,) = sources
    assert (source["chip"], source["kind"], source["label"]) == (
        "previous",
        "previous",
        "משיחה קודמת",
    )
    assert source["slot"] == "base_salary" and source["origin"]["label"] == "משיחה קודמת, {date}"
    assert audit(text, sources) == []

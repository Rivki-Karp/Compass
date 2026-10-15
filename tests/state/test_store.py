import sqlite3
import threading
from pathlib import Path

import pytest

from compass.state import Event, NotFound, SlotUpdate, StateError, Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "app.db")


def _types(store: Store, session_id: str) -> list[str]:
    return [e.type for e in store.events_after(session_id)]


def test_create_session(store: Store) -> None:
    sid = store.create_session()
    assert store.session_status(sid) == "active"
    assert _types(store, sid) == ["session_created"]


def test_schema_and_wal(store: Store) -> None:
    conn = sqlite3.connect(store.path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("SELECT version FROM schema_version").fetchall() == [(1,)]
    conn.close()
    Store(store.path)  # reopening an existing file is fine


def test_schema_version_mismatch(store: Store) -> None:
    conn = sqlite3.connect(store.path)
    conn.execute("UPDATE schema_version SET version = 99")
    conn.commit()
    conn.close()
    with pytest.raises(StateError, match="schema version 99"):
        Store(store.path)


def test_unknown_session_and_ticket(store: Store) -> None:
    with pytest.raises(NotFound):
        store.session_status("nope")
    with pytest.raises(NotFound):
        store.add_message("nope", "user", "hi")
    with pytest.raises(NotFound):
        store.ticket("nope")


def test_messages(store: Store) -> None:
    sid = store.create_session()
    assert store.add_message(sid, "user", {"text": "שלום"}) == 1
    assert store.add_message(sid, "tool", {"name": "compare"}) == 2
    assert store.add_message(sid, "assistant", {"text": "היי"}) == 3
    assert [m.role for m in store.messages(sid)] == ["user", "tool", "assistant"]
    assert store.messages(sid)[0].content == {"text": "שלום"}
    # Tool transcript entries are not UI events.
    assert _types(store, sid) == ["session_created", "user_message", "assistant_message"]


def test_slots_upsert_and_event(store: Store) -> None:
    sid = store.create_session()
    store.update_slots(
        sid,
        {
            "base_salary": SlotUpdate(value="18500", source="employee"),
            "pension_pct": SlotUpdate(state="unknown", source="employee"),
        },
    )
    store.update_slots(sid, {"base_salary": SlotUpdate(value="19000", source="payslip")})
    slots = store.slots(sid)
    assert (slots["base_salary"].value, slots["base_salary"].source) == ("19000", "payslip")
    assert (slots["pension_pct"].state, slots["pension_pct"].value) == ("unknown", None)
    last = store.events_after(sid)[-1]
    assert last.type == "profile_updated"
    assert last.payload["fields"]["base_salary"]["value"] == "19000"


def test_unknown_slot_never_keeps_a_value(store: Store) -> None:
    sid = store.create_session()
    store.update_slots(sid, {"bonus": SlotUpdate(value="5", state="unknown", source="employee")})
    assert store.slots(sid)["bonus"].value is None


def test_today_and_comparisons(store: Store) -> None:
    sid = store.create_session()
    store.set_today(sid, {"kind": "company_car", "car_id": "CAR-09"})
    first = store.record_comparison(sid, {"kind": "waiver"}, {"display_diff": 2914})
    second = store.record_comparison(sid, {"kind": "company_car", "car_id": "CAR-06"}, {"n": 2})
    again = store.record_comparison(sid, {"kind": "waiver"}, {"display_diff": 2914})
    assert (first, second, again) == ("alternative:1", "alternative:2", "alternative:1")
    assert set(store.scenarios(sid)) == {"today", "alternative:1", "alternative:2"}
    assert _types(store, sid)[1:] == ["current_situation_set"] + ["comparison_ready"] * 3


def test_ticket_flow(store: Store) -> None:
    sid = store.create_session()
    ticket = store.open_ticket(
        sid,
        "מה ההשתתפות שלי ברכב?",
        {"occupation": "מפתח/ת תוכנה"},
        ["participation"],
        [{"id": "a", "label": "300", "values": {"participation": "300"}}],
    )
    assert store.session_status(sid) == "waiting_for_rep"
    assert store.slots(sid)["participation"].state == "pending_rep"
    assert [t.id for t in store.tickets(status="open")] == [ticket.id]
    assert _types(store, sid)[-2:] == ["ticket_opened", "session_status"]

    answered = store.answer_ticket(ticket.id, {"text": "300 ש״ח"}, {"participation": "300"})
    assert answered.status == "answered" and answered.answered_at is not None
    slot = store.slots(sid)["participation"]
    assert (slot.value, slot.state, slot.source) == ("300", "filled", "representative")
    assert store.session_status(sid) == "active"
    assert store.tickets(status="open") == []
    assert _types(store, sid)[-2:] == ["ticket_answered", "session_status"]
    with pytest.raises(StateError, match="already answered"):
        store.answer_ticket(ticket.id, {}, {})


def test_events_after(store: Store) -> None:
    sid = store.create_session()
    for i in range(3):
        store.add_message(sid, "user", {"text": str(i)})
    assert [e.seq for e in store.events_after(sid)] == [1, 2, 3, 4]
    assert [e.seq for e in store.events_after(sid, 2)] == [3, 4]
    assert store.events_after(sid, 4) == []


def test_subscribers_see_committed_events_only(store: Store) -> None:
    seen: list[Event] = []
    store.subscribers.append(seen.append)
    sid = store.create_session()
    ticket = store.open_ticket(sid, "q", {}, ["bonus"], [])
    store.answer_ticket(ticket.id, {}, {"bonus": "0"})
    published = len(seen)
    with pytest.raises(StateError):
        store.answer_ticket(ticket.id, {}, {"bonus": "1"})  # rolled back
    assert len(seen) == published == len(store.events_after(sid))
    assert [e.seq for e in seen] == [e.seq for e in store.events_after(sid)]
    assert store.slots(sid)["bonus"].value == "0"


def test_concurrent_writers_get_unique_contiguous_seqs(store: Store) -> None:
    sid = store.create_session()

    def write(n: int) -> None:
        for i in range(20):
            store.add_message(sid, "user", {"thread": n, "i": i})

    threads = [threading.Thread(target=write, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [e.seq for e in store.events_after(sid)] == list(range(1, 162))
    assert [m.seq for m in store.messages(sid)] == list(range(1, 161))


def test_snapshot(store: Store) -> None:
    sid = store.create_session()
    store.add_message(sid, "user", {"text": "שלום"})
    store.update_slots(sid, {"group": SlotUpdate(value="ב", source="derived")})
    store.set_today(sid, {"kind": "maintenance", "amount": "1500"})
    store.record_comparison(sid, {"kind": "waiver"}, {"display_diff": 1})
    store.record_comparison(sid, {"kind": "company_car", "car_id": "CAR-06"}, {"display_diff": 2})
    ticket = store.open_ticket(sid, "q", {}, ["bonus"], [])
    snap = store.snapshot(sid)
    assert snap["status"] == "waiting_for_rep"
    assert [m["content"] for m in snap["messages"]] == [{"text": "שלום"}]
    assert snap["slots"]["group"]["value"] == "ב"
    assert snap["slots"]["bonus"]["state"] == "pending_rep"
    assert set(snap["scenarios"]) == {"today", "alternative:1", "alternative:2"}
    assert [t["id"] for t in snap["open_tickets"]] == [ticket.id]
    assert snap["last_comparison"]["comparison"] == {"display_diff": 2}
    assert snap["last_event_seq"] == store.events_after(sid)[-1].seq

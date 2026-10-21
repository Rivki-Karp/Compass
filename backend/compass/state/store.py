"""Session store: repository functions over SQLite (no ORM).

Every operation is one write transaction (BEGIN IMMEDIATE) that also appends the event(s)
describing the change, so the events table is the single source for the live UI. Subscribers
are called after commit (the API uses this to wake SSE streams).

The store holds JSON only. Callers convert Decimals to strings before storing.
"""

import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = 1
SCHEMA_SQL = Path(__file__).with_name("schema.sql")

SessionStatus = Literal["active", "waiting_for_rep", "closed"]
Role = Literal["user", "assistant", "tool", "system_event"]
SlotState = Literal["filled", "unknown", "pending_rep"]
SlotSource = Literal["employee", "payslip", "representative", "derived"]
TicketStatus = Literal["open", "answered"]

# Event types (payload in parentheses):
#   session_created (status) · session_status (status) · user_message (seq, content)
#   profile_updated (fields) · current_situation_set (scenario) · comparison_ready (comparison)
#   ticket_opened (ticket) · ticket_answered (ticket_id, answer, fields, unknown, partial,
#   pending, questions?): `partial` answers fill some fields and leave the ticket open with
#   `pending` ones (bound fields, and free questions' ids); `questions` is this part's answer
#   to each question, display-ready
EVENT_TYPES = frozenset(
    {
        "session_created",
        "session_status",
        "user_message",
        "assistant_message",
        "profile_updated",
        "current_situation_set",
        "comparison_ready",
        # every eligible alternative's view at once (list_options; origin server)
        "comparison_set_ready",
        # today's car is unknown: the catalog picker the server offers, and the employee's pick
        # (compass/tools/car_picker.py)
        # the employee asked for every option (list_options); fulfilled by the next
        # comparison_set_ready (the pending request, satisfied by the server once it can)
        "options_requested",
        "current_car_offered",
        "current_car_picked",
        "ticket_opened",
        "ticket_answered",
        # The agent (Day 3): live progress for the UI and judges mode.
        "agent_started",
        "agent_finished",
        "tool_call",
        "tool_result",
        "guard_check",
        "agent_error",
        # The payslip upload (COMPASS_PAYSLIP=1): a pending candidate (numbers, confidences and
        # flags only; never the file), or why reading it failed (a code). One per upload that
        # reached the extractor: the per-session count.
        "payslip_extracted",
        "payslip_failed",
        # the employee confirmed (part of) the candidate: what was applied, with its source
        "payslip_confirmed",
    }
)


class NotFound(LookupError):
    """No such session or ticket."""


class StateError(ValueError):
    """The operation does not fit the current state (e.g. answering an answered ticket)."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class Slot(_Model):
    field: str
    value: Any  # JSON; None unless state == "filled"
    state: SlotState
    source: SlotSource
    updated_at: str


class SlotUpdate(_Model):
    value: Any = None
    state: SlotState = "filled"
    source: SlotSource


class Event(_Model):
    session_id: str
    seq: int
    type: str
    payload: Any
    created_at: str


class Message(_Model):
    seq: int
    role: Role
    content: Any
    created_at: str


class Ticket(_Model):
    id: str
    session_id: str
    question: str
    context: Any
    blocking_fields: list[str]
    quick_answers: list[Any]
    # The questions (compass/tools/questions.py); empty for a ticket stored before them.
    questions: list[Any] = []
    status: TicketStatus
    answer: Any
    created_at: str
    answered_at: str | None


# An empty conversation (a condition on a `sessions` row): the employee has said nothing and
# uploaded no payslip. The one definition the list and the clean-up share.
_IS_EMPTY = (
    "NOT EXISTS (SELECT 1 FROM events e WHERE e.session_id = sessions.id "
    "AND e.type IN ('user_message', 'payslip_extracted', 'payslip_failed'))"
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.subscribers: list[Callable[[Event], None]] = []
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row[0] != SCHEMA_VERSION:
                raise StateError(
                    f"{path}: schema version {row[0]}, expected {SCHEMA_VERSION}; "
                    "delete the file to recreate it"
                )
            self._add_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS sessions_by_owner ON sessions (owner_user_id)")
        finally:
            conn.close()

    # Nullable columns added after a file was created: added in place (additive, so every row
    # stored before reads as it did). table -> (column, SQL type).
    _ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
        ("tickets", "questions_json", "TEXT"),
        # the account that owns the conversation (COMPASS_AUTH=1); NULL: created with the flag off
        ("sessions", "owner_user_id", "TEXT"),
    )

    @classmethod
    def _add_columns(cls, conn: sqlite3.Connection) -> None:
        for table, column, sql_type in cls._ADDED_COLUMNS:
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")

    # --- plumbing ---------------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def _write(self) -> Iterator[tuple[sqlite3.Connection, list[Event]]]:
        """One write transaction; events appended in it are published after commit."""
        conn = self._connect()
        events: list[Event] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn, events
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()
        for event in events:
            for subscriber in list(self.subscribers):
                subscriber(event)

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _require_session(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise NotFound(f"session {session_id!r} not found")
        return row

    @staticmethod
    def _event(
        conn: sqlite3.Connection, events: list[Event], session_id: str, type_: str, payload: Any
    ) -> Event:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type_!r}")
        seq = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        now = _now()
        conn.execute(
            "INSERT INTO events (session_id, seq, type, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, seq, type_, _dump(payload), now),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        event = Event(session_id=session_id, seq=seq, type=type_, payload=payload, created_at=now)
        events.append(event)
        return event

    @staticmethod
    def _set_status(
        conn: sqlite3.Connection,
        events: list[Event],
        session_id: str,
        status: SessionStatus,
    ) -> None:
        current = Store._require_session(conn, session_id)["status"]
        if current != status:
            conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
            Store._event(conn, events, session_id, "session_status", {"status": status})

    @staticmethod
    def _upsert_slots(
        conn: sqlite3.Connection, session_id: str, updates: Mapping[str, SlotUpdate]
    ) -> None:
        now = _now()
        for field, update in updates.items():
            value = update.value if update.state == "filled" else None
            conn.execute(
                "INSERT INTO profile_slots (session_id, field, value_json, state, source, "
                "updated_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (session_id, field) DO UPDATE SET value_json = excluded.value_json, "
                "state = excluded.state, source = excluded.source, "
                "updated_at = excluded.updated_at",
                (session_id, field, _dump(value), update.state, update.source, now),
            )

    # --- sessions ---------------------------------------------------------------------------

    def create_session(self, owner_user_id: str | None = None) -> str:
        """A new conversation. With COMPASS_AUTH=1 `owner_user_id` is the account it belongs to
        (every route then checks it); None: created with accounts off, owned by nobody."""
        session_id = uuid.uuid4().hex
        now = _now()
        with self._write() as (conn, events):
            conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at, status, owner_user_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, now, now, "active", owner_user_id),
            )
            self._event(conn, events, session_id, "session_created", {"status": "active"})
        return session_id

    def session_owner(self, session_id: str) -> str | None:
        """The account that owns the session; None if nobody does. NotFound: no such session."""
        with self._read() as conn:
            owner = self._require_session(conn, session_id)["owner_user_id"]
        return None if owner is None else str(owner)

    def conversation_rows(self, owner_user_id: str) -> list[dict[str, Any]]:
        """The account's own sessions, newest first, each with the latest event of the kinds a
        list entry is built from: {id, status, updated_at, latest: {type: (seq, payload)}}."""
        kinds = ("comparison_ready", "comparison_set_ready", "options_requested")
        with self._read() as conn:
            sessions = conn.execute(
                "SELECT id, status, updated_at FROM sessions WHERE owner_user_id = ? "
                f"AND NOT {_IS_EMPTY} ORDER BY updated_at DESC, created_at DESC, id",
                (owner_user_id,),
            ).fetchall()
            rows = []
            for s in sessions:
                latest = {}
                for kind in kinds:
                    event = conn.execute(
                        "SELECT seq, payload_json FROM events WHERE session_id = ? AND type = ? "
                        "ORDER BY seq DESC LIMIT 1",
                        (s["id"], kind),
                    ).fetchone()
                    if event is not None:
                        latest[kind] = (event["seq"], json.loads(event["payload_json"]))
                rows.append(
                    {
                        "id": s["id"],
                        "status": s["status"],
                        "updated_at": s["updated_at"],
                        "latest": latest,
                    }
                )
        return rows

    def owned_session_ids(self, owner_user_id: str) -> list[str]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT id FROM sessions WHERE owner_user_id = ?", (owner_user_id,)
            ).fetchall()
        return [r["id"] for r in rows]

    def empty_session_ids(self, owner_user_id: str) -> list[str]:
        """The account's empty conversations: no employee message and no payslip upload."""
        with self._read() as conn:
            rows = conn.execute(
                f"SELECT id FROM sessions WHERE owner_user_id = ? AND {_IS_EMPTY}",
                (owner_user_id,),
            ).fetchall()
        return [r["id"] for r in rows]

    def delete_session(self, session_id: str) -> bool:
        """Delete a conversation and everything of it: messages, events (the pending payslip
        candidate among them), profile, scenarios and tickets (open ones included). Pages are
        scrubbed when freed and the write-ahead log is checkpointed, so the content does not
        linger in the files. Nothing about the content is recorded. False: no such session."""
        with self._write() as (conn, _events):
            conn.execute("PRAGMA secure_delete = ON")
            found = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if found is None:
                return False
            for table in ("events", "messages", "profile_slots", "scenarios", "tickets"):
                conn.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn = self._connect()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # best effort: a reader may hold it
        except sqlite3.Error:
            pass
        finally:
            conn.close()
        return True

    def count_user_events(self, user_id: str, types: tuple[str, ...], since: str) -> int:
        """How many events of `types`, at or after `since` (an ISO UTC time), the sessions of
        this account have (the per-user daily payslip count)."""
        marks = ", ".join("?" for _ in types)
        with self._read() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM events e JOIN sessions s ON s.id = e.session_id "
                f"WHERE s.owner_user_id = ? AND e.created_at >= ? AND e.type IN ({marks})",
                (user_id, since, *types),
            ).fetchone()
        return int(row[0])

    def session_status(self, session_id: str) -> SessionStatus:
        with self._read() as conn:
            return self._require_session(conn, session_id)["status"]

    def set_status(self, session_id: str, status: SessionStatus) -> None:
        with self._write() as (conn, events):
            self._set_status(conn, events, session_id, status)

    # --- messages ---------------------------------------------------------------------------

    def add_message(
        self, session_id: str, role: Role, content: Any, emit_event: bool = True
    ) -> int:
        """Store a message; user and assistant messages also append an event unless
        `emit_event` is False (the agent's transcript rows: it emits its own events)."""
        with self._write() as (conn, events):
            self._require_session(conn, session_id)
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO messages (session_id, seq, role, content_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, seq, role, _dump(content), _now()),
            )
            if emit_event and role in ("user", "assistant"):
                payload = {"message_seq": seq, "content": content}
                self._event(conn, events, session_id, f"{role}_message", payload)
        return seq

    def append_event(self, session_id: str, type_: str, payload: Any) -> Event:
        """Append one event (a known type) to the session's log."""
        with self._write() as (conn, events):
            self._require_session(conn, session_id)
            return self._event(conn, events, session_id, type_, payload)

    def messages(self, session_id: str) -> list[Message]:
        with self._read() as conn:
            self._require_session(conn, session_id)
            return self._messages(conn, session_id)

    @staticmethod
    def _messages(conn: sqlite3.Connection, session_id: str) -> list[Message]:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY seq", (session_id,)
        ).fetchall()
        return [
            Message(
                seq=r["seq"],
                role=r["role"],
                content=json.loads(r["content_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- profile slots ----------------------------------------------------------------------

    def update_slots(self, session_id: str, updates: Mapping[str, SlotUpdate]) -> None:
        if not updates:
            return
        with self._write() as (conn, events):
            self._require_session(conn, session_id)
            self._upsert_slots(conn, session_id, updates)
            fields = {
                field: {"state": u.state, "source": u.source, "value": u.value}
                for field, u in updates.items()
            }
            self._event(conn, events, session_id, "profile_updated", {"fields": fields})

    def slots(self, session_id: str) -> dict[str, Slot]:
        with self._read() as conn:
            self._require_session(conn, session_id)
            return self._slots(conn, session_id)

    @staticmethod
    def _slots(conn: sqlite3.Connection, session_id: str) -> dict[str, Slot]:
        rows = conn.execute(
            "SELECT * FROM profile_slots WHERE session_id = ? ORDER BY field", (session_id,)
        ).fetchall()
        return {
            r["field"]: Slot(
                field=r["field"],
                value=json.loads(r["value_json"]),
                state=r["state"],
                source=r["source"],
                updated_at=r["updated_at"],
            )
            for r in rows
        }

    # --- scenarios --------------------------------------------------------------------------

    def set_today(self, session_id: str, payload: Any) -> None:
        with self._write() as (conn, events):
            self._require_session(conn, session_id)
            self._put_scenario(conn, session_id, "today", payload)
            self._event(conn, events, session_id, "current_situation_set", {"scenario": payload})

    @staticmethod
    def _put_scenario(conn: sqlite3.Connection, session_id: str, kind: str, payload: Any) -> None:
        conn.execute(
            "INSERT INTO scenarios (session_id, kind, payload_json, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (session_id, kind) DO UPDATE SET "
            "payload_json = excluded.payload_json, updated_at = excluded.updated_at",
            (session_id, kind, _dump(payload), _now()),
        )

    def scenarios(self, session_id: str) -> dict[str, Any]:
        with self._read() as conn:
            self._require_session(conn, session_id)
            return self._scenarios(conn, session_id)

    @staticmethod
    def _scenarios(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        rows = conn.execute(
            "SELECT kind, payload_json FROM scenarios WHERE session_id = ? ORDER BY kind",
            (session_id,),
        ).fetchall()
        return {r["kind"]: json.loads(r["payload_json"]) for r in rows}

    def record_comparison(
        self, session_id: str, alternative: Any, result: Mapping[str, Any]
    ) -> str:
        """Store the alternative (reusing its kind if it was compared before) and append
        comparison_ready = {alternative_kind, alternative, **result}: the last comparison."""
        with self._write() as (conn, events):
            self._require_session(conn, session_id)
            rows = conn.execute(
                "SELECT kind, payload_json FROM scenarios WHERE session_id = ? "
                "AND kind LIKE 'alternative:%'",
                (session_id,),
            ).fetchall()
            existing = {r["payload_json"]: r["kind"] for r in rows}
            kind = existing.get(_dump(alternative))
            if kind is None:
                kind = f"alternative:{len(rows) + 1}"
            self._put_scenario(conn, session_id, kind, alternative)
            payload = {"alternative_kind": kind, "alternative": alternative, **result}
            self._event(conn, events, session_id, "comparison_ready", payload)
        return kind

    # --- spend ------------------------------------------------------------------------------

    def add_spend(self, day: str, usd: float) -> None:
        """Add one model call's cost to `day` (YYYY-MM-DD, UTC)."""
        micro = round(usd * 1_000_000)
        with self._write() as (conn, _events):
            conn.execute(
                "INSERT INTO daily_spend (day, micro_usd) VALUES (?, ?) "
                "ON CONFLICT (day) DO UPDATE SET micro_usd = micro_usd + excluded.micro_usd",
                (day, micro),
            )

    def spend_on(self, day: str) -> float:
        """The model spend recorded for `day`, USD."""
        with self._read() as conn:
            row = conn.execute("SELECT micro_usd FROM daily_spend WHERE day = ?", (day,)).fetchone()
        return 0.0 if row is None else row[0] / 1_000_000

    # --- tickets ----------------------------------------------------------------------------

    def open_ticket(
        self,
        session_id: str,
        question: str,
        context: Any,
        blocking_fields: Sequence[str],
        quick_answers: Sequence[Any],
        pending_slots: Sequence[str] | None = None,
        questions: Sequence[Any] = (),
    ) -> Ticket:
        """Create a ticket, mark its slots pending_rep, and wait for the representative.

        `pending_slots` are the slot names to mark (default: `blocking_fields`), for callers
        whose ticket names fields differently from the slots (tool vs engine units).
        """
        ticket_id = uuid.uuid4().hex
        now = _now()
        with self._write() as (conn, events):
            self._require_session(conn, session_id)
            conn.execute(
                "INSERT INTO tickets (id, session_id, question, context_json, "
                "blocking_fields_json, quick_answers_json, questions_json, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (
                    ticket_id,
                    session_id,
                    question,
                    _dump(context),
                    _dump(list(blocking_fields)),
                    _dump(list(quick_answers)),
                    _dump(list(questions)) if questions else None,
                    now,
                ),
            )
            marked = blocking_fields if pending_slots is None else pending_slots
            pending = {f: SlotUpdate(state="pending_rep", source="representative") for f in marked}
            self._upsert_slots(conn, session_id, pending)
            ticket = self._ticket(conn, ticket_id)
            self._event(conn, events, session_id, "ticket_opened", {"ticket": ticket.model_dump()})
            self._set_status(conn, events, session_id, "waiting_for_rep")
        return ticket

    def answer_ticket(
        self,
        ticket_id: str,
        answer: Any,
        values: Mapping[str, Any],
        unknown: Sequence[str] = (),
        pending: Sequence[str] = (),
        part: Any = None,
        questions: Sequence[Any] = (),
        sources: Mapping[str, SlotSource] | None = None,
        today: Any = None,
    ) -> Ticket:
        """Fill the given slots (source representative), mark `unknown` slots unknown (the
        representative answered without a value), and, unless fields are still `pending` (a
        partial answer: those slots stay pending_rep), close the ticket and resume the session.

        `answer` is stored as the ticket's answer so far (the caller merges earlier parts); the
        event carries this `part` of it (default: the whole answer) and its slot values, and
        `questions`, this part's answer to each question (display-ready), when given. `sources`
        overrides a filled slot's source (a group derived from the approved occupation). `today`,
        when given, becomes today's situation in the same write (a current_car answer)."""
        with self._write() as (conn, events):
            ticket = self._ticket(conn, ticket_id)
            if ticket.status != "open":
                raise StateError(f"ticket {ticket_id} is already {ticket.status}")
            source_of = sources or {}
            filled = {
                f: SlotUpdate(value=v, source=source_of.get(f, "representative"))
                for f, v in values.items()
            }
            filled |= {f: SlotUpdate(state="unknown", source="representative") for f in unknown}
            self._upsert_slots(conn, ticket.session_id, filled)
            if today is not None:
                self._put_scenario(conn, ticket.session_id, "today", today)
                self._event(
                    conn, events, ticket.session_id, "current_situation_set", {"scenario": today}
                )
            if pending:
                conn.execute(
                    "UPDATE tickets SET answer_json = ? WHERE id = ?", (_dump(answer), ticket_id)
                )
            else:
                conn.execute(
                    "UPDATE tickets SET status = 'answered', answer_json = ?, answered_at = ? "
                    "WHERE id = ?",
                    (_dump(answer), _now(), ticket_id),
                )
            payload = {
                "ticket_id": ticket_id,
                "answer": answer if part is None else part,
                "fields": dict(values),
                "unknown": list(unknown),
                "partial": bool(pending),
                "pending": list(pending),
            }
            if questions:
                payload["questions"] = list(questions)
            self._event(conn, events, ticket.session_id, "ticket_answered", payload)
            if not pending:
                self._set_status(conn, events, ticket.session_id, "active")
            return self._ticket(conn, ticket_id)

    @staticmethod
    def _ticket(conn: sqlite3.Connection, ticket_id: str) -> Ticket:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise NotFound(f"ticket {ticket_id!r} not found")
        return Store._ticket_from_row(row)

    @staticmethod
    def _ticket_from_row(row: sqlite3.Row) -> Ticket:
        return Ticket(
            id=row["id"],
            session_id=row["session_id"],
            question=row["question"],
            context=json.loads(row["context_json"]),
            blocking_fields=json.loads(row["blocking_fields_json"]),
            quick_answers=json.loads(row["quick_answers_json"]),
            questions=json.loads(row["questions_json"] or "[]"),
            status=row["status"],
            answer=None if row["answer_json"] is None else json.loads(row["answer_json"]),
            created_at=row["created_at"],
            answered_at=row["answered_at"],
        )

    def ticket(self, ticket_id: str) -> Ticket:
        with self._read() as conn:
            return self._ticket(conn, ticket_id)

    def tickets(
        self, status: TicketStatus | None = None, session_id: str | None = None
    ) -> list[Ticket]:
        with self._read() as conn:
            return self._tickets(conn, status, session_id)

    @staticmethod
    def _tickets(
        conn: sqlite3.Connection, status: TicketStatus | None, session_id: str | None
    ) -> list[Ticket]:
        where: list[str] = []
        params: list[str] = []
        if status is not None:
            where.append("status = ?")
            params.append(status)
        if session_id is not None:
            where.append("session_id = ?")
            params.append(session_id)
        sql = "SELECT * FROM tickets"
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = conn.execute(sql + " ORDER BY created_at, id", params).fetchall()
        return [Store._ticket_from_row(r) for r in rows]

    # --- events -----------------------------------------------------------------------------

    def events_after(self, session_id: str, after_seq: int = 0) -> list[Event]:
        with self._read() as conn:
            self._require_session(conn, session_id)
            rows = conn.execute(
                "SELECT * FROM events WHERE session_id = ? AND seq > ? ORDER BY seq",
                (session_id, after_seq),
            ).fetchall()
        return [
            Event(
                session_id=r["session_id"],
                seq=r["seq"],
                type=r["type"],
                payload=json.loads(r["payload_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count_events(self, session_id: str, types: tuple[str, ...]) -> int:
        """How many of the session's events have one of `types`."""
        marks = ", ".join("?" for _ in types)
        with self._read() as conn:
            self._require_session(conn, session_id)
            row = conn.execute(
                f"SELECT COUNT(*) FROM events WHERE session_id = ? AND type IN ({marks})",
                (session_id, *types),
            ).fetchone()
        return int(row[0])

    def last_event_payload(self, session_id: str, type_: str) -> Any:
        """The payload of the session's latest event of `type_`, or None."""
        with self._read() as conn:
            self._require_session(conn, session_id)
            row = conn.execute(
                "SELECT payload_json FROM events WHERE session_id = ? AND type = ? "
                "ORDER BY seq DESC LIMIT 1",
                (session_id, type_),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def last_comparison(self, session_id: str) -> dict[str, Any] | None:
        """The payload of the session's latest comparison_ready, if any."""
        with self._read() as conn:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE session_id = ? AND type = "
                "'comparison_ready' ORDER BY seq DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    # --- snapshot ---------------------------------------------------------------------------

    def snapshot(self, session_id: str) -> dict[str, Any]:
        """Everything the UI needs to restore after a refresh, read in one transaction."""
        with self._read() as conn:
            conn.execute("BEGIN")  # one consistent read
            session = self._require_session(conn, session_id)
            last = conn.execute(
                "SELECT MAX(seq) FROM events WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            comparison = conn.execute(
                "SELECT payload_json FROM events WHERE session_id = ? AND type = "
                "'comparison_ready' ORDER BY seq DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            snapshot = {
                "id": session_id,
                "status": session["status"],
                "created_at": session["created_at"],
                "updated_at": session["updated_at"],
                "messages": [m.model_dump() for m in self._messages(conn, session_id)],
                "slots": {f: s.model_dump() for f, s in self._slots(conn, session_id).items()},
                "scenarios": self._scenarios(conn, session_id),
                "open_tickets": [t.model_dump() for t in self._tickets(conn, "open", session_id)],
                "last_comparison": None if comparison is None else json.loads(comparison[0]),
                "last_event_seq": last or 0,
            }
            conn.execute("COMMIT")
        return snapshot

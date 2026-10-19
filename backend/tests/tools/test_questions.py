"""Ticket questions (compass/tools/questions.py): the model, its storage, and the inbox view.

Stored tickets from before questions existed keep working: the column is added in place, and
their blocking fields are their questions."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from compass.state import Store
from compass.state.store import SCHEMA_SQL
from compass.tools import Services, ToolRunner
from compass.tools.questions import (
    OTHER_OCCUPATION,
    bound_question,
    free_question,
    ticket_questions,
)
from compass.tools.view import build_ticket_view

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


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


def ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, result
    return result


def _session(services: Services) -> str:
    tools = ToolRunner(services)
    sid = services.store.create_session()
    ok(tools.run(sid, "save_profile", DEVELOPER))
    ok(tools.run(sid, "set_current_situation", COROLLA_CROSS))
    return sid


def test_a_file_from_before_questions_gets_the_column_and_reads_as_before(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    old_schema = "\n".join(
        line
        for line in SCHEMA_SQL.read_text(encoding="utf-8").splitlines()
        if "questions_json" not in line
    )
    conn = sqlite3.connect(path)
    conn.executescript(old_schema)
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute(
        "INSERT INTO sessions VALUES ('s1', '2026-10-18', '2026-10-18', 'waiting_for_rep')"
    )
    conn.execute(
        "INSERT INTO tickets (id, session_id, question, context_json, blocking_fields_json, "
        "quick_answers_json, status, created_at) VALUES ('t1', 's1', '?', '{}', "
        "'[\"current_participation\"]', '[]', 'open', '2026-10-18')"
    )
    conn.commit()
    conn.close()

    store = Store(path)
    ticket = store.ticket("t1")
    assert ticket.questions == []
    assert ticket.blocking_fields == ["current_participation"]
    columns = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(tickets)")}
    assert "questions_json" in columns
    Store(path)  # opening it again adds nothing


def test_questions_round_trip(services: Services) -> None:
    sid = _session(services)
    questions = [
        bound_question(services, sid, "group_exception", qid="q1"),
        free_question("q2", "האם יש חניה בבניין?", "yes_no"),
    ]
    ticket = services.store.open_ticket(sid, "?", {}, ["group_exception"], [], questions=questions)
    assert services.store.ticket(ticket.id).questions == questions


def test_a_legacy_ticket_has_one_bound_question_per_field(services: Services) -> None:
    sid = _session(services)
    ticket = services.store.open_ticket(
        sid, "?", {}, ["current_participation", "group_exception"], []
    )
    questions = ticket_questions(services, ticket)
    assert [q["id"] for q in questions] == ["current_participation", "group_exception"]
    assert [q["answer"]["type"] for q in questions] == ["amount", "choice"]
    view = build_ticket_view(services, ticket)
    assert [q["id"] for q in view["questions"]] == ["current_participation", "group_exception"]
    assert [q["kind"] for q in view["questions"]] == ["bound", "bound"]
    # the old `fields` are unchanged, and the title is built from them as before
    assert [f["field"] for f in view["fields"]] == ["current_participation", "group_exception"]
    assert view["title"].startswith("השתתפות עצמית ברכב של היום")


def test_occupation_options_come_from_the_table_by_the_matcher(services: Services) -> None:
    sid = _session(services)
    question = bound_question(services, sid, "occupation", qid="q1", occupation_query="מפתח AI")
    options = question["answer"]["options"]
    titles = [o["value"] for o in options[:-1]]
    assert titles[0] == "מפתח/ת תוכנה"
    assert set(titles) <= set(services.ctx.occupations)
    assert options[-1]["value"] == OTHER_OCCUPATION
    assert options[0]["label"] == "מפתח/ת תוכנה · קבוצה ב׳"


def test_a_free_question_view_and_title(services: Services) -> None:
    sid = _session(services)
    prompt = "האם החברה מאפשרת טעינה חינם של רכב חשמלי בחניון של משרדי החברה בתל אביב?"
    ticket = services.store.open_ticket(
        sid,
        prompt,
        {},
        [],
        [],
        questions=[free_question("q1", prompt, "choice", ["כן, בכל החניונים", "רק בחלק"])],
    )
    view = build_ticket_view(services, ticket)
    (question,) = view["questions"]
    assert question["kind"] == "free"
    assert question["type"] == "choice"
    assert question["prompt_he"] == prompt
    assert question["title"].endswith("…") and len(question["title"]) <= 60
    assert [o["value"] for o in question["options"]] == ["o1", "o2"]
    assert question["status"] == "pending"
    assert view["fields"] == []
    assert view["title"].endswith("…") and len(view["title"]) <= 40

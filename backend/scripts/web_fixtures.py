"""Record real session event logs for the web UI's tests (frontend/src/test/fixtures/*.json).

    uv run --project backend python backend/scripts/web_fixtures.py   (from the repo root)

Runs the two demo scripts (walkthrough, E-001 with the representative's answer) through the
real API in demo mode (scripted model, real tools, guard and tickets) and saves each session's
events as the admin stream sends them. Ids and timestamps differ per run; the numbers don't.

Also records `options`: the walkthrough, then list_options (through the dev tools endpoint): every
eligible alternative on screen (comparison_set_ready).

Also records `questions` and `questions_inbox`: an employee who describes themselves as an AI
developer and asks about parking; the agent opens one ticket with an occupation question and a
free yes/no question; the representative picks software developer and answers yes with a note.

Also records `options_without_today`: list_options before today's car is known (each option's
net, "חסר הרכב של היום" for the diff), then set_current_situation, after which the server puts
the same options on screen again with their diffs.

Also records `guard_retry`: the walkthrough with a first draft of the last reply that has a number
no tool produced, so the real guard rejects it and the model rewrites it (judges mode's rejected
draft card).
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from compass.agent import demo_llm
from compass.agent.demo_llm import E001, WALKTHROUGH
from compass.agent.factory import build_claude_runner
from compass.agent.llm import LLMResponse, ScriptedClient, text_response, tool_response
from compass.api import Settings, create_app
from compass.config import REPO_ROOT

OUT = REPO_ROOT / "frontend" / "src" / "test" / "fixtures"
# options_without_today: a profile, the options before today's car is known, then today's car
NO_TODAY_PROFILE = {
    "occupation_query": "מפתחת תוכנה",
    "base_salary": 18500,
    "commissions": 0,
    "bonus": 0,
    "pension_percent": 6.5,
    "study_fund_percent": 2.5,
    "credit_points": 3,
}
COROLLA_CROSS_TODAY = {"kind": "company_car", "car_id": "CAR-09", "participation": 300}
REP = {"Authorization": "Bearer rep"}


def _events(app: Any, sid: str) -> list[dict[str, Any]]:
    return [e.model_dump() for e in app.state.services.store.events_after(sid)]


def guard_retry_steps() -> list[LLMResponse]:
    """The walkthrough's model responses, with one more before the last: a draft that says
    +2,915 where the comparison says +2,914. The guard rejects it; the rewrite is the original."""
    steps = [
        tool_response(*step) if kind == "tools" else text_response(step)
        for turn in WALKTHROUGH.turns
        for kind, step in turn.steps
    ]
    final = steps[-1].content[0]["text"]
    assert "2,914" in final
    return [*steps[:-1], text_response(final.replace("2,914", "2,915")), steps[-1]]


def _guard_retry_log() -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(app_db=Path(tmp) / "app.db", llm="scripted")
        app = create_app(
            settings,
            agent_factory=lambda s, services, tools: build_claude_runner(
                s, services, llm=ScriptedClient(guard_retry_steps()), tool_runner=tools
            ),
        )
        with TestClient(app) as client:
            sid = client.post("/api/sessions").json()["id"]
            for text in WALKTHROUGH.employee_messages:
                client.post(f"/api/sessions/{sid}/messages", json={"text": text})
                assert app.state.agent.wait_idle(30)
            log = _events(app, sid)
    actions = [e["payload"]["action"] for e in log if e["type"] == "guard_check"]
    assert actions == ["accept", "retry", "accept_after_retry"], actions
    return log


AI_DEVELOPER_HE = (
    "אני מפתח AI. שכר בסיס 18,500, אין לי עמלות או בונוסים. פנסיה 6.5%, קרן השתלמות 2.5%, "
    "3 נקודות זיכוי. היום יש לי קורולה קרוס 2025 ואני משתתף ב-300 ₪. האם יש חניה לעובדים "
    "בבניין? ומה יקרה לנטו אם אעבור ל-ATTO 3?"
)
QUESTIONS_ASK = {
    "question": "העובד מתאר את עצמו כ'מפתח AI', עיסוק שלא מופיע בטבלה, ושואל על חניה לעובדים.",
    "questions": [
        {
            "bound_field": "occupation",
            "occupation_query": "מפתח AI",
            "prompt_he": "האם 'מפתח AI' נחשב מפתח/ת תוכנה?",
        },
        {"prompt_he": "האם יש חניה לעובדים בבניין המשרדים?", "type": "yes_no"},
    ],
}
QUESTIONS_ANSWER = {
    "answers": {
        "q1": {"value": "מפתח/ת תוכנה"},
        "q2": {"value": "yes", "note": "בחניון התת-קרקעי, עם תג עובד"},
    },
    "partial": True,
}


def questions_steps() -> list[LLMResponse]:
    """The scripted model of the `questions` recording (real tools, guard and tickets)."""
    profile = {
        "base_salary": 18500,
        "commissions": 0,
        "bonus": 0,
        "pension_percent": 6.5,
        "study_fund_percent": 2.5,
        "credit_points": 3,
    }
    today = {"today": {"kind": "company_car", "car_id": "CAR-09", "participation": 300}}
    return [
        tool_response(
            ("save_profile", profile),
            ("lookup_occupation", {"query": "מפתח AI"}),
            ("set_current_situation", today),
        ),
        tool_response(("ask_representative", QUESTIONS_ASK)),
        text_response(
            "העיסוק 'מפתח AI' לא מופיע ברשימת העיסוקים, ולכן שאלתי את הנציג לאיזה עיסוק הוא "
            "מתאים, ובאותה פנייה גם אם יש חניה לעובדים. התשובה תופיע כאן."
        ),
        tool_response(("compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})),
        text_response(
            "הנציג ענה: יש חניה לעובדים, בחניון התת-קרקעי עם תג עובד. העיסוק סווג כמפתח/ת "
            "תוכנה, ולכן הקבוצה שלך ב׳. ההשוואה ל-ATTO 3 מוצגת בכרטיס, והיא מותנית באישור כי "
            "ATTO 3 בקבוצה גבוהה יותר."
        ),
    ]


def _questions_log() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(the inbox before the answer, the session's events)."""
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(app_db=Path(tmp) / "app.db", llm="scripted", rep_token="rep")
        app = create_app(
            settings,
            agent_factory=lambda s, services, tools: build_claude_runner(
                s, services, llm=ScriptedClient(questions_steps()), tool_runner=tools
            ),
        )
        with TestClient(app) as client:
            sid = client.post("/api/sessions").json()["id"]
            client.post(f"/api/sessions/{sid}/messages", json={"text": AI_DEVELOPER_HE})
            assert app.state.agent.wait_idle(30)
            inbox = client.get("/api/tickets", params={"status": "open"}, headers=REP).json()
            (ticket,) = inbox
            answered = client.post(
                f"/api/tickets/{ticket['id']}/answer", json=QUESTIONS_ANSWER, headers=REP
            )
            assert answered.status_code == 200, answered.text
            assert app.state.agent.wait_idle(30)
            log = _events(app, sid)
    actions = [e["payload"]["action"] for e in log if e["type"] == "guard_check"]
    assert actions == ["accept", "accept"], actions
    return inbox, log


def main() -> int:
    demo_llm.DEMO_DELAY_SECONDS = 0
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            app_db=Path(tmp) / "app.db", llm="scripted", rep_token="rep", dev_tools=True
        )
        app = create_app(settings)
        with TestClient(app) as client:
            agent = app.state.agent

            def run(texts: list[str]) -> str:
                sid = client.post("/api/sessions").json()["id"]
                for text in texts:  # one at a time, as a person would type them
                    client.post(f"/api/sessions/{sid}/messages", json={"text": text})
                    assert agent.wait_idle(30)
                return sid

            walkthrough = run(WALKTHROUGH.employee_messages)
            options = run(WALKTHROUGH.employee_messages)
            listed = client.post(f"/api/sessions/{options}/tools/list_options", json={})
            assert listed.json()["ok"], listed.text
            no_today = client.post("/api/sessions").json()["id"]
            for name, body in (
                ("save_profile", NO_TODAY_PROFILE),
                ("list_options", {}),
                ("set_current_situation", {"today": COROLLA_CROSS_TODAY}),
            ):
                done = client.post(f"/api/sessions/{no_today}/tools/{name}", json=body)
                assert done.json()["ok"], done.text
            e001 = run(E001.employee_messages)
            inbox = client.get("/api/tickets", params={"status": "open"}, headers=REP).json()
            (ticket,) = inbox
            answer_url = f"/api/tickets/{ticket['id']}/answer"
            refused = client.post(
                answer_url,
                json={"values": {"alternative_participation:CAR-10": "-50"}},
                headers=REP,
            )
            assert refused.status_code == 422
            client.post(
                answer_url,
                json={"values": {"alternative_participation:CAR-10": 350}},
                headers=REP,
            )
            assert agent.wait_idle(30)
            OUT.mkdir(parents=True, exist_ok=True)
            outputs: dict[str, Any] = {
                "walkthrough": _events(app, walkthrough),
                "e001": _events(app, e001),
                "options": _events(app, options),
                "options_without_today": _events(app, no_today),
                "e001_inbox": inbox,  # GET /api/tickets?status=open before the answer
                "e001_answer_negative": refused.json(),  # the 422 body for -50
                "guard_retry": _guard_retry_log(),
            }
            outputs["questions_inbox"], outputs["questions"] = _questions_log()
            for name, data in outputs.items():
                path = OUT / f"{name}.json"
                text = json.dumps(data, ensure_ascii=False, indent=1)
                path.write_text(text + "\n", encoding="utf-8", newline="\n")
                print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

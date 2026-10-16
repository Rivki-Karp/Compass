"""Record real session event logs for the web UI's tests (web/src/test/fixtures/*.json).

    uv run python scripts/web_fixtures.py

Runs the two demo scripts (walkthrough, E-001 with the representative's answer) through the
real API in demo mode (scripted model, real tools, guard and tickets) and saves each session's
events as the admin stream sends them. Ids and timestamps differ per run; the numbers don't.

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

OUT = REPO_ROOT / "web" / "src" / "test" / "fixtures"
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


def main() -> int:
    demo_llm.DEMO_DELAY_SECONDS = 0
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(app_db=Path(tmp) / "app.db", llm="scripted", rep_token="rep")
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
                "e001_inbox": inbox,  # GET /api/tickets?status=open before the answer
                "e001_answer_negative": refused.json(),  # the 422 body for -50
                "guard_retry": _guard_retry_log(),
            }
            for name, data in outputs.items():
                path = OUT / f"{name}.json"
                text = json.dumps(data, ensure_ascii=False, indent=1)
                path.write_text(text + "\n", encoding="utf-8", newline="\n")
                print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

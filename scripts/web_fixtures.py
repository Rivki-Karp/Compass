"""Record real session event logs for the web UI's tests (web/src/test/fixtures/*.json).

    uv run python scripts/web_fixtures.py

Runs the two demo scripts (walkthrough, E-001 with the representative's answer) through the
real API in demo mode (scripted model, real tools, guard and tickets) and saves each session's
events as the admin stream sends them. Ids and timestamps differ per run; the numbers don't.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from compass.agent import demo_llm
from compass.agent.demo_llm import E001, WALKTHROUGH
from compass.api import Settings, create_app
from compass.config import REPO_ROOT

OUT = REPO_ROOT / "web" / "src" / "test" / "fixtures"
REP = {"Authorization": "Bearer rep"}


def _events(app: Any, sid: str) -> list[dict[str, Any]]:
    return [e.model_dump() for e in app.state.services.store.events_after(sid)]


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
            }
            for name, data in outputs.items():
                path = OUT / f"{name}.json"
                text = json.dumps(data, ensure_ascii=False, indent=1)
                path.write_text(text + "\n", encoding="utf-8", newline="\n")
                print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

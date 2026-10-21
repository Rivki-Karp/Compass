"""The labels of "מאיפה המספר הזה?" never overclaim: a computed output is "חושב בשרת", "לפי הכללים"
is only for the company rules' own values, and only a computing tool is "חושב בכלי X". The table
at the bottom pins every number of the walkthrough and of E-001 with the representative."""

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_number_sources import REPLY, turn

from compass.agent import demo_llm
from compass.agent.demo_llm import E001, WALKTHROUGH
from compass.agent.guard import Allowed, check_text
from compass.agent.number_sources import Context, build_number_sources
from compass.api import Settings, create_app
from compass.state import Store
from compass.tools.services import Services

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_the_new_chips_pass_the_contrast_check() -> None:
    """computed = navy on light steel, rule = teal on light teal: at least 4.5:1."""
    css = (FRONTEND / "index.css").read_text(encoding="utf-8")
    for name in ("computed", "rule"):
        text = re.search(rf"--color-chip-{name}: (#\w{{6}})", css)
        fill = re.search(rf"--color-chip-{name}-bg: (#\w{{6}})", css)
        assert text and fill, name
        light, dark = sorted((_luminance(text[1]), _luminance(fill[1])), reverse=True)
        assert (light + 0.05) / (dark + 0.05) >= 4.5, name


def test_a_tool_that_only_echoes_data_is_never_a_computation() -> None:
    allowed = Allowed()
    allowed.add_json({"base_salary": 18500, "budget": 3700, "n": 4321}, "save_profile")
    allowed.add_json({"price": 250000}, "search_catalog")
    allowed.add_json({"group": 12345}, "lookup_occupation")
    text = "שכר 18,500 ₪, תקציב 3,700 ₪, מחיר 250,000 ₪, קבוצה 12,345, ועוד 4,321 ₪."
    salary = {"id": "base_salary", "label": "שכר בסיס", "unit": "ils"}
    context = Context(
        inputs=[{**salary, "value": 18500, "source": "employee_input"}],
        budget={"value": 3700, "group": "ב", "from_occupation": False},
    )
    records = build_number_sources(text, check_text(text, allowed).spans, [], 0, context)
    got = {text[r["start"] : r["end"]]: r for r in records}
    assert set(got) == {"18,500", "3,700", "250,000", "12,345"}  # 4,321: nothing says what it is
    seen = {k: (v["chip"], v["origin"]["label"]) for k, v in got.items()}
    assert seen == {
        "18,500": ("employee_input", "לפי דבריך"),
        "3,700": ("rule", "לפי כללי החברה · קבוצה ב׳"),
        "250,000": ("catalog_default", "מהקטלוג"),
        "12,345": ("occupation", "לפי העיסוק"),
    }
    assert not any("חושב" in r["origin"]["label"] for r in records)


def test_list_options_numbers_are_the_servers_option_set() -> None:
    allowed = Allowed()
    allowed.add_json({"options": [{"net": 12345}]}, "list_options")
    text = "הנטו באפשרות הזו: 12,345 ₪."
    (record,) = build_number_sources(text, check_text(text, allowed).spans, [], 0)
    assert (record["chip"], record["kind"]) == ("computed", "server")
    assert record["origin"]["label"] == "חושב בשרת · רשימת החלופות"


def test_the_option_set_view_is_searched_too(services: Services) -> None:
    _, events = turn(services, REPLY)
    ready = [e for e in events if e.type == "comparison_ready"][-1]
    view = {**ready.payload["view"], "alternative_net": 12345, "computed_by": {"origin": "server"}}
    forged = ready.model_copy(
        update={
            "type": "comparison_set_ready",
            "seq": ready.seq + 100,
            "payload": {"origin": "server", "options": [{"alternative": {}, "view": view}]},
        }
    )
    allowed = Allowed()
    allowed.add_json({"options": [{"net": 12345}]}, "list_options")
    text = "הנטו באפשרות הזו: 12,345 ₪."
    (record,) = build_number_sources(text, check_text(text, allowed).spans, [forged], 0)
    assert record["what"] == "נטו בחודש, בחלופה" and record["chip"] == "computed"
    assert record["ref"]["option_set_seq"] == forged.seq
    assert record["origin"]["label"] == "חושב בשרת · רשימת החלופות"


# --- the table: the walkthrough and E-001 with the representative ---------------------------

COMPARE = "חושב בכלי compare · בשרת, בלי מודל"
EMPLOYEE = "לפי דבריך, בהודעה מ־{time}"
REP = "אושר על ידי נציג, {time}"
# (the number as written, its chip, its origin label), in the order of the replies
WALKTHROUGH_TABLE = [
    ("3,700", "rule", "לפי כללי החברה · קבוצה ב׳ לפי העיסוק"),
    ("11,000", "computed", COMPARE),
    ("13,914", "computed", COMPARE),
    ("+2,914", "computed", COMPARE),
]
E001_TABLE = [
    ("4,500", "rule", "לפי כללי החברה · קבוצה ג׳ לפי העיסוק"),
    ("300", "employee_input", EMPLOYEE),
    ("300", "employee_input", EMPLOYEE),
    ("661", "computed", COMPARE),
    ("350", "representative", REP),
    ("11,032", "computed", COMPARE),
    ("11,643", "computed", COMPARE),
    ("+611", "computed", COMPARE),
]


@pytest.fixture
def demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(demo_llm, "DEMO_DELAY_SECONDS", 0.0)
    settings = Settings(
        app_db=tmp_path / "app.db", llm="scripted", rep_token="rep", number_sources=True
    )
    with TestClient(create_app(settings)) as client:
        yield client


def _table(client: TestClient, sid: str) -> list[tuple[str, str, str]]:
    store = client.app.state.services.store  # type: ignore[attr-defined]
    rows: list[tuple[str, str, str]] = []
    views: list[dict[str, Any]] = []
    for event in store.events_after(sid):
        if event.type == "comparison_ready":
            views.append(event.payload["view"])
        if event.type != "assistant_message":
            continue
        text = event.payload["text"]
        outputs = {
            abs(v)
            for view in views
            for v in (view["display_diff"], view["today_net"], view["alternative_net"])
            if v is not None
        }
        for r in event.payload["number_sources"]:
            shown = text[r["start"] : r["end"]]
            rows.append((shown, r["chip"], r["origin"]["label"]))
            # a computed output never wears the rules' or any other chip ...
            if abs(Decimal(r["value"])) in outputs:
                assert r["chip"] == "computed" and r["kind"] in ("tool", "server"), (shown, r)
            # ... only compare is ever "חושב בכלי" ...
            if r["origin"]["label"].startswith("חושב בכלי"):
                assert r["chip"] == "computed" and r["origin"]["tool"] == "compare", (shown, r)
            # ... and "לפי הכללים" is only ever a rule
            assert (r["chip"] == "rule") == (r["kind"] == "rule"), (shown, r)
    return rows


def _say(client: TestClient, sid: str, *texts: str) -> None:
    for text in texts:
        client.post(f"/api/sessions/{sid}/messages", json={"text": text})
        assert client.app.state.agent.wait_idle(20)  # type: ignore[attr-defined]


def test_the_walkthrough_table(demo: TestClient) -> None:
    sid = demo.post("/api/sessions").json()["id"]
    _say(demo, sid, *WALKTHROUGH.employee_messages)
    assert _table(demo, sid) == WALKTHROUGH_TABLE


def test_the_e001_rep_flow_table(demo: TestClient) -> None:
    sid = demo.post("/api/sessions").json()["id"]
    _say(demo, sid, *E001.employee_messages)
    headers = {"Authorization": "Bearer rep"}
    (ticket,) = demo.get("/api/tickets", params={"status": "open"}, headers=headers).json()
    answer = demo.post(
        f"/api/tickets/{ticket['id']}/answer",
        json={"values": {"alternative_participation:CAR-10": 350}},
        headers=headers,
    )
    assert answer.status_code == 200
    assert demo.app.state.agent.wait_idle(20)  # type: ignore[attr-defined]
    assert _table(demo, sid) == E001_TABLE

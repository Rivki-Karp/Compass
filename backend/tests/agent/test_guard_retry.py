"""The guard's retry (live finding, 2026-10-20): a draft that asked "כמה ילדים מתחת לגיל 23?"
was rejected for the unsourced 23 (correct: no source, and the guard stays strict), the retry
repeated the 23, and the employee got the template. The retry message must name the exact
rejected numbers and say to rephrase without them, a number inside a question included; then a
clean second draft is sent, with no template. Real guard, scripted model."""

from pathlib import Path

from test_runner import make_runner, say

from compass.agent.guard import make_guard
from compass.agent.llm import text_response
from compass.agent.transcript import guard_note
from compass.state import Store
from compass.tools.services import Services

DRAFT = "רשמתי את השכר. כמה ילדים מתחת לגיל 23 יש לך?"
CLEAN = "רשמתי את השכר. כמה ילדים צעירים יש לך, כאלה שעדיין לומדים או משרתים?"


def test_the_retry_names_the_number_and_the_second_clean_draft_is_sent(tmp_path: Path) -> None:
    services = Services(Store(tmp_path / "app.db"))
    sid = services.store.create_session()
    runner, llm = make_runner(
        services,
        [text_response(DRAFT), text_response(CLEAN)],
        guard=make_guard(services.store),
        template=lambda session_id: "TEMPLATE",
    )
    say(runner, sid, "אני מנהלת מוצר, שכר בסיס 18500")

    outcome = runner.last_outcome[sid]
    assert (outcome.kind, outcome.text) == ("reply", CLEAN)  # no template
    assert [v.passed for v in outcome.guard] == [False, True]
    assert outcome.guard[0].violations == ["23"]  # strict: 23 has no source, no allowlist

    retry = llm.calls[1]
    note = retry.messages[-1]
    assert note["role"] == "system" and retry.tool_choice == {"type": "none"}
    assert "23" in note["content"]  # the exact rejected number
    assert "WITHOUT these exact numbers" in note["content"]
    assert "ask that question in words with no number" in note["content"]
    assert all(DRAFT not in str(m) for m in retry.messages[:-1])  # the draft was never kept

    shown = [
        e.payload["text"] for e in services.store.events_after(sid) if e.type == "assistant_message"
    ]
    assert shown == [CLEAN]  # the employee only ever saw the checked reply
    actions = [
        e.payload["action"] for e in services.store.events_after(sid) if e.type == "guard_check"
    ]
    assert actions == ["retry", "accept_after_retry"]


def test_guard_note_lists_every_rejected_number() -> None:
    note = guard_note(["23", "2,915", "+300"])
    for number in ("23", "2,915", "+300"):
        assert number in note
    assert "NOT shown" in note and "Do not compute or estimate" in note

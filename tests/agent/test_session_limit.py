"""The session safety limit (Day 5 Stage 3, replaces drop_block): a cap on agent turns and on
input tokens per session. Reached -> a fixed reply, no model call, no guard; a new session works."""

from pathlib import Path
from typing import Any

import pytest

from compass.agent.llm import ScriptedClient, Usage, text_response
from compass.agent.runner import SESSION_LIMIT_HE, ClaudeAgentRunner, GuardVerdict
from compass.api.settings import (
    DEFAULT_MAX_SESSION_INPUT_TOKENS,
    DEFAULT_MAX_SESSION_TURNS,
    Settings,
    SettingsError,
)
from compass.state import Store
from compass.tools import ToolRunner
from compass.tools.services import Services
from compass.tools.tickets import answer_ticket


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


class RecordingGuard:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def __call__(self, text: str, session_id: str) -> GuardVerdict:
        self.texts.append(text)
        return GuardVerdict(passed=True)


def make_runner(
    services: Services, steps: list[Any], **kwargs: Any
) -> tuple[ClaudeAgentRunner, ScriptedClient, RecordingGuard]:
    llm, guard = ScriptedClient(steps), RecordingGuard()
    runner = ClaudeAgentRunner(services, llm, "SYSTEM", guard=guard, background=False, **kwargs)
    return runner, llm, guard


def say(runner: ClaudeAgentRunner, sid: str, text: str) -> None:
    runner.on_user_message(sid, runner.store.add_message(sid, "user", {"text": text}))


def replies(services: Services, sid: str) -> list[tuple[str, str]]:
    return [
        (e.payload["kind"], e.payload["text"])
        for e in services.store.events_after(sid)
        if e.type == "assistant_message"
    ]


def triggers(services: Services, sid: str) -> int:
    return sum(
        1
        for m in services.store.messages(sid)
        if m.role == "system_event" and m.content.get("kind") in ("employee_turn", "rep_answer")
    )


def test_the_message_is_fixed_polite_and_has_no_numbers() -> None:
    assert SESSION_LIMIT_HE == "השיחה הגיעה לאורך המרבי. אפשר להתחיל שיחה חדשה."
    assert not any(ch.isdigit() for ch in SESSION_LIMIT_HE)


def test_turn_cap_stops_calling_the_model(services: Services) -> None:
    runner, llm, guard = make_runner(
        services, [text_response("שלום"), text_response("שוב שלום")], max_session_turns=2
    )
    sid = services.store.create_session()
    say(runner, sid, "א")
    say(runner, sid, "ב")
    assert len(llm.calls) == 2 and len(guard.texts) == 2

    say(runner, sid, "ג")
    say(runner, sid, "ד")  # and stays stopped
    assert len(llm.calls) == 2  # no model call
    assert len(guard.texts) == 2  # the guard is not involved
    assert replies(services, sid)[-2:] == [("limit", SESSION_LIMIT_HE)] * 2
    outcome = runner.last_outcome[sid]
    assert (outcome.kind, outcome.limit, outcome.text) == ("limit", "turns", SESSION_LIMIT_HE)
    assert triggers(services, sid) == 2  # the transcript (model input) did not grow

    types = [e.type for e in services.store.events_after(sid)]
    assert "agent_error" not in types and "guard_check" in types  # only the two real runs
    finished = [e.payload for e in services.store.events_after(sid) if e.type == "agent_finished"]
    assert [f["outcome"] for f in finished] == ["reply", "reply", "limit", "limit"]
    assert finished[-1]["limit"] == "turns" and finished[-1]["usage"]["input_tokens"] == 0
    # every limited run still starts and finishes, so the UI's thinking state closes
    assert types.count("agent_started") == types.count("agent_finished") == 4


def test_input_token_cap_counts_cached_input_and_guard_retries(services: Services) -> None:
    big = Usage(input_tokens=400, cache_read_input_tokens=500, cache_creation_input_tokens=100)
    runner, llm, guard = make_runner(
        services,
        [text_response("ראשון", usage=big), text_response("שני")],
        max_session_input_tokens=1_000,
    )
    sid = services.store.create_session()
    say(runner, sid, "א")  # 1,000 input tokens: the cap
    say(runner, sid, "ב")
    assert len(llm.calls) == 1 and len(guard.texts) == 1
    assert replies(services, sid)[-1] == ("limit", SESSION_LIMIT_HE)
    assert runner.last_outcome[sid].limit == "input_tokens"


def test_under_the_caps_nothing_changes(services: Services) -> None:
    runner, llm, _ = make_runner(
        services,
        [text_response("א", usage=Usage(input_tokens=999))],
        max_session_turns=2,
        max_session_input_tokens=1_000,
    )
    sid = services.store.create_session()
    say(runner, sid, "שלום")
    assert len(llm.calls) == 1 and replies(services, sid) == [("reply", "א")]


def test_a_rep_answer_after_the_limit_gets_the_same_reply(services: Services) -> None:
    runner, llm, _ = make_runner(services, [text_response("שלום")], max_session_turns=1)
    sid = services.store.create_session()
    say(runner, sid, "א")
    opened = ToolRunner(services).run(
        sid, "ask_representative", {"question": "?", "blocking_fields": ["study_fund_percent"]}
    )
    assert opened["ok"], opened
    answer_ticket(services, opened["ticket_id"], values={"study_fund_percent": "2.5"})
    runner.on_ticket_answered(sid, opened["ticket_id"])
    assert len(llm.calls) == 1
    assert replies(services, sid)[-1] == ("limit", SESSION_LIMIT_HE)


def test_a_new_session_works(services: Services) -> None:
    runner, llm, _ = make_runner(
        services, [text_response("ראשונה"), text_response("חדשה")], max_session_turns=1
    )
    old = services.store.create_session()
    say(runner, old, "א")
    say(runner, old, "ב")
    assert replies(services, old)[-1][0] == "limit"

    new = services.store.create_session()
    say(runner, new, "שלום")
    assert len(llm.calls) == 2
    assert replies(services, new) == [("reply", "חדשה")]


def test_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COMPASS_MAX_SESSION_TURNS", "COMPASS_MAX_SESSION_INPUT_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings.from_env(env_file=None)
    assert defaults.max_session_turns == DEFAULT_MAX_SESSION_TURNS == 40
    assert defaults.max_session_input_tokens == DEFAULT_MAX_SESSION_INPUT_TOKENS

    monkeypatch.setenv("COMPASS_MAX_SESSION_TURNS", "5")
    monkeypatch.setenv("COMPASS_MAX_SESSION_INPUT_TOKENS", "123456")
    settings = Settings.from_env(env_file=None)
    assert (settings.max_session_turns, settings.max_session_input_tokens) == (5, 123456)

    monkeypatch.setenv("COMPASS_MAX_SESSION_TURNS", "0")
    with pytest.raises(SettingsError, match="COMPASS_MAX_SESSION_TURNS"):
        Settings.from_env(env_file=None)


def test_the_factory_passes_the_caps(services: Services) -> None:
    from compass.agent.factory import build_claude_runner

    settings = Settings(app_db=Path("unused.db"), max_session_turns=7, max_session_input_tokens=99)
    runner = build_claude_runner(settings, services, llm=ScriptedClient([]), background=False)
    assert (runner.max_session_turns, runner.max_session_input_tokens) == (7, 99)

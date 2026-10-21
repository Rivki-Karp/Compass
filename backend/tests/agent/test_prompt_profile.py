"""The remembered-details section of the system prompt: only with COMPASS_PROFILE_MEMORY=1 and
accounts. With the flag off the prompt is byte for byte what it was, with or without the
payslip section."""

from pathlib import Path

from compass.agent.factory import build_claude_runner
from compass.agent.llm import ScriptedClient
from compass.agent.prompts import (
    PAYSLIP_SECTION,
    PROFILE_SECTION,
    SYSTEM_PROMPT,
    load_system_prompt,
)
from compass.api import Settings
from compass.state import Store
from compass.tools import Services

SECTION = PROFILE_SECTION.read_text(encoding="utf-8").strip()
PAYSLIP = PAYSLIP_SECTION.read_text(encoding="utf-8").strip()


def test_flag_off_is_what_it_was_byte_for_byte() -> None:
    raw = SYSTEM_PROMPT.read_text(encoding="utf-8").strip()
    assert load_system_prompt().encode() == raw.encode()
    assert load_system_prompt(payslip=True) == raw + "\n\n" + PAYSLIP
    assert SECTION not in load_system_prompt(payslip=True)


def test_flag_on_adds_the_section_after_the_rest() -> None:
    base = load_system_prompt(payslip=True)
    assert load_system_prompt(payslip=True, profile=True) == base + "\n\n" + SECTION
    assert load_system_prompt(profile=True).startswith(load_system_prompt())


def test_the_section_says_what_the_owner_approved() -> None:
    assert 'התווית "משיחה קודמת"' in SECTION and "profile_notification" in SECTION
    assert "אל תשאל שוב" in SECTION  # no re-asking what was confirmed
    assert "אל תשתמש, תצטט או תנחש ערך שלא אושר" in SECTION
    assert "לעולם אל תכתוב שאין לך גישה" in SECTION
    assert len(SECTION.splitlines()) <= 8  # short


def test_the_runner_gets_the_prompt_for_its_flag(tmp_path: Path) -> None:
    def prompt(**values: object) -> str:
        settings = Settings(app_db=tmp_path / "a.db", **values)  # type: ignore[arg-type]
        services = Services(Store(settings.app_db))
        return build_claude_runner(settings, services, llm=ScriptedClient([])).system_prompt

    assert SECTION in prompt(auth=True, profile_memory=True)
    assert SECTION not in prompt(auth=True)
    assert SECTION not in prompt(profile_memory=True)  # no accounts: inert
    assert prompt() == load_system_prompt()

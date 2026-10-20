"""The payslip section of the system prompt: only with COMPASS_PAYSLIP=1. With it off the prompt
is the system prompt file and nothing else, byte for byte (the flag-off guarantee)."""

from pathlib import Path

from compass.agent.factory import build_claude_runner
from compass.agent.llm import ScriptedClient
from compass.agent.prompts import PAYSLIP_SECTION, SYSTEM_PROMPT, load_system_prompt
from compass.api import Settings
from compass.state import Store
from compass.tools import Services

SECTION = PAYSLIP_SECTION.read_text(encoding="utf-8").strip()


def test_flag_off_is_the_system_prompt_file_byte_for_byte() -> None:
    raw = SYSTEM_PROMPT.read_text(encoding="utf-8").strip()
    assert load_system_prompt().encode() == raw.encode()
    assert load_system_prompt(payslip=False) == load_system_prompt()


def test_flag_off_has_no_payslip_section() -> None:
    assert SECTION not in load_system_prompt()


def test_flag_on_is_the_same_prompt_plus_the_section() -> None:
    on = load_system_prompt(payslip=True)
    assert on == load_system_prompt() + "\n\n" + SECTION
    assert on.startswith(load_system_prompt())  # the cached prefix is untouched


def test_the_section_says_what_the_owner_approved() -> None:
    assert "פעם אחת" in SECTION  # may be mentioned once, when salary details are missing
    assert 'התווית "לפי התלוש"' in SECTION and "payslip_notification" in SECTION
    assert "אל תבקש את הקובץ בצ'אט" in SECTION
    assert "אינם ערכים מאושרים" in SECTION  # pasted payslip numbers are not confirmed
    assert len(SECTION.splitlines()) <= 8  # short


def test_the_runner_gets_the_prompt_for_its_flag(tmp_path: Path) -> None:
    services = Services(Store(tmp_path / "app.db"))
    for flag in (False, True):
        runner = build_claude_runner(
            Settings(app_db=tmp_path / "app.db", payslip=flag),
            services,
            llm=ScriptedClient([]),
            background=False,
        )
        assert runner.system_prompt == load_system_prompt(payslip=flag)


def test_the_section_offers_the_upload_once_in_the_first_salary_question() -> None:
    """Item 1: the first reply that asks for salary data offers the upload, once; and with the
    upload on, the base prompt's "if the employee offers a document, say they can just write the
    data here" gives way to the paperclip."""
    assert "בתשובה הראשונה שלך שמבקשת נתוני שכר" in SECTION
    assert "פעם אחת בלבד בכל השיחה" in SECTION
    assert "אל תחזור על ההצעה" in SECTION
    assert "כלל זה גובר" in SECTION and "אם העובד מציע לשלוח מסמך" in SECTION
    # the flag-off prompt is untouched: it still says to write the data in the chat
    assert "אם העובד מציע לשלוח מסמך" in load_system_prompt()
    assert "הפנה לכפתור האטב" not in load_system_prompt()


def test_the_section_tells_the_agent_what_to_say_about_a_field_not_found() -> None:
    """Item 2: no "I have no access to the payslip" when a field was simply not found."""
    for key in ("not_in_payslip", "unreadable", "removed_by_employee"):
        assert key in SECTION
    assert "לא הצלחתי לקרוא בתלוש את אחוז הפנסיה" in SECTION
    assert "לעולם אל תכתוב שאין לך גישה לתלוש" in SECTION

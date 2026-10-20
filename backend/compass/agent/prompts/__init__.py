"""Versioned prompt files. The system prompt is read once per runner and never changes within
a session (it is part of the cached, thinking-bound prefix)."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
SYSTEM_PROMPT = PROMPTS_DIR / "system_he.md"
OPENING_MESSAGE = PROMPTS_DIR / "opening_he.md"
# A short section, added only when COMPASS_PAYSLIP=1; with it off the prompt is exactly the
# system prompt file, byte for byte (tests/agent/test_prompt_payslip.py).
PAYSLIP_SECTION = PROMPTS_DIR / "system_payslip_he.md"


def load_system_prompt(path: Path = SYSTEM_PROMPT, *, payslip: bool = False) -> str:
    prompt = path.read_text(encoding="utf-8").strip()
    if not payslip:
        return prompt
    return prompt + "\n\n" + PAYSLIP_SECTION.read_text(encoding="utf-8").strip()


def opening_message(path: Path = OPENING_MESSAGE) -> str:
    """The fixed greeting the UI / terminal shows before the first employee message."""
    return path.read_text(encoding="utf-8").strip()

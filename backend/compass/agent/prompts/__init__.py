"""Versioned prompt files. The system prompt is read once per runner and never changes within
a session (it is part of the cached, thinking-bound prefix)."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
SYSTEM_PROMPT = PROMPTS_DIR / "system_he.md"
OPENING_MESSAGE = PROMPTS_DIR / "opening_he.md"


def load_system_prompt(path: Path = SYSTEM_PROMPT) -> str:
    return path.read_text(encoding="utf-8").strip()


def opening_message(path: Path = OPENING_MESSAGE) -> str:
    """The fixed greeting the UI / terminal shows before the first employee message."""
    return path.read_text(encoding="utf-8").strip()

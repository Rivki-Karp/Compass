"""Start-up checks shared by `tasks.py chat` and `tasks.py eval`."""

import sys
from pathlib import Path

from compass.api.settings import Settings, SettingsError
from compass.config import ENV_FILE

MISSING_KEY_MESSAGE = """\
חסר מפתח API של Claude. הוסיפו את השורה ANTHROPIC_API_KEY=... לקובץ .env
(העתיקו את .env.example אם הקובץ עוד לא קיים) והריצו שוב.

ANTHROPIC_API_KEY is not set. Add ANTHROPIC_API_KEY=... to the .env file
(copy .env.example if you don't have one yet) and run again."""


def load_agent_settings(env_file: Path | None = ENV_FILE) -> Settings:
    """Settings for chat / eval, or a clear message and exit code 2 (never a stack trace).

    The key itself is never printed.
    """
    try:
        settings = Settings.from_env(env_file=env_file)
    except SettingsError as error:
        print(f"הגדרה לא תקינה ב-.env / Invalid setting: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    if not settings.anthropic_api_key:
        print(MISSING_KEY_MESSAGE, file=sys.stderr)
        raise SystemExit(2)
    return settings

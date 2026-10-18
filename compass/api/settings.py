"""API settings, from the environment (COMPASS_*) or passed explicitly (tests).

`from_env()` also reads the repo's .env file, so no shell (PowerShell, cmd, bash) needs
variables set by hand. A variable set in the real environment wins over the file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from compass.config import (
    ALIASES_YAML,
    APP_DB,
    DEMO_DB,
    ENV_FILE,
    REPO_ROOT,
    RULES_YAML,
    VEHICLES_DB,
    WEB_DIST,
)


def _path(value: str | None, default: Path) -> Path:
    """Relative paths are relative to the repo root, not the current directory."""
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAX_TOOL_ROUNDS = 8


class SettingsError(ValueError):
    """A setting in .env or the environment has an invalid value."""


def _positive_int(value: str | None, name: str) -> int:
    if not value:
        return DEFAULT_MAX_TOOL_ROUNDS
    try:
        number = int(value)
    except ValueError:
        raise SettingsError(f"{name} must be a whole number (got {value!r})") from None
    if number < 1:
        raise SettingsError(f"{name} must be at least 1 (got {number})")
    return number


LLM_CHOICES = ("anthropic", "scripted")


def _llm(value: str | None) -> str:
    """COMPASS_LLM: "anthropic" (default: Claude, needs ANTHROPIC_API_KEY) or "scripted" (demo
    mode: the scripted model, no key, no network)."""
    if not value:
        return "anthropic"
    if value not in LLM_CHOICES:
        raise SettingsError(f"COMPASS_LLM must be one of {', '.join(LLM_CHOICES)} (got {value!r})")
    return value


DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")  # Vite dev server


def _env(env_file: Path | None) -> dict[str, str]:
    file_values = {} if env_file is None or not env_file.is_file() else dotenv_values(env_file)
    # The real environment wins; an empty variable counts as unset (so `KEY=` in a shell
    # doesn't hide the value in .env).
    return {k: v for k, v in file_values.items() if v} | {k: v for k, v in os.environ.items() if v}


def demo_db_from_env(env_file: Path | None = ENV_FILE) -> Path:
    """Demo mode's database: COMPASS_DEMO_DB, default data/demo.db. Never app.db."""
    path = _path(_env(env_file).get("COMPASS_DEMO_DB"), DEMO_DB)
    if path.resolve() == APP_DB.resolve():
        raise SettingsError(f"COMPASS_DEMO_DB must not be {APP_DB.name}")
    return path


@dataclass(frozen=True)
class Settings:
    app_db: Path = APP_DB
    rules_path: Path = RULES_YAML
    aliases_path: Path = ALIASES_YAML
    vehicles_db: Path = VEHICLES_DB
    # The built web UI, served at / with an SPA fallback when its index.html exists.
    web_dist: Path | None = WEB_DIST
    # POST /api/sessions/{id}/tools/{name}: dev / demo only.
    dev_tools: bool = False
    cors_origins: tuple[str, ...] = field(default=DEFAULT_CORS_ORIGINS)
    heartbeat_seconds: float = 15.0
    # Shared bearer tokens. Unset -> the guarded endpoints answer 503 (never open by default).
    rep_token: str | None = field(default=None, repr=False)  # /api/tickets*
    admin_token: str | None = field(default=None, repr=False)  # /api/admin/*
    # The agent (Claude). No key -> the API runs with NullAgentRunner; chat/eval refuse to start.
    anthropic_api_key: str | None = field(default=None, repr=False)  # never printed
    model: str = DEFAULT_MODEL
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    # "anthropic" or "scripted" (demo mode: compass/agent/demo_llm.py).
    llm: str = "anthropic"

    def __post_init__(self) -> None:
        # Demo mode has its own database (data/demo.db, wiped by `tasks.py demo-reset`); it
        # must never read or write the real sessions in app.db.
        if self.llm == "scripted" and self.app_db.resolve() == APP_DB.resolve():
            raise SettingsError(
                f"demo mode (COMPASS_LLM=scripted) must not use {APP_DB.name}; "
                "it uses COMPASS_DEMO_DB (default data/demo.db)"
            )

    @classmethod
    def from_env(cls, env_file: Path | None = ENV_FILE) -> "Settings":
        env = _env(env_file)
        origins = env.get("COMPASS_CORS_ORIGINS")
        llm = _llm(env.get("COMPASS_LLM"))
        return cls(
            # Demo mode never touches app.db: COMPASS_APP_DB is ignored there.
            app_db=demo_db_from_env(env_file)
            if llm == "scripted"
            else _path(env.get("COMPASS_APP_DB"), APP_DB),
            rules_path=_path(env.get("COMPASS_RULES"), RULES_YAML),
            web_dist=_path(env.get("COMPASS_WEB_DIST"), WEB_DIST),
            dev_tools=env.get("COMPASS_DEV_TOOLS") == "1",
            rep_token=env.get("COMPASS_REP_TOKEN") or None,
            admin_token=env.get("COMPASS_ADMIN_TOKEN") or None,
            anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
            model=env.get("COMPASS_MODEL") or DEFAULT_MODEL,
            llm=llm,
            max_tool_rounds=_positive_int(
                env.get("COMPASS_MAX_TOOL_ROUNDS"), "COMPASS_MAX_TOOL_ROUNDS"
            ),
            cors_origins=tuple(o.strip() for o in origins.split(","))
            if origins
            else DEFAULT_CORS_ORIGINS,
        )

"""API settings, from the environment (COMPASS_*) or passed explicitly (tests).

`from_env()` also reads backend/.env, so no shell (PowerShell, cmd, bash) needs
variables set by hand. A variable set in the real environment wins over the file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from compass.config import (
    ALIASES_YAML,
    APP_DB,
    BACKEND_ROOT,
    DEMO_DB,
    ENV_FILE,
    RULES_YAML,
    VEHICLES_DB,
    WEB_DIST,
)


def _path(value: str | None, default: Path) -> Path:
    """Relative paths are relative to backend/, not the current directory."""
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else BACKEND_ROOT / path


DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAX_TOOL_ROUNDS = 8
# The session safety limit (Day 5, replaces drop_block): after this many agent runs, or this many
# input tokens (uncached + cache read + cache write, summed over every model call), the session
# gets a fixed reply and no more model calls. The longest eval conversation (e001_rep_flow, 4
# turns) used about 114k input tokens, so 2M is about 17 times that (roughly $1 at its rate).
DEFAULT_MAX_SESSION_TURNS = 40
DEFAULT_MAX_SESSION_INPUT_TOKENS = 2_000_000
# Live mode (round 2, item 6): all model calls on the server, per UTC day; then a fixed reply.
DEFAULT_DAILY_SPEND_CAP_USD = 5.0
# POST /api/sessions/{id}/messages per client IP per minute.
DEFAULT_MESSAGE_RATE_PER_MINUTE = 20


class SettingsError(ValueError):
    """A setting in .env or the environment has an invalid value."""


def _positive_int(value: str | None, name: str, default: int) -> int:
    if not value:
        return default
    try:
        number = int(value)
    except ValueError:
        raise SettingsError(f"{name} must be a whole number (got {value!r})") from None
    if number < 1:
        raise SettingsError(f"{name} must be at least 1 (got {number})")
    return number


def _positive_float(value: str | None, name: str, default: float) -> float:
    if not value:
        return default
    try:
        number = float(value)
    except ValueError:
        raise SettingsError(f"{name} must be a number (got {value!r})") from None
    if not number > 0:
        raise SettingsError(f"{name} must be above 0 (got {number})")
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


# Cross-origin callers (the UI on Cloudflare Pages): none by default, same origin only. In dev the
# Vite proxy keeps the browser on one origin, so it needs none either.
DEFAULT_CORS_ORIGINS: tuple[str, ...] = ()


def _cors_origins(value: str | None) -> tuple[str, ...]:
    """COMPASS_CORS_ORIGINS: a comma-separated list of exact origins, never a wildcard."""
    origins = tuple(o.strip() for o in (value or "").split(",") if o.strip())
    if any("*" in o for o in origins):
        raise SettingsError("COMPASS_CORS_ORIGINS takes exact origins, never a wildcard")
    return origins or DEFAULT_CORS_ORIGINS


def _env(env_file: Path | None) -> dict[str, str]:
    # COMPASS_ENV_ONLY=1 (the container image sets it): the environment only, never a file.
    if os.environ.get("COMPASS_ENV_ONLY") == "1":
        env_file = None
    file_values = {} if env_file is None or not env_file.is_file() else dotenv_values(env_file)
    # The real environment wins; an empty variable counts as unset (so `KEY=` in a shell
    # doesn't hide the value in .env).
    return {k: v for k, v in file_values.items() if v} | {k: v for k, v in os.environ.items() if v}


# An empty token leaves its screen unusable (503); say so at startup, never with the value.
TOKEN_USES = {
    "COMPASS_REP_TOKEN": "the representative screen (/rep)",
    "COMPASS_ADMIN_TOKEN": "judges mode",
}


def token_warnings(rep_token: str | None, admin_token: str | None) -> list[str]:
    """One line per empty token: which screen it disables and where the fix is. Never a value."""
    given = {"COMPASS_REP_TOKEN": rep_token, "COMPASS_ADMIN_TOKEN": admin_token}
    return [
        f"{name} is empty: {use} cannot be used. Generate a token and set it in .env "
        "(see docs/demo-runbook.md, section 1)."
        for name, use in TOKEN_USES.items()
        if not given[name]
    ]


# Demo mode's well-known tokens (tasks.py demo, docker compose --profile demo) and the
# .env.example placeholders: fine for a local demo, never for a live server.
KNOWN_TOKENS = frozenset({"rep-demo", "admin-demo", "rep-demo-change-me", "admin-demo-change-me"})


def live_token_errors(settings: "Settings") -> list[str]:
    """Why a live server (COMPASS_LLM=anthropic) must not start: an empty token, or a demo /
    placeholder one. Demo mode (scripted) has none. Never includes a token's value."""
    if settings.llm == "scripted":
        return []
    given = {"COMPASS_REP_TOKEN": settings.rep_token, "COMPASS_ADMIN_TOKEN": settings.admin_token}
    errors = []
    for name, value in given.items():
        if not value:
            errors.append(f"{name} is empty")
        elif value in KNOWN_TOKENS:
            errors.append(f"{name} is a demo or placeholder value")
    return errors


def live_token_message(errors: list[str]) -> str:
    lines = "\n".join(f"  - {e}" for e in errors)
    return (
        "Compass will not start in live mode:\n"
        f"{lines}\n"
        "Generate a token for each (PowerShell: [guid]::NewGuid().ToString()), set it in .env or "
        "the environment, and start again. See docs/demo-runbook.md, section 1. "
        "(Demo mode, `tasks.py demo`, needs neither.)"
    )


def token_warnings_from_env(env_file: Path | None = ENV_FILE) -> list[str]:
    env = _env(env_file)
    return token_warnings(env.get("COMPASS_REP_TOKEN"), env.get("COMPASS_ADMIN_TOKEN"))


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
    max_session_turns: int = DEFAULT_MAX_SESSION_TURNS
    max_session_input_tokens: int = DEFAULT_MAX_SESSION_INPUT_TOKENS
    # "anthropic" or "scripted" (demo mode: compass/agent/demo_llm.py).
    llm: str = "anthropic"
    # Live mode only: the server's model spend per UTC day, USD; then a fixed reply until tomorrow.
    daily_spend_cap_usd: float = DEFAULT_DAILY_SPEND_CAP_USD
    message_rate_per_minute: int = DEFAULT_MESSAGE_RATE_PER_MINUTE
    # Behind a platform's reverse proxy: rate-limit by X-Forwarded-For's rightmost entry.
    trust_proxy: bool = False

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
                env.get("COMPASS_MAX_TOOL_ROUNDS"),
                "COMPASS_MAX_TOOL_ROUNDS",
                DEFAULT_MAX_TOOL_ROUNDS,
            ),
            max_session_turns=_positive_int(
                env.get("COMPASS_MAX_SESSION_TURNS"),
                "COMPASS_MAX_SESSION_TURNS",
                DEFAULT_MAX_SESSION_TURNS,
            ),
            max_session_input_tokens=_positive_int(
                env.get("COMPASS_MAX_SESSION_INPUT_TOKENS"),
                "COMPASS_MAX_SESSION_INPUT_TOKENS",
                DEFAULT_MAX_SESSION_INPUT_TOKENS,
            ),
            daily_spend_cap_usd=_positive_float(
                env.get("COMPASS_DAILY_SPEND_CAP_USD"),
                "COMPASS_DAILY_SPEND_CAP_USD",
                DEFAULT_DAILY_SPEND_CAP_USD,
            ),
            message_rate_per_minute=_positive_int(
                env.get("COMPASS_MESSAGE_RATE_PER_MINUTE"),
                "COMPASS_MESSAGE_RATE_PER_MINUTE",
                DEFAULT_MESSAGE_RATE_PER_MINUTE,
            ),
            trust_proxy=env.get("COMPASS_TRUST_PROXY") == "1",
            cors_origins=_cors_origins(env.get("COMPASS_CORS_ORIGINS")),
        )

"""API settings, from the environment (COMPASS_*) or passed explicitly (tests).

`from_env()` also reads the repo's .env file, so no shell (PowerShell, cmd, bash) needs
variables set by hand. A variable set in the real environment wins over the file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from compass.config import ALIASES_YAML, APP_DB, ENV_FILE, REPO_ROOT, RULES_YAML, VEHICLES_DB


def _path(value: str | None, default: Path) -> Path:
    """Relative paths are relative to the repo root, not the current directory."""
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")  # Vite dev server


@dataclass(frozen=True)
class Settings:
    app_db: Path = APP_DB
    rules_path: Path = RULES_YAML
    aliases_path: Path = ALIASES_YAML
    vehicles_db: Path = VEHICLES_DB
    # POST /api/sessions/{id}/tools/{name}: dev / demo only.
    dev_tools: bool = False
    cors_origins: tuple[str, ...] = field(default=DEFAULT_CORS_ORIGINS)
    heartbeat_seconds: float = 15.0
    # Shared bearer tokens. Unset -> the guarded endpoints answer 503 (never open by default).
    rep_token: str | None = field(default=None, repr=False)  # /api/tickets*
    admin_token: str | None = field(default=None, repr=False)  # /api/admin/*

    @classmethod
    def from_env(cls, env_file: Path | None = ENV_FILE) -> "Settings":
        file_values = {} if env_file is None or not env_file.is_file() else dotenv_values(env_file)
        env = {k: v for k, v in file_values.items() if v is not None} | dict(os.environ)
        origins = env.get("COMPASS_CORS_ORIGINS")
        return cls(
            app_db=_path(env.get("COMPASS_APP_DB"), APP_DB),
            rules_path=_path(env.get("COMPASS_RULES"), RULES_YAML),
            dev_tools=env.get("COMPASS_DEV_TOOLS") == "1",
            rep_token=env.get("COMPASS_REP_TOKEN") or None,
            admin_token=env.get("COMPASS_ADMIN_TOKEN") or None,
            cors_origins=tuple(o.strip() for o in origins.split(","))
            if origins
            else DEFAULT_CORS_ORIGINS,
        )

"""API settings, from the environment (COMPASS_*) or passed explicitly (tests)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from compass.config import ALIASES_YAML, APP_DB, RULES_YAML, VEHICLES_DB

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
    def from_env(cls) -> "Settings":
        env = os.environ
        origins = env.get("COMPASS_CORS_ORIGINS")
        return cls(
            app_db=Path(env.get("COMPASS_APP_DB", APP_DB)),
            rules_path=Path(env.get("COMPASS_RULES", RULES_YAML)),
            dev_tools=env.get("COMPASS_DEV_TOOLS") == "1",
            rep_token=env.get("COMPASS_REP_TOKEN") or None,
            admin_token=env.get("COMPASS_ADMIN_TOKEN") or None,
            cors_origins=tuple(o.strip() for o in origins.split(","))
            if origins
            else DEFAULT_CORS_ORIGINS,
        )

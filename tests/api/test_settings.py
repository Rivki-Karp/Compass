"""Settings read the .env file, so no shell needs variables set by hand."""

from pathlib import Path

import pytest

from compass.api import Settings
from compass.config import APP_DB, REPO_ROOT

ENV_VARS = (
    "COMPASS_DEV_TOOLS",
    "COMPASS_REP_TOKEN",
    "COMPASS_ADMIN_TOKEN",
    "COMPASS_APP_DB",
    "COMPASS_RULES",
    "COMPASS_CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_reads_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "COMPASS_DEV_TOOLS=1\n"
        "COMPASS_REP_TOKEN=rep-from-file\n"
        'COMPASS_ADMIN_TOKEN="admin from file"\n'
        "COMPASS_APP_DB=data/demo.db\n",
        encoding="utf-8",
    )
    settings = Settings.from_env(env_file=env_file)
    assert settings.dev_tools is True
    assert settings.rep_token == "rep-from-file"
    assert settings.admin_token == "admin from file"
    assert settings.app_db == REPO_ROOT / "data" / "demo.db"  # relative to the repo, not cwd


def test_real_environment_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("COMPASS_REP_TOKEN=from-file\nCOMPASS_DEV_TOOLS=1\n", encoding="utf-8")
    monkeypatch.setenv("COMPASS_REP_TOKEN", "from-shell")
    monkeypatch.setenv("COMPASS_DEV_TOOLS", "0")
    settings = Settings.from_env(env_file=env_file)
    assert settings.rep_token == "from-shell" and settings.dev_tools is False


def test_missing_file_and_empty_values(tmp_path: Path) -> None:
    defaults = Settings.from_env(env_file=tmp_path / "nope.env")
    assert defaults.app_db == APP_DB and defaults.rep_token is None and not defaults.dev_tools
    env_file = tmp_path / ".env"
    env_file.write_text("COMPASS_REP_TOKEN=\nCOMPASS_ADMIN_TOKEN\n", encoding="utf-8")
    settings = Settings.from_env(env_file=env_file)
    assert settings.rep_token is None and settings.admin_token is None  # empty = unset -> 503


def test_example_file_is_valid() -> None:
    settings = Settings.from_env(env_file=REPO_ROOT / ".env.example")
    assert settings.dev_tools is True
    assert settings.rep_token and settings.admin_token
    assert settings.rep_token != settings.admin_token

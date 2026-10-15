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


# --- agent settings ---------------------------------------------------------------------------


def test_agent_settings_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ANTHROPIC_API_KEY", "COMPASS_MODEL", "COMPASS_MAX_TOOL_ROUNDS"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-ant-test-secret\nCOMPASS_MAX_TOOL_ROUNDS=5\n", encoding="utf-8"
    )
    settings = Settings.from_env(env_file=env_file)
    assert settings.anthropic_api_key == "sk-ant-test-secret"
    assert settings.model == "claude-sonnet-5-5" and settings.max_tool_rounds == 5
    assert "sk-ant" not in repr(settings)  # the key is never printed


def test_empty_shell_variable_does_not_hide_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert Settings.from_env(env_file=env_file).anthropic_api_key == "from-file"


@pytest.mark.parametrize("value", ["zero", "0", "-3"])
def test_invalid_tool_rounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    from compass.api.settings import SettingsError

    monkeypatch.delenv("COMPASS_MAX_TOOL_ROUNDS", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"COMPASS_MAX_TOOL_ROUNDS={value}\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="COMPASS_MAX_TOOL_ROUNDS"):
        Settings.from_env(env_file=env_file)


def test_chat_and_eval_refuse_to_start_without_a_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from compass.agent.startup import load_agent_settings

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        load_agent_settings(env_file=tmp_path / "missing.env")
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY is not set" in err and "חסר מפתח API" in err


def test_invalid_setting_is_a_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from compass.agent.startup import load_agent_settings

    monkeypatch.delenv("COMPASS_MAX_TOOL_ROUNDS", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=x\nCOMPASS_MAX_TOOL_ROUNDS=lots\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        load_agent_settings(env_file=env_file)
    assert exc_info.value.code == 2
    assert "COMPASS_MAX_TOOL_ROUNDS" in capsys.readouterr().err


def test_real_env_file_loads_agent_settings() -> None:
    """The developer's own .env (if any) is valid; the key is never printed."""
    from compass.config import ENV_FILE

    if not ENV_FILE.is_file():
        pytest.skip("no .env")
    settings = Settings.from_env()
    assert settings.max_tool_rounds >= 1
    assert (settings.anthropic_api_key or "<none>") not in repr(settings)

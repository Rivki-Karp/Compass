"""Settings read the .env file, so no shell needs variables set by hand."""

from pathlib import Path

import pytest

from compass.api import Settings
from compass.config import APP_DB, BACKEND_ROOT, DEMO_DB

ENV_VARS = (
    "COMPASS_DEV_TOOLS",
    "COMPASS_REP_TOKEN",
    "COMPASS_ADMIN_TOKEN",
    "COMPASS_APP_DB",
    "COMPASS_RULES",
    "COMPASS_CORS_ORIGINS",
    "COMPASS_LLM",
    "COMPASS_DEMO_DB",
    "COMPASS_MODEL",
    "COMPASS_EFFORT",
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
    assert settings.app_db == BACKEND_ROOT / "data" / "demo.db"  # relative to backend/, not cwd


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
    settings = Settings.from_env(env_file=BACKEND_ROOT / ".env.example")
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


def test_model_and_effort(tmp_path: Path) -> None:
    from compass.api.settings import SettingsError

    defaults = Settings.from_env(env_file=tmp_path / "nope.env")
    assert (defaults.model, defaults.effort) == ("claude-sonnet-5-5", "low")
    env_file = tmp_path / ".env"
    env_file.write_text("COMPASS_MODEL=claude-haiku-5-5\nCOMPASS_EFFORT=medium\n", encoding="utf-8")
    settings = Settings.from_env(env_file=env_file)
    assert (settings.model, settings.effort) == ("claude-haiku-5-5", "medium")
    env_file.write_text("COMPASS_EFFORT=huge\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="COMPASS_EFFORT"):
        Settings.from_env(env_file=env_file)


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


def test_llm_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from compass.api.settings import SettingsError

    assert Settings.from_env(env_file=None).llm == "anthropic"
    env_file = tmp_path / ".env"
    env_file.write_text("COMPASS_LLM=scripted\n", encoding="utf-8")
    assert Settings.from_env(env_file=env_file).llm == "scripted"
    monkeypatch.setenv("COMPASS_LLM", "gpt")
    with pytest.raises(SettingsError, match="COMPASS_LLM"):
        Settings.from_env(env_file=None)


# --- demo mode's own database ----------------------------------------------------------------


def test_demo_mode_uses_demo_db_and_ignores_app_db(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("COMPASS_LLM=scripted\nCOMPASS_APP_DB=data/app.db\n", encoding="utf-8")
    assert Settings.from_env(env_file=env_file).app_db == DEMO_DB
    env_file.write_text("COMPASS_LLM=anthropic\nCOMPASS_APP_DB=data/app.db\n", encoding="utf-8")
    assert Settings.from_env(env_file=env_file).app_db == APP_DB


def test_demo_db_can_be_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPASS_LLM", "scripted")
    monkeypatch.setenv("COMPASS_DEMO_DB", str(tmp_path / "other-demo.db"))
    assert Settings.from_env(env_file=None).app_db == tmp_path / "other-demo.db"


@pytest.mark.parametrize("value", ["data/app.db", str(APP_DB)])
def test_demo_mode_never_points_at_app_db(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    from compass.api.settings import SettingsError

    monkeypatch.setenv("COMPASS_LLM", "scripted")
    monkeypatch.setenv("COMPASS_DEMO_DB", value)
    with pytest.raises(SettingsError, match="app.db"):
        Settings.from_env(env_file=None)


def test_explicit_demo_settings_on_app_db_are_refused() -> None:
    from compass.api.settings import SettingsError

    with pytest.raises(SettingsError, match="demo mode"):
        Settings(app_db=APP_DB, llm="scripted")
    Settings(app_db=APP_DB)  # the real mode keeps app.db


def test_demo_reset_wipes_the_demo_db_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tasks

    demo = tmp_path / "demo.db"
    for name in ("demo.db", "demo.db-wal", "demo.db-shm", "keep.db"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setenv("COMPASS_DEMO_DB", str(demo))
    app_db_before = APP_DB.stat().st_mtime_ns if APP_DB.exists() else None
    tasks.demo_reset()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.db"]
    assert (APP_DB.stat().st_mtime_ns if APP_DB.exists() else None) == app_db_before
    tasks.demo_reset()  # nothing there: still fine


def test_token_warnings_name_the_empty_token_never_a_value() -> None:
    from compass.api.settings import token_warnings

    assert token_warnings("rep-value", "admin-value") == []
    (rep,) = token_warnings(None, "admin-value")
    assert rep.startswith("COMPASS_REP_TOKEN is empty: the representative screen (/rep)")
    assert "docs/demo-runbook.md" in rep and "admin-value" not in rep
    both = token_warnings("", None)
    assert [w.split(" ", 1)[0] for w in both] == ["COMPASS_REP_TOKEN", "COMPASS_ADMIN_TOKEN"]


@pytest.mark.parametrize(
    ("rep", "admin", "errors"),
    [
        ("a-real-token", "another-real-token", []),
        (None, "another-real-token", ["COMPASS_REP_TOKEN is empty"]),
        (
            "rep-demo",
            "admin-demo",
            [
                "COMPASS_REP_TOKEN is a demo or placeholder value",
                "COMPASS_ADMIN_TOKEN is a demo or placeholder value",
            ],
        ),
        (
            "rep-demo-change-me",
            "",
            [
                "COMPASS_REP_TOKEN is a demo or placeholder value",
                "COMPASS_ADMIN_TOKEN is empty",
            ],
        ),
    ],
)
def test_live_mode_refuses_empty_and_demo_tokens(
    tmp_path: Path, rep: str | None, admin: str | None, errors: list[str]
) -> None:
    from compass.api.settings import live_token_errors

    live = Settings(app_db=tmp_path / "a.db", rep_token=rep, admin_token=admin)
    assert live_token_errors(live) == errors
    demo = Settings(app_db=tmp_path / "d.db", llm="scripted", rep_token=rep, admin_token=admin)
    assert live_token_errors(demo) == []  # demo mode: the demo defaults are fine


def test_the_server_entry_point_refuses_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy

    bad = Settings(app_db=tmp_path / "a.db", rep_token="rep-demo", admin_token="x" * 32)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls, env_file=None: bad))
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("compass.api.main")
    message = str(stopped.value.code)
    assert message.startswith("Compass will not start in live mode")
    assert "COMPASS_REP_TOKEN is a demo or placeholder value" in message
    assert "x" * 32 not in message

    good = Settings(app_db=tmp_path / "b.db", rep_token="r" * 32, admin_token="a" * 32)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls, env_file=None: good))
    assert runpy.run_module("compass.api.main")["app"] is not None

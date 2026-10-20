"""Payslip upload settings (COMPASS_PAYSLIP): off by default, and a live server with it on
refuses to start without a Claude key, or with a model its spend cap cannot price."""

import runpy
from pathlib import Path

import pytest

from compass.agent.llm import PRICES
from compass.api import Settings
from compass.api.settings import (
    DEFAULT_PAYSLIP_MAX_BYTES,
    SettingsError,
    live_payslip_errors,
)
from compass.config import BACKEND_ROOT

PAYSLIP_VARS = (
    "COMPASS_PAYSLIP",
    "COMPASS_PAYSLIP_MODEL",
    "COMPASS_PAYSLIP_FALLBACK_MODEL",
    "COMPASS_PAYSLIP_MAX_BYTES",
    "COMPASS_PAYSLIP_MAX_PAGES",
    "COMPASS_PAYSLIP_PER_SESSION",
    "COMPASS_PAYSLIP_TIMEOUT_S",
    "ANTHROPIC_API_KEY",
    "COMPASS_LLM",
    "COMPASS_ENV_ONLY",
)
FAKE_KEY = "sk-ant-" + "fake-key-for-tests-" * 2  # built, never a literal
NO_KEY = "ANTHROPIC_API_KEY is empty"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PAYSLIP_VARS:
        monkeypatch.delenv(name, raising=False)


def _live(tmp_path: Path, **overrides: object) -> Settings:
    tokens = {"rep_token": "r" * 32, "admin_token": "a" * 32}
    return Settings(app_db=tmp_path / "a.db", **tokens, **overrides)  # type: ignore[arg-type]


def _env_file(tmp_path: Path, text: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(text, encoding="utf-8")
    return env_file


def test_off_by_default(tmp_path: Path) -> None:
    settings = Settings.from_env(env_file=tmp_path / "nope.env")
    assert settings.payslip is False
    assert settings.payslip_model == "claude-haiku-5-5"
    assert settings.payslip_fallback_model == "claude-sonnet-5-5"
    # both defaults are priced, so their calls count toward the daily spend cap
    assert {settings.payslip_model, settings.payslip_fallback_model} <= set(PRICES)
    assert settings.payslip_max_bytes == DEFAULT_PAYSLIP_MAX_BYTES == 5 * 1024 * 1024
    assert (settings.payslip_max_pages, settings.payslip_per_session) == (3, 3)
    assert settings.payslip_timeout_s == 30.0


def test_the_example_file_keeps_it_off() -> None:
    assert Settings.from_env(env_file=BACKEND_ROOT / ".env.example").payslip is False


def test_settings_from_the_file(tmp_path: Path) -> None:
    env_file = _env_file(
        tmp_path,
        "COMPASS_PAYSLIP=1\nCOMPASS_PAYSLIP_MODEL=m1\nCOMPASS_PAYSLIP_FALLBACK_MODEL=m2\n"
        "COMPASS_PAYSLIP_MAX_BYTES=1000\nCOMPASS_PAYSLIP_MAX_PAGES=2\n"
        "COMPASS_PAYSLIP_PER_SESSION=5\nCOMPASS_PAYSLIP_TIMEOUT_S=7.5\n",
    )
    settings = Settings.from_env(env_file=env_file)
    assert settings.payslip is True
    assert (settings.payslip_model, settings.payslip_fallback_model) == ("m1", "m2")
    assert settings.payslip_max_bytes == 1000 and settings.payslip_max_pages == 2
    assert settings.payslip_per_session == 5 and settings.payslip_timeout_s == 7.5


@pytest.mark.parametrize("value", ["0", "", "true", "yes", "on"])
def test_only_1_turns_it_on(tmp_path: Path, value: str) -> None:
    env_file = _env_file(tmp_path, f"COMPASS_PAYSLIP={value}\n")
    assert Settings.from_env(env_file=env_file).payslip is False


@pytest.mark.parametrize(
    "line",
    [
        "COMPASS_PAYSLIP_MAX_BYTES=0",
        "COMPASS_PAYSLIP_MAX_PAGES=two",
        "COMPASS_PAYSLIP_PER_SESSION=-1",
        "COMPASS_PAYSLIP_TIMEOUT_S=0",
    ],
)
def test_invalid_limits_are_refused(tmp_path: Path, line: str) -> None:
    with pytest.raises(SettingsError, match=line.split("=")[0]):
        Settings.from_env(env_file=_env_file(tmp_path, line + "\n"))


def test_live_refuses_without_a_key_or_a_priced_model(tmp_path: Path) -> None:
    assert live_payslip_errors(_live(tmp_path)) == []  # off: nothing to check
    ready = _live(tmp_path, payslip=True, anthropic_api_key=FAKE_KEY)
    assert live_payslip_errors(ready) == []
    errors = live_payslip_errors(_live(tmp_path, payslip=True, payslip_fallback_model="x-model"))
    assert errors == [
        NO_KEY,
        "COMPASS_PAYSLIP_FALLBACK_MODEL (x-model) has no price entry in compass.agent.llm.PRICES",
    ]
    assert all(FAKE_KEY not in e for e in errors)


def test_demo_mode_needs_no_key(tmp_path: Path) -> None:
    demo = Settings(app_db=tmp_path / "d.db", llm="scripted", payslip=True)
    assert live_payslip_errors(demo) == []


def test_the_server_entry_point_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _live(tmp_path, payslip=True)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls, env_file=None: bad))
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("compass.api.main")
    message = str(stopped.value.code)
    assert message.startswith("Compass will not start in live mode with COMPASS_PAYSLIP=1")
    assert NO_KEY in message

    good = _live(tmp_path, payslip=True, anthropic_api_key=FAKE_KEY)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls, env_file=None: good))
    assert runpy.run_module("compass.api.main")["app"] is not None


def test_tasks_serve_refuses_before_uvicorn_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tasks

    bad = _live(tmp_path, payslip=True, anthropic_api_key=FAKE_KEY, payslip_model="x-model")
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls, env_file=None: bad))
    started: list[object] = []
    monkeypatch.setattr(tasks, "run", lambda *args: started.append(args))
    with pytest.raises(SystemExit) as stopped:
        tasks.serve()
    message = str(stopped.value.code)
    assert "COMPASS_PAYSLIP_MODEL (x-model) has no price entry" in message and started == []
    assert FAKE_KEY not in message

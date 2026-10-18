"""`tasks.py demo`: the one command for the final demo."""

import os
import time
from pathlib import Path
from typing import Any

import pytest

import tasks


@pytest.fixture
def web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "web"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.tsx").write_text("x", encoding="utf-8")
    (root / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tasks, "WEB", root)
    return root


def _touch(path: Path, at: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, (at, at))


def test_build_is_stale_when_missing_or_older_than_any_source(web: Path) -> None:
    assert tasks._web_build_is_stale()  # no build
    now = time.time()
    _touch(web / "src" / "main.tsx", now - 100)
    _touch(web / "package.json", now - 100)
    _touch(web / "dist" / "index.html", now - 50)
    assert not tasks._web_build_is_stale()
    _touch(web / "src" / "deep" / "new.tsx", now)  # a source changed after the build
    assert tasks._web_build_is_stale()


@pytest.mark.parametrize("stale", [True, False])
def test_demo_resets_builds_when_needed_and_serves_in_demo_mode(
    monkeypatch: pytest.MonkeyPatch, stale: bool
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(tasks, "demo_reset", lambda: calls.append("reset"))
    monkeypatch.setattr(tasks, "build_web", lambda: calls.append("build"))
    monkeypatch.setattr(tasks, "_web_build_is_stale", lambda: stale)
    monkeypatch.setattr(tasks, "run", lambda *args: calls.append(args))
    for name in ("COMPASS_LLM", *tasks.DEMO_TOKENS):  # restored after the test
        monkeypatch.delenv(name, raising=False)
    tasks.demo()
    assert os.environ["COMPASS_LLM"] == "scripted"
    expected_build = ["build"] if stale else []
    assert calls[:-1] == ["reset", *expected_build]
    served = calls[-1]
    assert "compass.api.main:app" in served and "--reload" not in served
    assert served[served.index("--port") + 1] == "8000"


def test_demo_with_an_employee_id_is_still_the_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(tasks, "run", lambda *args: calls.append(args))
    tasks.demo("E-001")
    assert calls == [(tasks.sys.executable, "-m", "compass.demo", "E-001")]


def test_demo_prints_the_urls_and_never_a_token_from_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tasks, "demo_reset", lambda: None)
    monkeypatch.setattr(tasks, "_web_build_is_stale", lambda: False)
    monkeypatch.setattr(tasks, "run", lambda *args: None)
    monkeypatch.delenv("COMPASS_LLM", raising=False)  # restored after the test
    monkeypatch.setenv("COMPASS_REP_TOKEN", "secret-rep-value")
    monkeypatch.delenv("COMPASS_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(tasks, "REPO_ROOT", Path("/nonexistent-repo"))  # no .env
    tasks.demo()
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8000/" in out and "http://127.0.0.1:8000/rep" in out
    assert "secret-rep-value" not in out and "(COMPASS_REP_TOKEN)" in out
    assert "admin-demo" in out  # unset: the demo default, shown
    assert os.environ["COMPASS_ADMIN_TOKEN"] == "admin-demo"


def test_serve_warns_about_an_empty_token_and_never_prints_a_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "COMPASS_REP_TOKEN=\nCOMPASS_ADMIN_TOKEN=secret-admin-value\n", encoding="utf-8"
    )
    monkeypatch.setattr(tasks, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("COMPASS_REP_TOKEN", raising=False)
    monkeypatch.delenv("COMPASS_ADMIN_TOKEN", raising=False)
    calls: list[Any] = []
    monkeypatch.setattr(tasks, "run", lambda *args: calls.append(args))
    tasks.serve()
    out = capsys.readouterr().out
    assert "WARNING: COMPASS_REP_TOKEN is empty: the representative screen (/rep)" in out
    assert "docs/demo-runbook.md" in out
    assert "COMPASS_ADMIN_TOKEN" not in out and "secret-admin-value" not in out
    assert calls  # still serves


def test_demo_has_no_token_warning_its_defaults_fill_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(tasks, "demo_reset", lambda: None)
    monkeypatch.setattr(tasks, "_web_build_is_stale", lambda: False)
    monkeypatch.setattr(tasks, "run", lambda *args: None)
    monkeypatch.delenv("COMPASS_LLM", raising=False)
    monkeypatch.delenv("COMPASS_REP_TOKEN", raising=False)
    monkeypatch.delenv("COMPASS_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(tasks, "REPO_ROOT", tmp_path)  # an empty .env-less repo
    tasks.demo()
    assert "WARNING" not in capsys.readouterr().out

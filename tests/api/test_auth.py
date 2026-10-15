"""Shared bearer tokens: representative (/api/tickets*) and admin (/api/admin/*)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from helpers import ADMIN, REP

from compass.api import Settings, create_app

GUARDED = [
    ("get", "/api/tickets", REP),
    ("post", "/api/tickets/some-ticket/answer", REP),
    ("post", "/api/admin/reload-rules", ADMIN),
]


def _call(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    kwargs = {"json": {"answer_text": "x"}} if path.endswith("/answer") else {}
    return getattr(client, method)(path, headers=headers or {}, **kwargs)


@pytest.mark.parametrize(("method", "path", "good"), GUARDED)
def test_missing_or_wrong_token_is_401(
    client: TestClient, method: str, path: str, good: dict[str, str]
) -> None:
    for headers in (None, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic abc"}):
        response = _call(client, method, path, headers)
        assert response.status_code == 401, (path, headers)
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path", "good"), GUARDED)
def test_right_token_passes(
    client: TestClient, method: str, path: str, good: dict[str, str]
) -> None:
    response = _call(client, method, path, good)
    # 404 for the made-up ticket id: past the guard.
    assert response.status_code in (200, 404), response.text


def test_tokens_are_not_interchangeable(client: TestClient) -> None:
    assert client.get("/api/tickets", headers=ADMIN).status_code == 401
    assert client.post("/api/admin/reload-rules", headers=REP).status_code == 401


@pytest.mark.parametrize(("method", "path", "good"), GUARDED)
def test_unconfigured_is_503_never_open(
    make_settings: Callable[..., Settings], method: str, path: str, good: dict[str, str]
) -> None:
    with TestClient(create_app(make_settings(rep_token=None, admin_token=None))) as client:
        for headers in (None, good):
            response = _call(client, method, path, headers)
            assert response.status_code == 503
            assert "not configured" in response.json()["detail"]


def test_open_endpoints_stay_open(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(rep_token=None, admin_token=None))) as client:
        assert client.get("/api/health").status_code == 200
        sid = client.post("/api/sessions").json()["id"]
        assert client.get(f"/api/sessions/{sid}").status_code == 200
        assert client.get("/api/catalog").status_code == 200


def test_dev_tools_stay_behind_their_flag(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(dev_tools=False))) as client:
        sid = client.post("/api/sessions").json()["id"]
        url = f"/api/sessions/{sid}/tools/get_rule"
        for headers in (REP, ADMIN):  # no token opens them
            assert client.post(url, json={"topic": "budgets"}, headers=headers).status_code == 404


def test_tokens_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPASS_REP_TOKEN", "s3cr3t-rep-xyz")
    monkeypatch.setenv("COMPASS_ADMIN_TOKEN", "")
    settings = Settings.from_env()
    assert settings.rep_token == "s3cr3t-rep-xyz"
    assert settings.admin_token is None  # empty = unset
    assert "s3cr3t" not in repr(settings)  # tokens are never printed

"""The built web UI is served from the API with an SPA fallback, and never shadows the API."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.api import Settings, create_app

INDEX = "<!doctype html><title>Compass</title><div id=root></div>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (root / "favicon.png").write_bytes(b"\x89PNG")
    (tmp_path / "secret.txt").write_text("not served", encoding="utf-8")
    return root


@pytest.fixture
def web(make_settings: Callable[..., Settings], dist: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings(web_dist=dist))) as client:
        yield client


@pytest.mark.parametrize(
    "path", ["/", "/rep", "/__styleguide", "/rep?ticket=abc", "/some/deep/route"]
)
def test_ui_routes_get_index_html(web: TestClient, path: str) -> None:
    response = web.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"


def test_build_files_are_served(web: TestClient) -> None:
    asset = web.get("/assets/index-abc123.js")
    assert asset.status_code == 200 and asset.text == "console.log(1)"
    assert "immutable" in asset.headers["cache-control"]
    assert web.get("/favicon.png").content == b"\x89PNG"


def test_the_api_is_not_shadowed(web: TestClient) -> None:
    health = web.get("/api/health")
    assert health.status_code == 200 and health.json()["ok"] is True
    assert web.get("/docs").status_code == 200 and "swagger" in web.get("/docs").text.lower()
    assert web.get("/openapi.json").json()["info"]["title"]
    for path in ("/api/no-such-route", "/api/docs", "/api", "/api/sessions/x/nope"):
        response = web.get(path)
        assert response.status_code == 404, path
        assert response.json() == {"detail": "Not Found"}, path
    # the fallback is GET only: other methods on API paths behave as before
    assert web.post("/api/sessions").status_code == 201


def test_no_path_escapes_the_build(web: TestClient) -> None:
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        response = web.get(path)
        assert "not served" not in response.text, path


def test_without_a_build_only_the_api_runs(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(web_dist=None))) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_the_ui_is_not_in_the_api_docs(web: TestClient) -> None:
    paths = web.get("/openapi.json").json()["paths"]
    assert "/{path}" not in paths

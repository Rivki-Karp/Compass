import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.config import RULES_YAML


@pytest.fixture
def rules_copy(tmp_path: Path) -> Path:
    """A private copy of rules.yaml: reload tests edit it, never the real file."""
    path = tmp_path / "rules.yaml"
    shutil.copyfile(RULES_YAML, path)
    return path


@pytest.fixture
def make_settings(tmp_path: Path, rules_copy: Path) -> Callable[..., Settings]:
    def make(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "app_db": tmp_path / "app.db",
            "rules_path": rules_copy,
            "dev_tools": True,
            "heartbeat_seconds": 1.0,
        }
        values.update(overrides)
        return Settings(**values)  # type: ignore[arg-type]

    return make


@pytest.fixture
def client(make_settings: Callable[..., Settings]) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


@pytest.fixture
def sid(client: TestClient) -> str:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return response.json()["id"]

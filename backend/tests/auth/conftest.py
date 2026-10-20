import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.auth.passwords import hash_password
from compass.auth.seed import parse_seed_users
from compass.config import RULES_YAML
from compass.state.accounts import Accounts

PASSWORD = "correct horse battery"
# role -> the seeded account's email; every one logs in with PASSWORD
EMAILS = {
    "employee": "dana@example.com",
    "other": "avi@example.com",
    "rep": "rep@example.com",
    "admin": "admin@example.com",
}


@pytest.fixture(scope="session")
def password_hash() -> str:
    return hash_password(PASSWORD)


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    rules = tmp_path / "rules.yaml"
    shutil.copyfile(RULES_YAML, rules)

    def make(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "app_db": tmp_path / "app.db",
            "rules_path": rules,
            "heartbeat_seconds": 1.0,
            "web_dist": None,
        }
        values.update(overrides)
        return Settings(**values)  # type: ignore[arg-type]

    return make


@pytest.fixture
def auth_settings(make_settings: Callable[..., Settings], password_hash: str) -> Settings:
    """COMPASS_AUTH=1 with an employee, a second employee, a rep and an admin."""
    roles = {"employee": "employee", "other": "employee", "rep": "rep", "admin": "admin"}
    seeds = parse_seed_users(
        json.dumps(
            [
                {
                    "email": EMAILS[key],
                    "name": key.capitalize(),
                    "role": role,
                    "password_hash": password_hash,
                }
                for key, role in roles.items()
            ]
        )
    )
    # the login limits are tested on their own; the others log in freely
    return make_settings(auth=True, seed_users=seeds, login_per_ip_per_minute=1000)


@pytest.fixture
def client(auth_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(auth_settings)) as test_client:
        yield test_client


@pytest.fixture
def accounts(client: TestClient) -> Accounts:
    return client.app.state.accounts  # type: ignore[attr-defined, no-any-return]


@pytest.fixture
def login(client: TestClient) -> Callable[[str], dict[str, str]]:
    """Log in as a seeded account (EMAILS key) and return its Authorization header."""

    def do(who: str) -> dict[str, str]:
        response = client.post("/api/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['token']}"}

    return do

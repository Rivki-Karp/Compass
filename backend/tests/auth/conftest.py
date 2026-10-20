import json
import shutil
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.api.agent import NullAgentRunner
from compass.auth.passwords import hash_password
from compass.auth.seed import parse_seed_users
from compass.config import RULES_YAML
from compass.state.accounts import Accounts

# the helpers of tests/api (live server, SSE reader) and tests/payslip (synthetic files)
for _helpers in ("api", "payslip"):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / _helpers))

PASSWORD = "correct horse battery"
STATIC_REP, STATIC_ADMIN = "rep-static-token", "admin-static-token"
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


@pytest.fixture
def full_settings(auth_settings: Settings) -> Settings:
    """Accounts on, plus everything with a session id on it: dev tools (run a tool), the payslip
    upload (demo extractor), and the old static tokens set, to show they are refused."""
    return replace(
        auth_settings,
        llm="scripted",
        dev_tools=True,
        payslip=True,
        rep_token=STATIC_REP,
        admin_token=STATIC_ADMIN,
    )


@pytest.fixture
def full_client(full_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(full_settings, agent=NullAgentRunner())) as test_client:
        yield test_client

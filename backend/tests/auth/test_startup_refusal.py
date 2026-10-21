"""A live server with COMPASS_AUTH=1 refuses to start without an admin or with a weak hash."""

import json
from pathlib import Path

from compass.api import Settings
from compass.api.settings import live_auth_errors, live_auth_message
from compass.auth.passwords import hash_password
from compass.auth.seed import parse_seed_users

GOOD = hash_password("correct horse battery")


def _settings(tmp_path: Path, users: list[dict[str, str]], **overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_db": tmp_path / "app.db",
        "auth": True,
        "seed_users": parse_seed_users(json.dumps(users)),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _user(email: str, role: str, password_hash: str) -> dict[str, str]:
    return {"email": email, "name": "x", "role": role, "password_hash": password_hash}


def test_an_admin_with_an_argon2id_hash_starts(tmp_path: Path) -> None:
    users = [_user("a@x.com", "admin", GOOD), _user("e@x.com", "employee", GOOD)]
    assert live_auth_errors(_settings(tmp_path, users)) == []


def test_no_admin_is_refused(tmp_path: Path) -> None:
    errors = live_auth_errors(_settings(tmp_path, [_user("e@x.com", "employee", GOOD)]))
    assert errors == ["COMPASS_SEED_USERS holds no admin"]
    assert live_auth_errors(_settings(tmp_path, [])) == ["COMPASS_SEED_USERS holds no admin"]


def test_a_hash_that_is_not_argon2id_is_refused_without_showing_it(tmp_path: Path) -> None:
    weak = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
    users = [_user("a@x.com", "admin", GOOD), _user("e@x.com", "employee", weak)]
    errors = live_auth_errors(_settings(tmp_path, users))
    assert errors == ["COMPASS_SEED_USERS entry 2: password_hash is not an argon2id hash"]
    assert weak not in live_auth_message(errors)


def test_flag_off_and_demo_mode_have_no_such_check(tmp_path: Path) -> None:
    assert live_auth_errors(_settings(tmp_path, [], auth=False)) == []
    demo = _settings(tmp_path, [], llm="scripted", app_db=tmp_path / "demo.db")
    assert live_auth_errors(demo) == []

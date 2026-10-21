"""COMPASS_SEED_USERS: parsing, the upsert at start, and no hash in a repr or an error."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.api import Settings, create_app
from compass.api.settings import SettingsError
from compass.auth.passwords import hash_password, verify_password
from compass.auth.seed import SeedError, parse_seed_users
from compass.state import Store
from compass.state.accounts import Accounts

PASSWORD = "correct horse battery"


@pytest.fixture(scope="module")
def stored_hash() -> str:
    return hash_password(PASSWORD)


def _entry(email: str, role: str, password_hash: str, name: str = "דנה") -> dict[str, str]:
    return {"email": email, "name": name, "role": role, "password_hash": password_hash}


def test_parse_normalises_and_keeps_the_hash(stored_hash: str) -> None:
    raw = json.dumps([_entry(" Dana@X.com", "employee", stored_hash)])
    (user,) = parse_seed_users(raw)
    assert (user.email, user.name, user.role) == ("dana@x.com", "דנה", "employee")
    assert user.password_hash == stored_hash


@pytest.mark.parametrize("raw", [None, "", "   ", "[]"])
def test_no_seed_users_is_fine(raw: str | None) -> None:
    assert parse_seed_users(raw) == ()


def test_malformed_seeds_are_refused_without_echoing_a_value() -> None:
    secret = "Sup3rSecretValue"
    bad = [
        "not json",
        '{"a": 1}',
        json.dumps([{"email": "a@x.com"}]),
        json.dumps([_entry("a@x.com", "boss", secret)]),
        json.dumps([_entry("not-an-email", "admin", secret)]),
        json.dumps([_entry("a@x.com", "admin", secret, name="")]),
        json.dumps([_entry("a@x.com", "admin", secret, name="x" * 61)]),
        json.dumps([_entry("a@x.com", "admin", "")]),
        json.dumps([_entry("a@x.com", "admin", secret), _entry("A@x.com ", "rep", secret)]),
        json.dumps([{**_entry("a@x.com", "admin", secret), "extra": "1"}]),
    ]
    for raw in bad:
        with pytest.raises(SeedError) as caught:
            parse_seed_users(raw)
        assert secret not in str(caught.value)


def test_settings_from_env_reads_the_flag_and_seeds(
    monkeypatch: pytest.MonkeyPatch, stored_hash: str
) -> None:
    for name in (
        "COMPASS_AUTH",
        "COMPASS_SEED_USERS",
        "COMPASS_INVITE_TTL_HOURS",
        "COMPASS_SESSION_TTL_HOURS",
    ):
        monkeypatch.delenv(name, raising=False)
    off = Settings.from_env(None)
    assert not off.auth and off.seed_users == ()
    assert (off.invite_ttl_hours, off.session_ttl_hours) == (48, 8)
    assert (off.login_per_ip_per_minute, off.login_max_failures, off.login_lock_minutes) == (
        10,
        5,
        15,
    )

    monkeypatch.setenv("COMPASS_AUTH", "1")
    monkeypatch.setenv("COMPASS_INVITE_TTL_HOURS", "2")
    monkeypatch.setenv("COMPASS_SESSION_TTL_HOURS", "3")
    monkeypatch.setenv("COMPASS_SEED_USERS", json.dumps([_entry("a@x.com", "admin", stored_hash)]))
    on = Settings.from_env(None)
    assert on.auth and (on.invite_ttl_hours, on.session_ttl_hours) == (2, 3)
    assert [u.email for u in on.seed_users] == ["a@x.com"]

    monkeypatch.setenv("COMPASS_SEED_USERS", "nope")
    with pytest.raises(SettingsError, match="COMPASS_SEED_USERS"):
        Settings.from_env(None)
    monkeypatch.setenv("COMPASS_SEED_USERS", "[]")
    monkeypatch.setenv("COMPASS_INVITE_TTL_HOURS", "0")
    with pytest.raises(SettingsError, match="COMPASS_INVITE_TTL_HOURS"):
        Settings.from_env(None)


def test_repr_never_shows_a_hash(tmp_path: Path, stored_hash: str) -> None:
    seeds = parse_seed_users(json.dumps([_entry("a@x.com", "admin", stored_hash)]))
    settings = Settings(app_db=tmp_path / "app.db", auth=True, seed_users=seeds)
    for text in (repr(settings), str(settings), repr(seeds), repr(seeds[0])):
        assert stored_hash not in text and "argon2" not in text
    user = Accounts(Store(tmp_path / "app.db")).create_user("b@x.com", "ב", "rep", stored_hash)
    assert stored_hash not in repr(user) and stored_hash not in str(user)


def test_seed_upserts_updates_and_reactivates(tmp_path: Path, stored_hash: str) -> None:
    accounts = Accounts(Store(tmp_path / "app.db"))
    first = parse_seed_users(
        json.dumps([_entry("a@x.com", "admin", stored_hash), _entry("e@x.com", "employee", "h1")])
    )
    assert accounts.seed(first) == 2
    admin = accounts.user_by_email("A@X.com ")
    assert admin is not None and admin.status == "active" and admin.role == "admin"
    assert verify_password(admin.password_hash, PASSWORD)
    original = accounts.user_by_email("e@x.com")
    assert original is not None

    # the same user again with a new name, role and hash; a disabled account comes back
    with accounts.store._write() as (conn, _):
        conn.execute("UPDATE users SET status = 'disabled' WHERE email = 'e@x.com'")
    second = parse_seed_users(
        json.dumps([_entry("e@x.com", "rep", "h2", name="אבי"), _entry("n@x.com", "rep", "h3")])
    )
    accounts.seed(second)
    again = accounts.user_by_email("e@x.com")
    assert again is not None
    assert (again.name, again.role, again.status, again.password_hash) == (
        "אבי",
        "rep",
        "active",
        "h2",
    )
    assert again.id == original.id  # updated in place, not re-created
    # a user not in the list is left alone, and nobody is duplicated
    assert accounts.user_by_email("a@x.com") is not None
    assert accounts.count_users() == 3


def test_app_seeds_at_start_only_with_the_flag(
    tmp_path: Path, make_settings: Callable[..., Settings], stored_hash: str
) -> None:
    seeds = parse_seed_users(json.dumps([_entry("a@x.com", "admin", stored_hash)]))
    off = make_settings(app_db=tmp_path / "off.db", seed_users=seeds)
    with TestClient(create_app(off)) as client:
        assert client.app.state.accounts.count_users() == 0  # type: ignore[attr-defined]
    on = make_settings(app_db=tmp_path / "on.db", seed_users=seeds, auth=True)
    with TestClient(create_app(on)) as client:
        assert client.app.state.accounts.count_users() == 1  # type: ignore[attr-defined]
    with TestClient(create_app(on)) as client:  # a restart: the upsert is idempotent
        assert client.app.state.accounts.count_users() == 1  # type: ignore[attr-defined]
    for suffix in ("", "-wal", "-shm"):  # a deploy wipes the database: the seed comes back
        (tmp_path / f"on.db{suffix}").unlink(missing_ok=True)
    with TestClient(create_app(on)) as client:
        assert client.app.state.accounts.count_users() == 1  # type: ignore[attr-defined]

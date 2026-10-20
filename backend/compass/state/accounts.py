"""User accounts over the session store's database (COMPASS_AUTH=1).

The same SQLite file and transaction helpers as Store; only hashes are stored (passwords, invite
codes and tokens never are), and nothing here logs: a caller refers to a user by id.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

from compass.auth.emails import normalize_email
from compass.auth.seed import SeedUser
from compass.state.store import Store, _now


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    role: str
    status: str
    created_at: str
    last_login_at: str | None
    # the argon2id hash: never in a repr, a dump or a response
    password_hash: str = ""

    def __repr_args__(self) -> Iterable[tuple[str | None, Any]]:
        return [(k, v) for k, v in super().__repr_args__() if k != "password_hash"]


def _user(row: Any) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        status=row["status"],
        created_at=row["created_at"],
        last_login_at=row["last_login_at"],
        password_hash=row["password_hash"],
    )


class Accounts:
    def __init__(self, store: Store) -> None:
        self.store = store

    def user_by_email(self, email: str) -> User | None:
        with self.store._read() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (normalize_email(email),)
            ).fetchone()
        return None if row is None else _user(row)

    def user_by_id(self, user_id: str) -> User | None:
        with self.store._read() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return None if row is None else _user(row)

    def count_users(self) -> int:
        with self.store._read() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def create_user(self, email: str, name: str, role: str, password_hash: str) -> User:
        user_id = uuid.uuid4().hex
        with self.store._write() as (conn, _events):
            conn.execute(
                "INSERT INTO users (id, email, name, role, password_hash, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?)",
                (user_id, normalize_email(email), name, role, password_hash, _now()),
            )
        created = self.user_by_id(user_id)
        assert created is not None
        return created

    def seed(self, seeds: Iterable[SeedUser]) -> int:
        """Upsert every seed user in one transaction: create it, or set its name, role and hash and
        activate it again. Returns how many there were. Other users are left alone."""
        count = 0
        with self.store._write() as (conn, _events):
            for seed in seeds:
                conn.execute(
                    "INSERT INTO users (id, email, name, role, password_hash, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, 'active', ?) "
                    "ON CONFLICT (email) DO UPDATE SET name = excluded.name, "
                    "role = excluded.role, password_hash = excluded.password_hash, "
                    "status = 'active'",
                    (
                        uuid.uuid4().hex,
                        seed.email,
                        seed.name,
                        seed.role,
                        seed.password_hash,
                        _now(),
                    ),
                )
                count += 1
        return count

"""User accounts over the session store's database (COMPASS_AUTH=1).

The same SQLite file and transaction helpers as Store. Only hashes are stored: of passwords
(argon2id), invite codes and login tokens (SHA-256). Nothing here logs; a caller refers to a user
by id, never by email.
"""

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict

from compass.auth.codes import format_code, hash_secret, new_invite_code, new_token, normalize_code
from compass.auth.emails import normalize_email
from compass.auth.seed import SeedUser
from compass.state.store import Store

# last_seen_at is refreshed at most this often: a request is not a write transaction every time
LAST_SEEN_EVERY = timedelta(minutes=1)
# an expired login session is kept this long before it is deleted
KEEP_EXPIRED = timedelta(days=1)


class LastAdminError(Exception):
    """The change would leave no active admin."""


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


class LoggedIn(BaseModel):
    """A new login session: the one time the token exists in plain text."""

    user: User
    token: str = ""

    def __repr_args__(self) -> Iterable[tuple[str | None, Any]]:
        return [(k, v) for k, v in super().__repr_args__() if k != "token"]


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


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds")


class Accounts:
    def __init__(
        self, store: Store, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.store = store
        self.clock = clock  # tests move it to expire a code or a session

    def _now(self) -> str:
        return _stamp(self.clock())

    def _later(self, hours: float) -> str:
        return _stamp(self.clock() + timedelta(hours=hours))

    # --- users --------------------------------------------------------------------------------

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
                (user_id, normalize_email(email), name, role, password_hash, self._now()),
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
                        self._now(),
                    ),
                )
                count += 1
        return count

    def list_users(self) -> list[User]:
        """Every account, oldest first."""
        with self.store._read() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at, email").fetchall()
        return [_user(r) for r in rows]

    def count_active_admins(self) -> int:
        with self.store._read() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'"
            ).fetchone()
        return int(row[0])

    @staticmethod
    def _guard_last_admin(conn: Any, user_id: str) -> None:
        """Inside the write transaction (so two admins removing each other cannot both pass):
        refuse to remove the only active admin."""
        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'"
        ).fetchone()[0]
        target = conn.execute(
            "SELECT 1 FROM users WHERE id = ? AND role = 'admin' AND status = 'active'", (user_id,)
        ).fetchone()
        if target is not None and count <= 1:
            raise LastAdminError

    def update_user(self, user_id: str, role: str | None, status: str | None) -> User | None:
        """Set the role and/or status; a disabled user's login sessions end at once. None: no
        such user. Raises LastAdminError if it would leave no active admin."""
        with self.store._write() as (conn, _events):
            if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
                return None
            if (role is not None and role != "admin") or status == "disabled":
                self._guard_last_admin(conn, user_id)
            if role is not None:
                conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            if status is not None:
                conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
            if status == "disabled":
                conn.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? "
                    "AND revoked_at IS NULL",
                    (self._now(), user_id),
                )
        return self.user_by_id(user_id)

    def delete_user(self, user_id: str) -> bool:
        """Delete the account, its login sessions and its invites, in one transaction (its
        conversations are the caller's to delete afterwards). False: no such user. Raises
        LastAdminError if it is the only active admin."""
        with self.store._write() as (conn, _events):
            row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                return False
            self._guard_last_admin(conn, user_id)
            conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM invites WHERE email = ?", (row["email"],))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return True

    def record_login(self, user_id: str) -> None:
        with self.store._write() as (conn, _events):
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (self._now(), user_id))

    # --- invites ------------------------------------------------------------------------------

    def create_invite(self, email: str, role: str, created_by: str, ttl_hours: float) -> str:
        """A new one-time invite for `email`, replacing its unused one. Returns the code as the
        admin sees it (XXXXX-XXXXX): the only time it exists in plain text."""
        return self.issue_invite(email, role, created_by, ttl_hours)[0]

    def issue_invite(
        self, email: str, role: str, created_by: str, ttl_hours: float
    ) -> tuple[str, str]:
        """create_invite, with the time it expires: (code, expires_at)."""
        code = new_invite_code()
        expires_at = self._later(ttl_hours)
        with self.store._write() as (conn, _events):
            email = normalize_email(email)
            conn.execute("DELETE FROM invites WHERE email = ? AND used_at IS NULL", (email,))
            conn.execute(
                "INSERT INTO invites (id, email, role, code_hash, created_by, created_at, "
                "expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    email,
                    role,
                    hash_secret(code),
                    created_by,
                    self._now(),
                    expires_at,
                ),
            )
        return format_code(code), expires_at

    def register(
        self, email: str, code: str, name: str, password_hash: str, session_ttl_hours: float
    ) -> LoggedIn | None:
        """Use an invite: one transaction that finds an unused, unexpired invite for this email
        and code, creates the user (the invite's role), marks the invite used and opens a login
        session. None for any reason it cannot (the caller must not say which)."""
        email = normalize_email(email)
        with self.store._write() as (conn, _events):
            invite = conn.execute(
                "SELECT id, role FROM invites WHERE code_hash = ? AND email = ? "
                "AND used_at IS NULL AND expires_at > ?",
                (hash_secret(normalize_code(code)), email, self._now()),
            ).fetchone()
            if invite is None:
                return None
            if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                return None
            user_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO users (id, email, name, role, password_hash, status, created_at, "
                "last_login_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (user_id, email, name, invite["role"], password_hash, self._now(), self._now()),
            )
            conn.execute("UPDATE invites SET used_at = ? WHERE id = ?", (self._now(), invite["id"]))
            token = self._open_session(conn, user_id, session_ttl_hours)
        user = self.user_by_id(user_id)
        assert user is not None
        return LoggedIn(user=user, token=token)

    # --- login sessions -----------------------------------------------------------------------

    def _open_session(self, conn: Any, user_id: str, ttl_hours: float) -> str:
        token = new_token()
        now = self._now()
        conn.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (hash_secret(token), user_id, now, self._later(ttl_hours), now),
        )
        return token

    def open_session(self, user_id: str, ttl_hours: float) -> str:
        """A login session for the user; returns its token (never stored). Also forgets login
        sessions that expired more than a day ago."""
        with self.store._write() as (conn, _events):
            conn.execute(
                "DELETE FROM auth_sessions WHERE expires_at < ?",
                (_stamp(self.clock() - KEEP_EXPIRED),),
            )
            return self._open_session(conn, user_id, ttl_hours)

    def user_for_token(self, token: str) -> User | None:
        """The active user a live token belongs to, else None. A token is live until it is
        revoked or its absolute expiry (it is never extended). A disabled or deleted user gets
        None and every session of theirs is revoked."""
        token_hash = hash_secret(token)
        now = self._now()
        with self.store._read() as conn:
            row = conn.execute(
                "SELECT u.*, s.last_seen_at AS seen FROM auth_sessions s "
                "JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?",
                (token_hash, now),
            ).fetchone()
        if row is None:
            return None
        user = _user(row)
        if user.status != "active":
            self.revoke_user_sessions(user.id)
            return None
        if row["seen"] < _stamp(self.clock() - LAST_SEEN_EVERY):
            with self.store._write() as (conn, _events):
                conn.execute(
                    "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
                    (now, token_hash),
                )
        return user

    def revoke_token(self, token: str) -> None:
        with self.store._write() as (conn, _events):
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ? "
                "AND revoked_at IS NULL",
                (self._now(), hash_secret(token)),
            )

    def revoke_user_sessions(self, user_id: str) -> None:
        with self.store._write() as (conn, _events):
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (self._now(), user_id),
            )

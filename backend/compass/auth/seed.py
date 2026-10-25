"""COMPASS_SEED_USERS: the accounts that exist after every start (the free plan wipes the
database on each deploy, so the demo accounts are re-created from the environment).

A JSON list of {email, name, role, password_hash} and, optionally, `demo` (a JSON true: a shared
demo account, see COMPASS_DEMO_LOGIN). Only hashes: a password never goes into the
environment or a file (`tasks.py hash-password`). Errors name the entry and the key, never a value.
"""

import json
from dataclasses import dataclass, field
from typing import Literal, get_args

from compass.auth.emails import normalize_email

Role = Literal["employee", "rep", "admin"]
ROLES: tuple[str, ...] = get_args(Role)
MAX_NAME_LENGTH = 60
_KEYS = frozenset({"email", "name", "role", "password_hash"})
_OPTIONAL_KEYS = frozenset({"demo"})


class SeedError(ValueError):
    """COMPASS_SEED_USERS is malformed. The message never contains a value."""


@dataclass(frozen=True)
class SeedUser:
    email: str  # normalised
    name: str
    role: Role
    password_hash: str = field(repr=False)
    demo: bool = False


def parse_seed_users(raw: str | None) -> tuple[SeedUser, ...]:
    if not raw or not raw.strip():
        return ()
    try:
        entries = json.loads(raw)
    except ValueError:
        raise SeedError("COMPASS_SEED_USERS is not valid JSON") from None
    if not isinstance(entries, list):
        raise SeedError("COMPASS_SEED_USERS must be a JSON list")
    users: list[SeedUser] = []
    for index, entry in enumerate(entries, start=1):
        where = f"COMPASS_SEED_USERS entry {index}"
        if not isinstance(entry, dict) or not _KEYS <= set(entry) <= _KEYS | _OPTIONAL_KEYS:
            raise SeedError(f"{where} must be an object with exactly: {', '.join(sorted(_KEYS))}")
        if not all(isinstance(entry[key], str) for key in _KEYS):
            raise SeedError(f"{where}: every value must be a string")
        if not isinstance(entry.get("demo", False), bool):
            raise SeedError(f"{where}: demo must be true or false")
        email = normalize_email(entry["email"])
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise SeedError(f"{where}: email is not an email address")
        name = entry["name"].strip()
        if not 1 <= len(name) <= MAX_NAME_LENGTH:
            raise SeedError(f"{where}: name must be 1 to {MAX_NAME_LENGTH} characters")
        if entry["role"] not in ROLES:
            raise SeedError(f"{where}: role must be one of {', '.join(ROLES)}")
        if not entry["password_hash"]:
            raise SeedError(f"{where}: password_hash is empty")
        users.append(
            SeedUser(email, name, entry["role"], entry["password_hash"], entry.get("demo", False))
        )
    if len({u.email for u in users}) != len(users):
        raise SeedError("COMPASS_SEED_USERS lists the same email twice")
    return tuple(users)

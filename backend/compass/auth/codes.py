"""Invite codes and login tokens: generated here, shown once, stored only as SHA-256 hashes.

A code is 10 characters from an alphabet without 0/O/1/I, shown as XXXXX-XXXXX. A token is
`secrets.token_urlsafe(32)`. Both are high-entropy random values, so an unsalted SHA-256 is enough
to store them (there is nothing to guess, unlike a password), and a lookup by hash needs no
timing-sensitive comparison.
"""

import hashlib
import secrets

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I
CODE_LENGTH = 10
MAX_CODE_INPUT = 64


def new_invite_code() -> str:
    """A fresh code, ungrouped (what is hashed): 10 characters."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def format_code(code: str) -> str:
    """XXXXX-XXXXX, for showing the admin."""
    return f"{code[:5]}-{code[5:]}"


def normalize_code(raw: str) -> str:
    """What the employee typed, as the stored form: no dashes or spaces, upper case."""
    return "".join(raw.split()).replace("-", "").upper()[:MAX_CODE_INPUT]


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

"""Password hashing: argon2id with the library's defaults (argon2-cffi).

A hash is stored and compared; a password is never kept, logged or returned. `verify_password`
answers False for anything that is not a valid hash, so a bad stored value can never let a login in.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
ARGON2ID_PREFIX = "$argon2id$"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def is_argon2id(password_hash: str) -> bool:
    """Whether the string is an argon2id hash (what COMPASS_SEED_USERS must hold)."""
    if not password_hash.startswith(ARGON2ID_PREFIX):
        return False
    try:
        _hasher.check_needs_rehash(password_hash)
    except (VerificationError, InvalidHashError):
        return False
    return True

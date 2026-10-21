"""Hashing and verification, and one spelling of an email."""

import pytest

from compass.auth.emails import normalize_email
from compass.auth.passwords import hash_password, is_argon2id, verify_password


def test_hash_is_argon2id_and_salted() -> None:
    first, second = hash_password("correct horse battery"), hash_password("correct horse battery")
    assert first.startswith("$argon2id$") and is_argon2id(first)
    assert first != second  # a fresh salt each time
    assert "correct horse" not in first


def test_verify_accepts_the_password_and_nothing_else() -> None:
    stored = hash_password("correct horse battery")
    assert verify_password(stored, "correct horse battery")
    assert not verify_password(stored, "correct horse batterY")
    assert not verify_password(stored, "")


@pytest.mark.parametrize("bad", ["", "plain text", "$argon2id$garbage", "$2b$12$abcdefghijklmnop"])
def test_a_bad_stored_value_never_verifies(bad: str) -> None:
    assert not verify_password(bad, "anything at all")
    assert not is_argon2id(bad)


def test_other_argon2_variants_are_not_argon2id() -> None:
    from argon2 import PasswordHasher, Type

    argon2i = PasswordHasher(type=Type.I).hash("correct horse battery")
    assert not is_argon2id(argon2i)


@pytest.mark.parametrize(
    "spelling",
    [
        "Dana@X.com ",
        "  dana@x.com",
        "DANA@X.COM",
        "dana@x.com",
        "ｄａｎａ＠ｘ．ｃｏｍ",  # full-width forms
        "dana@x.com ",
    ],
)
def test_emails_normalise_to_one_spelling(spelling: str) -> None:
    assert normalize_email(spelling) == "dana@x.com"

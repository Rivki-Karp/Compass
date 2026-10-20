"""Invite codes and the login guard, on their own."""

from compass.auth.codes import (
    CODE_ALPHABET,
    format_code,
    hash_secret,
    new_invite_code,
    new_token,
    normalize_code,
)
from compass.auth.limits import LoginGuard


def test_codes_are_10_unambiguous_characters_shown_in_two_groups() -> None:
    assert not set("0O1I") & set(CODE_ALPHABET) and len(CODE_ALPHABET) == 32
    codes = {new_invite_code() for _ in range(200)}
    assert len(codes) == 200  # no repeats in a few hundred
    for code in codes:
        assert len(code) == 10 and set(code) <= set(CODE_ALPHABET)
    shown = format_code("ABCDEFGHJK")
    assert shown == "ABCDE-FGHJK"


def test_a_typed_code_is_normalised() -> None:
    assert normalize_code(" abcde-fghjk ") == "ABCDEFGHJK"
    assert normalize_code("abcde fghjk") == "ABCDEFGHJK"
    assert len(normalize_code("x" * 5000)) <= 64  # bounded before hashing


def test_tokens_are_long_random_and_hashed_with_sha256() -> None:
    first, second = new_token(), new_token()
    assert first != second and len(first) >= 43
    assert len(hash_secret(first)) == 64 and hash_secret(first) != first


def _guard(now: list[float], **kw: int) -> LoginGuard:
    return LoginGuard(
        kw.get("ip", 10), kw.get("failures", 5), kw.get("lock", 900), clock=lambda: now[0]
    )


def test_failures_in_a_row_lock_and_the_lock_ends() -> None:
    now = [0.0]
    guard = _guard(now)
    for _ in range(4):
        guard.record_failure("a@x.com")
    assert not guard.is_locked("a@x.com")
    guard.record_failure("a@x.com")
    assert guard.is_locked("a@x.com") and not guard.is_locked("b@x.com")
    now[0] = 899
    assert guard.is_locked("a@x.com")
    now[0] = 901
    assert not guard.is_locked("a@x.com")


def test_old_failures_are_forgotten_and_a_success_clears() -> None:
    now = [0.0]
    guard = _guard(now)
    for _ in range(4):
        guard.record_failure("a@x.com")
    now[0] = 1000  # idle for longer than the lock: the count starts again
    guard.record_failure("a@x.com")
    assert not guard.is_locked("a@x.com")
    for _ in range(3):
        guard.record_failure("a@x.com")
    guard.record_success("a@x.com")
    guard.record_failure("a@x.com")
    assert not guard.is_locked("a@x.com")


def test_attempts_per_ip_per_minute() -> None:
    now = [0.0]
    guard = _guard(now, ip=3)
    assert [guard.check_ip("1.2.3.4") for _ in range(3)] == [None, None, None]
    assert guard.check_ip("1.2.3.4") is not None
    assert guard.check_ip("5.6.7.8") is None
    now[0] = 61
    assert guard.check_ip("1.2.3.4") is None

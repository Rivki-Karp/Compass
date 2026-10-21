"""Invite codes and the login guard, on their own."""

import pytest

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
        kw.get("ip", 10),
        kw.get("failures", 5),
        kw.get("lock", 900),
        kw.get("ceiling", 50),
        kw.get("window", 3600),
        clock=lambda: now[0],
    )


def test_failures_in_a_row_lock_and_the_lock_ends() -> None:
    now = [0.0]
    guard = _guard(now)
    for _ in range(4):
        guard.record_failure("a@x.com", "1.1.1.1")
    assert not guard.is_locked("a@x.com", "1.1.1.1")
    guard.record_failure("a@x.com", "1.1.1.1")
    assert guard.is_locked("a@x.com", "1.1.1.1") and not guard.is_locked("b@x.com", "1.1.1.1")
    now[0] = 899
    assert guard.is_locked("a@x.com", "1.1.1.1")
    now[0] = 901
    assert not guard.is_locked("a@x.com", "1.1.1.1")


def test_a_lock_from_one_address_does_not_block_another() -> None:
    now = [0.0]
    guard = _guard(now)
    for _ in range(5):
        guard.record_failure("a@x.com", "1.1.1.1")
    assert guard.is_locked("a@x.com", "1.1.1.1")
    assert not guard.is_locked("a@x.com", "2.2.2.2")  # the same email, elsewhere
    assert not guard.is_locked("b@x.com", "1.1.1.1")  # another email, the same address


def test_many_addresses_hit_the_ceiling_on_the_email(caplog: pytest.LogCaptureFixture) -> None:
    now = [0.0]
    guard = _guard(now, ceiling=12)
    for i in range(11):  # one failure from each of many addresses: no pair ever locks
        guard.record_failure("a@x.com", f"10.0.0.{i}")
    assert not guard.is_locked("a@x.com", "10.9.9.9")
    with caplog.at_level("WARNING"):
        guard.record_failure("a@x.com", "10.0.0.99")
    assert guard.is_locked("a@x.com", "10.9.9.9") and not guard.is_locked("b@x.com", "10.9.9.9")
    assert "ceiling" in caplog.text and "a@x.com" not in caplog.text and "10.0.0" not in caplog.text
    now[0] = 901  # the lock ends after the lock time
    assert not guard.is_locked("a@x.com", "10.9.9.9")


def test_the_ceiling_counts_a_sliding_window() -> None:
    now = [0.0]
    guard = _guard(now, ceiling=5, window=100)
    for i in range(4):
        guard.record_failure("a@x.com", f"10.0.0.{i}")
    now[0] = 101  # those four are out of the window
    for i in range(4):
        guard.record_failure("a@x.com", f"10.0.1.{i}")
    assert not guard.is_locked("a@x.com", "10.9.9.9")


def test_old_failures_are_forgotten_and_a_success_clears() -> None:
    now = [0.0]
    guard = _guard(now)
    ip = "1.1.1.1"
    for _ in range(4):
        guard.record_failure("a@x.com", ip)
    now[0] = 1000  # idle for longer than the lock: the count starts again
    guard.record_failure("a@x.com", ip)
    assert not guard.is_locked("a@x.com", ip)
    for _ in range(3):
        guard.record_failure("a@x.com", ip)
    guard.record_success("a@x.com", ip)
    guard.record_failure("a@x.com", ip)
    assert not guard.is_locked("a@x.com", ip)


def test_attempts_per_ip_per_minute() -> None:
    now = [0.0]
    guard = _guard(now, ip=3)
    assert [guard.check_ip("1.2.3.4") for _ in range(3)] == [None, None, None]
    assert guard.check_ip("1.2.3.4") is not None
    assert guard.check_ip("5.6.7.8") is None
    now[0] = 61
    assert guard.check_ip("1.2.3.4") is None

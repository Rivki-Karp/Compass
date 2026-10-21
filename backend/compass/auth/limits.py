"""Login limits, in memory (one server process, as the agent and the rate limiter need).

Three limits:

* attempts per client IP per minute (the shared RateLimiter);
* failures per (email, IP) pair: after `max_failures` the pair is locked for `lock_seconds`. A
  lock from one address does not block the same email from another, so nobody in the room can
  lock a demo account out;
* a looser ceiling per email over all addresses: `email_ceiling` failures within
  `email_window_seconds` lock that email for `lock_seconds` whoever asks, so a many-address
  attack on one account still ends.

A failure is counted whether or not an account has the email, so a lock looks the same for a real
and an invented address and never tells which exists. A success clears the pair's count (not the
email's window). Failures that stop for `lock_seconds` are forgotten.
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from compass.api.ratelimit import RateLimiter

log = logging.getLogger("compass.auth")

MAX_TRACKED = 10_000  # bounded memory: idle entries are dropped past this


@dataclass
class _Failures:
    count: int
    last: float
    locked_until: float = 0.0


class LoginGuard:
    def __init__(
        self,
        per_ip_per_minute: int,
        max_failures: int,
        lock_seconds: float,
        email_ceiling: int = 50,
        email_window_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.lock_seconds = lock_seconds
        self.email_ceiling = email_ceiling
        self.email_window_seconds = email_window_seconds
        self.clock = clock
        self.ips = RateLimiter(per_ip_per_minute, clock=lambda: self.clock())
        self._pairs: dict[tuple[str, str], _Failures] = {}
        self._emails: dict[str, deque[float]] = {}
        self._email_locks: dict[str, float] = {}
        self._lock = threading.Lock()

    def check_ip(self, ip: str) -> int | None:
        """Record an attempt from `ip`; None if allowed, else the seconds to wait."""
        return self.ips.check(ip)

    def is_locked(self, email: str, ip: str) -> bool:
        now = self.clock()
        with self._lock:
            pair = self._pairs.get((email, ip))
            return (pair is not None and pair.locked_until > now) or (
                self._email_locks.get(email, 0.0) > now
            )

    def record_failure(self, email: str, ip: str) -> None:
        now = self.clock()
        with self._lock:
            pair = self._pairs.get((email, ip))
            if pair is None or now - pair.last >= self.lock_seconds:
                pair = self._pairs[(email, ip)] = _Failures(0, now)
            pair.count += 1
            pair.last = now
            if pair.count >= self.max_failures:
                pair.locked_until = now + self.lock_seconds

            window = self._emails.setdefault(email, deque())
            while window and window[0] <= now - self.email_window_seconds:
                window.popleft()
            window.append(now)
            if len(window) >= self.email_ceiling and self._email_locks.get(email, 0.0) <= now:
                self._email_locks[email] = now + self.lock_seconds
                window.clear()
                # no identifier: which email, or from where, is not for the log
                log.warning("login: an email reached the failure ceiling and is locked")
            if len(self._pairs) > MAX_TRACKED or len(self._emails) > MAX_TRACKED:
                self._forget_idle(now)

    def record_success(self, email: str, ip: str) -> None:
        with self._lock:
            self._pairs.pop((email, ip), None)

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, e in self._pairs.items() if now - e.last >= self.lock_seconds]:
            del self._pairs[key]
        cutoff = now - self.email_window_seconds
        for key in [k for k, w in self._emails.items() if not w or w[-1] <= cutoff]:
            del self._emails[key]
        for key in [k for k, until in self._email_locks.items() if until <= now]:
            del self._email_locks[key]

"""Login limits, in memory (one server process, as the agent and the rate limiter need).

Two limits: attempts per client IP per minute (the shared RateLimiter), and failures per email.
A failure is counted for the normalised email whether or not an account has it, so a lock looks
the same for a real and an invented address and never tells which exists. After `max_failures`
failures the email is locked for `lock_seconds`; a success clears its count, and failures that
stop for `lock_seconds` are forgotten.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from compass.api.ratelimit import RateLimiter

MAX_TRACKED = 10_000  # bounded memory: expired entries are dropped past this


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
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.lock_seconds = lock_seconds
        self.clock = clock
        self.ips = RateLimiter(per_ip_per_minute, clock=lambda: self.clock())
        self._failures: dict[str, _Failures] = {}
        self._lock = threading.Lock()

    def check_ip(self, ip: str) -> int | None:
        """Record an attempt from `ip`; None if allowed, else the seconds to wait."""
        return self.ips.check(ip)

    def is_locked(self, email: str) -> bool:
        now = self.clock()
        with self._lock:
            entry = self._failures.get(email)
            return entry is not None and entry.locked_until > now

    def record_failure(self, email: str) -> None:
        now = self.clock()
        with self._lock:
            entry = self._failures.get(email)
            if entry is None or now - entry.last >= self.lock_seconds:
                entry = self._failures[email] = _Failures(0, now)
            entry.count += 1
            entry.last = now
            if entry.count >= self.max_failures:
                entry.locked_until = now + self.lock_seconds
            if len(self._failures) > MAX_TRACKED:
                self._forget_idle(now)

    def record_success(self, email: str) -> None:
        with self._lock:
            self._failures.pop(email, None)

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, e in self._failures.items() if now - e.last >= self.lock_seconds]:
            del self._failures[key]

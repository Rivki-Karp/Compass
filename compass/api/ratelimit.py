"""A per-key sliding-window rate limit, in memory (one server process, as the agent needs).

    limiter = RateLimiter(per_minute=20)
    limiter.check("203.0.113.7")  -> None if allowed, else the seconds until the next slot

The key is the client's IP (client_ip): the socket's address, or, behind a platform's reverse
proxy with COMPASS_TRUST_PROXY=1, the rightmost X-Forwarded-For entry, the one that proxy added
(docs/demo-runbook.md, "Before a public deployment").
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.requests import Request


def client_ip(request: Request, trust_proxy: bool) -> str:
    """The IP to rate-limit. With `trust_proxy`, the rightmost X-Forwarded-For entry: the address
    the platform's proxy saw and appended. Entries to its left come from the client and can be
    forged, so they are never used. Without it, or with no header, the socket's address."""
    if trust_proxy:
        forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
        entries = [entry.strip() for entry in forwarded.split(",") if entry.strip()]
        if entries:
            return entries[-1]
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(
        self, per_minute: int, window: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.per_minute = per_minute
        self.window = window
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """Record a hit for `key` if it is allowed; else the whole seconds to wait (Retry-After)."""
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle keys now and then; bounded memory
                for idle in [k for k, h in self._hits.items() if not h]:
                    del self._hits[idle]
            return None

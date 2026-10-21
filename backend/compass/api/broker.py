"""Wake SSE streams when the store commits an event.

The events table is the source of truth; this only says "look again". The store calls
`publish` after commit from whatever thread wrote, so wake-ups hop onto the event loop.

Besides one channel per session, TICKETS wakes the representative's inbox stream on any event
that changes a ticket or the comparison a ticket shows.
"""

import asyncio
from collections import defaultdict

from compass.state import Event

TICKETS = "*tickets"  # not a session id (those are hex)
TICKET_EVENTS = frozenset({"ticket_opened", "ticket_answered", "comparison_ready"})


class Broker:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._waiters: defaultdict[str, set[asyncio.Event]] = defaultdict(set)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: Event) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._wake, event.session_id)
        if event.type in TICKET_EVENTS:
            loop.call_soon_threadsafe(self._wake, TICKETS)

    def wake(self, *channels: str) -> None:
        """Wake streams without an event (a session was deleted; the inbox lost a ticket)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for channel in channels:
            loop.call_soon_threadsafe(self._wake, channel)

    def _wake(self, session_id: str) -> None:
        for waiter in self._waiters.get(session_id, ()):
            waiter.set()

    def has_stream(self, session_id: str) -> bool:
        """Is an events stream open on this session right now?"""
        return bool(self._waiters.get(session_id))

    def subscribe(self, session_id: str) -> asyncio.Event:
        waiter = asyncio.Event()
        self._waiters[session_id].add(waiter)
        return waiter

    def unsubscribe(self, session_id: str, waiter: asyncio.Event) -> None:
        waiters = self._waiters.get(session_id)
        if waiters is not None:
            waiters.discard(waiter)
            if not waiters:
                del self._waiters[session_id]

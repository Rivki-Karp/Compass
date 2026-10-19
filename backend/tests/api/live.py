"""A real uvicorn server in a background thread, and an SSE reader (for streaming tests).

The in-process TestClient can't consume a never-ending SSE response, so streaming is tested
against a real socket.
"""

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI


@contextmanager
def live_server(app: FastAPI) -> Iterator[str]:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


class SSEReader:
    """Reads one SSE stream in a thread; events land in `events` as dicts."""

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self.comments = 0
        self._url, self._headers = url, headers or {}
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "SSEReader":
        self._thread.start()
        if not self._connected.wait(10):
            raise RuntimeError("SSE stream did not connect")
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        with (
            httpx.Client(timeout=httpx.Timeout(30, read=30)) as client,
            client.stream("GET", self._url, headers=self._headers) as response,
        ):
            response.raise_for_status()
            self._connected.set()
            current: dict[str, Any] = {}
            for line in response.iter_lines():
                if self._stop.is_set():
                    return
                if line.startswith(":"):
                    self.comments += 1  # heartbeat
                elif not line:
                    if current:
                        self.events.append(current)
                        current = {}
                else:
                    key, _, value = line.partition(":")
                    value = value.removeprefix(" ")
                    if key == "data":
                        current["data"] = json.loads(value)
                    elif key in ("id", "event"):
                        current[key] = int(value) if key == "id" else value

    def wait_for(self, event_type: str, timeout: float = 10) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get("event") == event_type:
                    return event
            time.sleep(0.02)
        raise AssertionError(f"no {event_type} event; got {[e.get('event') for e in self.events]}")

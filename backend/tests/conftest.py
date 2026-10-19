import sqlite3
from collections.abc import Iterator

import pytest

from compass.config import VEHICLES_DB


@pytest.fixture(scope="session")
def vehicles_conn() -> Iterator[sqlite3.Connection]:
    if not VEHICLES_DB.is_file():
        pytest.fail(f"{VEHICLES_DB} is missing — run `uv run python tasks.py data` first")
    conn = sqlite3.connect(f"{VEHICLES_DB.as_uri()}?mode=ro", uri=True)
    yield conn
    conn.close()

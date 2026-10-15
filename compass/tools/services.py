"""What the tools stand on: the session store, the current engine data and the search index.

The engine context and the searcher are swapped together on a live rules reload. A reload
validates the new file first; if it is invalid the previous rules stay active.
"""

import copy
import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path

from compass.config import ALIASES_YAML, RULES_YAML, VEHICLES_DB
from compass.engine.context import EngineContext, build_context
from compass.rules import Rules, load_rules
from compass.search import Searcher, load_aliases
from compass.state import Store


@dataclass(frozen=True)
class _Data:
    ctx: EngineContext
    searcher: Searcher
    rules_sha256: str


class Services:
    def __init__(
        self,
        store: Store,
        rules_path: Path = RULES_YAML,
        aliases_path: Path = ALIASES_YAML,
        vehicles_db: Path = VEHICLES_DB,
    ) -> None:
        self.store = store
        self.rules_path = rules_path
        self.aliases_path = aliases_path
        self.vehicles_db = vehicles_db
        self._lock = threading.Lock()
        self._data = self._build()

    def _build(self) -> _Data:
        """Read and validate everything; raises without touching the active data."""
        sha256 = hashlib.sha256(self.rules_path.read_bytes()).hexdigest()
        ctx = build_context(rules=load_rules(self.rules_path))
        searcher = Searcher(
            ctx.catalog,
            ctx.occupations,
            load_aliases(self.aliases_path),
            ctx.rules.value_of_use.tax_year,
            vehicles_db=self.vehicles_db,
        )
        return _Data(ctx=ctx, searcher=searcher, rules_sha256=sha256)

    @property
    def ctx(self) -> EngineContext:
        return self._data.ctx

    @property
    def searcher(self) -> Searcher:
        return self._data.searcher

    @property
    def rules_sha256(self) -> str:
        """SHA-256 of the rules file as it was when the active rules were loaded."""
        return self._data.rules_sha256

    def pinned(self) -> "Services":
        """A view whose rules, catalog and searcher stay fixed even if a reload happens, so
        one tool call never mixes old and new rules."""
        view = copy.copy(self)
        view._data = self._data
        return view

    def reload_rules(self) -> Rules:
        """Re-read rules_path. Raises RulesError / ContextError and keeps the old rules."""
        with self._lock:
            data = self._build()  # validate fully before swapping
            self._data = data
            return data.ctx.rules

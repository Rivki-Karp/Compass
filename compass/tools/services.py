"""What the tools stand on: the session store, the current engine data and the search index.

The engine context and the searcher are swapped together on a live rules reload. A reload
validates the new file first; if it is invalid the previous rules stay active.
"""

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
        self._data = self._build(load_rules(rules_path))

    def _build(self, rules: Rules) -> _Data:
        ctx = build_context(rules=rules)
        searcher = Searcher(
            ctx.catalog,
            ctx.occupations,
            load_aliases(self.aliases_path),
            ctx.rules.value_of_use.tax_year,
            vehicles_db=self.vehicles_db,
        )
        return _Data(ctx=ctx, searcher=searcher)

    @property
    def ctx(self) -> EngineContext:
        return self._data.ctx

    @property
    def searcher(self) -> Searcher:
        return self._data.searcher

    def reload_rules(self) -> Rules:
        """Re-read rules_path. Raises RulesError / ContextError and keeps the old rules."""
        with self._lock:
            data = self._build(load_rules(self.rules_path))  # validate fully before swapping
            self._data = data
            return data.ctx.rules

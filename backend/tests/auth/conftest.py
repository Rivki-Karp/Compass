import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from compass.api import Settings
from compass.config import RULES_YAML


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    rules = tmp_path / "rules.yaml"
    shutil.copyfile(RULES_YAML, rules)

    def make(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "app_db": tmp_path / "app.db",
            "rules_path": rules,
            "heartbeat_seconds": 1.0,
        }
        values.update(overrides)
        return Settings(**values)  # type: ignore[arg-type]

    return make

import pytest

from compass.engine.context import EngineContext, build_context


@pytest.fixture(scope="session")
def ctx() -> EngineContext:
    return build_context()

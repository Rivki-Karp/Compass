from compass import config


def test_paths_are_resolved_under_backend_root() -> None:
    assert (config.BACKEND_ROOT / "pyproject.toml").is_file()
    for path in (config.RAW_DIR, config.DATA_DIR, config.FIXTURES_DIR, config.VEHICLES_DB):
        assert path.is_absolute()
        assert path.is_relative_to(config.BACKEND_ROOT)

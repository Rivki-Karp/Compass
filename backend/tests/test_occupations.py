import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from compass.data.occupations import get_occupation, load_occupations


def test_fourteen_occupations() -> None:
    occupations = load_occupations()
    assert len(occupations) == 14
    assert len({o.title for o in occupations}) == 14


def test_software_developer_may_waive() -> None:
    dev = get_occupation("מפתח/ת תוכנה")
    assert dev is not None
    assert dev.group == "ב"
    assert dev.car_mandatory is False
    assert dev.waiver_allowed is True
    assert dev.waiver_maintenance == Decimal(1500)
    assert isinstance(dev.waiver_maintenance, Decimal)


def test_service_technician_car_is_mandatory() -> None:
    tech = get_occupation("טכנאי/ת שירות")
    assert tech is not None
    assert tech.car_mandatory is True
    assert tech.waiver_allowed is False


def test_exact_match_only() -> None:
    assert get_occupation("מפתח תוכנה") is None
    assert get_occupation(" מפתח/ת תוכנה") is None


def _write(tmp_path: Path, **overrides: object) -> Path:
    occupation = {
        "title": "בודק/ת",
        "group": "א",
        "car_mandatory": False,
        "waiver_allowed": True,
        "waiver_maintenance": 1200,
        **overrides,
    }
    path = tmp_path / "occupations.json"
    path.write_text(json.dumps([occupation], ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_custom_file_loads(tmp_path: Path) -> None:
    assert load_occupations(_write(tmp_path))[0].waiver_maintenance == Decimal(1200)
    mandatory = _write(tmp_path, car_mandatory=True, waiver_allowed=False, waiver_maintenance=0)
    assert load_occupations(mandatory)[0].car_mandatory is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"car_mandatory": True, "waiver_allowed": True, "waiver_maintenance": 1200},
        {"car_mandatory": True, "waiver_allowed": False, "waiver_maintenance": 500},
    ],
    ids=["mandatory-but-waivable", "mandatory-with-maintenance"],
)
def test_mandatory_car_forbids_waiver(tmp_path: Path, overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="car is mandatory"):
        load_occupations(_write(tmp_path, **overrides))


@pytest.mark.parametrize("maintenance", [0, -100])
def test_waiver_requires_positive_maintenance(tmp_path: Path, maintenance: int) -> None:
    with pytest.raises(ValidationError, match="waiver_maintenance must be positive"):
        load_occupations(_write(tmp_path, waiver_maintenance=maintenance))

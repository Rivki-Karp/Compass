from decimal import Decimal

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

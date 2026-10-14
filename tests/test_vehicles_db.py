import sqlite3
from decimal import Decimal

import pytest

from compass.config import RAW_VALUE_OF_USE_CSV
from compass.data.vehicles import find_by_codes, get_value_of_use


def test_row_count(vehicles_conn: sqlite3.Connection) -> None:
    (count,) = vehicles_conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()
    assert count == 77_988


def test_primary_key_is_unique(vehicles_conn: sqlite3.Connection) -> None:
    (distinct,) = vehicles_conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT tax_year, registration_year, vehicle_type_code,"
        " manufacturer_code, model_code FROM vehicles)"
    ).fetchone()
    assert distinct == 77_988


def test_codes_keep_leading_zeros(vehicles_conn: sqlite3.Connection) -> None:
    rows = vehicles_conn.execute(
        "SELECT manufacturer_code, model_code, typeof(manufacturer_code), typeof(model_code)"
        " FROM vehicles WHERE manufacturer_code = '00413' LIMIT 1"
    ).fetchall()
    assert rows == [("00413", rows[0][1], "text", "text")]
    assert len(rows[0][1]) == 5
    (bad,) = vehicles_conn.execute(
        "SELECT COUNT(*) FROM vehicles"
        " WHERE length(manufacturer_code) != 5 OR length(model_code) != 5"
    ).fetchone()
    assert bad == 0


def test_drive_code_follows_rules_mapping_not_csv_header(
    vehicles_conn: sqlite3.Connection,
) -> None:
    # Header claims 1=electric, 2=hybrid, 3=plug-in; data is 0=petrol 1=hybrid 2=plug-in 3=electric.
    def drive(manufacturer_code: str, model_code: str) -> int:
        (code,) = vehicles_conn.execute(
            "SELECT drive_code FROM vehicles WHERE registration_year = 2025"
            " AND vehicle_type_code = 1 AND manufacturer_code = ? AND model_code = ?",
            (manufacturer_code, model_code),
        ).fetchone()
        return code

    assert drive("01014", "00003") == 3  # BYD ATTO 3 -> electric
    assert drive("01014", "00012") == 3  # BYD DOLPHIN -> electric
    assert drive("00672", "00130") == 1  # Toyota YARIS CROSS HSD -> hybrid
    assert drive("00885", "00643") == 0  # Kia PICANTO -> petrol


def test_effective_date_is_iso(vehicles_conn: sqlite3.Connection) -> None:
    (bad,) = vehicles_conn.execute(
        "SELECT COUNT(*) FROM vehicles WHERE effective_date NOT GLOB"
        " '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'"
    ).fetchone()
    assert bad == 0


def test_meta_records_source(vehicles_conn: sqlite3.Connection) -> None:
    meta = dict(vehicles_conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta["source_filename"] == RAW_VALUE_OF_USE_CSV.name
    assert meta["row_count"] == "77988"
    assert len(meta["source_sha256"]) == 64
    assert meta["built_at"]


# --- data-access layer ----------------------------------------------------------------------


def test_drive_mapping_via_records() -> None:
    def summary(manufacturer_code: str, model_code: str) -> tuple[str, int, str]:
        found = get_value_of_use(2026, 2025, 1, manufacturer_code, model_code)
        assert found is not None
        return found.commercial_name, found.drive_code, found.drive

    assert summary("01014", "00003") == ("ATTO 3", 3, "electric")
    assert summary("00672", "00130") == ("YARIS CROSS HSD", 1, "hybrid")
    assert summary("00885", "00643") == ("PICANTO", 0, "petrol")


def test_codes_alone_are_ambiguous_atto3_vs_tang() -> None:
    # Same manufacturer/model codes + registration year -> two DIFFERENT vehicles.
    matches = find_by_codes("01014", "00003", 2025)
    assert [(m.vehicle_type_code, m.commercial_name, m.value_of_use) for m in matches] == [
        (1, "ATTO 3", Decimal(3130)),
        (2, "TANG", Decimal(6950)),
    ]
    assert matches[0].commercial_name != matches[1].commercial_name


def test_full_official_key_returns_exactly_atto3() -> None:
    record = get_value_of_use(2026, 2025, 1, "01014", "00003")
    assert record is not None
    assert record.commercial_name == "ATTO 3"
    assert record.value_of_use == Decimal(3130)
    assert isinstance(record.value_of_use, Decimal)
    assert record.manufacturer_code == "01014"


def test_unknown_key_returns_none_and_no_matches() -> None:
    assert get_value_of_use(2026, 2025, 1, "01014", "99999") is None
    assert find_by_codes("01014", "99999", 2025) == []
    assert find_by_codes("01014", "00003", 2025, tax_year=2025) == []


@pytest.mark.parametrize("bad", [413, "413", "0041", "00413 "])
def test_codes_must_be_zero_padded_strings(bad: object) -> None:
    with pytest.raises(ValueError, match="5-digit zero-padded string"):
        find_by_codes(bad, "00296", 2025)  # type: ignore[arg-type]


def test_records_are_frozen() -> None:
    record = get_value_of_use(2026, 2025, 1, "01014", "00003")
    assert record is not None
    with pytest.raises(ValueError):
        record.value_of_use = Decimal(0)  # type: ignore[misc]

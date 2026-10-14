import sqlite3

from compass.config import RAW_VALUE_OF_USE_CSV


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

"""Lookups in the Tax Authority value-of-use dataset (data/vehicles.db).

Only the full official key (tax year, registration year, vehicle type, manufacturer code, model
code) identifies a vehicle. Partial lookups return every match and never pick one: e.g. codes
01014/00003 (2025) are a private BYD ATTO 3 AND a commercial BYD TANG.
"""

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from compass.config import VEHICLES_DB
from compass.data.drive import DRIVE_BY_CODE, Drive

_COLUMNS = (
    "tax_year, registration_year, vehicle_type_code, manufacturer_code, manufacturer_name,"
    " model_code, model_description, fuel_type_code, commercial_name, is_automatic, drive_code,"
    " green_score, pollution_level, engine_cc, weight_kg, effective_date, list_price,"
    " adjusted_price, value_of_use"
)


class VehicleRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tax_year: int
    registration_year: int
    vehicle_type_code: int  # 1 = private, 2 = commercial
    manufacturer_code: str
    manufacturer_name: str
    model_code: str
    model_description: str
    fuel_type_code: int  # raw code; no source defines its labels
    commercial_name: str
    is_automatic: bool
    drive_code: int
    green_score: int
    pollution_level: int
    engine_cc: int
    weight_kg: int
    effective_date: date
    list_price: Decimal
    adjusted_price: Decimal
    value_of_use: Decimal  # ILS / month

    @property
    def drive(self) -> Drive:
        return DRIVE_BY_CODE[self.drive_code]


def _check_code(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 5 or not value.isdigit():
        raise ValueError(
            f"{name} must be a 5-digit zero-padded string (e.g. '00413'), got {value!r}"
        )


def _query(db_path: Path, where: str, params: tuple[object, ...]) -> list[VehicleRecord]:
    if not db_path.is_file():
        raise FileNotFoundError(f"{db_path} is missing; run `uv run python tasks.py data`")
    conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM vehicles WHERE {where} ORDER BY vehicle_type_code", params
        ).fetchall()
    finally:
        conn.close()
    return [VehicleRecord.model_validate(dict(row)) for row in rows]


def get_value_of_use(
    tax_year: int,
    registration_year: int,
    vehicle_type_code: int,
    manufacturer_code: str,
    model_code: str,
    db_path: Path = VEHICLES_DB,
) -> VehicleRecord | None:
    """Exact lookup by the full official key; None if the vehicle is not in the dataset."""
    _check_code("manufacturer_code", manufacturer_code)
    _check_code("model_code", model_code)
    records = _query(
        db_path,
        "tax_year = ? AND registration_year = ? AND vehicle_type_code = ?"
        " AND manufacturer_code = ? AND model_code = ?",
        (tax_year, registration_year, vehicle_type_code, manufacturer_code, model_code),
    )
    return records[0] if records else None


def find_by_codes(
    manufacturer_code: str,
    model_code: str,
    registration_year: int,
    tax_year: int = 2026,
    db_path: Path = VEHICLES_DB,
) -> list[VehicleRecord]:
    """All vehicles matching the codes, across vehicle types. The caller must disambiguate."""
    _check_code("manufacturer_code", manufacturer_code)
    _check_code("model_code", model_code)
    return _query(
        db_path,
        "tax_year = ? AND registration_year = ? AND manufacturer_code = ? AND model_code = ?",
        (tax_year, registration_year, manufacturer_code, model_code),
    )


def commercial_names(
    tax_year: int,
    vehicle_type_code: int = 1,
    registration_year: int | None = None,
    db_path: Path = VEHICLES_DB,
) -> list[str]:
    """Distinct commercial names (for fuzzy search). A name is NOT a key; see find_by_names()."""
    if not db_path.is_file():
        raise FileNotFoundError(f"{db_path} is missing; run `uv run python tasks.py data`")
    where = "tax_year = ? AND vehicle_type_code = ?"
    params: tuple[object, ...] = (tax_year, vehicle_type_code)
    if registration_year is not None:
        where += " AND registration_year = ?"
        params += (registration_year,)
    conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            f"SELECT DISTINCT commercial_name FROM vehicles WHERE {where} ORDER BY 1", params
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def find_by_names(
    names: list[str],
    tax_year: int,
    vehicle_type_code: int = 1,
    registration_year: int | None = None,
    db_path: Path = VEHICLES_DB,
) -> list[VehicleRecord]:
    """Every full-key record with one of these commercial names (often several per name)."""
    if not names:
        return []
    where = (
        f"tax_year = ? AND vehicle_type_code = ? AND commercial_name IN "
        f"({', '.join('?' * len(names))})"
    )
    params: tuple[object, ...] = (tax_year, vehicle_type_code, *names)
    if registration_year is not None:
        where += " AND registration_year = ?"
        params += (registration_year,)
    records = _query(db_path, where, params)
    return sorted(
        records,
        key=lambda r: (r.commercial_name, -r.registration_year, r.manufacturer_code, r.model_code),
    )

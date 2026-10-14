"""Build data/vehicles.db from the Tax Authority "value of use" CSV (raw/value_of_use_2026.csv).

Fail-fast: any deviation from the expected shape aborts the build and leaves the existing
database untouched (we build into a temp file and atomically replace).

Note on drive_code: the CSV header reads "1-חשמלי.2-היברידי.3-פלג-אין", but the data follows
the rules-file mapping 0=petrol, 1=hybrid, 2=plug-in, 3=electric. We store the raw code; see
raw/README.md.
"""

import csv
import hashlib
import os
import sqlite3
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from compass.config import RAW_VALUE_OF_USE_CSV, VEHICLES_DB

EXPECTED_ROW_COUNT = 77_988
SOURCE_ENCODING = "cp1255"


def parse_int(value: str) -> int:
    if not value.lstrip("-").isdigit():
        raise ValueError(f"not an integer: {value!r}")
    return int(value)


def parse_code(value: str) -> str:
    """Zero-padded numeric code, kept as a string ("00413" != 413)."""
    if len(value) != 5 or not value.isdigit():
        raise ValueError(f"not a 5-digit code: {value!r}")
    return value


def parse_bool01(value: str) -> int:
    if value not in ("0", "1"):
        raise ValueError(f"not 0/1: {value!r}")
    return int(value)


def parse_text(value: str) -> str:
    return value


def parse_date(value: str) -> str:
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat()


# (CSV header after strip, column name, SQL type, parser) — in CSV order.
COLUMNS: list[tuple[str, str, str, Callable[[str], int | str]]] = [
    ("שנת מס", "tax_year", "INTEGER", parse_int),
    ("שנת רישום", "registration_year", "INTEGER", parse_int),
    ("קוד סוג רכב", "vehicle_type_code", "INTEGER", parse_int),
    ("קוד תוצר", "manufacturer_code", "TEXT", parse_code),
    ("תוצר", "manufacturer_name", "TEXT", parse_text),
    ("קוד דגם", "model_code", "TEXT", parse_code),
    ("תאור דגם", "model_description", "TEXT", parse_text),
    ("סוג דלק", "fuel_type_code", "INTEGER", parse_int),
    ("כינוי מסחרי", "commercial_name", "TEXT", parse_text),
    ("לא-0.כן-1 אוטומט", "is_automatic", "INTEGER", parse_bool01),
    ("1-חשמלי.2-היברידי.3-פלג-אין", "drive_code", "INTEGER", parse_int),
    ("ציון ירוק", "green_score", "INTEGER", parse_int),
    ("דרגת זיהום", "pollution_level", "INTEGER", parse_int),
    ("נפח מנוע", "engine_cc", "INTEGER", parse_int),
    ("משקל", "weight_kg", "INTEGER", parse_int),
    ("תאריך תחולה", "effective_date", "TEXT", parse_date),
    ("מחיר מחירון", "list_price", "INTEGER", parse_int),
    ("מחיר מתואם", "adjusted_price", "INTEGER", parse_int),
    ("שווי שימוש", "value_of_use", "INTEGER", parse_int),
]
PRIMARY_KEY: list[str] = [
    "tax_year",
    "registration_year",
    "vehicle_type_code",
    "manufacturer_code",
    "model_code",
]
COLUMN_NAMES: list[str] = [name for _, name, _, _ in COLUMNS]


class BuildError(Exception):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(
    path: Path, expected_row_count: int = EXPECTED_ROW_COUNT
) -> list[tuple[int | str, ...]]:
    with path.open(encoding=SOURCE_ENCODING, newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        expected_header = [h for h, _, _, _ in COLUMNS]
        if header != expected_header:
            raise BuildError(
                f"unexpected CSV header:\n  got      {header}\n  expected {expected_header}"
            )

        rows: list[tuple[int | str, ...]] = []
        for line_no, raw in enumerate(reader, start=2):
            if len(raw) != len(COLUMNS):
                raise BuildError(f"line {line_no}: expected {len(COLUMNS)} columns, got {len(raw)}")
            fields = [value.strip() for value in raw]
            if fields[-1] == "":
                raise BuildError(f"line {line_no}: empty value_of_use")
            parsed: list[int | str] = []
            for (_, column, _, parse), value in zip(COLUMNS, fields, strict=True):
                try:
                    parsed.append(parse(value))
                except ValueError as exc:
                    raise BuildError(f"line {line_no}, column {column}: {exc}") from exc
            rows.append(tuple(parsed))

    if len(rows) != expected_row_count:
        raise BuildError(f"expected {expected_row_count} rows, got {len(rows)}")

    key_indexes = [COLUMN_NAMES.index(c) for c in PRIMARY_KEY]
    key_counts = Counter(tuple(row[i] for i in key_indexes) for row in rows)
    duplicates = [key for key, count in key_counts.items() if count > 1]
    if duplicates:
        raise BuildError(f"primary key {PRIMARY_KEY} not unique: {duplicates[:5]} ...")
    return rows


def write_db(rows: list[tuple[int | str, ...]], target: Path, source: Path) -> None:
    tmp = target.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    column_defs = ",\n    ".join(f"{name} {sql_type} NOT NULL" for _, name, sql_type, _ in COLUMNS)
    with sqlite3.connect(tmp) as conn:
        conn.execute(
            f"CREATE TABLE vehicles (\n    {column_defs},\n"
            f"    PRIMARY KEY ({', '.join(PRIMARY_KEY)})\n) WITHOUT ROWID"
        )
        conn.execute("CREATE INDEX idx_vehicles_commercial_name ON vehicles (commercial_name)")
        placeholders = ", ".join("?" for _ in COLUMNS)
        conn.executemany(
            f"INSERT INTO vehicles ({', '.join(COLUMN_NAMES)}) VALUES ({placeholders})", rows
        )
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [
                ("source_filename", source.name),
                ("source_sha256", sha256_of(source)),
                ("row_count", str(len(rows))),
                ("built_at", datetime.now(UTC).isoformat(timespec="seconds")),
            ],
        )
    conn.close()
    os.replace(tmp, target)


def print_summary(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()
        tax_years = [
            year for (year,) in conn.execute("SELECT DISTINCT tax_year FROM vehicles ORDER BY 1")
        ]
        drive = conn.execute(
            "SELECT drive_code, COUNT(*) FROM vehicles GROUP BY drive_code ORDER BY 1"
        ).fetchall()
    conn.close()
    print(f"built {db_path}")
    print(f"  rows:            {count}")
    print(f"  tax years:       {tax_years}")
    print(f"  per drive_code:  {dict(drive)}  (0=petrol 1=hybrid 2=plug-in 3=electric)")


def main() -> None:
    rows = read_rows(RAW_VALUE_OF_USE_CSV)
    write_db(rows, VEHICLES_DB, RAW_VALUE_OF_USE_CSV)
    print_summary(VEHICLES_DB)


if __name__ == "__main__":
    main()

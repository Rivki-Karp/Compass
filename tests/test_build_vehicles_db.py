"""The ETL must fail loudly on malformed input (synthetic CSVs, not the real dataset)."""

from pathlib import Path

import pytest

from scripts.build_vehicles_db import COLUMNS, BuildError, read_rows

HEADER = ",".join(f"{h} " for h, _, _, _ in COLUMNS)  # source pads headers with spaces
ROW_A = (
    "2026,2025,1,01014,BYD ,00003, SC2E ,4, ATTO 3 ,1,3,000,01,00000,02160,01/01/2025,"
    " 177500 , 181690 ,  3130 "
)
ROW_B = (
    "2026,2025,2,01014,BYD ,00003, STE2 ,4, TANG ,1,3,000,01,00000,03204,01/06/2025,"
    " 327990 , 335733 ,  6950 "
)


def write_csv(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "vou.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="cp1255")
    return path


def test_valid_rows_are_parsed_and_stripped(tmp_path: Path) -> None:
    rows = read_rows(write_csv(tmp_path, ROW_A, ROW_B), expected_row_count=2)
    assert rows[0][3:6] == ("01014", "BYD", "00003")
    assert rows[0][15] == "2025-01-01"
    assert rows[1][-1] == 6950


def test_duplicate_primary_key_fails(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="primary key"):
        read_rows(write_csv(tmp_path, ROW_A, ROW_A), expected_row_count=2)


def test_wrong_column_count_fails(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="expected 19 columns, got 20"):
        read_rows(write_csv(tmp_path, ROW_A + ",extra"), expected_row_count=1)


def test_empty_value_of_use_fails(tmp_path: Path) -> None:
    row = ROW_A.rsplit(",", 1)[0] + ",   "
    with pytest.raises(BuildError, match="empty value_of_use"):
        read_rows(write_csv(tmp_path, row), expected_row_count=1)


def test_row_count_mismatch_fails(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="expected 77988 rows, got 1"):
        read_rows(write_csv(tmp_path, ROW_A))


def test_non_padded_code_fails(tmp_path: Path) -> None:
    row = ROW_A.replace(",01014,", ",1014,")
    with pytest.raises(BuildError, match="manufacturer_code"):
        read_rows(write_csv(tmp_path, row), expected_row_count=1)

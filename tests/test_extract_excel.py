import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from compass.config import CATALOG_JSON, FIXTURES_DIR, OCCUPATIONS_JSON, RAW_CHALLENGE_XLSX
from scripts.extract_excel import build_outputs


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(not RAW_CHALLENGE_XLSX.is_file(), reason="raw/ files not present")
def test_committed_outputs_match_a_fresh_extraction() -> None:
    for path, content in build_outputs().items():
        assert path.read_text(encoding="utf-8") == content, f"{path.name} is stale; run data"


def test_catalog_shape() -> None:
    cars = load(CATALOG_JSON)
    assert [car["id"] for car in cars] == [f"CAR-{n:02d}" for n in range(1, 21)]
    for car in cars:
        assert isinstance(car["manufacturer_code"], str) and len(car["manufacturer_code"]) == 5
        assert isinstance(car["model_code"], str) and len(car["model_code"]) == 5
        assert car["drive"] in {"petrol", "hybrid", "plugin", "electric"}
    by_id = {car["id"]: car for car in cars}
    assert by_id["CAR-10"]["drive"] == "electric"  # ATTO 3
    assert by_id["CAR-16"]["drive"] == "plugin"  # SPORTAGE HEV, Excel label "פלאג-אין"


def test_employee_fixtures() -> None:
    employees = load(FIXTURES_DIR / "reference_employees.json")
    assert list(employees) == ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"]
    e003 = employees["E-003"]
    assert e003["current"] == {"raw": "אין (אחזקה 1500 ₪)", "kind": "waiver", "maintenance": 1500}
    assert Decimal(e003["pension_employee_rate"]) == Decimal("0.065")
    assert employees["E-001"]["current"]["car_id"] == "CAR-09"  # COROLLA CROSS


def test_result_fixtures() -> None:
    results = load(FIXTURES_DIR / "reference_results.json")
    assert list(results) == ["E-001", "E-002", "E-003", "E-004", "E-005", "E-006"]
    assert results["E-001"]["alternative"]["car_id"] == "CAR-10"  # ATTO 3 (2025)
    assert results["E-005"]["alternative"] == {
        "raw": "ויתור - אחזקת רכב 2000 ₪",
        "kind": "waiver",
        "maintenance": 2000,
    }
    for r in results.values():
        assert r["net_alternative"] - r["net_today"] == r["net_diff"]


def test_occupations_shape() -> None:
    occupations = load(OCCUPATIONS_JSON)
    assert len(occupations) == 14
    assert all(isinstance(o["car_mandatory"], bool) for o in occupations)

"""Extract curated datasets and golden test fixtures from raw/strauss_challenge_data.xlsx.

Outputs (deterministic: fixed key order, ensure_ascii=False, 2-space indent, LF):
    data/catalog.json
    data/occupations.json
    tests/fixtures/reference_employees.json
    tests/fixtures/reference_results.json

Non-integer numbers (percentages, credit points) are written as strings so they never pass
through float; percentages are converted to rates ("6.5" % -> "0.065").
"""

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from compass.config import (
    CATALOG_JSON,
    FIXTURES_DIR,
    OCCUPATIONS_JSON,
    RAW_CHALLENGE_XLSX,
    RAW_RULES_JSON,
)
from compass.data.drive import DRIVE_BY_CODE

REFERENCE_EMPLOYEES_JSON = FIXTURES_DIR / "reference_employees.json"
REFERENCE_RESULTS_JSON = FIXTURES_DIR / "reference_results.json"

GROUPS = ("א", "ב", "ג", "ד", "משפחתי")
YES_NO = {"כן": True, "לא": False}

CATALOG_HEADER = [
    "מזהה",
    "קבוצה",
    "תוצר",
    "קוד תוצר",
    "דגם (כינוי מסחרי)",
    "קוד דגם",
    "תאור דגם",
    "שנת רישום",
    "הנעה",
    "מחיר מחירון",
    "שווי שימוש חודשי",
    "עלות חודשית לחברה (דמה)",
    "השתתפות עובד ברירת מחדל (דמה)",
]
OCCUPATIONS_HEADER = ["עיסוק", "קבוצת זכאות", "רכב חובה", "מותר לוותר", "אחזקת רכב בוויתור (₪)"]
EMPLOYEES_HEADER = [
    "מזהה",
    "שם",
    "ת״ז (פיקטיבית)",
    "עיסוק",
    "קבוצה",
    "שכר בסיס",
    "עמלות",
    "בונוס",
    "פנסיה עובד %",
    "קרן השתלמות עובד %",
    "נקודות זיכוי",
    "ילדים עד 23",
    "רכב היום",
    "השתתפות היום",
    "השאלה",
]
RESULTS_HEADER = [
    "מזהה",
    "שם",
    "היום",
    "החלופה",
    "זכאות",
    "סיבה",
    "נטו היום",
    "נטו בחלופה",
    "הפרש",
    "מס היום",
    "מס בחלופה",
    "ביטוח לאומי+בריאות היום",
    "ביטוח לאומי+בריאות בחלופה",
    "החזר חשמל ברוטו",
    "חלק העובד במסלול המשפחתי",
    "למה",
]

# Free-text cells in the employee / results sheets.
EMPLOYEE_WAIVER_RE = re.compile(r"^אין \(אחזקה (\d+) ₪\)$")  # "אין (אחזקה 1500 ₪)"
SCENARIO_WAIVER_RE = re.compile(r"^ויתור - אחזקת רכב (\d+) ₪$")  # "ויתור - אחזקת רכב 2000 ₪"
SCENARIO_CAR_RE = re.compile(r"^(.+) \((\d{4})\)$")  # "ATTO 3 (2025)"


class ExtractError(Exception):
    pass


# --- cell helpers ---------------------------------------------------------------------------


def read_sheet(ws: Worksheet, expected_header: list[str]) -> list[tuple[Any, ...]]:
    rows = [row for row in ws.iter_rows(values_only=True) if any(v is not None for v in row)]
    header = [str(v).strip() if v is not None else None for v in rows[0]]
    if header != expected_header:
        raise ExtractError(
            f"sheet {ws.title!r}: unexpected header\n  got      {header}\n"
            f"  expected {expected_header}"
        )
    return rows[1:]


def as_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExtractError(f"{where}: expected an integer, got {value!r}")
    return value


def as_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtractError(f"{where}: expected non-empty text, got {value!r}")
    return value.strip()


def as_code(value: Any, where: str) -> str:
    text = as_str(value, where)
    if len(text) != 5 or not text.isdigit():
        raise ExtractError(f"{where}: expected a 5-digit zero-padded code, got {value!r}")
    return text


def as_decimal_text(value: Any, where: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ExtractError(f"{where}: expected a number, got {value!r}")
    return str(Decimal(str(value)))


def as_rate_text(percent: Any, where: str) -> str:
    return str(Decimal(as_decimal_text(percent, where)) / 100)


def as_yes_no(value: Any, where: str) -> bool:
    if value not in YES_NO:
        raise ExtractError(f"{where}: expected כן/לא, got {value!r}")
    return YES_NO[value]


def as_group(value: Any, where: str) -> str:
    if value not in GROUPS:
        raise ExtractError(f"{where}: unknown group {value!r}")
    return value


# --- datasets -------------------------------------------------------------------------------


def drive_by_hebrew_label() -> dict[str, str]:
    """Map Excel 'הנעה' labels to Drive ids via the rules-file driveField (code -> Hebrew)."""
    rules = json.loads(RAW_RULES_JSON.read_text(encoding="utf-8"))
    drive_field: dict[str, str] = rules["valueOfUse"]["driveField"]
    return {label: DRIVE_BY_CODE[int(code)] for code, label in drive_field.items()}


def extract_catalog(ws: Worksheet) -> list[dict[str, Any]]:
    drives = drive_by_hebrew_label()
    cars: list[dict[str, Any]] = []
    for row in read_sheet(ws, CATALOG_HEADER):
        car_id = as_str(row[0], f"{ws.title}: id")
        where = f"{ws.title} {car_id}"
        if row[8] not in drives:
            raise ExtractError(f"{where}: unknown drive label {row[8]!r}")
        cars.append(
            {
                "id": car_id,
                "group": as_group(row[1], f"{where}: group"),
                "manufacturer_name": as_str(row[2], f"{where}: manufacturer_name"),
                "manufacturer_code": as_code(row[3], f"{where}: manufacturer_code"),
                "commercial_name": as_str(row[4], f"{where}: commercial_name"),
                "model_code": as_code(row[5], f"{where}: model_code"),
                "model_description": as_str(row[6], f"{where}: model_description"),
                "registration_year": as_int(row[7], f"{where}: registration_year"),
                "drive": drives[row[8]],
                "list_price": as_int(row[9], f"{where}: list_price"),
                "value_of_use": as_int(row[10], f"{where}: value_of_use"),
                "monthly_company_cost": as_int(row[11], f"{where}: monthly_company_cost"),
                "default_employee_participation": as_int(
                    row[12], f"{where}: default_employee_participation"
                ),
            }
        )
    ids = [car["id"] for car in cars]
    if len(cars) != 20 or len(set(ids)) != 20:
        raise ExtractError(f"catalog: expected 20 unique cars, got ids {ids}")
    return cars


def extract_occupations(ws: Worksheet) -> list[dict[str, Any]]:
    occupations: list[dict[str, Any]] = []
    for row in read_sheet(ws, OCCUPATIONS_HEADER):
        title = as_str(row[0], f"{ws.title}: title")
        where = f"{ws.title} {title!r}"
        occupations.append(
            {
                "title": title,
                "group": as_group(row[1], f"{where}: group"),
                "car_mandatory": as_yes_no(row[2], f"{where}: car_mandatory"),
                "waiver_allowed": as_yes_no(row[3], f"{where}: waiver_allowed"),
                "waiver_maintenance": as_int(row[4], f"{where}: waiver_maintenance"),
            }
        )
    titles = [o["title"] for o in occupations]
    if len(occupations) != 14 or len(set(titles)) != 14:
        raise ExtractError(f"occupations: expected 14 unique titles, got {titles}")
    return occupations


# --- fixtures -------------------------------------------------------------------------------


def find_car_id(cars: list[dict[str, Any]], name: str, year: int | None, where: str) -> str:
    matches = [
        car["id"]
        for car in cars
        if car["commercial_name"] == name and (year is None or car["registration_year"] == year)
    ]
    if len(matches) != 1:
        raise ExtractError(f"{where}: expected exactly one catalog car for {name!r}, {matches}")
    return matches[0]


def parse_current_car(raw: str, cars: list[dict[str, Any]], where: str) -> dict[str, Any]:
    if waiver := EMPLOYEE_WAIVER_RE.match(raw):
        return {"raw": raw, "kind": "waiver", "maintenance": int(waiver.group(1))}
    return {"raw": raw, "kind": "car", "car_id": find_car_id(cars, raw, None, where)}


def parse_scenario(raw: str, cars: list[dict[str, Any]], where: str) -> dict[str, Any]:
    if waiver := SCENARIO_WAIVER_RE.match(raw):
        return {"raw": raw, "kind": "waiver", "maintenance": int(waiver.group(1))}
    if car := SCENARIO_CAR_RE.match(raw):
        car_id = find_car_id(cars, car.group(1), int(car.group(2)), where)
        return {"raw": raw, "kind": "car", "car_id": car_id}
    raise ExtractError(f"{where}: unrecognised scenario text {raw!r}")


def extract_employees(ws: Worksheet, cars: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    employees: dict[str, dict[str, Any]] = {}
    for row in read_sheet(ws, EMPLOYEES_HEADER):
        emp_id = as_str(row[0], f"{ws.title}: id")
        where = f"{ws.title} {emp_id}"
        employees[emp_id] = {
            "name": as_str(row[1], f"{where}: name"),
            "national_id": as_str(row[2], f"{where}: national_id"),
            "occupation": as_str(row[3], f"{where}: occupation"),
            "group": as_group(row[4], f"{where}: group"),
            "base_salary": as_int(row[5], f"{where}: base_salary"),
            "commissions": as_int(row[6], f"{where}: commissions"),
            "bonus": as_int(row[7], f"{where}: bonus"),
            "pension_employee_rate": as_rate_text(row[8], f"{where}: pension %"),
            "study_fund_employee_rate": as_rate_text(row[9], f"{where}: study fund %"),
            "credit_points": as_decimal_text(row[10], f"{where}: credit_points"),
            "children_under_23": as_int(row[11], f"{where}: children_under_23"),
            "current": parse_current_car(as_str(row[12], f"{where}: current car"), cars, where),
            "current_participation": as_int(row[13], f"{where}: current_participation"),
            "question": as_str(row[14], f"{where}: question"),
        }
    return employees


def extract_results(ws: Worksheet, cars: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    int_fields = [
        "net_today",
        "net_alternative",
        "net_diff",
        "tax_today",
        "tax_alternative",
        "ni_health_today",
        "ni_health_alternative",
        "electric_refund_gross",
        "family_track_employee_share",
    ]
    results: dict[str, dict[str, Any]] = {}
    for row in read_sheet(ws, RESULTS_HEADER):
        emp_id = as_str(row[0], f"{ws.title}: id")
        where = f"{ws.title} {emp_id}"
        result: dict[str, Any] = {
            "name": as_str(row[1], f"{where}: name"),
            "today": parse_scenario(as_str(row[2], f"{where}: today"), cars, where),
            "alternative": parse_scenario(as_str(row[3], f"{where}: alternative"), cars, where),
            "eligible": as_yes_no(row[4], f"{where}: eligible"),
            "reason": as_str(row[5], f"{where}: reason"),
        }
        for offset, field in enumerate(int_fields, start=6):
            result[field] = as_int(row[offset], f"{where}: {field}")
        result["explanation"] = as_str(row[15], f"{where}: explanation")
        results[emp_id] = result
    return results


# --- output ---------------------------------------------------------------------------------


def render_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def build_outputs() -> dict[Path, str]:
    """Return {output path: file content}; pure, so tests can check committed files are fresh."""
    wb = openpyxl.load_workbook(RAW_CHALLENGE_XLSX, read_only=True)
    cars = extract_catalog(wb["קטלוג רכבים"])
    occupations = extract_occupations(wb["עיסוקים"])
    employees = extract_employees(wb["עובדים לדוגמה"], cars)
    results = extract_results(wb["חישובים"], cars)
    wb.close()

    expected_ids = [f"E-{n:03d}" for n in range(1, 7)]
    if list(employees) != expected_ids or list(results) != expected_ids:
        raise ExtractError(
            f"expected employees {expected_ids}, got {list(employees)} / {list(results)}"
        )
    for emp_id in expected_ids:
        if employees[emp_id]["name"] != results[emp_id]["name"]:
            raise ExtractError(f"{emp_id}: name differs between employees and results sheets")

    return {
        CATALOG_JSON: render_json(cars),
        OCCUPATIONS_JSON: render_json(occupations),
        REFERENCE_EMPLOYEES_JSON: render_json(employees),
        REFERENCE_RESULTS_JSON: render_json(results),
    }


def main() -> None:
    for path, content in build_outputs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()

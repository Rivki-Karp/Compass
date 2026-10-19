"""The 6 golden reference employees (tests/fixtures) as engine inputs.

Used by the golden tests and the demo CLI. Not part of the engine: the engine never reads fixtures.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from compass.config import FIXTURES_DIR
from compass.engine.context import EngineContext
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    Scenario,
    Waiver,
)

REFERENCE_EMPLOYEES_JSON: Path = FIXTURES_DIR / "reference_employees.json"
REFERENCE_RESULTS_JSON: Path = FIXTURES_DIR / "reference_results.json"


@dataclass(frozen=True)
class ReferenceCase:
    employee_id: str
    name: str
    profile: EmployeeProfile
    today: Scenario
    alternative: Scenario
    expected: dict[str, Any]  # reference_results.json entry


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)


def _car(car_id: str, ctx: EngineContext, participation: Decimal | None) -> Scenario:
    if ctx.is_family_car(car_id):
        return FamilyCar(car_id=car_id, participation=participation)
    return CompanyCar(car_id=car_id, participation=participation)


def load_reference_cases(ctx: EngineContext) -> dict[str, ReferenceCase]:
    employees = _load(REFERENCE_EMPLOYEES_JSON)
    results = _load(REFERENCE_RESULTS_JSON)
    cases: dict[str, ReferenceCase] = {}
    for employee_id, emp in employees.items():
        profile = EmployeeProfile(
            group=emp["group"],
            occupation=emp["occupation"],
            base_salary=Decimal(emp["base_salary"]),
            commissions=Decimal(emp["commissions"]),
            bonus=Decimal(emp["bonus"]),
            pension_pct=Decimal(emp["pension_employee_rate"]),
            study_fund_pct=Decimal(emp["study_fund_employee_rate"]),
            credit_points=Decimal(emp["credit_points"]),
            children_under_23=emp["children_under_23"],
        )
        result = results[employee_id]

        today_raw = result["today"]
        if today_raw["kind"] == "car":
            # Today's participation is what the employee pays now (employee input).
            participation = Decimal(emp["current_participation"])
            today = _car(today_raw["car_id"], ctx, participation)
        else:
            today = CurrentMaintenance(amount=Decimal(today_raw["maintenance"]))

        alt_raw = result["alternative"]
        # A new car's participation is the catalog default; a waiver's maintenance comes from
        # the occupation (the fixture's amount is checked against it in the golden tests).
        alternative = _car(alt_raw["car_id"], ctx, None) if alt_raw["kind"] == "car" else Waiver()

        cases[employee_id] = ReferenceCase(
            employee_id=employee_id,
            name=emp["name"],
            profile=profile,
            today=today,
            alternative=alternative,
            expected=result,
        )
    return cases

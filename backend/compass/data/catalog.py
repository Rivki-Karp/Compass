"""Strauss company-car catalog (data/catalog.json)."""

import json
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from compass.config import CATALOG_JSON
from compass.data.drive import Drive
from compass.rules import Rules

FAMILY_GROUP = "משפחתי"


class CatalogCar(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    group: str  # one of rules.group_order, or FAMILY_GROUP
    manufacturer_name: str
    manufacturer_code: str
    commercial_name: str
    model_code: str
    model_description: str
    registration_year: int
    drive: Drive
    list_price: Decimal
    value_of_use: Decimal
    # For FAMILY_GROUP cars this is the family-track car cost (per car, not a single rule value).
    monthly_company_cost: Decimal
    default_employee_participation: Decimal


def load_catalog(path: Path = CATALOG_JSON) -> tuple[CatalogCar, ...]:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)  # never float
    return tuple(CatalogCar.model_validate(item) for item in data)


def get_car(car_id: str, path: Path = CATALOG_JSON) -> CatalogCar | None:
    return next((car for car in load_catalog(path) if car.id == car_id), None)


def cars_for_group(
    group: str,
    rules: Rules,
    include_family: bool = False,
    path: Path = CATALOG_JSON,
) -> tuple[CatalogCar, ...]:
    """Cars from `group` or any lower group (per rules.group_order).

    Family-track cars are returned only when `include_family` is set; deciding whether the
    employee qualifies for the family track is the caller's job.
    """
    if group not in rules.group_order:
        raise ValueError(f"unknown group {group!r}; expected one of {list(rules.group_order)}")
    allowed = set(rules.group_order[: rules.group_order.index(group) + 1])
    if include_family:
        allowed.add(FAMILY_GROUP)
    return tuple(car for car in load_catalog(path) if car.group in allowed)

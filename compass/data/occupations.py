"""Occupations and their car / waiver terms (data/occupations.json)."""

import json
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from compass.config import OCCUPATIONS_JSON


class Occupation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str  # Hebrew, as in the source
    group: str
    car_mandatory: bool
    waiver_allowed: bool
    waiver_maintenance: Decimal  # ILS / month paid instead of a car when waived


def load_occupations(path: Path = OCCUPATIONS_JSON) -> tuple[Occupation, ...]:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)  # never float
    return tuple(Occupation.model_validate(item) for item in data)


def get_occupation(title: str, path: Path = OCCUPATIONS_JSON) -> Occupation | None:
    """Exact title match only (fuzzy matching is out of scope for the data layer)."""
    return next((o for o in load_occupations(path) if o.title == title), None)

"""The extraction contract: what Claude must answer, and what we keep of it.

Claude answers in EXTRACTION_SCHEMA (structured output): one object per field, each
{"value": number | null, "confidence": "high" | "medium" | "low"}, and nothing else. There is no
free-text field; the one string (payslip_month) is kept only when it is exactly YYYY-MM.

`parse_extraction` turns the answer's text into a PayslipCandidate:
  - numbers are read as Decimal straight from the JSON text (no float, no rounding);
  - a value of the wrong type, out of its range, with more than 2 decimals or (credit points)
    off the 0.25 step becomes None with a flag, so it can never reach a slot;
  - unknown keys, at the top or inside a field, are dropped and only counted: their names and
    values (an ID number, a name, a bank account...) are never kept, returned or logged.
It raises InvalidExtraction only when the text is not JSON or not a JSON object: the one case
where the extractor tries the fallback model.

Every field maps to an existing profile slot except car_benefit_value (the engine derives the
value of use from the catalog car) and payslip_month: those two are information only.
"""

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Confidence = Literal["high", "medium", "low"]
CONFIDENCES: tuple[str, ...] = ("high", "medium", "low")
Flag = Literal["wrong_type", "out_of_range", "too_many_decimals", "not_a_step", "invalid"]

# payslip field -> the existing profile tool field it fills (compass.tools.profile.SLOT_OF)
PROFILE_FIELD_OF: dict[str, str] = {
    "base_salary": "base_salary",
    "commissions": "commissions",
    "bonus": "bonus",
    "pension_percent": "pension_percent",
    "study_fund_percent": "study_fund_percent",
    "credit_points": "credit_points",
}
# shown to the employee, never a calculation input
INFO_FIELDS: tuple[str, ...] = ("car_benefit_value", "payslip_month")
NUMBER_FIELDS: tuple[str, ...] = (*PROFILE_FIELD_OF, "car_benefit_value")
FIELDS: tuple[str, ...] = (*NUMBER_FIELDS, "payslip_month")

# Inclusive ranges, in the employee's units (6.5 = 6.5%). Each lies inside the slot's own limits
# (compass.tools.profile), so a value kept here also passes to_slot_value.
RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "base_salary": (Decimal(1_000), Decimal(200_000)),
    "commissions": (Decimal(0), Decimal(200_000)),
    "bonus": (Decimal(0), Decimal(200_000)),
    "pension_percent": (Decimal(0), Decimal(10)),
    "study_fund_percent": (Decimal(0), Decimal(10)),
    "credit_points": (Decimal(0), Decimal(15)),
    "car_benefit_value": (Decimal(0), Decimal(20_000)),
}
CREDIT_POINT_STEP = Decimal("0.25")
CENT = Decimal("0.01")
MONTH = re.compile(r"(20\d\d)-(0[1-9]|1[0-2])")


def _field_schema(value_type: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "value": {"type": [value_type, "null"]},
            "confidence": {"type": "string", "enum": list(CONFIDENCES)},
        },
        "required": ["value", "confidence"],
        "additionalProperties": False,
    }


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{name: _field_schema("number") for name in NUMBER_FIELDS},
        "payslip_month": _field_schema("string"),
    },
    "required": list(FIELDS),
    "additionalProperties": False,
}


class FieldReading(BaseModel):
    """One field as the model sent it: types are checked in `normalise`, not here, so one bad
    field never discards the others."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    value: Any = None
    confidence: Any = None


class PayslipExtraction(BaseModel):
    """The model's answer, fixed fields only; anything else is ignored (and counted)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    base_salary: FieldReading | None = None
    commissions: FieldReading | None = None
    bonus: FieldReading | None = None
    pension_percent: FieldReading | None = None
    study_fund_percent: FieldReading | None = None
    credit_points: FieldReading | None = None
    car_benefit_value: FieldReading | None = None
    payslip_month: FieldReading | None = None


@dataclass(frozen=True)
class CandidateField:
    """A normalised field: `value` is a Decimal string (or YYYY-MM), or None; a flagged field
    always has None."""

    value: str | None
    confidence: Confidence
    flag: Flag | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "confidence": self.confidence, "flag": self.flag}


@dataclass(frozen=True)
class PayslipCandidate:
    """What is kept of an extraction: numbers, confidences and flags. Pending until the employee
    confirms; never a guard source, never shown to the agent before that."""

    fields: dict[str, CandidateField] = field(default_factory=dict)
    dropped_keys: int = 0  # unknown keys discarded (names and values never kept)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": {name: f.to_dict() for name, f in self.fields.items()},
            "dropped_keys": self.dropped_keys,
        }

    @property
    def flagged(self) -> int:
        return sum(1 for f in self.fields.values() if f.flag is not None)


class InvalidExtraction(ValueError):
    """The answer is not JSON, or not a JSON object. Its message never quotes the answer."""


def _confidence(raw: Any) -> Confidence | None:
    return raw if isinstance(raw, str) and raw in CONFIDENCES else None  # type: ignore[return-value]


def _number(name: str, raw: Any) -> tuple[str | None, Flag | None]:
    if raw is None:
        return None, None
    if isinstance(raw, bool) or not isinstance(raw, int | float | Decimal):
        return None, "wrong_type"  # a string, a list, an object... never parsed from text
    try:
        # JSON arrives as Decimal (parse_extraction); a float (the scripted extractor) through
        # repr, which is exactly what was written: 6.5 -> "6.5"
        value = Decimal(repr(raw)) if isinstance(raw, float) else Decimal(raw)
    except (InvalidOperation, ValueError):
        return None, "wrong_type"
    if not value.is_finite():
        return None, "wrong_type"
    low, high = RANGES[name]
    if not low <= value <= high:
        return None, "out_of_range"
    if value != value.quantize(CENT):
        return None, "too_many_decimals"
    if name == "credit_points" and value % CREDIT_POINT_STEP != 0:
        return None, "not_a_step"
    return format(value.normalize(), "f"), None


def _month(raw: Any) -> tuple[str | None, Flag | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, "wrong_type"
    if not MONTH.fullmatch(raw):
        return None, "invalid"
    return raw, None


def normalise(raw: dict[str, Any]) -> PayslipCandidate:
    """The model's JSON object -> a PayslipCandidate (see the module docstring)."""
    dropped = sum(1 for key in raw if key not in FIELDS)
    extraction = PayslipExtraction.model_validate(
        {k: v for k, v in raw.items() if k in FIELDS and isinstance(v, dict)}
    )
    fields: dict[str, CandidateField] = {}
    for name in FIELDS:
        given = raw.get(name)
        if given is None:
            continue  # not sent: not a field of this candidate
        if not isinstance(given, dict):
            fields[name] = CandidateField(None, "low", "invalid")
            continue
        dropped += sum(1 for key in given if key not in ("value", "confidence"))
        reading = getattr(extraction, name)
        confidence = _confidence(reading.confidence)
        if confidence is None:
            fields[name] = CandidateField(None, "low", "invalid")
            continue
        value, flag = (
            _month(reading.value) if name == "payslip_month" else _number(name, reading.value)
        )
        fields[name] = CandidateField(value, confidence, flag)
    return PayslipCandidate(fields=fields, dropped_keys=dropped)


def parse_extraction(text: str) -> PayslipCandidate:
    """The answer's text -> a candidate. Raises InvalidExtraction for non-JSON or a non-object."""
    try:
        raw = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    except (ValueError, TypeError, RecursionError):
        raise InvalidExtraction("the answer is not JSON") from None
    if not isinstance(raw, dict):
        raise InvalidExtraction("the answer is not a JSON object")
    return normalise(raw)

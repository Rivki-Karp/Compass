"""Profile fields as tools see them, and the one set of validation rules for them.

Tools speak in the employee's units (pension_percent = 6.5); slots and the engine store
fractions (pension_pct = 0.065). This module is the only place that translates between them,
and both save_profile and the representative's ticket answer validate through it.
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from compass.engine.context import EngineContext
from compass.engine.models import EmployeeProfile
from compass.state import Slot

# tool field -> slot / engine field
SLOT_OF: dict[str, str] = {
    "display_name": "display_name",
    "occupation": "occupation",
    "group": "group",
    "base_salary": "base_salary",
    "commissions": "commissions",
    "bonus": "bonus",
    "pension_percent": "pension_pct",
    "study_fund_percent": "study_fund_pct",
    "credit_points": "credit_points",
    "children_under_23": "children_under_23",
}
TOOL_OF: dict[str, str] = {slot: tool for tool, slot in SLOT_OF.items()}
PROFILE_FIELDS: tuple[str, ...] = tuple(SLOT_OF)

# Fields the calculation needs (children only matter for the family track).
REQUIRED_FIELDS: tuple[str, ...] = (
    "occupation",
    "group",
    "base_salary",
    "commissions",
    "bonus",
    "pension_percent",
    "study_fund_percent",
    "credit_points",
)
# Fields printed on a payslip: when unknown, the UI offers "upload payslip".
PAYSLIP_FIELDS: tuple[str, ...] = (
    "base_salary",
    "commissions",
    "bonus",
    "pension_percent",
    "study_fund_percent",
    "credit_points",
)

MAX_SALARY = Decimal(500_000)
MAX_PERCENT = Decimal(20)
MAX_CREDIT_POINTS = Decimal(15)
CREDIT_POINT_STEP = Decimal("0.25")
MAX_CHILDREN = 20
MAX_NAME_LENGTH = 80


class FieldError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"{field}: {message}")


def _decimal(field: str, raw: Any) -> Decimal:
    if isinstance(raw, bool) or raw is None:
        raise FieldError(field, f"expected a number, got {raw!r}")
    try:
        value = Decimal(str(raw).replace(",", "").strip())
    except InvalidOperation:
        raise FieldError(field, f"expected a number, got {raw!r}") from None
    if not value.is_finite():
        raise FieldError(field, f"expected a number, got {raw!r}")
    if value != value.quantize(Decimal("0.01")):
        raise FieldError(field, f"at most 2 decimal places (got {raw})")
    return value


def to_slot_value(field: str, raw: Any, ctx: EngineContext) -> Any:
    """Validate one tool-unit value and return its JSON slot value. Raises FieldError."""
    if field not in SLOT_OF:
        raise FieldError(field, "unknown profile field")
    if field == "display_name":
        name = str(raw).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise FieldError(field, f"must be 1-{MAX_NAME_LENGTH} characters")
        if sum(ch.isdigit() for ch in name) >= 5:
            raise FieldError(field, "a name, not a number (never store an ID number)")
        return name
    if field == "occupation":
        if raw not in ctx.occupations:
            raise FieldError(field, f"unknown occupation title {raw!r}")
        return raw
    if field == "group":
        if raw not in ctx.rules.group_order:
            raise FieldError(field, f"must be one of {list(ctx.rules.group_order)} (got {raw!r})")
        return raw
    if field == "children_under_23":
        if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= MAX_CHILDREN:
            raise FieldError(field, f"must be a whole number 0-{MAX_CHILDREN} (got {raw!r})")
        return raw
    value = _decimal(field, raw)
    if field == "base_salary" and not 0 < value <= MAX_SALARY:
        raise FieldError(field, f"must be above 0 and at most {MAX_SALARY:,} (got {value})")
    if field in ("commissions", "bonus") and not 0 <= value <= MAX_SALARY:
        raise FieldError(field, f"must be 0-{MAX_SALARY:,} (got {value})")
    if field in ("pension_percent", "study_fund_percent"):
        if not 0 <= value <= MAX_PERCENT:
            raise FieldError(field, f"a percentage 0-{MAX_PERCENT} (got {value})")
        return format(value.scaleb(-2), "f")  # 6.5 -> "0.065", exact
    if field == "credit_points" and (
        not 0 <= value <= MAX_CREDIT_POINTS or value % CREDIT_POINT_STEP != 0
    ):
        raise FieldError(field, f"0-{MAX_CREDIT_POINTS} in steps of 0.25 (got {value})")
    return str(value)


def to_tool_value(field: str, slot_value: Any) -> Any:
    """Slot value -> tool units (fractions back to percent)."""
    if slot_value is None:
        return None
    if field in ("pension_percent", "study_fund_percent"):
        return str(Decimal(slot_value).scaleb(2).normalize())
    return slot_value


def profile_from_slots(slots: Mapping[str, Slot]) -> EmployeeProfile:
    """Only filled slots count; unknown and pending_rep fields stay None (never a default)."""
    decimals = {"base_salary", "commissions", "bonus", "pension_pct", "study_fund_pct"}
    decimals.add("credit_points")
    values: dict[str, Any] = {}
    for slot_field in SLOT_OF.values():
        slot = slots.get(slot_field)
        if slot is None or slot.state != "filled" or slot_field == "display_name":
            continue
        values[slot_field] = Decimal(slot.value) if slot_field in decimals else slot.value
    return EmployeeProfile(**values)


def tool_fields(engine_fields: list[str] | tuple[str, ...]) -> list[str]:
    """Engine/slot field names (e.g. MissingInputs.fields) -> tool field names."""
    return [TOOL_OF.get(f, f) for f in engine_fields]

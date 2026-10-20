"""Profile fields as tools see them, and the one set of validation rules for them.

Tools speak in the employee's units (pension_percent = 6.5); slots and the engine store
fractions (pension_pct = 0.065). This module is the only place that translates between them,
and both save_profile and the representative's ticket answer validate through it.
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

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
MAX_SALARY = Decimal(500_000)
MAX_PERCENT = Decimal(20)
MAX_CREDIT_POINTS = Decimal(15)
CREDIT_POINT_STEP = Decimal("0.25")
MAX_CHILDREN = 20
MAX_NAME_LENGTH = 80
MAX_PARTICIPATION = Decimal(20_000)

# Participation fields: filled by a representative (ticket blocking fields), not by save_profile.
# Slot value: {"amount": "350", "effective_from": "2026-11-01" | None}.
CURRENT_PARTICIPATION = "current_participation"
ALTERNATIVE_PARTICIPATION = "alternative_participation:"  # + catalog car id


# A representative's answer to a group exception (a ticket blocking field, its own slot): the
# group the employee is approved for (above the occupation's group), or NOT_APPROVED. An approved
# group also becomes the group slot (source representative): only a ticket answer sets it.
GROUP_EXCEPTION = "group_exception"
NOT_APPROVED = "not_approved"

# A representative's answer to "which car does the employee have today" (a ticket blocking
# field, its own slot): a catalog car id. The answer also becomes today's situation (source
# representative); a car outside the catalog is answered "other" with a note (the slot unknown).
CURRENT_CAR = "current_car"


def alternative_participation(car_id: str) -> str:
    return f"{ALTERNATIVE_PARTICIPATION}{car_id}"


def is_participation(field: str) -> bool:
    return field == CURRENT_PARTICIPATION or field.startswith(ALTERNATIVE_PARTICIPATION)


def is_fillable(field: str, ctx: EngineContext) -> bool:
    """A field a ticket may block on and a representative may fill."""
    if field in SLOT_OF or field in (CURRENT_PARTICIPATION, GROUP_EXCEPTION, CURRENT_CAR):
        return True
    return (
        field.startswith(ALTERNATIVE_PARTICIPATION)
        and field.removeprefix(ALTERNATIVE_PARTICIPATION) in ctx.catalog
    )


def slot_name(field: str) -> str:
    return SLOT_OF.get(field, field)  # participation fields are their own slot names


FieldErrorCode = Literal[
    "not_a_number",
    "too_many_decimals",
    "unknown_car",
    "out_of_range",
    "effective_from_not_participation",
    "unknown_field",
    "name_length",
    "name_is_a_number",
    "unknown_occupation",
    "unknown_group",
    "credit_points_step",
]


class FieldError(ValueError):
    """`message` is English (the model reads it); `code` and `params` let the UI show Hebrew
    (compass.labels.ERROR_MESSAGES)."""

    def __init__(self, field: str, message: str, code: FieldErrorCode, **params: Any) -> None:
        self.field = field
        self.code = code
        self.params = params
        super().__init__(f"{field}: {message}")


def _decimal(field: str, raw: Any) -> Decimal:
    if isinstance(raw, bool) or raw is None:
        raise FieldError(field, f"expected a number, got {raw!r}", "not_a_number")
    try:
        value = Decimal(str(raw).replace(",", "").strip())
    except InvalidOperation:
        raise FieldError(field, f"expected a number, got {raw!r}", "not_a_number") from None
    if not value.is_finite():
        raise FieldError(field, f"expected a number, got {raw!r}", "not_a_number")
    if value != value.quantize(Decimal("0.01")):
        raise FieldError(field, f"at most 2 decimal places (got {raw})", "too_many_decimals")
    return value


def to_slot_value(
    field: str, raw: Any, ctx: EngineContext, effective_from: date | None = None
) -> Any:
    """Validate one tool-unit value and return its JSON slot value. Raises FieldError.

    `effective_from` applies to participation fields only (when the amount takes effect).
    """
    if is_participation(field):
        if not is_fillable(field, ctx):
            car_id = field.removeprefix(ALTERNATIVE_PARTICIPATION)
            raise FieldError(field, f"unknown catalog car {car_id!r}", "unknown_car")
        amount = _decimal(field, raw)
        if not 0 <= amount <= MAX_PARTICIPATION:
            raise FieldError(
                field,
                f"must be 0-{MAX_PARTICIPATION:,} (got {amount})",
                "out_of_range",
                min=0,
                max=int(MAX_PARTICIPATION),
            )
        return {
            "amount": str(amount),
            "effective_from": None if effective_from is None else effective_from.isoformat(),
        }
    if effective_from is not None:
        raise FieldError(
            field,
            "effective_from applies to participation fields only",
            "effective_from_not_participation",
        )
    if field == CURRENT_CAR:
        if not isinstance(raw, str) or raw not in ctx.catalog:
            raise FieldError(field, f"a catalog car id (got {raw!r})", "unknown_car")
        return raw
    if field == GROUP_EXCEPTION:
        if raw != NOT_APPROVED and raw not in ctx.rules.group_order:
            raise FieldError(
                field,
                f"an approved group {list(ctx.rules.group_order)} or {NOT_APPROVED!r} "
                f"(got {raw!r})",
                "unknown_group",
                groups=list(ctx.rules.group_order),
            )
        return raw
    if field not in SLOT_OF:
        raise FieldError(field, "unknown profile field", "unknown_field")
    if field == "display_name":
        name = str(raw).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise FieldError(
                field, f"must be 1-{MAX_NAME_LENGTH} characters", "name_length", max=MAX_NAME_LENGTH
            )
        if sum(ch.isdigit() for ch in name) >= 5:
            raise FieldError(
                field, "a name, not a number (never store an ID number)", "name_is_a_number"
            )
        return name
    if field == "occupation":
        if raw not in ctx.occupations:
            raise FieldError(field, f"unknown occupation title {raw!r}", "unknown_occupation")
        return raw
    if field == "group":
        if raw not in ctx.rules.group_order:
            raise FieldError(
                field,
                f"must be one of {list(ctx.rules.group_order)} (got {raw!r})",
                "unknown_group",
                groups=list(ctx.rules.group_order),
            )
        return raw
    if field == "children_under_23":
        if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= MAX_CHILDREN:
            raise FieldError(
                field,
                f"must be a whole number 0-{MAX_CHILDREN} (got {raw!r})",
                "out_of_range",
                min=0,
                max=MAX_CHILDREN,
            )
        return raw
    value = _decimal(field, raw)
    if field == "base_salary" and not 0 < value <= MAX_SALARY:
        raise FieldError(
            field,
            f"must be above 0 and at most {MAX_SALARY:,} (got {value})",
            "out_of_range",
            min=1,
            max=int(MAX_SALARY),
        )
    if field in ("commissions", "bonus") and not 0 <= value <= MAX_SALARY:
        raise FieldError(
            field,
            f"must be 0-{MAX_SALARY:,} (got {value})",
            "out_of_range",
            min=0,
            max=int(MAX_SALARY),
        )
    if field in ("pension_percent", "study_fund_percent"):
        if not 0 <= value <= MAX_PERCENT:
            raise FieldError(
                field,
                f"a percentage 0-{MAX_PERCENT} (got {value})",
                "out_of_range",
                min=0,
                max=int(MAX_PERCENT),
            )
        return format(value.scaleb(-2), "f")  # 6.5 -> "0.065", exact
    if field == "credit_points" and (
        not 0 <= value <= MAX_CREDIT_POINTS or value % CREDIT_POINT_STEP != 0
    ):
        raise FieldError(
            field,
            f"0-{MAX_CREDIT_POINTS} in steps of 0.25 (got {value})",
            "credit_points_step",
            max=int(MAX_CREDIT_POINTS),
        )
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
    group = slots.get("group")
    if group is not None and group.state == "filled" and group.source == "representative":
        values["group_approved"] = True
    return EmployeeProfile(**values)


def tool_fields(engine_fields: list[str] | tuple[str, ...]) -> list[str]:
    """Engine/slot field names (e.g. MissingInputs.fields) -> tool field names."""
    return [TOOL_OF.get(f, f) for f in engine_fields]

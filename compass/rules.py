"""Typed, validated, immutable view of data/rules.yaml.

`load_rules(path)` either returns a frozen `Rules` or raises `RulesError` with one readable line per
problem, naming the offending field, e.g.:

    Invalid rules file data/rules.yaml:
      - net_method.brackets[2].rate: must be between 0 and 1 (got 1.4)
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    ValidationError,
    model_validator,
)

from compass.config import RULES_YAML
from compass.data.drive import DRIVE_BY_CODE


class RulesError(ValueError):
    """The rules file is missing, unparsable or invalid."""


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"expected a number, got {value!r}")
    if isinstance(value, int | float | str):
        try:
            # str(float) is the shortest round-trip repr: 0.1 -> Decimal("0.1"), not binary noise.
            return Decimal(str(value).strip())
        except InvalidOperation:
            pass
    raise ValueError(f"expected a number, got {value!r}")


def _non_negative(value: Decimal) -> Decimal:
    if not value.is_finite() or value < 0:
        raise ValueError(f"must be a non-negative amount (got {value})")
    return value


def _unit_interval(value: Decimal) -> Decimal:
    if not value.is_finite() or not Decimal(0) <= value <= Decimal(1):
        raise ValueError(f"must be between 0 and 1 (got {value})")
    return value


def _freeze_mapping(value: dict[Any, Any]) -> Mapping[Any, Any]:
    return MappingProxyType(value)


Money = Annotated[Decimal, BeforeValidator(_to_decimal), AfterValidator(_non_negative)]
Rate = Annotated[Decimal, BeforeValidator(_to_decimal), AfterValidator(_unit_interval)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ElectricRules(_Frozen):
    method: Literal["gross_up", "gross"] = "gross_up"
    net_bonus: Money  # method = gross_up
    gross_amount: Money  # method = gross
    note: str = ""


class FamilyTrackRules(_Frozen):
    """Car cost is per car: catalog.monthly_company_cost of the listed cars.

    That every id in `cars` exists in the catalog with group "משפחתי" is checked when the engine
    context is built (the rules file is validated on its own, without the catalog).
    """

    min_children: int
    child_max_age: int
    cars: tuple[str, ...]
    price_source: Literal["catalogue"]
    gap_split_employee: Rate
    note: str = ""

    @model_validator(mode="after")
    def _cars_listed_once(self) -> "FamilyTrackRules":
        if not self.cars:
            raise ValueError("cars: must list at least one family-track car")
        if len(set(self.cars)) != len(self.cars):
            raise ValueError(f"cars: duplicate entries {list(self.cars)}")
        return self


class WaiverRules(_Frozen):
    allowed_by: Literal["occupation"]
    maintenance_is_taxable: bool
    maintenance_is_pensionable: bool


class TaxBracket(_Frozen):
    up_to: Money | None
    rate: Rate


class SocialInsuranceRules(_Frozen):
    threshold: Money
    ceiling: Money
    low_rate: Rate
    high_rate: Rate

    @model_validator(mode="after")
    def _threshold_below_ceiling(self) -> "SocialInsuranceRules":
        if self.threshold >= self.ceiling:
            raise ValueError(
                f"threshold ({self.threshold}) must be lower than ceiling ({self.ceiling})"
            )
        return self


class PensionCreditRules(_Frozen):
    rate: Rate
    max_contribution_rate: Rate
    income_ceiling: Money
    note: str = ""


class ParticipationRules(_Frozen):
    """Only the values in the official file are supported; anything else is a schema error."""

    treatment: Literal["net_deduction"]
    reduces_value_of_use: Literal[False]
    note: str = ""


class RoundingRules(_Frozen):
    during: Literal["none"]  # no rounding inside the calculation (including the gross-up)
    display: Literal["shekel"]  # round to whole ILS (half-up) for display only
    note: str = ""


class NetMethodRules(_Frozen):
    basis: Literal["monthly"]
    tax_year: int
    credit_point_value: Money
    brackets: tuple[TaxBracket, ...]
    national_insurance: SocialInsuranceRules
    health: SocialInsuranceRules
    pension_credit: PensionCreditRules
    # "gross" = base_salary + commissions + bonus (not value of use, gross-up or maintenance).
    contributions_base: Literal["gross"]
    contributions_note: str = ""
    participation: ParticipationRules
    rounding: RoundingRules
    note: str = ""

    @model_validator(mode="after")
    def _brackets_ascending_and_open_ended(self) -> "NetMethodRules":
        if not self.brackets:
            raise ValueError("brackets: at least one bracket is required")
        *closed, last = self.brackets
        if last.up_to is not None:
            raise ValueError(
                f"brackets: the last bracket must be open-ended (up_to: null), "
                f"got up_to: {last.up_to}"
            )
        previous: Decimal | None = None
        for index, bracket in enumerate(closed):
            if bracket.up_to is None:
                raise ValueError(f"brackets[{index}]: only the last bracket may have up_to: null")
            if previous is not None and bracket.up_to <= previous:
                raise ValueError(
                    f"brackets[{index}]: up_to must be strictly ascending "
                    f"({bracket.up_to} is not above {previous})"
                )
            previous = bracket.up_to
        return self


class ValueOfUseRules(_Frozen):
    source: str
    tax_year: int  # our addition: the dataset's tax year (net_method.tax_year is the tables' year)
    key: tuple[str, ...]
    drive_field: Annotated[dict[int, str], AfterValidator(_freeze_mapping)]

    @model_validator(mode="after")
    def _drive_codes_known(self) -> "ValueOfUseRules":
        if set(self.drive_field) != set(DRIVE_BY_CODE):
            raise ValueError(
                f"drive_field: codes must be exactly {sorted(DRIVE_BY_CODE)}, "
                f"got {sorted(self.drive_field)}"
            )
        return self


class Rules(_Frozen):
    version: str
    note: str = ""
    budgets: Annotated[dict[str, Money], AfterValidator(_freeze_mapping)]
    group_order: tuple[str, ...]
    choose_from: Literal["own_group_or_lower"]
    electric: ElectricRules
    family_track: FamilyTrackRules
    waiver: WaiverRules
    unused_budget: Literal["not_paid"]
    net_method: NetMethodRules
    value_of_use: ValueOfUseRules

    @model_validator(mode="after")
    def _group_order_matches_budgets(self) -> "Rules":
        if len(set(self.group_order)) != len(self.group_order):
            raise ValueError(f"group_order: duplicate groups {list(self.group_order)}")
        if set(self.group_order) != set(self.budgets):
            raise ValueError(
                f"group_order {list(self.group_order)} must list exactly the budget groups "
                f"{list(self.budgets)}"
            )
        return self


def _format_location(loc: tuple[int | str, ...]) -> str:
    text = ""
    for part in loc:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}" if text else str(part)
    return text or "(top level)"


def _format_errors(path: Path, exc: ValidationError) -> str:
    lines = [f"Invalid rules file {path}:"]
    for error in exc.errors():
        location = _format_location(error["loc"])
        message = error["msg"].removeprefix("Value error, ")
        # Our own validators already quote the bad value; pydantic's built-in messages don't.
        if error["type"] not in ("value_error", "missing"):
            message += f" (got {error['input']!r})"
        lines.append(f"  - {location}: {message}")
    return "\n".join(lines)


def load_rules(path: Path = RULES_YAML) -> Rules:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RulesError(f"Cannot read rules file {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError(f"Rules file {path} is not valid YAML:\n{exc}") from exc
    if not isinstance(raw, dict):
        raise RulesError(f"Rules file {path} must contain a mapping at the top level")
    try:
        return Rules.model_validate(raw)
    except ValidationError as exc:
        raise RulesError(_format_errors(path, exc)) from None

"""Engine domain models: frozen Pydantic, Decimal everywhere.

A field the employee did not provide is `None`. The engine never substitutes a "typical" value;
it raises `MissingInputs` (or returns `needs_info`) instead.
"""

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


class MissingInputs(ValueError):
    """Required profile inputs are unknown. `fields` lists all of them at once."""

    def __init__(self, fields: list[str]) -> None:
        self.fields: tuple[str, ...] = tuple(dict.fromkeys(fields))
        super().__init__(f"missing inputs: {', '.join(self.fields)}")


def _non_negative(value: Decimal | None) -> Decimal | None:
    if value is not None and (not value.is_finite() or value < 0):
        raise ValueError(f"must be a non-negative amount (got {value})")
    return value


def _fraction(value: Decimal | None) -> Decimal | None:
    if value is not None and (not value.is_finite() or not 0 <= value <= 1):
        raise ValueError(f"must be a fraction between 0 and 1, e.g. 0.065 for 6.5% (got {value})")
    return value


def _freeze(value: dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(value)


Amount = Annotated[Decimal, AfterValidator(_non_negative)]
OptionalAmount = Annotated[Decimal | None, AfterValidator(_non_negative)]
OptionalFraction = Annotated[Decimal | None, AfterValidator(_fraction)]
FrozenFacts = Annotated[dict[str, Any], AfterValidator(_freeze)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EmployeeProfile(_Frozen):
    group: str | None = None
    occupation: str | None = None  # exact title from data/occupations.json
    base_salary: OptionalAmount = None
    commissions: OptionalAmount = None
    bonus: OptionalAmount = None
    pension_pct: OptionalFraction = None  # employee pension rate, 0.06 = 6%
    study_fund_pct: OptionalFraction = None  # employee study-fund rate, 0.025 = 2.5%
    credit_points: OptionalAmount = None
    children_under_23: Annotated[int | None, Field(ge=0)] = None


# --- scenarios ------------------------------------------------------------------------------

ParticipationSource = Literal["employee_input", "catalog_default", "representative"]
# "employee_input": today's existing maintenance (CurrentMaintenance).
MaintenanceSource = Literal["occupation", "representative", "employee_input"]


class CompanyCar(_Frozen):
    """A regular (budget-group) company car."""

    kind: Literal["company_car"] = "company_car"
    car_id: str
    # None -> catalog default_employee_participation (source "catalog_default").
    participation: OptionalAmount = None
    # Who supplied `participation` when it is given.
    participation_source: Literal["employee_input", "representative"] = "employee_input"


class FamilyCar(_Frozen):
    """A family-track car (rules.family_track.cars)."""

    kind: Literal["family_car"] = "family_car"
    car_id: str
    participation: OptionalAmount = None
    participation_source: Literal["employee_input", "representative"] = "employee_input"


class Waiver(_Frozen):
    """Give up the car.

    maintenance None -> the occupation's waiver_maintenance (source "occupation"). A value
    quoted by a representative must say so: maintenance=X, maintenance_source="representative".
    """

    kind: Literal["waiver"] = "waiver"
    maintenance: OptionalAmount = None
    maintenance_source: Literal["occupation", "representative"] = "occupation"

    @model_validator(mode="after")
    def _source_matches_value(self) -> "Waiver":
        if (self.maintenance is None) != (self.maintenance_source == "occupation"):
            raise ValueError(
                "maintenance comes from the occupation (maintenance=None) or from a "
                "representative (maintenance=X, maintenance_source='representative')"
            )
        return self


class CurrentMaintenance(_Frozen):
    """Today only: no car and an existing maintenance payment of `amount` (e.g. E-003)."""

    kind: Literal["current_maintenance"] = "current_maintenance"
    amount: Amount


Scenario = Annotated[
    CompanyCar | FamilyCar | Waiver | CurrentMaintenance, Field(discriminator="kind")
]


# --- results --------------------------------------------------------------------------------


class Metadata(_Frozen):
    rules_version: str
    tax_tables_year: int  # rules.net_method.tax_year
    value_of_use_year: int  # rules.value_of_use.tax_year
    participation_source: ParticipationSource | None  # None: no car in this scenario
    maintenance_source: MaintenanceSource | None  # None: no maintenance in this scenario
    electric_method: Literal["gross_up", "gross"] | None  # None: not an electric car


class NetBreakdown(_Frozen):
    """Every line of the net formula, unrounded.

    net = cash_income + maintenance + electric_gross
          - income_tax - national_insurance - health
          - employee_pension - employee_study - participation - family_employee_share

    `employee_pension`, `employee_study` and `net` are None only inside a partial `Comparison`
    (contribution rates unknown).
    """

    scenario: Scenario
    car_id: str | None
    cash_income: Decimal
    value_of_use: Decimal
    maintenance: Decimal
    electric_gross: Decimal
    taxable_income: Decimal
    income_tax_before_credits: Decimal
    credit_points_value: Decimal
    pension_credit: Decimal
    income_tax: Decimal
    national_insurance: Decimal
    health: Decimal
    employee_pension: Decimal | None
    employee_study: Decimal | None
    participation: Decimal
    family_employee_share: Decimal
    net: Decimal | None
    metadata: Metadata


DeltaLineName = Literal[
    "cash_income",
    "maintenance",
    "electric_gross",
    "income_tax",
    "national_insurance",
    "health",
    "employee_pension",
    "employee_study",
    "participation",
    "family_employee_share",
]


class DeltaLine(_Frozen):
    """Effect of one formula line on net, alternative vs today: positive = more money for the
    employee. Deductions are negated, so a higher income tax is a negative net_effect.
    """

    line: DeltaLineName
    net_effect: Decimal


class DisplayDeltaLine(_Frozen):
    line: DeltaLineName
    net_effect: int  # same convention as DeltaLine, whole ILS


class EngineWarning(_Frozen):
    """Non-blocking: something the employee or representative should double-check.

    Codes: group_mismatch_with_occupation, current_car_above_group.
    """

    code: str
    facts: FrozenFacts = Field(default_factory=dict)


class Comparison(_Frozen):
    today: NetBreakdown
    alternative: NetBreakdown
    diff: Decimal  # exact: alternative.net - today.net
    # round(alternative.net) - round(today.net), so the shown numbers subtract correctly. In a
    # partial comparison the nets are unknown and this is round(diff).
    display_diff: int
    delta_lines: tuple[DeltaLine, ...]  # sum == diff exactly
    display_delta_lines: tuple[DisplayDeltaLine, ...]  # largest remainder; sum == display_diff
    explanation_facts: tuple[FrozenFacts, ...]
    warnings: tuple[EngineWarning, ...] = ()
    missing: tuple[str, ...] = ()  # non-empty -> partial: nets are None, diff is still exact

    @property
    def partial(self) -> bool:
        return bool(self.missing)


# --- eligibility ----------------------------------------------------------------------------

EligibilityStatus = Literal["eligible", "not_eligible", "needs_info"]


class Eligibility(_Frozen):
    status: EligibilityStatus
    reason: str  # machine code, e.g. "car_group_higher"
    facts: FrozenFacts = Field(default_factory=dict)
    warnings: tuple[EngineWarning, ...] = ()


class Option(_Frozen):
    scenario: Scenario
    eligibility: Eligibility
    comparison: Comparison

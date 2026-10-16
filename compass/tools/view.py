"""The display-ready `view` of a comparison, attached to every comparison_ready event.

The UI renders it as is: amounts are already rounded, every line and input carries its Hebrew
label (compass.labels), every input carries its source, and every non-zero line names the
inputs and rules it depends on (PROVENANCE). The browser does no money math, so the two
display invariants are checked here before the event is stored:

    sum(line.net_effect) == display_diff
    today_net + display_diff == alternative_net        (when both nets are known)
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from compass.engine.decimal_math import to_display
from compass.engine.models import DeltaLineName
from compass.labels import (
    DELTA_LABELS,
    RULE_LABELS,
    alternative_title,
    field_label,
    group_label,
    group_letter,
    ticket_field_title,
    warning_message,
)
from compass.state import Slot, Ticket
from compass.tools.profile import ALTERNATIVE_PARTICIPATION, CURRENT_PARTICIPATION, SLOT_OF
from compass.tools.services import Services

VIEW_VERSION = 1

ChipSource = Literal[
    "employee_input", "occupation", "representative", "catalog_default", "pending_rep"
]
Unit = Literal["ils", "percent", "points", "count", "text"]

# Which inputs (view input ids) and rules (RULE_LABELS keys) each line of the difference
# depends on. Inputs absent from a given comparison are skipped. Every DeltaLineName must be
# here (tested), so a new line can never reach the screen without a source.
PROVENANCE: dict[DeltaLineName, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "cash_income": (("base_salary", "commissions", "bonus"), ()),
    "maintenance": (
        ("alternative_maintenance", "today_maintenance", "occupation"),
        ("waiver_maintenance",),
    ),
    "electric_gross": (
        ("alternative_car", "today_car"),
        ("electric_reimbursement", "income_tax_brackets"),
    ),
    "income_tax": (
        ("credit_points", "pension_percent", "base_salary", "today_car", "alternative_car"),
        ("income_tax_brackets", "credit_point_value", "pension_credit", "value_of_use"),
    ),
    "national_insurance": (
        ("base_salary", "today_car", "alternative_car"),
        ("national_insurance_brackets", "value_of_use"),
    ),
    "health": (
        ("base_salary", "today_car", "alternative_car"),
        ("health_brackets", "value_of_use"),
    ),
    "employee_pension": (("base_salary", "pension_percent"), ()),
    "employee_study": (("base_salary", "study_fund_percent"), ()),
    "participation": (("today_participation", "alternative_participation"), ()),
    "family_employee_share": (("alternative_car", "group"), ("family_track",)),
}


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ViewInput(_View):
    id: str  # e.g. "credit_points", "alternative_participation"
    label: str
    value: int | str | None  # ils -> whole ILS (int); other units -> exact decimal string
    unit: Unit
    source: ChipSource
    ticket_field: str | None = None  # the ticket field it waits for / was answered on


class ViewRule(_View):
    key: str
    label: str


class ViewLine(_View):
    key: DeltaLineName
    label: str
    net_effect: int
    inputs: list[str]  # ids into ComparisonView.inputs
    rules: list[ViewRule]


class ViewField(_View):
    field: str
    label: str


class ViewWarning(_View):
    code: str
    message: str


class ComparisonView(_View):
    version: int = VIEW_VERSION
    today_title: str
    alternative_title: str
    alternative_kind: str
    alternative_car_id: str | None
    group: str | None
    group_label: str | None
    group_budget: int | None
    today_net: int | None
    alternative_net: int | None
    display_diff: int
    direction: Literal["up", "down", "flat"]  # flat: display_diff == 0
    breakdown: list[ViewLine]  # non-zero lines only, in API order
    inputs: list[ViewInput]
    pending: bool
    pending_fields: list[str]
    partial: bool
    missing: list[ViewField]
    warnings: list[ViewWarning]
    hypothetical: bool
    rules_version: str


class ViewInvariantError(AssertionError):
    """The numbers to display don't add up: never emit them."""


_SLOT_SOURCE: dict[str, ChipSource] = {
    "employee": "employee_input",
    "payslip": "employee_input",  # no payslip upload yet; the employee supplied it
    "derived": "occupation",  # the group, derived from the occupation
    "representative": "representative",
}
_PROFILE_INPUTS: tuple[tuple[str, Unit], ...] = (
    ("occupation", "text"),
    ("group", "text"),
    ("base_salary", "ils"),
    ("commissions", "ils"),
    ("bonus", "ils"),
    ("pension_percent", "percent"),
    ("study_fund_percent", "percent"),
    ("credit_points", "points"),
    ("children_under_23", "count"),
)


def _profile_input(services: Services, tool: str, unit: Unit, slot: Slot) -> ViewInput:
    source: ChipSource = "pending_rep" if slot.state == "pending_rep" else _SLOT_SOURCE[slot.source]
    value: int | str | None = None
    if slot.state == "filled":
        raw = slot.value
        if unit == "ils":
            value = to_display(Decimal(raw), services.ctx.rules)
        elif unit == "percent":
            value = str((Decimal(raw) * 100).normalize())
        elif unit in ("points", "count"):
            value = str(Decimal(str(raw)).normalize())
        elif tool == "group":
            value = group_letter(raw)  # "ב׳", like the pill
        else:
            value = str(raw)
    return ViewInput(id=tool, label=field_label(tool), value=value, unit=unit, source=source)


def _car_name(services: Services, car_id: str) -> str:
    car = services.ctx.catalog.get(car_id)
    return car_id if car is None else car.commercial_name


def _participation_input(
    input_id: str,
    amount: int | None,
    source: str | None,
    pending: bool,
    ticket_field: str,
) -> ViewInput:
    chip: ChipSource = "pending_rep" if pending else source  # type: ignore[assignment]
    return ViewInput(
        id=input_id,
        label=field_label(input_id),
        value=amount,
        unit="ils",
        source=chip,
        ticket_field=ticket_field,
    )


def _scenario_inputs(
    services: Services,
    payload: Mapping[str, Any],
    today_label: str | None,
) -> list[ViewInput]:
    comparison = payload["comparison"]
    today, alt = comparison["today"], comparison["alternative"]
    inputs: list[ViewInput] = []

    today_scenario = today["scenario"]
    if today_scenario["kind"] in ("company_car", "family_car", "external_car"):
        name = today_label or _car_name(services, today_scenario.get("car_id", ""))
        inputs.append(
            ViewInput(
                id="today_car",
                label=field_label("today_car"),
                value=name,
                unit="text",
                source="employee_input",
            )
        )
        info = payload["today_participation"]
        inputs.append(
            _participation_input(
                "today_participation",
                today["display"]["participation"],
                info["source"],
                info["pending_rep"],
                CURRENT_PARTICIPATION,
            )
        )
    elif today_scenario["kind"] == "current_maintenance":
        inputs.append(
            ViewInput(
                id="today_maintenance",
                label=field_label("today_maintenance"),
                value=today["display"]["maintenance"],
                unit="ils",
                source="employee_input",
            )
        )

    alt_scenario = alt["scenario"]
    if alt_scenario["kind"] in ("company_car", "family_car"):
        car_id = alt_scenario["car_id"]
        inputs.append(
            ViewInput(
                id="alternative_car",
                label=field_label("alternative_car"),
                value=_car_name(services, car_id),
                unit="text",
                source="employee_input",
            )
        )
        inputs.append(
            _participation_input(
                "alternative_participation",
                alt["display"]["participation"],
                payload["participation_source"],
                payload["pending_rep"],
                f"{ALTERNATIVE_PARTICIPATION}{car_id}",
            )
        )
    elif alt_scenario["kind"] == "waiver":
        inputs.append(
            ViewInput(
                id="alternative_maintenance",
                label=field_label("alternative_maintenance"),
                value=alt["display"]["maintenance"],
                unit="ils",
                source=alt["metadata"]["maintenance_source"],
            )
        )
    return inputs


def _today_title(stored: Mapping[str, Any]) -> str | None:
    """Today's car as stored ("COROLLA CROSS"), with the registration year the employee gave
    for a catalog car ("COROLLA CROSS 2025"). An external car's label already has its year.
    No brand: the catalog has none."""
    label = stored.get("label")
    year = (stored.get("input") or {}).get("registration_year")
    kind = (stored.get("scenario") or {}).get("kind")
    if label and year and kind in ("company_car", "family_car"):
        return f"{label} {year}"
    return label


def build_view(
    services: Services, session_id: str, alternative: Mapping[str, Any], payload: Mapping[str, Any]
) -> dict[str, Any]:
    """The `view` for a compare payload (as stored in comparison_ready), JSON-ready.

    Raises ViewInvariantError if the display numbers don't add up, or a non-zero line has
    no provenance.
    """
    ctx = services.ctx
    comparison = payload["comparison"]
    slots = services.store.slots(session_id)
    today_stored = services.store.scenarios(session_id).get("today") or {}
    today_label = _today_title(today_stored)

    inputs = [
        _profile_input(services, tool, unit, slots[SLOT_OF[tool]])
        for tool, unit in _PROFILE_INPUTS
        if SLOT_OF[tool] in slots and slots[SLOT_OF[tool]].state != "unknown"
    ]
    inputs += _scenario_inputs(services, payload, today_label)
    present = {i.id for i in inputs}

    breakdown: list[ViewLine] = []
    for line in comparison["display_delta_lines"]:
        if not line["net_effect"]:
            continue
        key = line["line"]
        input_ids, rule_keys = PROVENANCE[key]
        used = [i for i in input_ids if i in present]
        if not used and not rule_keys:
            raise ViewInvariantError(f"line {key} has no provenance in this comparison")
        breakdown.append(
            ViewLine(
                key=key,
                label=DELTA_LABELS[key],
                net_effect=line["net_effect"],
                inputs=used,
                rules=[ViewRule(key=r, label=RULE_LABELS[r]) for r in rule_keys],
            )
        )

    display_diff: int = comparison["display_diff"]
    today_net = comparison["today"]["display"]["net"]
    alt_net = comparison["alternative"]["display"]["net"]
    total = sum(line["net_effect"] for line in comparison["display_delta_lines"])
    if total != display_diff:
        raise ViewInvariantError(f"lines sum to {total}, display_diff is {display_diff}")
    if today_net is not None and alt_net is not None and today_net + display_diff != alt_net:
        raise ViewInvariantError(f"{today_net} + {display_diff} != {alt_net}")

    group_slot = slots.get("group")
    group = group_slot.value if group_slot is not None and group_slot.state == "filled" else None
    budget = ctx.rules.budgets.get(group) if group is not None else None
    car_id = alternative.get("car_id")
    pending_fields = [i.ticket_field or i.id for i in inputs if i.source == "pending_rep"]

    view = ComparisonView(
        today_title=today_label or "",
        alternative_title=alternative_title(
            alternative, None if car_id is None else _car_name(services, car_id)
        ),
        alternative_kind=alternative["kind"],
        alternative_car_id=car_id,
        group=group,
        group_label=None if group is None else group_label(group),
        group_budget=None if budget is None else to_display(budget, ctx.rules),
        today_net=today_net,
        alternative_net=alt_net,
        display_diff=display_diff,
        direction="up" if display_diff > 0 else "down" if display_diff < 0 else "flat",
        breakdown=breakdown,
        inputs=inputs,
        pending=bool(pending_fields),
        pending_fields=pending_fields,
        partial=comparison["partial"],
        missing=[ViewField(field=f, label=field_label(f)) for f in payload["missing"]],
        warnings=[
            ViewWarning(
                code=w["code"],
                message=warning_message(w["code"], w["facts"], lambda c: _car_name(services, c)),
            )
            for w in comparison["warnings"]
        ],
        hypothetical=payload["hypothetical"],
        rules_version=comparison["alternative"]["metadata"]["rules_version"],
    )
    return view.model_dump(mode="json")


# --- the representative's inbox ---------------------------------------------------------------


class TicketFieldView(_View):
    field: str  # the ticket's field, e.g. "alternative_participation:CAR-10"
    label: str
    unit: Unit
    car_id: str | None
    car_name: str | None
    catalog_default: int | None  # the participation the comparison uses until answered


class TicketComparisonView(_View):
    alternative_title: str
    display_diff: int
    pending: bool


class TicketView(_View):
    version: int = VIEW_VERSION
    title: str
    fields: list[TicketFieldView]
    comparison: TicketComparisonView | None  # the employee's latest comparison


_PROFILE_UNITS: dict[str, Unit] = dict(_PROFILE_INPUTS)


def _ticket_field(services: Services, field: str) -> TicketFieldView:
    car_id: str | None = None
    if field.startswith(ALTERNATIVE_PARTICIPATION):
        car_id = field.removeprefix(ALTERNATIVE_PARTICIPATION)
    car = None if car_id is None else services.ctx.catalog.get(car_id)
    default = None
    if car is not None:
        default = to_display(car.default_employee_participation, services.ctx.rules)
    participation = field == CURRENT_PARTICIPATION or car_id is not None
    return TicketFieldView(
        field=field,
        label=field_label(field),
        unit="ils" if participation else _PROFILE_UNITS.get(field, "text"),
        car_id=car_id,
        car_name=None if car is None else car.commercial_name,
        catalog_default=default,
    )


def build_ticket_view(services: Services, ticket: Ticket) -> dict[str, Any]:
    """Display-ready facts for one ticket in the representative's inbox, JSON-ready."""
    fields = [_ticket_field(services, f) for f in ticket.blocking_fields]
    first = ticket.blocking_fields[0] if ticket.blocking_fields else None
    title = "שאלה מהעובד/ת" if first is None else ticket_field_title(first)
    if fields and fields[0].car_name:
        title = f"{title} · {fields[0].car_name}"
    last = services.store.last_comparison(ticket.session_id)
    view = (last or {}).get("view")
    comparison = (
        None
        if view is None
        else TicketComparisonView(
            alternative_title=view["alternative_title"],
            display_diff=view["display_diff"],
            pending=view["pending"],
        )
    )
    return TicketView(title=title, fields=fields, comparison=comparison).model_dump(mode="json")

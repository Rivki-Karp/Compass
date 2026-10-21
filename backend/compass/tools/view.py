"""The display-ready `view` of a comparison, attached to every comparison_ready event.

The UI renders it as is: amounts are already rounded, every line and input carries its Hebrew
label (compass.labels), every input carries its source, and every non-zero line names the
inputs and rules it depends on (PROVENANCE). The browser does no money math, so the two
display invariants are checked here before the event is stored:

    sum(line.net_effect) == display_diff
    today_net + display_diff == alternative_net        (when both nets are known)

While today's car is unknown there is no diff: display_diff is None, there are no lines, and
`diff_note` says what is missing ("חסר הרכב של היום"); the alternative's own net is shown.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from compass.engine.decimal_math import to_display
from compass.engine.models import DeltaLineName
from compass.labels import (
    COMPUTED_BY_LABELS,
    CURRENT_CAR_QUESTION_TITLE,
    DELTA_LABELS,
    DIFF_WAITS_FOR_TODAY,
    FREE_ANSWER_LABELS,
    OCCUPATION_QUESTION_TITLE,
    RULE_LABELS,
    alternative_title,
    car_details,
    clamp,
    field_label,
    group_label,
    group_letter,
    ticket_field_title,
    warning_message,
)
from compass.state import Slot, Ticket
from compass.tools.profile import (
    ALTERNATIVE_PARTICIPATION,
    CURRENT_CAR,
    CURRENT_PARTICIPATION,
    GROUP_EXCEPTION,
    SLOT_OF,
)
from compass.tools.questions import (
    NOTE_FOR_OTHER,
    OCCUPATION,
    OTHER,
    YES_NO_LABELS,
    answer_label,
    car_detail,
    car_option_label,
    group_exception_bounds,
    group_exception_options,
    is_free,
    ticket_questions,
)
from compass.tools.services import Services

VIEW_VERSION = 1

ChipSource = Literal[
    "employee_input", "occupation", "representative", "catalog_default", "pending_rep", "payslip"
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


class ViewComputedBy(_View):
    origin: Literal["tool", "server"]
    label: str  # "חושב בכלי" / "חושב מחדש בשרת · בלי מודל"
    tool: str | None  # "compare" when the model called the tool; None for the server


class ComparisonView(_View):
    version: int = VIEW_VERSION
    today_title: str
    alternative_title: str
    alternative_kind: str
    alternative_car_id: str | None
    # The catalog car's drive and group ("חשמלי · קבוצה ג׳"); None for a waiver or a car
    # outside the catalog.
    alternative_details: str | None = None
    group: str | None
    group_label: str | None
    group_budget: int | None
    today_net: int | None
    alternative_net: int | None
    display_diff: int | None  # None: today unknown (diff_note says so)
    # flat: display_diff == 0; unknown: no diff yet (today unknown)
    direction: Literal["up", "down", "flat", "unknown"]
    # What the diff waits for, in place of it: "חסר הרכב של היום" (None when there is a diff).
    diff_note: str | None = None
    breakdown: list[ViewLine]  # non-zero lines only, in API order
    inputs: list[ViewInput]
    pending: bool
    pending_fields: list[str]
    partial: bool
    missing: list[ViewField]
    warnings: list[ViewWarning]
    hypothetical: bool
    rules_version: str
    computed_by: ViewComputedBy


class ViewInvariantError(AssertionError):
    """The numbers to display don't add up: never emit them."""


_SLOT_SOURCE: dict[str, ChipSource] = {
    "employee": "employee_input",
    "payslip": "payslip",  # confirmed by the employee from their payslip: "לפי התלוש"
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


def profile_inputs(services: Services, session_id: str) -> list[dict[str, Any]]:
    """The profile inputs as the view shows them now (the same builder, no comparison needed)."""
    slots = services.store.slots(session_id)
    return [
        _profile_input(services, tool, unit, slots[SLOT_OF[tool]]).model_dump(mode="json")
        for tool, unit in _PROFILE_INPUTS
        if SLOT_OF[tool] in slots and slots[SLOT_OF[tool]].state != "unknown"
    ]


def _car_name(services: Services, car_id: str) -> str:
    car = services.ctx.catalog.get(car_id)
    return car_id if car is None else car.commercial_name


def _car_details(services: Services, car_id: str | None) -> str | None:
    car = None if car_id is None else services.ctx.catalog.get(car_id)
    return None if car is None else car_details(car.drive, car.group)


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
    today_source: ChipSource = "employee_input",
    today_pending: bool = False,
) -> list[ViewInput]:
    comparison = payload["comparison"]
    today, alt = comparison["today"], comparison["alternative"]
    inputs: list[ViewInput] = []
    if today is None and today_pending:  # a representative is identifying today's car
        inputs.append(
            ViewInput(
                id="today_car",
                label=field_label("today_car"),
                value=None,
                unit="text",
                source="pending_rep",
                ticket_field=CURRENT_CAR,
            )
        )

    today_scenario = {} if today is None else today["scenario"]  # None: today unknown
    if today_scenario.get("kind") in ("company_car", "family_car", "external_car"):
        name = today_label or _car_name(services, today_scenario.get("car_id", ""))
        inputs.append(
            ViewInput(
                id="today_car",
                label=field_label("today_car"),
                value=name,
                unit="text",
                source=today_source,
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
    elif today_scenario.get("kind") == "current_maintenance":
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
    exception = slots.get(GROUP_EXCEPTION)
    if exception is not None and exception.state == "pending_rep":
        # the group in effect until a representative answers the group exception
        inputs = [i for i in inputs if i.id != "group"]
        group_input = (
            _profile_input(services, "group", "text", slots["group"])
            if ("group" in slots and slots["group"].state != "unknown")
            else None
        )
        inputs.insert(
            1 if inputs and inputs[0].id == "occupation" else 0,
            ViewInput(
                id="group",
                label=field_label("group"),
                value=None if group_input is None else group_input.value,
                unit="text",
                source="pending_rep",
                ticket_field=GROUP_EXCEPTION,
            ),
        )
    car_slot = slots.get(CURRENT_CAR)
    inputs += _scenario_inputs(
        services,
        payload,
        today_label,
        today_source=_SLOT_SOURCE.get(today_stored.get("source") or "employee", "employee_input"),
        today_pending=car_slot is not None and car_slot.state == "pending_rep",
    )
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

    display_diff: int | None = comparison["display_diff"]
    today = comparison["today"]
    today_net = None if today is None else today["display"]["net"]
    alt_net = comparison["alternative"]["display"]["net"]
    total = sum(line["net_effect"] for line in comparison["display_delta_lines"])
    if display_diff is None:  # today unknown: no lines, and the alternative's own net
        # (None only while the contribution rates are unknown too: the net needs them)
        rates_unknown = bool({"pension_pct", "study_fund_pct"} & set(comparison["missing"]))
        if (
            comparison["display_delta_lines"]
            or today is not None
            or (alt_net is None and not rates_unknown)
        ):
            raise ViewInvariantError("no diff: no lines and no today, but the alternative's net")
    elif total != display_diff:
        raise ViewInvariantError(f"lines sum to {total}, display_diff is {display_diff}")
    elif today_net is not None and alt_net is not None and today_net + display_diff != alt_net:
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
        alternative_details=_car_details(services, car_id),
        group=group,
        group_label=None if group is None else group_label(group),
        group_budget=None if budget is None else to_display(budget, ctx.rules),
        today_net=today_net,
        alternative_net=alt_net,
        display_diff=display_diff,
        direction=_direction(display_diff),
        diff_note=None if display_diff is not None else DIFF_WAITS_FOR_TODAY,
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
        computed_by=_computed_by(payload),
    )
    return view.model_dump(mode="json")


def _direction(display_diff: int | None) -> Literal["up", "down", "flat", "unknown"]:
    if display_diff is None:
        return "unknown"
    return "up" if display_diff > 0 else "down" if display_diff < 0 else "flat"


def _computed_by(payload: Mapping[str, Any]) -> ViewComputedBy:
    """The model's `compare` call, or the server's own run of it (`origin: "server"`)."""
    if payload.get("origin") == "server":
        return ViewComputedBy(origin="server", label=COMPUTED_BY_LABELS["server"], tool=None)
    return ViewComputedBy(origin="tool", label=COMPUTED_BY_LABELS["tool"], tool="compare")


# --- the representative's inbox ---------------------------------------------------------------


class TicketOptionView(_View):
    value: str  # what the answer sends for the field, e.g. "ג" or "not_approved"
    label: str  # "מאושר לקבוצה ג׳"
    # an occupation's group ("קבוצה ב׳"): the group this choice would give
    detail: str | None = None


class TicketFactView(_View):
    label: str  # "קבוצה לפי העיסוק"
    value: str  # "קבוצה ב׳"


class TicketComparisonView(_View):
    alternative_title: str
    display_diff: int | None  # None: today unknown (diff_note)
    pending: bool
    diff_note: str | None = None


class TicketFieldView(_View):
    field: str  # the ticket's field, e.g. "alternative_participation:CAR-10"
    title: str  # the section heading, e.g. "השתתפות עצמית" / "אישור חריג לקבוצה"
    label: str
    unit: Unit
    car_id: str | None
    car_name: str | None
    # the participation the comparison uses until answered; None: today's car is not in the
    # catalog (the screen says so)
    catalog_default: int | None
    # A field answered by a choice (group_exception: radio buttons); empty for a typed value.
    options: list[TicketOptionView] = []
    # What the representative needs to decide it, as text tiles (group_exception).
    facts: list[TicketFactView] = []
    # Answered in an earlier part of a partial answer (the ticket stays open for the rest):
    # what the representative answered, display-ready (whole ILS, or the chosen option's label).
    answered: bool = False
    answer: int | str | None = None
    # The employee's latest comparison that this field affects: that car's own comparison for a
    # car's participation; the latest one otherwise. Never another car's.
    comparison: TicketComparisonView | None = None


QuestionStatus = Literal["pending", "needs_checking", "answered", "unknown"]


class TicketQuestionView(_View):
    """One question as the representative's screen renders it: a heading, the model's prompt
    (secondary), and one input by `type` (amount / choice / yes_no / text), plus "needs
    checking" and a note on every question."""

    id: str  # what an answer names (`answers` in POST /tickets/{id}/answer)
    kind: Literal["bound", "free"]
    bound_field: str | None  # the calculation input a bound question fills
    type: Literal["amount", "choice", "yes_no", "text"]
    title: str  # the section heading (server-built; a free question's prompt, clamped)
    prompt_he: str  # the model's wording ("" when none)
    label: str  # the input's label
    options: list[TicketOptionView] = []  # choice and yes_no
    # An occupation question: every title in the occupations table, for the picker's search
    # box (the options are the closest ones). The answer is always one of these, or "other".
    # A current_car question: every catalog car, the same way.
    search_options: list[TicketOptionView] = []
    search_label: str | None = None  # the search box's label
    search_empty: str | None = None  # what the search says when nothing matches
    # The option that needs a note ("other"), and the note's label then.
    note_required_for: str | None = None
    note_required_label: str | None = None
    # A tile with the chosen option's detail (an occupation's group, a car's drive and group).
    detail_label: str | None = None
    facts: list[TicketFactView] = []
    car_id: str | None = None
    car_name: str | None = None
    catalog_default: int | None = None
    comparison: TicketComparisonView | None = None
    # pending: not answered yet; needs_checking: the rep is checking (still pending);
    # answered; unknown: the ticket closed without an answer to it
    status: QuestionStatus = "pending"
    answer: int | str | None = None  # display-ready (whole ILS, or the option's label / text)
    note: str | None = None


class TicketView(_View):
    version: int = VIEW_VERSION
    title: str
    fields: list[TicketFieldView]  # the bound questions' fields (clients before `questions`)
    questions: list[TicketQuestionView] = []
    comparison: TicketComparisonView | None  # the employee's latest comparison


_PROFILE_UNITS: dict[str, Unit] = dict(_PROFILE_INPUTS)


def _group_exception_field(services: Services, session_id: str) -> TicketFieldView:
    """The choices for a group exception (questions.group_exception_options), with the facts
    the representative decides by: the occupation's group and today's car with its group."""
    base, car_group = group_exception_bounds(services, session_id)
    options = [TicketOptionView(**o) for o in group_exception_options(services, session_id)]
    facts = []
    slots = services.store.slots(session_id)
    occupation = slots.get("occupation")
    if base is not None:
        known = occupation is not None and occupation.state == "filled"
        where = "קבוצה לפי העיסוק" if known else "הקבוצה שנמסרה"
        facts.append(TicketFactView(label=where, value=group_label(base)))
    today = _today_title(services.store.scenarios(session_id).get("today") or {})
    if today:
        value = today if car_group is None else f"{today} · {group_label(car_group)}"
        facts.append(TicketFactView(label=field_label("today_car"), value=value))
    return TicketFieldView(
        field=GROUP_EXCEPTION,
        title=ticket_field_title(GROUP_EXCEPTION),
        label=field_label(GROUP_EXCEPTION),
        unit="text",
        car_id=None,
        car_name=None,
        catalog_default=None,
        options=options,
        facts=facts,
    )


def _current_car_field(services: Services, session_id: str) -> TicketFieldView:
    """Today's participation: today's car with its registration year ("COROLLA CROSS 2025"),
    and the catalog default when today's car is a catalog car (None otherwise)."""
    stored = services.store.scenarios(session_id).get("today") or {}
    scenario = stored.get("scenario") or {}
    car = services.ctx.catalog.get(scenario.get("car_id") or "")
    name = _today_title(stored) if scenario.get("kind") != "current_maintenance" else None
    if car is not None and name == car.commercial_name:  # no year given: the catalog's
        name = f"{name} {car.registration_year}"
    return TicketFieldView(
        field=CURRENT_PARTICIPATION,
        title=ticket_field_title(CURRENT_PARTICIPATION),
        label=field_label(CURRENT_PARTICIPATION),
        unit="ils",
        car_id=None if car is None else car.id,
        car_name=name or None,
        catalog_default=None
        if car is None
        else to_display(car.default_employee_participation, services.ctx.rules),
    )


def _ticket_field(services: Services, ticket: Ticket, field: str) -> TicketFieldView:
    if field == GROUP_EXCEPTION:
        return _group_exception_field(services, ticket.session_id)
    if field == CURRENT_PARTICIPATION:
        return _current_car_field(services, ticket.session_id)
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
        title=ticket_field_title(field),
        label=field_label(field),
        unit="ils" if participation else _PROFILE_UNITS.get(field, "text"),
        car_id=car_id,
        car_name=None if car is None else car.commercial_name,
        catalog_default=default,
    )


def _ticket_comparison(view: Mapping[str, Any] | None) -> TicketComparisonView | None:
    if view is None:
        return None
    return TicketComparisonView(
        alternative_title=view["alternative_title"],
        display_diff=view["display_diff"],
        pending=view["pending"],
        diff_note=view.get("diff_note"),
    )


def _answer_display(services: Services, field: TicketFieldView, raw: Any) -> int | str | None:
    if field.options:
        return next((o.label for o in field.options if o.value == raw), str(raw))
    if field.unit == "ils":
        return to_display(Decimal(str(raw).replace(",", "")), services.ctx.rules)
    return None if raw is None else str(raw)


FREE_TITLE_LENGTH = 60  # a free question's heading, from its prompt
FREE_IN_TITLE_LENGTH = 40  # the same prompt inside the ticket's title


def _ticket_title(fields: list[TicketFieldView], free_prompts: Sequence[str] = ()) -> str:
    """Built from the fields, never from the model's question: "השתתפות עצמית · MG4",
    "השתתפות עצמית · 3 רכבים", and the other fields' titles; then each free question's prompt,
    clamped; joined with " + "."""
    cars = [f for f in fields if f.field.startswith(ALTERNATIVE_PARTICIPATION)]
    parts: list[str] = []
    for f in fields:
        if f in cars:
            if f is cars[0]:
                what = f.car_name if len(cars) == 1 else f"{len(cars)} רכבים"
                parts.append(f"{f.title} · {what}")
        else:
            parts.append(f"{f.title} · {f.car_name}" if f.car_name else f.title)
    parts += [clamp(p, FREE_IN_TITLE_LENGTH) for p in free_prompts]
    return " + ".join(parts) if parts else "שאלה מהעובד/ת"


def _occupation_field(question: Mapping[str, Any]) -> TicketFieldView:
    """A bound occupation question: the employee's words, and the closest titles as options."""
    query = question.get("occupation_query")
    facts = [] if not query else [TicketFactView(label="איך העובד/ת תיאר/ה", value=query)]
    return TicketFieldView(
        field=OCCUPATION,
        title=OCCUPATION_QUESTION_TITLE if not query else f"{OCCUPATION_QUESTION_TITLE} · {query}",
        label="העיסוק בטבלה שמתאים לעובד/ת",
        unit="text",
        car_id=None,
        car_name=None,
        catalog_default=None,
        options=[TicketOptionView(**o) for o in question["answer"]["options"]],
        facts=facts,
    )


def _which_car_field(services: Services, question: Mapping[str, Any]) -> TicketFieldView:
    """A bound current_car question: the employee's words, and the catalog cars they may mean."""
    query = question.get("car_query")
    facts = [] if not query else [TicketFactView(label="איך העובד/ת תיאר/ה", value=query)]
    options = [TicketOptionView(**o) for o in question["answer"]["options"]]
    return TicketFieldView(
        field=CURRENT_CAR,
        title=CURRENT_CAR_QUESTION_TITLE
        if not query
        else f"{CURRENT_CAR_QUESTION_TITLE} · {query}",
        label="הרכב מהקטלוג שיש לעובד/ת היום",
        unit="text",
        car_id=None,
        car_name=None,
        catalog_default=None,
        options=[_with_car_detail(services, o) for o in options],
        facts=facts,
    )


def _with_car_detail(services: Services, option: TicketOptionView) -> TicketOptionView:
    """A current_car option with the drive and group of that car (none for "not in catalog")."""
    detail = car_detail(services, option.value)
    return option if detail is None else option.model_copy(update={"detail": detail})


# What a choice with a search box and a noted "other" says, per bound field.
_PICKERS: dict[str, dict[str, str]] = {
    OCCUPATION: {
        "search_label": "לא ברשימה? חיפוש ברשימת העיסוקים המלאה",
        "search_empty": "אין עיסוק כזה ברשימה.",
        "note_required_label": "הערה (חובה: מה העיסוק)",
        "detail_label": "הקבוצה לפי הבחירה",
    },
    CURRENT_CAR: {
        "search_label": "לא ברשימה? חיפוש בקטלוג המלא",
        "search_empty": "אין רכב כזה בקטלוג.",
        "note_required_label": "הערה (חובה: איזה רכב, ושנת הרישום אם ידועה)",
        "detail_label": "הקבוצה וההנעה לפי הבחירה",
    },
}


def _with_group(services: Services, option: TicketOptionView) -> TicketOptionView:
    """An occupation option with the group it gives (none for "other")."""
    occupation = services.ctx.occupations.get(option.value)
    if occupation is None:
        return option
    return option.model_copy(update={"detail": group_label(occupation.group)})


def _participation_label(field: TicketFieldView) -> str:
    """The amount input's label, with the car's name: "סכום ההשתתפות החודשית ב-MG4 (₪)"."""
    if field.car_name:
        return f"סכום ההשתתפות החודשית ב-{field.car_name} (₪)"
    return "סכום ההשתתפות החודשית (₪)"


def _question_part(
    ticket: Ticket, question: Mapping[str, Any]
) -> tuple[QuestionStatus, Any, str | None]:
    """(status, the raw answer, the note) of one question, from the ticket's answer so far."""
    answer = ticket.answer or {}
    part = (answer.get("questions") or {}).get(question["id"])
    if part is not None:
        return part["status"], part.get("value"), part.get("note")
    field = question.get("bound_field")
    values = answer.get("values") or {}
    if field is not None and field in values:  # answered by field (an older answer, or values)
        return "answered", values[field], None
    return "pending", None, None


def build_ticket_view(services: Services, ticket: Ticket) -> dict[str, Any]:
    """Display-ready facts for one ticket in the representative's inbox, JSON-ready: one view
    per question (`questions`, the screen renders these), and the bound ones as `fields` too."""
    views = [
        e.payload.get("view")
        for e in services.store.events_after(ticket.session_id)
        if e.type == "comparison_ready"
    ]
    latest = views[-1] if views else None

    def latest_for(car_id: str) -> Mapping[str, Any] | None:
        return next((v for v in reversed(views) if v and v["alternative_car_id"] == car_id), None)

    fields: list[TicketFieldView] = []
    questions: list[TicketQuestionView] = []
    free_prompts: list[str] = []
    for question in ticket_questions(services, ticket):
        status, raw, note = _question_part(ticket, question)
        kind = question["answer"]["type"]
        options = [TicketOptionView(**o) for o in question["answer"]["options"]]
        if kind == "yes_no":
            options = [TicketOptionView(value=v, label=lbl) for v, lbl in YES_NO_LABELS.items()]
        if is_free(question):
            prompt = question["prompt_he"]
            free_prompts.append(prompt)
            questions.append(
                TicketQuestionView(
                    id=question["id"],
                    kind="free",
                    bound_field=None,
                    type=kind,
                    title=clamp(prompt, FREE_TITLE_LENGTH),
                    prompt_he=prompt,
                    label=FREE_ANSWER_LABELS[kind],
                    options=options,
                    status=status,
                    answer=answer_label(question, raw) if status == "answered" else None,
                    note=note,
                )
            )
            continue
        name = question["bound_field"]
        search: list[TicketOptionView] = []
        if name == OCCUPATION:
            options = [_with_group(services, o) for o in options]
            search = [
                _with_group(services, TicketOptionView(value=t, label=t))
                for t in services.ctx.occupations
            ]
        if name == CURRENT_CAR:
            options = [_with_car_detail(services, o) for o in options]
            search = [
                _with_car_detail(
                    services, TicketOptionView(value=c, label=car_option_label(services, c))
                )
                for c in services.ctx.catalog
            ]
        if name == OCCUPATION and "occupation_query" in question:
            field = _occupation_field(question)
        elif name == CURRENT_CAR:
            field = _which_car_field(services, question)
        else:
            field = _ticket_field(services, ticket, name)
        car_view = (
            latest_for(field.car_id) if field.car_id and name != CURRENT_PARTICIPATION else latest
        )
        update: dict[str, Any] = {"comparison": _ticket_comparison(car_view)}
        if status == "answered":
            update |= {"answered": True, "answer": _answer_display(services, field, raw)}
        field = field.model_copy(update=update)
        fields.append(field)
        participation = name == CURRENT_PARTICIPATION or name.startswith(ALTERNATIVE_PARTICIPATION)
        questions.append(
            TicketQuestionView(
                id=question["id"],
                kind="bound",
                bound_field=name,
                type=kind,
                title=field.title,
                prompt_he=question["prompt_he"],
                label=_participation_label(field) if participation else field.label,
                options=options or field.options,
                search_options=search,
                **(
                    {**_PICKERS[name], "note_required_for": OTHER}
                    if name in NOTE_FOR_OTHER and search
                    else {}
                ),
                facts=field.facts,
                car_id=field.car_id,
                car_name=field.car_name,
                catalog_default=field.catalog_default,
                comparison=field.comparison,
                status=status,
                answer=field.answer,
                note=note,
            )
        )
    return TicketView(
        title=_ticket_title(fields, free_prompts),
        fields=fields,
        questions=questions,
        comparison=_ticket_comparison(latest),
    ).model_dump(mode="json")

"""The agent-facing tools. Each = a Pydantic input model + a handler (services, session, input).

Handlers return plain JSON. Every number they return comes from the engine (via to_api_dict) or
from the data files; no handler calculates money. Expected failures raise ToolError, which the
runner turns into {"ok": false, "error": {...}}.
"""

import logging
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from compass.data.vehicles import get_value_of_use
from compass.engine.compare import compare as engine_compare
from compass.engine.eligibility import check_eligibility as engine_eligibility
from compass.engine.eligibility import profile_warnings
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    ExternalCar,
    FamilyCar,
    MissingInputs,
    Scenario,
    Waiver,
)
from compass.engine.options import list_eligibility as engine_eligibility_list
from compass.engine.options import list_options as engine_options
from compass.engine.serialize import plain_json, to_api_dict
from compass.labels import car_details
from compass.search import SearchResult
from compass.state import Slot, SlotUpdate
from compass.tools.car_picker import grouped_catalog, offer_current_car, open_offer
from compass.tools.profile import (
    ALTERNATIVE_PARTICIPATION,
    CURRENT_CAR,
    CURRENT_PARTICIPATION,
    GROUP_EXCEPTION,
    PROFILE_FIELDS,
    REQUIRED_FIELDS,
    SLOT_OF,
    FieldError,
    alternative_participation,
    is_fillable,
    is_participation,
    profile_from_slots,
    slot_name,
    to_slot_value,
    to_tool_value,
    tool_fields,
)
from compass.tools.questions import (
    MAX_OPTION_LABEL,
    MAX_OPTIONS,
    MAX_PROMPT,
    MAX_QUESTIONS,
    OCCUPATION,
    bound_field_names,
    bound_question,
    free_question,
    group_exception_bounds,
    is_bound_field,
)
from compass.tools.services import Services
from compass.tools.view import build_view

log = logging.getLogger(__name__)

SCENARIO = TypeAdapter(Scenario)


class ToolError(Exception):
    """An expected failure: becomes {"ok": false, "error": {"code": code, **details}}."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- helpers ----------------------------------------------------------------------------------


def _candidates(result: SearchResult) -> list[dict[str, Any]]:
    return [c.model_dump(exclude={"matched"}) for c in result.candidates]


def _profile(services: Services, session_id: str):  # type: ignore[no-untyped-def]
    return profile_from_slots(services.store.slots(session_id))


def _today(services: Services, session_id: str) -> Scenario | None:
    stored = services.store.scenarios(session_id).get("today")
    return None if stored is None else SCENARIO.validate_python(stored["scenario"])


def _missing(services: Services, session_id: str, error: MissingInputs) -> ToolError:
    slots = services.store.slots(session_id)
    fields = tool_fields(error.fields)
    pending = [
        f
        for f in fields
        if f in SLOT_OF and getattr(slots.get(SLOT_OF[f]), "state", None) == "pending_rep"
    ]
    unknown = [
        f
        for f in fields
        if f in SLOT_OF and getattr(slots.get(SLOT_OF[f]), "state", None) == "unknown"
    ]
    return ToolError(
        "missing_inputs",
        "the calculation needs these inputs",
        fields=fields,
        pending_rep=pending,
        unknown=unknown,
    )


def _warnings(services: Services, session_id: str) -> list[dict[str, Any]]:
    profile = _profile(services, session_id)
    found = profile_warnings(profile, _today(services, session_id), services.ctx)
    return [{"code": w.code, "facts": plain_json(w.facts)} for w in found]


# --- 1. save_profile --------------------------------------------------------------------------


class SaveProfileInput(_Input):
    """Any subset of the employee's details. Percentages in percent (6.5 = 6.5%)."""

    display_name: str | None = Field(None, description="How to address the employee. Never an ID.")
    occupation_query: str | None = Field(None, description="The occupation in the employee's words")
    group: str | None = Field(None, description="Car eligibility group, e.g. ב")
    base_salary: Decimal | None = Field(None, description="Monthly base salary, ILS")
    commissions: Decimal | None = Field(None, description="Monthly commissions, ILS")
    bonus: Decimal | None = Field(None, description="Monthly bonus, ILS")
    pension_percent: Decimal | None = Field(None, description="Employee pension rate, percent")
    study_fund_percent: Decimal | None = Field(None, description="Employee study fund, percent")
    credit_points: Decimal | None = Field(None, description="Tax credit points (0.25 steps)")
    children_under_23: int | None = Field(
        None,
        description=(
            "Number of the employee's children who count toward this benefit (the age limit is "
            "defined in the rules). When asking the employee, either call get_rule first and "
            "quote the limit from its result, or ask in words without stating an age."
        ),
    )
    unknown_fields: list[str] = Field(
        default_factory=list, description="Fields the employee said they don't know"
    )


def save_profile(services: Services, session_id: str, data: SaveProfileInput) -> dict[str, Any]:
    ctx, store = services.ctx, services.store
    slots = store.slots(session_id)
    given = {
        f: getattr(data, f)
        for f in PROFILE_FIELDS
        if f != "occupation" and getattr(data, f, None) is not None
    }
    unknown_bad = [f for f in data.unknown_fields if f not in PROFILE_FIELDS]
    if unknown_bad:
        raise ToolError("invalid_input", "unknown field in unknown_fields", fields=unknown_bad)
    both = sorted(set(given) & set(data.unknown_fields))
    if both:
        raise ToolError("invalid_input", "a field cannot be both given and unknown", fields=both)
    if "group" in given or "group" in data.unknown_fields:
        _require_group_not_with_rep(slots)
    occupation_slot = slots.get("occupation")
    if (data.occupation_query is not None or "occupation" in data.unknown_fields) and (
        occupation_slot is not None and occupation_slot.state == "pending_rep"
    ):
        raise ToolError(
            "invalid_input",
            "a representative is reviewing the occupation; wait for the answer",
            field="occupation_query",
        )

    updates: dict[str, SlotUpdate] = {}
    errors = []
    for field, raw in given.items():
        try:
            updates[SLOT_OF[field]] = SlotUpdate(
                value=to_slot_value(field, raw, ctx), source="employee"
            )
        except FieldError as error:
            errors.append({"field": error.field, "message": str(error)})
    if errors:
        raise ToolError("invalid_input", "some values are out of range", errors=errors)
    for field in data.unknown_fields:
        updates[SLOT_OF[field]] = SlotUpdate(state="unknown", source="employee")

    occupation_error: ToolError | None = None
    if data.occupation_query is not None:
        result = services.searcher.search_occupations(data.occupation_query)
        if result.best is not None:
            occupation = ctx.occupations[result.best.id]
            updates["occupation"] = SlotUpdate(value=occupation.title, source="employee")
            stated = "group" in given or (
                "group" in slots
                and slots["group"].source != "derived"
                and slots["group"].state == "filled"
            )
            if not stated:
                updates["group"] = SlotUpdate(value=occupation.group, source="derived")
        else:
            code = "ambiguous" if result.candidates else "not_found"
            occupation_error = ToolError(
                code,
                "occupation not recognised; nothing was stored for it",
                field="occupation_query",
                query=data.occupation_query,
                candidates=_candidates(result),
            )

    store.update_slots(session_id, updates)
    slots = store.slots(session_id)
    summary = {
        "saved": {
            tool: to_tool_value(tool, slots[SLOT_OF[tool]].value)
            for tool in PROFILE_FIELDS
            if SLOT_OF[tool] in updates and updates[SLOT_OF[tool]].state == "filled"
        },
        "missing": [f for f in REQUIRED_FIELDS if SLOT_OF[f] not in slots],
        "unknown": [
            f for f in PROFILE_FIELDS if getattr(slots.get(SLOT_OF[f]), "state", None) == "unknown"
        ],
        "warnings": _warnings(services, session_id),
    }
    # The group in effect and its budget (from the rules), so the agent can state what was
    # derived ("קבוצה ב', תקציב 3,700 ₪") without another tool call.
    group = slots.get("group")
    filled = group is not None and group.state == "filled"
    summary["group"] = group.value if filled else None
    summary["group_source"] = group.source if filled else None
    summary["group_budget"] = plain_json(ctx.rules.budgets[group.value]) if filled else None
    if occupation_error is not None:  # partial success: the rest was saved
        occupation_error.details["partial_result"] = summary
        raise occupation_error
    return summary


def profile_after(services: Services, session_id: str) -> dict[str, Any]:
    """The occupation and the group in effect, with their sources and the warnings: what a
    representative's occupation or group answer left (for the rep notification)."""
    slots = services.store.slots(session_id)

    def part(field: str) -> tuple[Any, str | None]:
        slot = slots.get(field)
        if slot is None:
            return None, None
        return (slot.value if slot.state == "filled" else None), (
            slot.source if slot.state == "filled" else slot.state
        )

    occupation, occupation_source = part("occupation")
    group, group_source = part("group")
    budget = services.ctx.rules.budgets.get(group) if group is not None else None
    return {
        "occupation": occupation,
        "occupation_source": occupation_source,
        "group": group,
        "group_source": group_source,
        "group_budget": plain_json(budget),
        "warnings": _warnings(services, session_id),
    }


def today_after(services: Services, session_id: str) -> dict[str, Any]:
    """Today's situation after a current_car answer, for the rep notification: the car (its
    label and catalog id) and who said it, or None when the representative found it outside
    the catalog; with the warnings (current_car_above_group, say)."""
    stored = services.store.scenarios(session_id).get("today")
    scenario = (stored or {}).get("scenario") or {}
    return {
        "current_situation": None if stored is None else stored.get("label"),
        "car_id": scenario.get("car_id"),
        "source": None if stored is None else stored.get("source", "employee"),
        "warnings": _warnings(services, session_id),
    }


def _require_group_not_with_rep(slots: Mapping[str, Slot]) -> None:
    """Only a representative's ticket answer changes a group the representative approved, or
    one a group-exception ticket is waiting on: never the employee's words (a claimed approval
    included)."""
    group, exception = slots.get("group"), slots.get(GROUP_EXCEPTION)
    if group is not None and group.state == "filled" and group.source == "representative":
        raise ToolError(
            "invalid_input",
            "the group was approved by a representative; only a representative can change it",
            field="group",
        )
    if exception is not None and exception.state == "pending_rep":
        raise ToolError(
            "invalid_input",
            "a representative is reviewing the group (group_exception); wait for the answer",
            field="group",
        )


# --- 2. lookup_occupation ---------------------------------------------------------------------


class LookupOccupationInput(_Input):
    query: str = Field(description="The occupation in the employee's words")


def lookup_occupation(services: Services, session_id: str, data: LookupOccupationInput):  # type: ignore[no-untyped-def]
    result = services.searcher.search_occupations(data.query)
    if not result.candidates:
        raise ToolError("not_found", "no occupation matches", query=data.query)
    candidates = []
    for candidate in result.candidates:
        occupation = services.ctx.occupations[candidate.id]
        candidates.append(
            {
                **candidate.model_dump(exclude={"matched"}),
                "group": occupation.group,
                "car_mandatory": occupation.car_mandatory,
                "waiver_allowed": occupation.waiver_allowed,
                "waiver_maintenance": plain_json(occupation.waiver_maintenance),
            }
        )
    return {"confident": result.confident, "candidates": candidates}


# --- 3. lookup_vehicle ------------------------------------------------------------------------


class LookupVehicleInput(_Input):
    query: str = Field(description="The car in the employee's words, e.g. קורולה קרוס")
    registration_year: int | None = Field(None, ge=1990, le=2100)


def _tax_record(key: str):  # type: ignore[no-untyped-def]
    tax_year, registration_year, vehicle_type, manufacturer, model = key.split("-")
    return get_value_of_use(
        int(tax_year), int(registration_year), int(vehicle_type), manufacturer, model
    )


def lookup_vehicle(services: Services, session_id: str, data: LookupVehicleInput):  # type: ignore[no-untyped-def]
    result = services.searcher.search_vehicles(data.query, data.registration_year)
    if not result.candidates:
        raise ToolError("not_found", "no vehicle matches", query=data.query)
    candidates = []
    for candidate in result.candidates:
        base = candidate.model_dump(exclude={"matched"})
        if candidate.in_catalog:
            car = services.ctx.catalog[candidate.id]
            facts = {
                "group": car.group,
                "family_track": services.ctx.is_family_car(car.id),
                "drive": car.drive,
                "registration_year": car.registration_year,
                "value_of_use": plain_json(car.value_of_use),
                "default_participation": plain_json(car.default_employee_participation),
            }
        else:
            record = _tax_record(candidate.id)
            assert record is not None
            facts = {
                "group": None,
                "family_track": False,
                "drive": record.drive,
                "registration_year": record.registration_year,
                "value_of_use": plain_json(record.value_of_use),
                "default_participation": None,
            }
        candidates.append({**base, **facts})
    return {"confident": result.confident, "truncated": result.truncated, "candidates": candidates}


# --- 3b. search_catalog -----------------------------------------------------------------------


class SearchCatalogInput(_Input):
    query: str = Field(
        "",
        max_length=200,
        description="The car as the employee wrote it: part of the name, the manufacturer, or "
        "the name in Hebrew letters, with the registration year if they gave one. Empty or "
        "'all': the whole catalog grouped by manufacturer (the employee gave nothing, or does "
        "not know)",
    )


# The two choices after the catalog cars, in this order (the employee may pick either).
NOT_IN_LIST, NO_CAR = "not_in_list", "no_car"
CATALOG_EXTRA_CHOICES = (
    (NOT_IN_LIST, "הרכב שלי לא ברשימה"),
    (NO_CAR, "אין לי רכב היום"),
)


ALL_WORDS = frozenset({"all", "everything", "הכל", "הכול", "כל הרכבים", "כולם"})
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
CHECK_WITH_REP = "check_with_rep"


def search_catalog(services: Services, session_id: str, data: SearchCatalogInput):  # type: ignore[no-untyped-def]
    """The catalog cars the employee may mean, as numbered choices, then "not in the list" and
    "no car today". Never a pick: the employee chooses.

    No query, or "all": the whole catalog, grouped by manufacturer (`manufacturers`), the list
    the agent may read from; the catalog picker is on the employee's screen too. A query that
    names no catalog car also puts the picker on screen. A registration year in the query that
    differs from the matched car's year marks that car `year_differs` (the model is in the
    catalog, the year is not the employee's): the choice is then "לבדיקת נציג", never "a
    different car"."""
    ctx = services.ctx
    query = data.query.strip()
    everything = not query or query.casefold() in ALL_WORDS
    stated = _YEAR.search(query)
    stated_year = None if everything or stated is None else int(stated.group(1))
    out: dict[str, Any]
    if everything:
        groups = grouped_catalog(services)
        total = sum(len(g["cars"]) for g in groups)
        out = {"query": query, "all": True, "cars": [], "manufacturers": groups}
        first_extra = total + 1
    else:
        choices: list[dict[str, Any]] = []
        for number, candidate in enumerate(services.searcher.search_catalog(query), start=1):
            car = ctx.catalog[candidate.id]
            choice = {
                "choice": number,
                "car_id": car.id,
                "name": car.commercial_name,
                "registration_year": car.registration_year,
                "group": car.group,
                "drive": car.drive,
                "details_he": car_details(car.drive, car.group),
            }
            if stated_year is not None and stated_year != car.registration_year:
                choice["year_differs"] = True  # the model matches; the employee's year does not
            choices.append(choice)
        out = {"query": query, "cars": choices}
        if stated_year is not None:
            out["stated_year"] = stated_year
        first_extra = len(choices) + 1
    others = [
        {"choice": first_extra + i, "id": key, "label_he": label}
        for i, (key, label) in enumerate(CATALOG_EXTRA_CHOICES)
    ]
    if any(c.get("year_differs") for c in out["cars"]):
        others.append(
            {"choice": first_extra + len(others), "id": CHECK_WITH_REP, "label_he": "לבדיקת נציג"}
        )
    out["other_choices"] = others
    # The catalog picker: on screen whenever the whole catalog is asked for or nothing matched
    # (the employee's way to pick without typing); a named car keeps the numbered list.
    if everything or not out["cars"]:
        offer_current_car(services, session_id)
    out["picker_on_screen"] = open_offer(services, session_id)
    return out


# --- 4. set_current_situation -----------------------------------------------------------------


class CompanyCarToday(_Input):
    kind: Literal["company_car"]
    car_id: str = Field(
        description="Catalog id (CAR-09) or a Tax Authority key from lookup_vehicle"
    )
    registration_year: int | None = None
    participation: Decimal | None = Field(None, ge=0, description="Monthly participation, ILS")


class MaintenanceToday(_Input):
    kind: Literal["maintenance"]
    amount: Decimal = Field(gt=0, description="Monthly car maintenance paid today, ILS")


class NoCarToday(_Input):
    kind: Literal["none"]


class SetCurrentSituationInput(_Input):
    today: Annotated[CompanyCarToday | MaintenanceToday | NoCarToday, Field(discriminator="kind")]


def _today_scenario(services: Services, today: Any) -> tuple[Scenario, str]:
    ctx = services.ctx
    if isinstance(today, MaintenanceToday):
        return CurrentMaintenance(amount=today.amount), f"אחזקה {today.amount}"
    if isinstance(today, NoCarToday):
        return CurrentMaintenance(amount=Decimal(0)), "ללא רכב"
    car = ctx.catalog.get(today.car_id)
    if car is not None:
        if today.registration_year not in (None, car.registration_year):
            raise ToolError(
                "not_found",
                f"{car.commercial_name} is in the catalog as the {car.registration_year} model, "
                f"not {today.registration_year}. Do not tell the employee it is a different car: "
                "offer the catalog model and 'לבדיקת נציג' (ask_representative, bound_field "
                "current_car), or the picker on their screen",
                car_id=car.id,
            )
        cls = FamilyCar if ctx.is_family_car(car.id) else CompanyCar
        return cls(car_id=car.id, participation=today.participation), car.commercial_name
    record = _tax_record(today.car_id) if today.car_id.count("-") == 4 else None
    if record is None:
        raise ToolError("not_found", "unknown car id or vehicle key", car_id=today.car_id)
    if today.participation is None:
        raise ToolError(
            "missing_inputs",
            "a car outside the catalog has no default participation",
            fields=["participation"],
        )
    label = f"{record.commercial_name} {record.registration_year}"
    return (
        ExternalCar(
            vehicle_key=today.car_id,
            label=label,
            value_of_use=record.value_of_use,
            drive=record.drive,
            participation=today.participation,
        ),
        label,
    )


def set_current_situation(
    services: Services, session_id: str, data: SetCurrentSituationInput
) -> dict[str, Any]:
    car = services.store.slots(session_id).get(CURRENT_CAR)
    if car is not None and car.state == "pending_rep":
        raise ToolError(
            "invalid_input",
            "a representative is identifying today's car (current_car); wait for the answer",
            field="today",
        )
    source = "employee"
    if car is not None and car.state == "filled":
        # The representative identified the car: the same car again (say, with the
        # participation the employee stated) stays the representative's, whatever way the model
        # calls; another one is not the employee's to change.
        if getattr(data.today, "car_id", None) != car.value:
            raise ToolError(
                "invalid_input",
                f"a representative identified today's car as {car.value}; only a "
                "representative can change it (set it again with that car_id, e.g. with the "
                "participation the employee stated)",
                field="today",
                car_id=car.value,
            )
        source = "representative"
    payload = today_payload(services, data.today, source=source)
    services.store.set_today(session_id, payload)
    refresh_without_today(services, session_id)
    return {"today": payload, "warnings": _warnings(services, session_id)}


def today_payload(services: Services, today: Any, source: str) -> dict[str, Any]:
    """Today's situation as stored: what was given, the engine scenario, its label, and who
    said it ("employee", or "representative" for a current_car answer)."""
    scenario, label = _today_scenario(services, today)
    return {
        "input": today.model_dump(mode="json"),
        "scenario": scenario.model_dump(mode="json"),
        "label": label,
        "source": source,
    }


def representative_today(services: Services, car_id: str) -> dict[str, Any]:
    """A representative's current_car answer as today's situation: the catalog car, at its
    catalog participation unless a current_participation answer says otherwise."""
    return today_payload(
        services, CompanyCarToday(kind="company_car", car_id=car_id), source="representative"
    )


def refresh_without_today(
    services: Services, session_id: str, extra: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """What is on screen without today's car, computed again with no model call: once today
    is known (the diffs appear), or when a current_car ticket opens or is answered without a
    car (the pending chip comes and goes). The latest option set, if it was computed without
    today, is computed again (the same stated participations), and so is the latest
    comparison, if it was; each one exactly as list_options and compare compute it. `extra`
    goes into the comparison's event (the ticket that caused it). Returns the refreshed
    comparison in compare's own shape, if any."""
    return _refresh(services, session_id, extra, only_without_today=True)


def refresh_after_profile_change(
    services: Services, session_id: str, extra: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """The profile changed outside a tool call (the employee confirmed payslip values): the
    latest option set and the latest comparison, computed again with no model call, exactly as
    list_options and compare compute them. Returns the refreshed comparison in compare's own
    shape (the model may state it; the guard allows its numbers as "server"), if any."""
    return _refresh(services, session_id, extra, only_without_today=False)


def _refresh(
    services: Services,
    session_id: str,
    extra: Mapping[str, Any] | None,
    *,
    only_without_today: bool,
) -> list[dict[str, Any]]:
    events = services.store.events_after(session_id)
    sets = [e for e in events if e.type == "comparison_set_ready"]
    if sets and (not only_without_today or sets[-1].payload.get("today_unknown")):
        stated = {k: Decimal(v) for k, v in (sets[-1].payload.get("stated") or {}).items()}
        try:
            options = _engine_options(services, session_id, stated)
        except ToolError as error:  # e.g. a contribution rate the diff depends on is unknown
            log.info("option set not refreshed in %s: %s", session_id, error)
        else:
            _emit_option_set(services, session_id, options, stated)
    comparisons = [e for e in events if e.type == "comparison_ready"]
    latest = comparisons[-1] if comparisons else None
    if latest is None or (
        only_without_today and not latest.payload["comparison"].get("today_unknown")
    ):
        return []
    try:
        scenario, payload = _comparison(
            services,
            session_id,
            SCENARIO.validate_python(latest.payload["alternative"]),
            explicit=False,
        )
    except ToolError as error:
        log.info("comparison not refreshed in %s: %s", session_id, error)
        return []
    refreshed = {**payload, "origin": "server", "recomputed_from": latest.seq, **(extra or {})}
    _record_comparison(services, session_id, scenario, refreshed)
    return [{"ok": True, **payload}]


# --- 5/6. alternatives: check_eligibility and compare -----------------------------------------


class AlternativeInput(_Input):
    kind: Literal["car", "waiver"]
    car_id: str | None = Field(None, description="Catalog id, for kind = car")
    participation: Decimal | None = Field(
        None,
        ge=0,
        description=(
            "Only if the employee stated it. Omit it after a representative's answer: the "
            "answer is applied automatically"
        ),
    )
    maintenance: Decimal | None = Field(
        None,
        gt=0,
        description=(
            "Only when a representative quoted a waiver maintenance amount. Omit it otherwise: "
            "the occupation's maintenance is used automatically (do not copy it from "
            "lookup_occupation; an amount equal to the occupation's counts as the occupation's)"
        ),
    )


def _occupation_maintenance(services: Services, session_id: str) -> Decimal | None:
    title = _profile(services, session_id).occupation
    occupation = None if title is None else services.ctx.occupations.get(title)
    return None if occupation is None else occupation.waiver_maintenance


def _alternative(services: Services, session_id: str, data: AlternativeInput) -> Scenario:
    ctx = services.ctx
    if data.kind == "waiver":
        if data.car_id is not None or data.participation is not None:
            raise ToolError("invalid_input", "a waiver has no car_id or participation")
        # An amount equal to the occupation's is the occupation's: only a different amount
        # was quoted by a representative. The source must not depend on how the model calls.
        if data.maintenance is None or data.maintenance == _occupation_maintenance(
            services, session_id
        ):
            return Waiver()
        return Waiver(maintenance=data.maintenance, maintenance_source="representative")
    if data.car_id is None or data.car_id not in ctx.catalog:
        raise ToolError("not_found", "alternatives must be catalog cars", car_id=data.car_id)
    if data.maintenance is not None:
        raise ToolError("invalid_input", "a car has no maintenance")
    cls = FamilyCar if ctx.is_family_car(data.car_id) else CompanyCar
    return cls(car_id=data.car_id, participation=data.participation)


_NEEDS_INFO_FIELD = {
    "unknown_group": "group",
    "unknown_children": "children_under_23",
    "unknown_occupation": "occupation",
}


class CheckEligibilityInput(_Input):
    scenario: AlternativeInput


def check_eligibility(
    services: Services, session_id: str, data: CheckEligibilityInput
) -> dict[str, Any]:
    scenario = _alternative(services, session_id, data.scenario)
    verdict = to_api_dict(
        engine_eligibility(_profile(services, session_id), scenario, services.ctx),
        services.ctx.rules,
    )
    if verdict["status"] == "not_eligible":
        raise ToolError("not_eligible", "not eligible", **verdict)
    if verdict["status"] == "needs_info":
        raise ToolError(
            "missing_inputs",
            "eligibility needs more information",
            fields=[_NEEDS_INFO_FIELD[verdict["reason"]]],
            **verdict,
        )
    return {"eligibility": verdict}


class CompareInput(_Input):
    alternative: AlternativeInput


def _with_participation(
    scenario: Scenario, slots: Mapping[str, Slot], field: str, explicit: bool
) -> tuple[Scenario, dict[str, Any]]:
    """Apply a representative's participation answer to a car scenario.

    - explicit participation in the call wins (employee input), unless it equals the
      representative's answer: then it is that answer (the source must not depend on whether
      the model repeats the amount);
    - a filled slot (the representative answered) -> that amount, source representative;
    - an open ticket blocking it (pending_rep) -> the catalog default for now, flagged
      pending_rep, never silently final.
    """
    if not isinstance(scenario, CompanyCar | FamilyCar | ExternalCar):
        return scenario, {"field": None, "pending_rep": False, "effective_from": None}
    slot = slots.get(field)
    info: dict[str, Any] = {"field": field, "pending_rep": False, "effective_from": None}
    if slot is None:
        return scenario, info
    if explicit and not (
        slot.state == "filled" and Decimal(slot.value["amount"]) == scenario.participation
    ):
        return scenario, info
    if slot.state == "pending_rep":
        info["pending_rep"] = True
    elif slot.state == "filled":
        scenario = scenario.model_copy(
            update={
                "participation": Decimal(slot.value["amount"]),
                "participation_source": "representative",
            }
        )
        info["effective_from"] = slot.value["effective_from"]
    info["state"] = slot.state
    return scenario, info


def _today_for_engine(
    services: Services, session_id: str, slots: Mapping[str, Slot]
) -> tuple[Scenario | None, dict[str, Any]]:
    """Today with its participation resolved; None while it is not known (each alternative
    then gets its own net and no diff: a partial comparison, never a refusal)."""
    today = _today(services, session_id)
    if today is None:
        return None, {"field": None, "pending_rep": False, "effective_from": None}
    return _with_participation(today, slots, CURRENT_PARTICIPATION, explicit=False)


def compare(services: Services, session_id: str, data: CompareInput) -> dict[str, Any]:
    scenario, payload = _comparison(
        services,
        session_id,
        _alternative(services, session_id, data.alternative),
        explicit=data.alternative.participation is not None,
    )
    kind = _record_comparison(services, session_id, scenario, payload)
    if payload["comparison"]["today_unknown"]:
        offer_current_car(services, session_id)  # the screen waits for today's car
    return {"alternative_kind": kind, **payload}


def _record_comparison(
    services: Services, session_id: str, scenario: Scenario, payload: dict[str, Any]
) -> str:
    """Store the comparison and emit comparison_ready with its display-ready `view` (the event
    only: the tool result stays as it was, so the model never sees the UI's labels)."""
    alternative = scenario.model_dump(mode="json")
    view = build_view(services, session_id, alternative, payload)
    return services.store.record_comparison(session_id, alternative, {**payload, "view": view})


def _comparison(
    services: Services, session_id: str, alternative: Scenario, explicit: bool
) -> tuple[Scenario, dict[str, Any]]:
    """The compare payload for one alternative, with participation resolved from the slots."""
    ctx = services.ctx
    slots = services.store.slots(session_id)
    today, today_info = _today_for_engine(services, session_id, slots)
    car_id = getattr(alternative, "car_id", None) or ""
    scenario, alt_info = _with_participation(
        alternative, slots, alternative_participation(car_id), explicit=explicit
    )
    profile = profile_from_slots(slots)
    try:
        result = engine_compare(profile, today, scenario, ctx)
    except MissingInputs as error:
        raise _missing(services, session_id, error) from None
    eligibility = to_api_dict(engine_eligibility(profile, scenario, ctx), ctx.rules)
    alt_meta = result.alternative.metadata
    today_source = None if result.today is None else result.today.metadata.participation_source
    payload = {
        "comparison": to_api_dict(result, ctx.rules),
        "eligibility": eligibility,
        "hypothetical": eligibility["status"] != "eligible",
        "missing": tool_fields(result.missing),
        # The alternative's participation: where the amount came from, and whether a
        # representative still has to confirm it.
        "participation_source": alt_meta.participation_source,
        "pending_rep": alt_info["pending_rep"],
        "participation_effective_from": alt_info["effective_from"],
        "today_participation": {
            "source": today_source,
            "pending_rep": today_info["pending_rep"],
            "effective_from": today_info["effective_from"],
        },
    }
    return scenario, payload


# --- 7. list_options --------------------------------------------------------------------------


class ListOptionsInput(_Input):
    participation: dict[str, Annotated[Decimal, Field(ge=0)]] = Field(
        default_factory=dict,
        description="Participation the employee stated per catalog car id (ILS / month)",
    )


def list_options(services: Services, session_id: str, data: ListOptionsInput) -> dict[str, Any]:
    """Each car's participation is resolved exactly as compare() resolves it.

    Never a refusal for a missing profile input: what is unknown is marked (`partial`,
    `missing`). Unknown pension / study fund rates and an unknown today's car give a partial
    comparison per option (as compare does); when an input every net needs is unknown
    (salary, commissions, bonus, credit points) the options are listed with their eligibility
    only."""
    ctx = services.ctx
    unknown = sorted(set(data.participation) - set(ctx.catalog))
    if unknown:
        raise ToolError("not_found", "unknown catalog car id in participation", car_ids=unknown)
    infos: dict[str, dict[str, Any]] = {}
    try:
        options = _engine_options(services, session_id, data.participation, infos)
    except ToolError as error:
        if error.code != "missing_inputs":
            raise
        if _today(services, session_id) is None:
            offer_current_car(services, session_id)  # no amounts, and no car either
        return _options_without_amounts(services, session_id, error)
    listed = to_api_dict(options, ctx.rules)
    for option, data_out in zip(options, listed, strict=True):
        info = infos.get(getattr(option.scenario, "car_id", ""), {})
        data_out["participation_source"] = (
            option.comparison.alternative.metadata.participation_source
        )
        data_out["pending_rep"] = info.get("pending_rep", False)
        data_out["participation_effective_from"] = info.get("effective_from")
        # Catalog facts, so the agent can offer same-drive alternatives without lookups.
        car = ctx.catalog.get(getattr(option.scenario, "car_id", ""))
        data_out["commercial_name"] = None if car is None else car.commercial_name
        data_out["group"] = None if car is None else car.group
        data_out["drive"] = None if car is None else car.drive
    _emit_option_set(services, session_id, options, data.participation)
    if any(o.comparison.today_unknown for o in options):
        offer_current_car(services, session_id)  # the screen waits for today's car
    missing = list(dict.fromkeys(f for o in options for f in tool_fields(o.comparison.missing)))
    return {"options": listed, "partial": bool(missing), "missing": missing}


def _options_without_amounts(
    services: Services, session_id: str, error: ToolError
) -> dict[str, Any]:
    """The eligibility of every alternative and no money, for when an input every net needs
    is unknown. Nothing goes on screen."""
    ctx = services.ctx
    slots = services.store.slots(session_id)
    today, _ = _today_for_engine(services, session_id, slots)
    verdicts = engine_eligibility_list(profile_from_slots(slots), today, ctx)
    listed = []
    for scenario, verdict in verdicts:
        car = ctx.catalog.get(getattr(scenario, "car_id", ""))
        listed.append(
            {
                "scenario": plain_json(scenario),
                "eligibility": to_api_dict(verdict, ctx.rules),
                "comparison": None,  # no amounts: an input every net needs is unknown
                "commercial_name": None if car is None else car.commercial_name,
                "group": None if car is None else car.group,
                "drive": None if car is None else car.drive,
            }
        )
    return {
        "options": listed,
        "partial": True,
        "no_amounts": True,
        "missing": error.details["fields"],
    }


def _engine_options(
    services: Services,
    session_id: str,
    participation: Mapping[str, Decimal],
    infos: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """The engine's options, each car's participation resolved as compare resolves it (the
    stated amounts first). `infos` collects each car's resolution (pending, effective_from)."""
    ctx = services.ctx
    slots = services.store.slots(session_id)
    today, _ = _today_for_engine(services, session_id, slots)
    infos = {} if infos is None else infos

    def adjust(candidate: Scenario) -> Scenario:
        if not isinstance(candidate, CompanyCar | FamilyCar):
            return candidate
        stated = participation.get(candidate.car_id)
        if stated is not None:
            candidate = candidate.model_copy(
                update={"participation": stated, "participation_source": "employee_input"}
            )
        resolved, info = _with_participation(
            candidate,
            slots,
            alternative_participation(candidate.car_id),
            explicit=stated is not None,
        )
        infos[candidate.car_id] = info
        return resolved

    try:
        return engine_options(profile_from_slots(slots), today, ctx, adjust=adjust)
    except MissingInputs as error:
        raise _missing(services, session_id, error) from None


def _emit_option_set(
    services: Services, session_id: str, options: Any, stated: Mapping[str, Decimal]
) -> None:
    """Every eligible alternative, on screen: one comparison_set_ready event with each one's
    display-ready `view`, computed exactly as compare computes it (the same participation
    resolution, so pending is marked per car; the same view builder and invariants), by the
    server, with no model call. Best first (by net while today is unknown: the same order).
    Nothing is stored as a comparison: the model's own compare stays the record of what it
    compared. The event keeps the stated participations and whether today was unknown, so
    refresh_without_today can compute the same set again once today is known."""
    entries = []
    for option in options:
        if option.eligibility.status != "eligible":
            continue
        car_id = getattr(option.scenario, "car_id", None)
        scenario, payload = _comparison(
            services, session_id, option.scenario, explicit=car_id in stated
        )
        alternative = scenario.model_dump(mode="json")
        view = build_view(services, session_id, alternative, {**payload, "origin": "server"})
        entries.append({"alternative": alternative, "view": view})
    ranks = [_rank(e["view"]) for e in entries]
    if None not in ranks:  # else (no nets at all): the engine's order, which ranks them too
        entries = [e for _, e in sorted(zip(ranks, entries, strict=True), key=lambda r: -r[0])]
    services.store.append_event(
        session_id,
        "comparison_set_ready",
        {
            "origin": "server",
            "tool": "list_options",
            "options": entries,
            "stated": plain_json(dict(stated)),
            "today_unknown": any(o.comparison.today_unknown for o in options),
        },
    )


def _rank(view: Mapping[str, Any]) -> int | None:
    """A view's place in the selector: its diff, or its own net while today is unknown (None
    when both are unknown: the engine ranked the options by the net at zero rates)."""
    diff = view["display_diff"]
    return view["alternative_net"] if diff is None else diff


# --- 8. get_rule ------------------------------------------------------------------------------

RuleTopic = Literal[
    "budgets",
    "choose_from",
    "unused_budget",
    "electric_bonus",
    "family_track",
    "waiver",
    "participation",
    "value_of_use",
    "tax_tables_year",
]


class GetRuleInput(_Input):
    topic: RuleTopic


def get_rule(services: Services, session_id: str, data: GetRuleInput) -> dict[str, Any]:
    rules = services.ctx.rules
    nm = rules.net_method
    topics: dict[str, tuple[Any, str | None]] = {
        "budgets": ({"budgets": dict(rules.budgets), "group_order": list(rules.group_order)}, None),
        "choose_from": (rules.choose_from, None),
        "unused_budget": (rules.unused_budget, None),
        "electric_bonus": (rules.electric.model_dump(exclude={"note"}), rules.electric.note),
        "family_track": (rules.family_track.model_dump(exclude={"note"}), rules.family_track.note),
        "waiver": (rules.waiver.model_dump(), None),
        "participation": (nm.participation.model_dump(exclude={"note"}), nm.participation.note),
        "value_of_use": (rules.value_of_use.model_dump(exclude={"drive_field"}), None),
        "tax_tables_year": (nm.tax_year, nm.note),
    }
    value, note = topics[data.topic]
    return {
        "topic": data.topic,
        "value": plain_json(value),
        "note": note or None,
        "rules_version": rules.version,
    }


# --- 9. ask_representative --------------------------------------------------------------------


class QuickAnswer(_Input):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=200)
    values: dict[str, Any] = Field(default_factory=dict, description="Profile fields it fills")


class QuestionInput(_Input):
    """One question for the representative. Bound: set bound_field (and occupation_query for
    the occupation); the server builds the answer options. Free: set prompt_he and type (and
    options for a choice); the answer comes back to you as data and changes no value."""

    prompt_he: str | None = Field(
        None,
        max_length=MAX_PROMPT,
        description="The question in Hebrew, one sentence (required for a free question)",
    )
    bound_field: str | None = Field(
        None,
        description=(
            "Only for a value the calculation needs: current_participation, "
            "alternative_participation:<catalog car id>, group_exception, occupation or "
            "current_car"
        ),
    )
    occupation_query: str | None = Field(
        None,
        max_length=200,
        description="bound_field occupation only: the occupation in the employee's words",
    )
    car_query: str | None = Field(
        None,
        max_length=200,
        description="bound_field current_car only: today's car in the employee's words",
    )
    type: Literal["yes_no", "choice", "text"] | None = Field(
        None, description="Free questions only"
    )
    options: list[str] | None = Field(
        None, description=f"Free choice questions only: 2-{MAX_OPTIONS} option labels in Hebrew"
    )


class AskRepresentativeInput(_Input):
    question: str | None = Field(
        None,
        min_length=1,
        max_length=2000,
        description="Context for the representative: one self-contained paragraph",
    )
    questions: list[QuestionInput] = Field(
        default_factory=list,
        description=f"At most {MAX_QUESTIONS}: only what is needed (see the tool description)",
    )
    blocking_fields: list[str] = Field(
        default_factory=list,
        description="Older form of bound questions (fields that wait for the answer)",
    )
    quick_answers: list[QuickAnswer] = Field(
        default_factory=list, description="Older form; not with questions"
    )


def _invalid(message: str, **details: Any) -> ToolError:
    return ToolError("invalid_input", message, **details)


def _ticket_questions(
    services: Services, session_id: str, data: AskRepresentativeInput
) -> list[dict[str, Any]]:
    """The questions[] input, validated, with the server's schema and options for each bound
    one. English messages the model can act on."""
    if data.blocking_fields or data.quick_answers:
        raise _invalid(
            "use questions[] alone: blocking_fields and quick_answers are the older form; a "
            "bound question's answer options are built by the server"
        )
    if len(data.questions) > MAX_QUESTIONS:
        raise _invalid(
            f"at most {MAX_QUESTIONS} questions per ticket (got {len(data.questions)}); ask "
            "only what the employee asked or what the next calculation strictly needs",
            max_questions=MAX_QUESTIONS,
        )
    ctx = services.ctx
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, q in enumerate(data.questions, start=1):
        qid, where = f"q{i}", f"questions[{i - 1}]"
        prompt = (q.prompt_he or "").strip() or None
        if q.bound_field is not None:
            field = q.bound_field
            if not is_bound_field(field, ctx):
                raise _invalid(
                    f"{where}: unknown bound_field {field!r}; bound fields are "
                    f"{bound_field_names()} (a catalog car id, e.g. CAR-10). For anything "
                    "else ask a free question (no bound_field, with prompt_he and type)",
                    question=i - 1,
                )
            if q.type is not None or q.options is not None:
                raise _invalid(
                    f"{where}: a bound question takes no type or options; the server builds "
                    f"the answer options for {field}. Remove type and options",
                    question=i - 1,
                )
            if field in seen:
                raise _invalid(f"{where}: {field} is asked twice", question=i - 1)
            seen.add(field)
            if field == OCCUPATION and not (q.occupation_query or "").strip():
                raise _invalid(
                    f"{where}: an occupation question needs occupation_query (the occupation "
                    "in the employee's words); the representative picks from the closest "
                    "titles in the occupations table",
                    question=i - 1,
                )
            if field != OCCUPATION and q.occupation_query is not None:
                raise _invalid(
                    f"{where}: occupation_query is for bound_field occupation only",
                    question=i - 1,
                )
            if field != CURRENT_CAR and q.car_query is not None:
                raise _invalid(
                    f"{where}: car_query is for bound_field current_car only", question=i - 1
                )
            if field == CURRENT_CAR:
                _check_current_car_question(services, session_id, where, i - 1, q.car_query)
            out.append(
                bound_question(
                    services,
                    session_id,
                    field,
                    qid=qid,
                    prompt_he=prompt,
                    occupation_query=None
                    if q.occupation_query is None
                    else q.occupation_query.strip(),
                    car_query=None if q.car_query is None else q.car_query.strip(),
                )
            )
            continue
        if q.occupation_query is not None:
            raise _invalid(
                f"{where}: occupation_query needs bound_field occupation", question=i - 1
            )
        if q.car_query is not None:
            raise _invalid(f"{where}: car_query needs bound_field current_car", question=i - 1)
        if prompt is None:
            raise _invalid(
                f"{where}: a free question needs prompt_he (the question, in Hebrew)",
                question=i - 1,
            )
        if q.type is None:
            raise _invalid(
                f"{where}: a free question needs type: yes_no, choice or text", question=i - 1
            )
        labels = [label.strip() for label in q.options or []]
        if q.type == "choice":
            if not 2 <= len(labels) <= MAX_OPTIONS or not all(labels):
                raise _invalid(
                    f"{where}: a choice needs 2-{MAX_OPTIONS} non-empty option labels",
                    question=i - 1,
                )
            if len(set(labels)) != len(labels) or max(map(len, labels)) > MAX_OPTION_LABEL:
                raise _invalid(
                    f"{where}: option labels must be unique, at most {MAX_OPTION_LABEL} "
                    "characters each",
                    question=i - 1,
                )
        elif q.options is not None:
            raise _invalid(f"{where}: options are for type choice only", question=i - 1)
        out.append(free_question(qid, prompt, q.type, labels))
    return out


def _check_current_car_question(
    services: Services, session_id: str, where: str, index: int, car_query: str | None
) -> None:
    """Which car the employee has today: only while it is not recorded (the employee could not
    name it), with the employee's words for the representative's list."""
    if not (car_query or "").strip():
        raise _invalid(
            f"{where}: a current_car question needs car_query (today's car in the employee's "
            "words, as they wrote it); the representative picks from the catalog",
            question=index,
        )
    if services.store.scenarios(session_id).get("today") is not None:
        raise _invalid(
            f"{where}: today's situation is already recorded; ask current_car only when the "
            "employee cannot identify today's car",
            question=index,
        )


def _check_group_question(services: Services, session_id: str, fields: list[str]) -> None:
    """The group derives from the occupation: a ticket may ask about it (group_exception, or the
    older `group` field) only when the occupation is known (not unknown, not pending, not asked
    in the same ticket) and today's car is above the occupation's group."""
    asked = [f for f in fields if f in (GROUP_EXCEPTION, "group")]
    if not asked:
        return
    occupation = services.store.slots(session_id).get("occupation")
    if OCCUPATION in fields or occupation is None or occupation.state != "filled":
        raise _invalid(
            f"{asked[0]}: the group derives from the occupation, which is not known yet. Do "
            "not ask about the group: ask about the occupation (bound_field occupation) if "
            "needed; the group follows from the representative's answer",
            fields=asked,
        )
    base, car_group = group_exception_bounds(services, session_id)
    order = list(services.ctx.rules.group_order)
    if car_group is None or base not in order or order.index(car_group) <= order.index(base):
        raise _invalid(
            f"{asked[0]}: only when today's car is above the occupation's group ({base}); "
            f"today's car is {'in group ' + car_group if car_group else 'not a catalog car'}. "
            "Do not ask the representative about the group",
            fields=asked,
        )


def ask_representative(
    services: Services, session_id: str, data: AskRepresentativeInput
) -> dict[str, Any]:
    ctx, store = services.ctx, services.store
    questions: list[dict[str, Any]] = []
    if data.questions:
        questions = _ticket_questions(services, session_id, data)
        blocking = [q["bound_field"] for q in questions if q["bound_field"] is not None]
        question = data.question or " / ".join(
            q["prompt_he"] or q["bound_field"] for q in questions
        )
    else:
        if data.question is None:
            raise _invalid("give questions[] (or the older question with blocking_fields)")
        blocking, question = data.blocking_fields, data.question
        bad = [f for f in blocking if not is_fillable(f, ctx)]
        if bad:
            raise _invalid(
                "blocking_fields must be profile fields, current_participation, group_exception "
                "or alternative_participation:<catalog car id>",
                fields=bad,
            )
    _check_group_question(services, session_id, blocking)
    _check_ticket_cars(services, session_id, blocking)
    if len(blocking) > MAX_QUESTIONS:
        raise _invalid(
            f"at most {MAX_QUESTIONS} blocking_fields per ticket (got {len(blocking)}); ask "
            "only what the employee asked or what the next calculation strictly needs",
            fields=blocking,
        )
    ids = [qa.id for qa in data.quick_answers]
    if len(ids) != len(set(ids)):
        raise ToolError("invalid_input", "quick answer ids must be unique")
    for qa in data.quick_answers:
        for field, raw in qa.values.items():
            if field not in blocking:
                raise ToolError(
                    "invalid_input",
                    "quick answer fills a non-blocking field",
                    quick_answer=qa.id,
                    field=field,
                )
            try:
                to_slot_value(field, raw, ctx)
            except FieldError as error:
                raise ToolError("invalid_input", str(error), quick_answer=qa.id) from None

    slots = store.slots(session_id)

    def filled(field: str) -> Any:
        slot = slots.get(SLOT_OF[field])
        return slot.value if slot is not None and slot.state == "filled" else None

    scenarios = store.scenarios(session_id)
    alternatives = [k for k in scenarios if k.startswith("alternative:")]
    context = {
        "display_name": filled("display_name"),
        "occupation": filled("occupation"),
        "group": filled("group"),
        "current_situation": scenarios.get("today", {}).get("label"),
        "requested_alternative": scenarios[max(alternatives, key=lambda k: int(k.split(":")[1]))]
        if alternatives
        else None,
    }
    ticket = store.open_ticket(
        session_id,
        question,
        context,
        blocking,  # tool field names: what the representative sees
        [qa.model_dump() for qa in data.quick_answers],
        pending_slots=[slot_name(f) for f in blocking],
        questions=questions,
    )
    _recompute_as_pending(services, session_id, ticket.id, blocking)
    if CURRENT_CAR in blocking:  # what is on screen without today's car now waits for it
        refresh_without_today(
            services, session_id, {"ticket_id": ticket.id, "pending_field": CURRENT_CAR}
        )
    provisional = _provisional_comparisons(services, session_id, ticket.id, blocking)
    result: dict[str, Any] = {"ticket_id": ticket.id, "status": ticket.status, "context": context}
    if questions:
        # what was asked: ids, and the options the server built (never the model's)
        result["questions"] = [
            {
                "id": q["id"],
                "bound_field": q["bound_field"],
                "type": q["answer"]["type"],
                "options": [o["label"] for o in q["answer"]["options"]],
            }
            for q in questions
        ]
    if provisional:
        # what compare would have returned: the model may state it (pending) without calling
        # compare, and the guard allows its numbers (they are in this tool result)
        result["provisional_comparisons"] = provisional
    return result


MAX_TICKET_CARS = 3


def _check_ticket_cars(services: Services, session_id: str, fields: list[str]) -> None:
    """A ticket asks about the cars the employee is actually considering: at most
    MAX_TICKET_CARS alternative participations, each for a car this session compared or the
    employee named in a message."""
    cars = [
        f.removeprefix(ALTERNATIVE_PARTICIPATION)
        for f in fields
        if f.startswith(ALTERNATIVE_PARTICIPATION)
    ]
    if len(cars) > MAX_TICKET_CARS:
        raise ToolError(
            "invalid_input",
            f"a ticket may ask about at most {MAX_TICKET_CARS} cars' participation (got "
            f"{len(cars)}); ask the representative only about the cars the employee is "
            "actually considering, or ask the employee which ones they mean",
            max_cars=MAX_TICKET_CARS,
            fields=[alternative_participation(c) for c in cars],
        )
    store = services.store
    compared = {
        e.payload["alternative"].get("car_id")
        for e in store.events_after(session_id)
        if e.type == "comparison_ready"
    }
    named: set[str] = set()
    for message in store.messages(session_id):
        if message.role == "user":
            named |= services.searcher.cars_named_in(message.content.get("text", ""))
    unknown = [c for c in cars if c not in compared and c not in named]
    if unknown:
        names = ", ".join(f"{c} ({services.ctx.catalog[c].commercial_name})" for c in unknown)
        raise ToolError(
            "invalid_input",
            f"participation can be asked only for cars the employee named or that were "
            f"compared in this conversation; not for {names}. Ask the representative only "
            "about the cars the employee is actually considering, or ask the employee first",
            fields=[alternative_participation(c) for c in unknown],
        )


def _provisional_comparisons(
    services: Services, session_id: str, ticket_id: str, fields: list[str]
) -> list[dict[str, Any]]:
    """A ticket for a car's participation, and no comparison of that car yet: compute one now
    (the current profile and situation, the catalog default for the participation, no model
    call) and emit it as a server comparison_ready, pending. The rep's answer then settles it
    (settle_answered), whatever the model does in between. Returns each one as compare returns
    it. Missing inputs: nothing is emitted (logged); the model asks for them as usual."""
    compared = {
        e.payload["alternative"].get("car_id")
        for e in services.store.events_after(session_id)
        if e.type == "comparison_ready"
    }
    results: list[dict[str, Any]] = []
    for field in fields:
        if not field.startswith(ALTERNATIVE_PARTICIPATION):
            continue
        car_id = field.removeprefix(ALTERNATIVE_PARTICIPATION)
        if car_id in compared:
            continue  # shown already: _recompute_as_pending marks it pending if needed
        try:
            alternative = _alternative(
                services, session_id, AlternativeInput(kind="car", car_id=car_id)
            )
            scenario, payload = _comparison(services, session_id, alternative, explicit=False)
        except ToolError as error:
            log.info("no provisional comparison for %s in %s: %s", car_id, session_id, error)
            continue
        if payload["missing"]:
            log.info(
                "no provisional comparison for %s in %s: missing %s",
                car_id,
                session_id,
                payload["missing"],
            )
            continue
        kind = _record_comparison(
            services,
            session_id,
            scenario,
            {**payload, "origin": "server", "ticket_id": ticket_id, "pending_field": field},
        )
        compared.add(car_id)
        results.append({"ok": True, "alternative_kind": kind, **payload})
    return results


# Bound fields every comparison uses (the group in effect, eligibility, warnings, the waiver's
# maintenance): a ticket on one of them affects the latest comparison, whatever it compared.
_EVERY_COMPARISON = (GROUP_EXCEPTION, "occupation")


def _uses_catalog_default(payload: Mapping[str, Any], field: str) -> bool | None:
    """Whether this comparison used `field` at the catalog default (None: it didn't use it).
    A group exception or the occupation: every comparison used it."""
    if field in _EVERY_COMPARISON:
        return True
    if field == CURRENT_PARTICIPATION:
        return payload["today_participation"]["source"] == "catalog_default"
    if payload["alternative"].get("car_id") != field.removeprefix(ALTERNATIVE_PARTICIPATION):
        return None
    return payload["participation_source"] == "catalog_default"


def _recompute_as_pending(
    services: Services, session_id: str, ticket_id: str, fields: list[str]
) -> None:
    """A comparison shown at a catalog default must not stay final once a ticket asks for that
    participation, whatever order the model called the tools in. Recompute the latest
    comparison that used the field (same alternative, no model call) and append it as a
    server-emitted comparison_ready with pending_rep. compare's own result is unchanged."""
    _recompute_latest(
        services, session_id, ticket_id, fields, _uses_catalog_default, "pending_field"
    )


def _uses_pending(payload: Mapping[str, Any], field: str) -> bool | None:
    """Whether this comparison waited for `field` (None: it didn't use it)."""
    if field in _EVERY_COMPARISON:
        return field in payload.get("view", {}).get("pending_fields", [])
    if field == CURRENT_PARTICIPATION:
        return bool(payload["today_participation"]["pending_rep"])
    if payload["alternative"].get("car_id") != field.removeprefix(ALTERNATIVE_PARTICIPATION):
        return None
    return bool(payload["pending_rep"])


def settle_answered(services: Services, session_id: str, ticket_id: str, fields: list[str]) -> None:
    """The representative answered: the comparison that waited for the answer must turn final
    without depending on the model calling compare again. Recompute the latest comparison that
    used each answered field, if it was pending (same alternative, the answer now in the slot,
    no model call), and append it as a server-emitted comparison_ready. A later compare by the
    model gives the same numbers."""
    _recompute_latest(services, session_id, ticket_id, fields, _uses_pending, "answered_field")


# Keys a server-emitted comparison_ready adds to compare's own result.
_EVENT_ONLY = frozenset(
    {
        "alternative",
        "view",
        "origin",
        "recomputed_from",
        "ticket_id",
        "pending_field",
        "answered_field",
    }
)


def settled_compare_results(
    services: Services, session_id: str, ticket_id: str, fields: list[str] | None = None
) -> list[dict[str, Any]]:
    """The comparisons the server settled when `ticket_id` was answered (only those settled by
    `fields`, one part of a partial answer, when given), each in the exact shape compare
    returns (what the model would have got by calling compare itself)."""
    return [
        {"ok": True, **{k: v for k, v in e.payload.items() if k not in _EVENT_ONLY}}
        for e in services.store.events_after(session_id)
        if e.type == "comparison_ready"
        and e.payload.get("origin") == "server"
        and e.payload.get("ticket_id") == ticket_id
        and "answered_field" in e.payload
        and (fields is None or e.payload["answered_field"] in fields)
    ]


def _recompute_latest(
    services: Services,
    session_id: str,
    ticket_id: str,
    fields: list[str],
    needs_recompute: Callable[[Mapping[str, Any], str], bool | None],
    field_key: str,
) -> None:
    comparisons = [
        e for e in services.store.events_after(session_id) if e.type == "comparison_ready"
    ]
    targets: dict[int, str] = {}  # event seq -> the field it concerns
    for field in fields:
        if not (is_participation(field) or field in _EVERY_COMPARISON):
            continue
        for event in reversed(comparisons):  # the latest comparison that used the field
            used = needs_recompute(event.payload, field)
            if used is not None:
                if used:
                    targets.setdefault(event.seq, field)
                break
    for seq, field in sorted(targets.items()):
        event = next(e for e in comparisons if e.seq == seq)
        try:
            scenario, payload = _comparison(
                services,
                session_id,
                SCENARIO.validate_python(event.payload["alternative"]),
                explicit=False,
            )
        except ToolError:  # the profile changed since and no longer computes: nothing to redo
            continue
        _record_comparison(
            services,
            session_id,
            scenario,
            {
                **payload,
                "origin": "server",
                "recomputed_from": seq,
                "ticket_id": ticket_id,
                field_key: field,
            },
        )

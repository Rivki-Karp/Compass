"""The agent-facing tools. Each = a Pydantic input model + a handler (services, session, input).

Handlers return plain JSON. Every number they return comes from the engine (via to_api_dict) or
from the data files; no handler calculates money. Expected failures raise ToolError, which the
runner turns into {"ok": false, "error": {...}}.
"""

from collections.abc import Mapping
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
from compass.engine.options import list_options as engine_options
from compass.engine.serialize import plain_json, to_api_dict
from compass.search import SearchResult
from compass.state import Slot, SlotUpdate
from compass.tools.profile import (
    CURRENT_PARTICIPATION,
    PAYSLIP_FIELDS,
    PROFILE_FIELDS,
    REQUIRED_FIELDS,
    SLOT_OF,
    FieldError,
    alternative_participation,
    is_fillable,
    profile_from_slots,
    slot_name,
    to_slot_value,
    to_tool_value,
    tool_fields,
)
from compass.tools.services import Services

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
    children_under_23: int | None = Field(None, description="Children under 23")
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
    summary["payslip_fields_unknown"] = [f for f in PAYSLIP_FIELDS if f in summary["unknown"]]
    if occupation_error is not None:  # partial success: the rest was saved
        occupation_error.details["partial_result"] = summary
        raise occupation_error
    return summary


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
                f"{car.id} is the {car.registration_year} model; look up the "
                f"{today.registration_year} model with lookup_vehicle",
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
    scenario, label = _today_scenario(services, data.today)
    payload = {
        "input": data.today.model_dump(mode="json"),
        "scenario": scenario.model_dump(mode="json"),
        "label": label,
    }
    services.store.set_today(session_id, payload)
    return {"today": payload, "warnings": _warnings(services, session_id)}


# --- 5/6. alternatives: check_eligibility and compare -----------------------------------------


class AlternativeInput(_Input):
    kind: Literal["car", "waiver"]
    car_id: str | None = Field(None, description="Catalog id, for kind = car")
    participation: Decimal | None = Field(
        None, ge=0, description="Only if the employee or a representative stated it"
    )
    maintenance: Decimal | None = Field(
        None, gt=0, description="Waiver maintenance quoted by a representative"
    )


def _alternative(services: Services, data: AlternativeInput) -> Scenario:
    ctx = services.ctx
    if data.kind == "waiver":
        if data.car_id is not None or data.participation is not None:
            raise ToolError("invalid_input", "a waiver has no car_id or participation")
        if data.maintenance is None:
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
    scenario = _alternative(services, data.scenario)
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

    - explicit participation in the call wins (employee input);
    - a filled slot (the representative answered) -> that amount, source representative;
    - an open ticket blocking it (pending_rep) -> the catalog default for now, flagged
      pending_rep, never silently final.
    """
    if not isinstance(scenario, CompanyCar | FamilyCar | ExternalCar):
        return scenario, {"field": None, "pending_rep": False, "effective_from": None}
    slot = slots.get(field)
    info: dict[str, Any] = {"field": field, "pending_rep": False, "effective_from": None}
    if explicit or slot is None:
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
) -> tuple[Scenario, dict[str, Any]]:
    today = _today(services, session_id)
    if today is None:
        raise ToolError(
            "missing_inputs", "set the current situation first", fields=["current_situation"]
        )
    return _with_participation(today, slots, CURRENT_PARTICIPATION, explicit=False)


def compare(services: Services, session_id: str, data: CompareInput) -> dict[str, Any]:
    ctx = services.ctx
    slots = services.store.slots(session_id)
    today, today_info = _today_for_engine(services, session_id, slots)
    scenario, alt_info = _with_participation(
        _alternative(services, data.alternative),
        slots,
        alternative_participation(data.alternative.car_id or ""),
        explicit=data.alternative.participation is not None,
    )
    profile = profile_from_slots(slots)
    try:
        result = engine_compare(profile, today, scenario, ctx)
    except MissingInputs as error:
        raise _missing(services, session_id, error) from None
    eligibility = to_api_dict(engine_eligibility(profile, scenario, ctx), ctx.rules)
    today_meta, alt_meta = result.today.metadata, result.alternative.metadata
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
            "source": today_meta.participation_source,
            "pending_rep": today_info["pending_rep"],
            "effective_from": today_info["effective_from"],
        },
    }
    kind = services.store.record_comparison(session_id, scenario.model_dump(mode="json"), payload)
    return {"alternative_kind": kind, **payload}


# --- 7. list_options --------------------------------------------------------------------------


class ListOptionsInput(_Input):
    pass


def list_options(services: Services, session_id: str, data: ListOptionsInput) -> dict[str, Any]:
    slots = services.store.slots(session_id)
    today, _ = _today_for_engine(services, session_id, slots)
    try:
        options = engine_options(profile_from_slots(slots), today, services.ctx)
    except MissingInputs as error:
        raise _missing(services, session_id, error) from None
    return {"options": to_api_dict(options, services.ctx.rules)}


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


class AskRepresentativeInput(_Input):
    question: str = Field(min_length=1, max_length=2000)
    blocking_fields: list[str] = Field(description="Profile fields that wait for the answer")
    quick_answers: list[QuickAnswer] = Field(default_factory=list)


def ask_representative(
    services: Services, session_id: str, data: AskRepresentativeInput
) -> dict[str, Any]:
    ctx, store = services.ctx, services.store
    bad = [f for f in data.blocking_fields if not is_fillable(f, ctx)]
    if bad:
        raise ToolError(
            "invalid_input",
            "blocking_fields must be profile fields, current_participation or "
            "alternative_participation:<catalog car id>",
            fields=bad,
        )
    ids = [qa.id for qa in data.quick_answers]
    if len(ids) != len(set(ids)):
        raise ToolError("invalid_input", "quick answer ids must be unique")
    for qa in data.quick_answers:
        for field, raw in qa.values.items():
            if field not in data.blocking_fields:
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
        data.question,
        context,
        data.blocking_fields,  # tool field names: what the representative sees
        [qa.model_dump() for qa in data.quick_answers],
        pending_slots=[slot_name(f) for f in data.blocking_fields],
    )
    return {"ticket_id": ticket.id, "status": ticket.status, "context": context}

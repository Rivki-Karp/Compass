"""Tool registry (Anthropic tool definitions) and the runner that never raises.

    runner = ToolRunner(services)
    runner.run(session_id, "compare", {"alternative": {"kind": "waiver"}})
    -> {"ok": true, ...}  or  {"ok": false, "error": {"code": ..., "message": ..., ...}}

Error codes: invalid_input, missing_inputs (fields), not_found, ambiguous (candidates),
not_eligible (reason), internal_error (a bug: logged, never shown as a number).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from compass.engine.models import MissingInputs
from compass.state import NotFound, StateError
from compass.tools import handlers as h
from compass.tools.profile import tool_fields
from compass.tools.services import Services

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Services, str, Any], dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        """Anthropic tool definition."""
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        schema.pop("description", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


TOOLS: tuple[Tool, ...] = (
    Tool(
        "save_profile",
        "Save any of the employee's details they stated (percentages in percent: 6.5 = 6.5%). "
        "List fields they said they don't know in unknown_fields. An occupation in their words "
        "goes in occupation_query; if recognised it also sets the group (unless they stated "
        "one). Returns what was saved, what is still missing, unknown fields, warnings, and "
        "group / group_source / group_budget (state the derived group and budget to the "
        "employee). Save only what the employee actually said: never guess or assume a value "
        "(a 'no' to commissions or bonus is 0; 'I don't know' goes in unknown_fields). Never "
        "ask for an ID number. There is no document upload: never offer one.",
        h.SaveProfileInput,
        h.save_profile,
    ),
    Tool(
        "lookup_occupation",
        "Find an occupation by the employee's description. Returns candidates with their group, "
        "whether a car is mandatory and whether a waiver (with maintenance) is allowed. "
        "If not confident, ask the employee to choose; never guess.",
        h.LookupOccupationInput,
        h.lookup_occupation,
    ),
    Tool(
        "lookup_vehicle",
        "Find a car by the employee's description (Hebrew or English, typos ok), optionally "
        "with its registration year. Catalog cars first; otherwise Tax Authority records "
        "(in_catalog=false). Returns group, drive, value of use and default participation. "
        "If not confident, ask the employee to choose; never guess.",
        h.LookupVehicleInput,
        h.lookup_vehicle,
    ),
    Tool(
        "set_current_situation",
        "Record what the employee has today: a company car (catalog id or a Tax Authority key "
        "from lookup_vehicle, with their participation), a maintenance payment, or none. "
        "A catalog id with a different registration year is a different vehicle (not_found: "
        "look it up with the year). Returns warnings such as current_car_above_group: raise "
        "them with the employee as a question, never resolve them by assumption.",
        h.SetCurrentSituationInput,
        h.set_current_situation,
    ),
    Tool(
        "check_eligibility",
        "Check whether the employee may choose an alternative (a catalog car or a waiver). "
        "Fails with not_eligible (and the reason) or missing_inputs.",
        h.CheckEligibilityInput,
        h.check_eligibility,
    ),
    Tool(
        "compare",
        "Calculate the monthly net today vs an alternative with the deterministic engine. "
        "The only source of net-salary numbers: quote its display values exactly, never "
        "compute, round or estimate. An ineligible alternative is still calculated and marked "
        "hypothetical (say it is conditional on approval). pending_rep: true means the "
        "participation is the catalog default until the representative confirms it. With "
        "unknown pension/study-fund rates the diff may still be known (partial: nets null).",
        h.CompareInput,
        h.compare,
    ),
    Tool(
        "list_options",
        "Every alternative (all catalog cars and the waiver if allowed) with its eligibility, "
        "net diff vs today and the car's name, group and drive, best eligible first. Use it to "
        "offer eligible alternatives of the same drive type. Quote only its display values.",
        h.ListOptionsInput,
        h.list_options,
    ),
    Tool(
        "get_rule",
        "Look up a business rule (value + the official Hebrew note) to explain it. Topics: "
        "budgets, choose_from, unused_budget, electric_bonus, family_track, waiver, "
        "participation, value_of_use, tax_tables_year.",
        h.GetRuleInput,
        h.get_rule,
    ),
    Tool(
        "ask_representative",
        "Open a ticket for a human representative, only for what only the company knows: the "
        "participation for a new car, group disputes, exceptions, policy questions. Ask the "
        "employee first. Write the question as one self-contained sentence. blocking_fields "
        "wait for the answer: profile fields, current_participation, group_exception, or "
        "alternative_participation:<catalog car id> (e.g. alternative_participation:CAR-10); "
        "quick_answers are one-click answers that fill them. group_exception: whether the "
        "employee is approved for a group above their occupation's group (when today's car "
        "is above it, or the employee says they have a special approval); the representative "
        "answers with the approved group or not_approved, and only that answer changes the "
        "group. One ticket may block on several fields: when both today's participation and "
        "the group approval are unknown, open one ticket with current_participation and "
        "group_exception.",
        h.AskRepresentativeInput,
        h.ask_representative,
    ),
)

REGISTRY: dict[str, Tool] = {tool.name: tool for tool in TOOLS}


def tool_definitions() -> list[dict[str, Any]]:
    return [tool.definition() for tool in TOOLS]


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, **details}}


class ToolRunner:
    def __init__(self, services: Services) -> None:
        self.services = services

    def run(self, session_id: str, name: str, raw_input: Any) -> dict[str, Any]:
        """Validate, execute and persist. Never raises."""
        tool = REGISTRY.get(name)
        if tool is None:
            return _error("not_found", f"unknown tool {name!r}", tools=sorted(REGISTRY))
        try:
            self.services.store.session_status(session_id)
            data = tool.input_model.model_validate(raw_input if raw_input is not None else {})
            return {"ok": True, **tool.handler(self.services.pinned(), session_id, data)}
        except ValidationError as error:
            details = [
                {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                for e in error.errors()
            ]
            return _error(
                "invalid_input", "the input does not match the tool schema", errors=details
            )
        except h.ToolError as error:
            return _error(error.code, error.message, **error.details)
        except MissingInputs as error:
            return _error("missing_inputs", str(error), fields=tool_fields(error.fields))
        except NotFound as error:
            return _error("not_found", str(error))
        except StateError as error:
            return _error("invalid_input", str(error))
        except Exception:  # a bug: never crash the agent loop, never invent a number
            log.exception("tool %s failed", name)
            return _error("internal_error", f"tool {name} failed unexpectedly")

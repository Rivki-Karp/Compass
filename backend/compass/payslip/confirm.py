"""The employee confirms a pending candidate: the accepted fields become profile values.

    unchanged value   source "payslip" (the chip "לפי התלוש"); a pension or study fund percent
                      the server derived from the printed amount and wage counts as the
                      payslip's, like a printed one
    edited value      source "employee" (the employee typed it; "אין" = 0 for commissions or a
                      bonus the payslip does not show is the employee's answer)
    left out          rejected: nothing changes

Precedence: a value a representative set is never overwritten, and a field a representative is
being asked about is left alone; a payslip value replaces an earlier employee value. Only the
six salary fields are slots; a payslip never sets occupation, group, a group exception, today's
car or any ticket answer (those names are refused). The values go through the slots' own
validation (compass.tools.profile.to_slot_value) and the existing recompute path; nothing here
calculates money.

car_benefit_value is no slot: when it equals exactly one catalog car's value of use, the result
carries that car as a hint the agent may ask the employee to confirm (the existing current-car
flow). No unique match: no hint, never a guess.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from compass.payslip.schema import (
    PROFILE_FIELD_OF,
    CandidateField,
    PayslipCandidate,
    derived_name,
)
from compass.payslip.upload import PayslipRejected
from compass.state import SlotUpdate
from compass.tools.handlers import refresh_after_profile_change
from compass.tools.profile import SLOT_OF, FieldError, to_slot_value, to_tool_value
from compass.tools.services import Services

CONFIRMABLE: tuple[str, ...] = (*PROFILE_FIELD_OF, "car_benefit_value")


@dataclass(frozen=True)
class Confirmed:
    # tool field -> {"value": tool units, "source": "payslip" | "employee"}
    applied: dict[str, dict[str, Any]] = field(default_factory=dict)
    kept_representative: list[str] = field(default_factory=list)
    waiting_for_rep: list[str] = field(default_factory=list)
    car_hint: dict[str, str] | None = None
    comparisons: list[dict[str, Any]] = field(default_factory=list)  # compare's own shape
    # The salary fields that did NOT become values, so the agent can say why instead of "I have
    # no access to the payslip": the payslip does not show them, they were printed but could not
    # be read as a valid number, or the employee removed a value that was read.
    not_in_payslip: list[str] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)
    removed_by_employee: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "kept_representative": self.kept_representative,
            "waiting_for_rep": self.waiting_for_rep,
            "car_hint": self.car_hint,
            "not_in_payslip": self.not_in_payslip,
            "unreadable": self.unreadable,
            "removed_by_employee": self.removed_by_employee,
        }


def pending_candidate(services: Services, session_id: str) -> tuple[int, PayslipCandidate] | None:
    """The latest payslip_extracted not yet confirmed (its seq and the candidate), or None."""
    pending: tuple[int, PayslipCandidate] | None = None
    for event in services.store.events_after(session_id):
        if event.type == "payslip_extracted":
            fields = {n: CandidateField(**f) for n, f in event.payload["fields"].items()}
            pending = (event.seq, PayslipCandidate(fields, event.payload["dropped_keys"]))
        elif event.type == "payslip_confirmed":
            pending = None
    return pending


def _same(raw: Any, candidate: CandidateField | None) -> bool:
    if candidate is None or candidate.value is None or isinstance(raw, bool):
        return False
    try:
        return Decimal(str(raw).replace(",", "").strip()) == Decimal(candidate.value)
    except InvalidOperation:
        return False


def _payslip_value(candidate: PayslipCandidate, name: str, raw: Any) -> str | None:
    """The candidate's value the employee left unchanged (the printed percent or the derived
    one), as the string the slot validation takes; None when `raw` is neither."""
    for key in (name, derived_name(name)):
        field = candidate.fields.get(key)
        if _same(raw, field):
            return field.value if field is not None else None
    return None


def _not_applied(candidate: PayslipCandidate, accepted: set[str]) -> dict[str, list[str]]:
    """Why each salary field the employee did not accept has no value from this payslip."""
    out: dict[str, list[str]] = {"not_in_payslip": [], "unreadable": [], "removed": []}
    for name in PROFILE_FIELD_OF:
        if name in accepted:
            continue
        readings = [candidate.fields.get(k) for k in (name, derived_name(name))]
        if any(f is not None and f.value is not None for f in readings):
            out["removed"].append(name)
        elif any(f is not None and f.flag is not None for f in readings):
            out["unreadable"].append(name)
        else:
            out["not_in_payslip"].append(name)
    return out


def car_hint(services: Services, value: Any) -> dict[str, str] | None:
    """The one catalog car whose value of use is exactly `value`, or None."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    matches = [c for c in services.ctx.catalog.values() if Decimal(c.value_of_use) == amount]
    if len(matches) != 1:
        return None
    return {"car_id": matches[0].id, "commercial_name": matches[0].commercial_name}


def confirm(services: Services, session_id: str, accepted: dict[str, Any]) -> Confirmed:
    """Apply the accepted fields (see the module docstring). Raises PayslipRejected."""
    pending = pending_candidate(services, session_id)
    if pending is None:
        raise PayslipRejected(409, "payslip_nothing_pending")
    seq, candidate = pending
    refused = sorted(set(accepted) - set(CONFIRMABLE))
    if refused:
        raise PayslipRejected(422, "payslip_field_not_allowed", fields=refused)

    store, ctx = services.store, services.ctx
    slots = store.slots(session_id)
    updates: dict[str, SlotUpdate] = {}
    applied: dict[str, dict[str, Any]] = {}
    kept: list[str] = []
    waiting: list[str] = []
    invalid: list[str] = []
    for name, raw in accepted.items():
        if name == "car_benefit_value":
            continue
        slot = slots.get(SLOT_OF[name])
        if slot is not None and slot.state == "pending_rep":
            waiting.append(name)  # a representative is answering it
            continue
        if slot is not None and slot.state == "filled" and slot.source == "representative":
            kept.append(name)  # the representative's value wins
            continue
        read = _payslip_value(candidate, name, raw)
        unchanged = read is not None
        try:
            value = to_slot_value(name, read if unchanged else raw, ctx)
        except FieldError:
            invalid.append(name)
            continue
        source = "payslip" if unchanged else "employee"
        updates[SLOT_OF[name]] = SlotUpdate(value=value, source=source)
        applied[name] = {"value": to_tool_value(name, value), "source": source}
    if invalid:
        raise PayslipRejected(422, "payslip_invalid_value", fields=sorted(invalid))

    hint = None
    if "car_benefit_value" in accepted:
        hint = car_hint(services, accepted["car_benefit_value"])
    not_applied = _not_applied(candidate, set(accepted))
    store.update_slots(session_id, updates)  # the existing path: profile_updated
    store.append_event(
        session_id,
        "payslip_confirmed",
        {
            "candidate_seq": seq,
            "applied": applied,
            "kept_representative": kept,
            "waiting_for_rep": waiting,
            "car_hint": hint,
            "not_in_payslip": not_applied["not_in_payslip"],
            "unreadable": not_applied["unreadable"],
            "removed_by_employee": not_applied["removed"],
        },
    )
    comparisons = (
        refresh_after_profile_change(services, session_id, {"payslip_seq": seq}) if updates else []
    )
    return Confirmed(
        applied,
        kept,
        waiting,
        hint,
        comparisons,
        not_applied["not_in_payslip"],
        not_applied["unreadable"],
        not_applied["removed"],
    )

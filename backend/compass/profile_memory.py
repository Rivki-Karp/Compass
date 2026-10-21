"""Remember the employee's details between conversations, with their confirmation
(COMPASS_PROFILE_MEMORY=1, with accounts).

    saving    whenever a detail is confirmed or settled in a conversation (said by the employee,
              confirmed from the payslip, or settled by a representative), the store also puts it
              in the owner's profile (Store._remember_slots / _remember_today). Pending,
              provisional, unknown, derived and default values are never saved.
    offering  a NEW conversation of an account with a saved profile gets one `profile_offer`
              event. The offer is a pending candidate, exactly like the payslip's: it is not
              applied, not in the agent's input and not a source for the number guard.
    applying  the employee confirms (keep / edit / drop per detail) and the details go through
              the existing slot path and recompute, with source "previous" (kept) or "employee"
              (edited); then the agent is told, as data. Anything new in this conversation wins:
                  representative > payslip / employee (this conversation) > previous > default
    dismissing "להתחיל מחדש", for this conversation only: nothing is deleted.

What is remembered: the occupation, the salary fields (base salary, commissions, bonus, pension
and study fund percent, credit points) and today's car as a catalog id with its model year. Never
the group (it is derived again from the occupation, so a rules change applies), a representative's
answer about a car's participation or a group exception, a payslip file, a name, an id or a bank
detail. No calculation happens here.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from compass.labels import NUMBER_CHIP_LABELS, field_label
from compass.state import SlotUpdate
from compass.state.store import REMEMBERED_SLOTS, TODAY_CAR
from compass.tools.handlers import (
    CompanyCarToday,
    ToolError,
    refresh_after_profile_change,
    today_after,
    today_payload,
)
from compass.tools.profile import (
    CURRENT_CAR,
    SLOT_OF,
    FieldError,
    to_slot_value,
    to_tool_value,
)
from compass.tools.services import Services

# The remembered details in the order the card shows them (tool names).
OFFERED: tuple[str, ...] = (
    "occupation",
    "base_salary",
    "commissions",
    "bonus",
    "pension_percent",
    "study_fund_percent",
    "credit_points",
    TODAY_CAR,
)
_UNIT = {
    "occupation": "text",
    "base_salary": "ils",
    "commissions": "ils",
    "bonus": "ils",
    "pension_percent": "percent",
    "study_fund_percent": "percent",
    "credit_points": "points",
    TODAY_CAR: "text",
}
_SLOT_OF_REMEMBERED = {tool: slot for slot, tool in REMEMBERED_SLOTS.items()}
_CHIP_OF_SOURCE = {
    "employee": "employee_input",
    "payslip": "payslip",
    "representative": "representative",
}
STALE_AFTER_DAYS = 30
STALE_NOTE = "ייתכן שהפרטים השתנו"
ACTIONS = ("keep", "edit", "drop")
_OFFER, _APPLIED, _DISMISSED = "profile_offer", "profile_applied", "profile_dismissed"


ProfileErrorCode = Literal[
    "profile_nothing_pending",
    "profile_field_not_allowed",
    "profile_invalid_value",
    "profile_action_invalid",
]


class ProfileRejected(Exception):
    """A refused apply / dismiss: the HTTP status and a code with a Hebrew message
    (compass.labels). `fields` name the details at fault."""

    def __init__(
        self, status: int, code: ProfileErrorCode, fields: list[str] | None = None
    ) -> None:
        self.status = status
        self.code = code
        self.fields = fields or []
        super().__init__(code)


@dataclass(frozen=True)
class Choice:
    name: str
    action: str  # keep | edit | drop
    value: Any = None


@dataclass
class Applied:
    # tool field -> {"value", "source": "previous" | "employee", ...}
    values: dict[str, dict[str, Any]] = field(default_factory=dict)
    kept_current: list[str] = field(default_factory=list)  # this conversation already has it
    waiting_for_rep: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    from_date: str | None = None
    today_after: dict[str, Any] | None = None
    comparisons: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """The public answer and the `profile_applied` event."""
        return {
            "values": self.values,
            "kept_current": self.kept_current,
            "waiting_for_rep": self.waiting_for_rep,
            "dropped": self.dropped,
            "from_date": self.from_date,
        }


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def _age_days(stamp: str, now: datetime) -> int:
    return max(0, (now - _parse(stamp)).days)


# --- the offer -----------------------------------------------------------------------------


def _offered_field(
    services: Services, name: str, saved: dict[str, Any], now: datetime
) -> dict[str, Any] | None:
    """One saved detail as the card shows it, or None when it no longer holds (an occupation or a
    car the rules or the catalog dropped, a car whose model year changed): the rules are the
    rules of today."""
    ctx = services.ctx
    source = saved.get("source")
    if source not in _CHIP_OF_SOURCE:
        return None
    if name == TODAY_CAR:
        car = ctx.catalog.get(str(saved.get("value")))
        if car is None or car.registration_year != saved.get("year"):
            return None
        value, display = car.id, f"{car.commercial_name} {car.registration_year}"
    else:
        slot = _SLOT_OF_REMEMBERED.get(name)
        if slot is None:
            return None
        value = to_tool_value(name, saved.get("value"))
        try:
            to_slot_value(name, value, ctx)
        except FieldError:
            return None
        display = value
    return {
        "name": name,
        "label": field_label(name),
        "value": value,
        "display": display,
        "unit": _UNIT[name],
        "source": source,
        "source_chip": _CHIP_OF_SOURCE[source],
        "source_label": NUMBER_CHIP_LABELS[_CHIP_OF_SOURCE[source]],
        "saved_at": saved["saved_at"],
        "age_days": _age_days(saved["saved_at"], now),
    }


def build_offer(
    services: Services, user_id: str, now: datetime | None = None
) -> dict[str, Any] | None:
    """The `profile_offer` payload for this account, or None when nothing usable is saved."""
    profile = services.store.profile(user_id)
    if profile is None:
        return None
    now = now or datetime.now(UTC)
    fields = [
        offered
        for name in OFFERED
        if (saved := profile["fields"].get(name)) is not None
        and (offered := _offered_field(services, name, saved, now)) is not None
    ]
    if not fields:
        return None
    saved_at = max(f["saved_at"] for f in fields)
    age = _age_days(saved_at, now)
    return {
        "fields": fields,
        "saved_at": saved_at,
        "age_days": age,
        "stale": age > STALE_AFTER_DAYS,
        "stale_note": STALE_NOTE if age > STALE_AFTER_DAYS else None,
    }


def offer_new_conversation(services: Services, session_id: str, user_id: str) -> bool:
    """A new conversation was just made: offer the saved profile, once. True: an offer was made."""
    offer = build_offer(services, user_id)
    if offer is None:
        return False
    services.store.append_event(session_id, _OFFER, offer)
    return True


def pending_offer(services: Services, session_id: str) -> tuple[int, dict[str, Any]] | None:
    """The offer not yet applied or dismissed (its seq and payload), or None."""
    pending: tuple[int, dict[str, Any]] | None = None
    for event in services.store.events_after(session_id):
        if event.type == _OFFER:
            pending = (event.seq, event.payload)
        elif event.type in (_APPLIED, _DISMISSED):
            pending = None
    return pending


# --- applying ------------------------------------------------------------------------------


def _today_choice(
    services: Services,
    session_id: str,
    choice: Choice,
    offered: dict[str, Any],
    result: Applied,
) -> None:
    """Today's car: kept or edited, unless this conversation already has one that wins."""
    store, ctx = services.store, services.ctx
    slot = store.slots(session_id).get(CURRENT_CAR)
    if slot is not None and slot.state == "pending_rep":
        result.waiting_for_rep.append(TODAY_CAR)  # a representative is identifying it
        return
    stored = store.scenarios(session_id).get("today") or {}
    current = stored.get("source")
    # a rep's value always wins; keeping never replaces what was said in this conversation
    if (slot is not None and slot.state == "filled") or current == "representative":
        result.kept_current.append(TODAY_CAR)
        return
    if choice.action == "keep" and current in ("employee", "representative"):
        result.kept_current.append(TODAY_CAR)
        return
    car_id = offered["value"] if choice.action == "keep" else choice.value
    car = ctx.catalog.get(car_id) if isinstance(car_id, str) else None
    if car is None:
        raise ProfileRejected(422, "profile_invalid_value", [TODAY_CAR])
    source = "previous" if choice.action == "keep" else "employee"
    try:
        payload = today_payload(
            services,
            CompanyCarToday(
                kind="company_car", car_id=car.id, registration_year=car.registration_year
            ),
            source=source,
        )
    except ToolError:
        raise ProfileRejected(422, "profile_invalid_value", [TODAY_CAR]) from None
    if source == "previous":
        payload["previous_from"] = offered["saved_at"]
    store.set_today(session_id, payload)
    result.values[TODAY_CAR] = {
        "value": car.id,
        "name": car.commercial_name,
        "year": car.registration_year,
        "source": source,
    }
    result.today_after = today_after(services, session_id)


def apply_profile(services: Services, session_id: str, choices: list[Choice]) -> Applied:
    """Apply the employee's choices on the pending offer (see the module docstring). Raises
    ProfileRejected; nothing is changed unless every choice is valid."""
    pending = pending_offer(services, session_id)
    if pending is None:
        raise ProfileRejected(409, "profile_nothing_pending")
    _seq, offer = pending
    offered = {f["name"]: f for f in offer["fields"]}
    names = [c.name for c in choices]
    unknown = sorted(
        {n for n in names if n not in offered} | {n for n in names if names.count(n) > 1}
    )
    if unknown:
        raise ProfileRejected(422, "profile_field_not_allowed", unknown)
    if any(c.action not in ACTIONS for c in choices):
        raise ProfileRejected(
            422,
            "profile_action_invalid",
            sorted(c.name for c in choices if c.action not in ACTIONS),
        )

    store, ctx = services.store, services.ctx
    slots = store.slots(session_id)
    result = Applied(from_date=offer["saved_at"])
    updates: dict[str, SlotUpdate] = {}
    invalid: list[str] = []
    wants_today: Choice | None = None
    for choice in choices:
        name = choice.name
        if choice.action == "drop":
            result.dropped.append(name)
            continue
        if name == TODAY_CAR:
            wants_today = choice
            continue
        if choice.action == "edit" and choice.value is None:
            invalid.append(name)
            continue
        slot = slots.get(SLOT_OF[name])
        if slot is not None and slot.state == "pending_rep":
            result.waiting_for_rep.append(name)  # a representative is answering it
            continue
        if slot is not None and slot.state == "filled":
            if slot.source == "representative":
                result.kept_current.append(name)  # the representative's value always wins
                continue
            if choice.action == "keep" and slot.source in ("employee", "payslip"):
                result.kept_current.append(name)  # new in this conversation: it wins
                continue
        raw = offered[name]["value"] if choice.action == "keep" else choice.value
        try:
            value = to_slot_value(name, raw, ctx)
        except FieldError:
            invalid.append(name)
            continue
        source = "previous" if choice.action == "keep" else "employee"
        updates[SLOT_OF[name]] = SlotUpdate(
            value=value,
            source=source,  # type: ignore[arg-type]
            previous_from=offered[name]["saved_at"] if source == "previous" else None,
        )
        result.values[name] = {"value": to_tool_value(name, value), "source": source}
        if name == "occupation":
            group = slots.get("group")
            stated = group is not None and group.state == "filled" and group.source != "derived"
            if not stated and (occupation := ctx.occupations.get(value)) is not None:
                updates["group"] = SlotUpdate(value=occupation.group, source="derived")
    if invalid:
        raise ProfileRejected(422, "profile_invalid_value", sorted(invalid))

    if wants_today is not None:
        _today_choice(services, session_id, wants_today, offered[TODAY_CAR], result)
    store.update_slots(session_id, updates)  # the existing path: profile_updated
    store.append_event(session_id, _APPLIED, result.to_dict())
    if updates or TODAY_CAR in result.values:
        result.comparisons = refresh_after_profile_change(
            services, session_id, {"profile_seq": _seq}
        )
    return result


def dismiss_profile(services: Services, session_id: str) -> None:
    """ "להתחיל מחדש": the offer is dropped for this conversation. Nothing is deleted."""
    pending = pending_offer(services, session_id)
    if pending is None:
        raise ProfileRejected(409, "profile_nothing_pending")
    services.store.append_event(session_id, _DISMISSED, {"offer_seq": pending[0]})

"""Answering a representative ticket: one validated path for the API and the terminal chat.

Values use the save_profile rules; a quick answer's values apply first and explicit values win;
blocking fields left without a value become unknown (answered, but not with a number).
"""

from datetime import date
from typing import Any

from compass.engine.serialize import plain_json
from compass.state import NotFound, StateError, Ticket
from compass.tools.profile import (
    FieldError,
    is_fillable,
    is_participation,
    slot_name,
    to_slot_value,
)
from compass.tools.services import Services


class TicketAnswerError(Exception):
    """`status` is the HTTP status the API answers with (404, 409, 422)."""

    def __init__(self, status: int, detail: Any) -> None:
        self.status = status
        self.detail = detail
        super().__init__(str(detail))


def answer_ticket(
    services: Services,
    ticket_id: str,
    *,
    answer_text: str | None = None,
    quick_answer_id: str | None = None,
    values: dict[str, Any] | None = None,
    effective_from: date | None = None,
) -> Ticket:
    store = services.store
    try:
        ticket = store.ticket(ticket_id)
    except NotFound:
        raise TicketAnswerError(404, f"ticket {ticket_id} not found") from None
    if ticket.status != "open":
        raise TicketAnswerError(409, f"ticket {ticket_id} is already {ticket.status}")
    explicit = values or {}
    if answer_text is None and quick_answer_id is None and not explicit:
        raise TicketAnswerError(422, "give answer_text, quick_answer_id or values")

    merged: dict[str, Any] = {}
    if quick_answer_id is not None:
        quick = {qa["id"]: qa for qa in ticket.quick_answers}
        if quick_answer_id not in quick:
            raise TicketAnswerError(
                422, f"unknown quick_answer_id {quick_answer_id!r}; have {list(quick)}"
            )
        merged.update(quick[quick_answer_id].get("values", {}))
    merged.update(explicit)  # explicit values win over the quick answer's

    errors: list[str] = []
    slot_values: dict[str, Any] = {}
    for field, raw in merged.items():
        if field not in ticket.blocking_fields or not is_fillable(field, services.ctx):
            errors.append(f"{field}: not a blocking field of this ticket")
            continue
        when = effective_from if is_participation(field) else None
        try:
            slot_values[slot_name(field)] = to_slot_value(field, raw, services.ctx, when)
        except FieldError as error:
            errors.append(str(error))
    if errors:
        raise TicketAnswerError(422, errors)
    if effective_from is not None and not any(map(is_participation, merged)):
        raise TicketAnswerError(422, "effective_from applies to participation fields only")

    unknown = [slot_name(f) for f in ticket.blocking_fields if f not in merged]
    answer = {
        "text": answer_text,
        "quick_answer_id": quick_answer_id,
        "values": plain_json(merged),
        "effective_from": None if effective_from is None else effective_from.isoformat(),
    }
    try:
        return store.answer_ticket(ticket_id, answer, slot_values, unknown=unknown)
    except StateError as error:  # answered concurrently
        raise TicketAnswerError(409, str(error)) from None

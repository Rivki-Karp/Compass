"""Answering a representative ticket: one validated path for the API and the terminal chat.

Values use the save_profile rules; a quick answer's values apply first and explicit values win;
blocking fields left without a value become unknown (answered, but not with a number).

A `partial` answer fills only the fields it has values for; the others stay pending and the
ticket stays open, until a later answer fills them (the last one closes it).
"""

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date
from typing import Any, Literal

from compass.engine.serialize import plain_json
from compass.state import NotFound, StateError, Ticket
from compass.tools.handlers import settle_answered
from compass.tools.profile import (
    GROUP_EXCEPTION,
    NOT_APPROVED,
    FieldError,
    is_fillable,
    is_participation,
    slot_name,
    to_slot_value,
)
from compass.tools.services import Services

TicketErrorCode = Literal[
    "ticket_not_found",
    "ticket_already_answered",
    "empty_answer",
    "unknown_quick_answer",
    "not_a_blocking_field",
    "field_already_answered",
    # questions (compass/tools/questions.py)
    "unknown_question",
    "not_an_option",
    "not_a_whole_amount",
    "empty_text",
    "text_too_long",
    "note_required",
    "value_with_needs_checking",
]


@dataclass(frozen=True)
class AnswerError:
    """One reason an answer was refused: a TicketErrorCode or a FieldErrorCode, with the field
    it concerns and the parameters its Hebrew message needs (compass.labels.error_message)."""

    code: str
    field: str | None = None
    params: dict[str, Any] = dc_field(default_factory=dict)


class TicketAnswerError(Exception):
    """`status` is the HTTP status the API answers with (404, 409, 422). `detail` is English
    (as before); `errors` carry codes for the UI's Hebrew messages."""

    def __init__(self, status: int, detail: Any, errors: list[AnswerError]) -> None:
        self.status = status
        self.detail = detail
        self.errors = errors
        super().__init__(str(detail))


def answer_ticket(
    services: Services,
    ticket_id: str,
    *,
    answer_text: str | None = None,
    quick_answer_id: str | None = None,
    values: dict[str, Any] | None = None,
    effective_from: date | None = None,
    partial: bool = False,
) -> Ticket:
    store = services.store
    try:
        ticket = store.ticket(ticket_id)
    except NotFound:
        raise TicketAnswerError(
            404, f"ticket {ticket_id} not found", [AnswerError("ticket_not_found")]
        ) from None
    if ticket.status != "open":
        raise TicketAnswerError(
            409,
            f"ticket {ticket_id} is already {ticket.status}",
            [AnswerError("ticket_already_answered")],
        )
    explicit = values or {}
    if partial and quick_answer_id is None and not explicit:
        raise TicketAnswerError(
            422, "a partial answer needs at least one value", [AnswerError("empty_answer")]
        )
    if answer_text is None and quick_answer_id is None and not explicit:
        raise TicketAnswerError(
            422, "give answer_text, quick_answer_id or values", [AnswerError("empty_answer")]
        )

    merged: dict[str, Any] = {}
    if quick_answer_id is not None:
        quick = {qa["id"]: qa for qa in ticket.quick_answers}
        if quick_answer_id not in quick:
            raise TicketAnswerError(
                422,
                f"unknown quick_answer_id {quick_answer_id!r}; have {list(quick)}",
                [AnswerError("unknown_quick_answer")],
            )
        merged.update(quick[quick_answer_id].get("values", {}))
    merged.update(explicit)  # explicit values win over the quick answer's

    errors: list[str] = []
    coded: list[AnswerError] = []
    slot_values: dict[str, Any] = {}
    earlier: dict[str, Any] = (ticket.answer or {}).get("values") or {}  # earlier partial parts
    for field, raw in merged.items():
        if field in earlier:
            errors.append(f"{field}: already answered")
            coded.append(AnswerError("field_already_answered", field))
            continue
        if field not in ticket.blocking_fields or not is_fillable(field, services.ctx):
            errors.append(f"{field}: not a blocking field of this ticket")
            coded.append(AnswerError("not_a_blocking_field", field))
            continue
        when = effective_from if is_participation(field) else None
        try:
            slot_values[slot_name(field)] = to_slot_value(field, raw, services.ctx, when)
        except FieldError as error:
            errors.append(str(error))
            coded.append(AnswerError(error.code, error.field, error.params))
    if errors:
        raise TicketAnswerError(422, errors, coded)
    if effective_from is not None and not any(map(is_participation, merged)):
        raise TicketAnswerError(
            422,
            "effective_from applies to participation fields only",
            [AnswerError("effective_from_not_participation")],
        )

    approved = slot_values.get(GROUP_EXCEPTION)
    if approved is not None and approved != NOT_APPROVED:
        # the approved group becomes the group in effect (source representative); eligibility
        # and the warnings follow from it in every later calculation
        slot_values["group"] = approved
    so_far = {**earlier, **plain_json(merged)}
    remaining = [f for f in ticket.blocking_fields if f not in so_far]
    pending = remaining if partial else []
    unknown = [] if partial else [slot_name(f) for f in remaining]
    when = None if effective_from is None else effective_from.isoformat()
    part = {
        "text": answer_text,
        "quick_answer_id": quick_answer_id,
        "values": plain_json(merged),
        "effective_from": when,
    }
    # the ticket keeps every part's values; the event (and the agent) get this part
    answer = {**part, "values": so_far}
    try:
        answered = store.answer_ticket(
            ticket_id, answer, slot_values, unknown=unknown, pending=pending, part=part
        )
    except StateError as error:  # answered concurrently
        raise TicketAnswerError(409, str(error), [AnswerError("ticket_already_answered")]) from None
    # The comparison that waited for this answer turns final now, not when the model next
    # calls compare (it may not).
    settle_answered(services, answered.session_id, ticket_id, list(merged))
    return answered

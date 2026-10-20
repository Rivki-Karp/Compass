"""Answering a representative ticket: one validated path for the API and the terminal chat.

A ticket is a list of questions (compass/tools/questions.py). An answer gives, per question
(`answers`, by question id), a value, or "needs checking" (the question stays pending), and an
optional note. `values` (by bound field) and a quick answer still work as before: they answer
the bound question of that field. Explicit values win over a quick answer's.

- A bound question's value goes into its slot (source representative), validated by the
  save_profile rules. An approved group becomes the group; an occupation re-derives the group,
  replacing one the employee stated (only a representative-approved group is kept); "another
  occupation" leaves it unknown. Today's car (current_car) becomes today's situation, source
  representative, and what was on screen without it is computed again; "not in the catalog"
  leaves it unknown (the note says what it is).
- A free question's value is checked against its type and never touches a slot: it goes back
  to the model as data.

A `partial` answer leaves the questions it does not answer pending and the ticket open, until a
later answer completes them. Otherwise, questions left without an answer become unknown
(answered, but not with a value) and the ticket closes.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from compass.engine.serialize import plain_json
from compass.state import NotFound, StateError, Ticket
from compass.state.store import SlotSource
from compass.tools.handlers import (
    refresh_without_today,
    representative_today,
    settle_answered,
)
from compass.tools.profile import (
    CURRENT_CAR,
    GROUP_EXCEPTION,
    NOT_APPROVED,
    FieldError,
    is_fillable,
    is_participation,
    slot_name,
    to_slot_value,
)
from compass.tools.questions import (
    MAX_NOTE,
    MAX_TEXT_ANSWER,
    NO,
    NOTE_FOR_OTHER,
    OCCUPATION,
    OTHER,
    YES,
    answer_label,
    is_free,
    ticket_questions,
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

QuestionAnswerStatus = Literal["answered", "needs_checking"]


@dataclass(frozen=True)
class QuestionAnswer:
    """One question's answer in one part: a value, or needs checking; a note either way."""

    value: Any = None
    status: QuestionAnswerStatus = "answered"
    note: str | None = None


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


def _free_value(question: Mapping[str, Any], raw: Any) -> tuple[Any, AnswerError | None, str]:
    """A free question's answer, checked against its type: (value, error, English message)."""
    kind = question["answer"]["type"]
    qid = question["id"]
    if kind == "yes_no":
        if raw not in (YES, NO):
            return None, AnswerError("not_an_option", qid), f"{qid}: answer {YES!r} or {NO!r}"
        return raw, None, ""
    if kind == "choice":
        values = [o["value"] for o in question["answer"]["options"]]
        if raw not in values:
            return None, AnswerError("not_an_option", qid), f"{qid}: one of {values}"
        return raw, None, ""
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        return None, AnswerError("empty_text", qid), f"{qid}: an answer text is required"
    if len(text) > MAX_TEXT_ANSWER:
        error = AnswerError("text_too_long", qid, {"max": MAX_TEXT_ANSWER})
        return None, error, f"{qid}: at most {MAX_TEXT_ANSWER} characters"
    return text, None, ""


def _whole_amount(field: str, raw: Any) -> AnswerError | None:
    """An amount question answered on the questions path is whole ILS."""
    try:
        amount = Decimal(str(raw).replace(",", "").strip())
    except InvalidOperation:
        return None  # to_slot_value reports it (not_a_number)
    if amount.is_finite() and amount != amount.to_integral_value():
        return AnswerError("not_a_whole_amount", field)
    return None


def _note(raw: str | None) -> str | None:
    text = (raw or "").strip()
    return text[:MAX_NOTE] or None


def answer_ticket(
    services: Services,
    ticket_id: str,
    *,
    answer_text: str | None = None,
    quick_answer_id: str | None = None,
    values: dict[str, Any] | None = None,
    answers: Mapping[str, QuestionAnswer] | None = None,
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
    answers = answers or {}
    if partial and quick_answer_id is None and not explicit and not answers:
        raise TicketAnswerError(
            422, "a partial answer needs at least one value", [AnswerError("empty_answer")]
        )
    if answer_text is None and quick_answer_id is None and not explicit and not answers:
        raise TicketAnswerError(
            422,
            "give answer_text, quick_answer_id, values or answers",
            [AnswerError("empty_answer")],
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

    questions = ticket_questions(services, ticket)
    by_id = {q["id"]: q for q in questions}
    by_field = {q["bound_field"]: q for q in questions if q["bound_field"] is not None}
    so_far_answer = ticket.answer or {}
    earlier: dict[str, Any] = so_far_answer.get("values") or {}  # earlier partial parts
    earlier_parts: dict[str, Any] = so_far_answer.get("questions") or {}

    def done_before(question: Mapping[str, Any]) -> bool:
        part = earlier_parts.get(question["id"])
        if part is not None and part["status"] == "answered":
            return True
        return question["bound_field"] is not None and question["bound_field"] in earlier

    errors: list[str] = []
    coded: list[AnswerError] = []

    def refuse(error: AnswerError, message: str) -> None:
        errors.append(message)
        coded.append(error)

    # this part's answer to each question: {"status", "value"?, "note"?}
    parts: dict[str, dict[str, Any]] = {}
    for qid, given in answers.items():
        question = by_id.get(qid)
        if question is None:
            refuse(AnswerError("unknown_question", qid), f"{qid}: not a question of this ticket")
            continue
        if done_before(question):
            refuse(AnswerError("field_already_answered", qid), f"{qid}: already answered")
            continue
        note = _note(given.note)
        if given.status == "needs_checking":
            if given.value is not None:
                refuse(
                    AnswerError("value_with_needs_checking", qid),
                    f"{qid}: needs_checking takes no value",
                )
                continue
            parts[qid] = {"status": "needs_checking", "note": note}
            continue
        if is_free(question):
            value, error, message = _free_value(question, given.value)
            if error is not None:
                refuse(error, message)
                continue
            parts[qid] = {"status": "answered", "value": value, "note": note}
            continue
        field = question["bound_field"]
        if question["answer"]["type"] == "amount":
            whole = _whole_amount(field, given.value)
            if whole is not None:
                refuse(whole, f"{field}: a whole amount in ILS")
                continue
        merged[field] = given.value  # validated with the values below
        parts[qid] = {"status": "answered", "value": given.value, "note": note}
    for field, raw in merged.items():  # values given by field answer their bound question
        question = by_field.get(field)
        if question is not None and question["id"] not in parts:
            parts[question["id"]] = {"status": "answered", "value": raw, "note": None}

    # "another occupation" / "not in the catalog": answered, but with nothing from the table;
    # the note says what
    other: list[str] = []
    for field in NOTE_FOR_OTHER:
        if merged.get(field) != OTHER or field not in by_field:
            continue
        part = parts[by_field[field]["id"]]
        if part["note"] is None and answer_text:
            part["note"] = _note(answer_text)
        if part["note"] is None:
            refuse(AnswerError("note_required", field), f"{field}: other needs a note")
        del merged[field]
        other.append(field)

    slot_values: dict[str, Any] = {}
    for field, raw in merged.items():
        if field in earlier:
            refuse(AnswerError("field_already_answered", field), f"{field}: already answered")
            continue
        if field not in ticket.blocking_fields or not is_fillable(field, services.ctx):
            refuse(
                AnswerError("not_a_blocking_field", field),
                f"{field}: not a blocking field of this ticket",
            )
            continue
        when = effective_from if is_participation(field) else None
        try:
            slot_values[slot_name(field)] = to_slot_value(field, raw, services.ctx, when)
        except FieldError as error:
            refuse(AnswerError(error.code, error.field, error.params), str(error))
    if errors:
        raise TicketAnswerError(422, errors, coded)
    if effective_from is not None and not any(map(is_participation, merged)):
        raise TicketAnswerError(
            422,
            "effective_from applies to participation fields only",
            [AnswerError("effective_from_not_participation")],
        )

    sources: dict[str, SlotSource] = {}
    approved = slot_values.get(GROUP_EXCEPTION)
    if approved is not None and approved != NOT_APPROVED:
        # the approved group becomes the group in effect (source representative); eligibility
        # and the warnings follow from it in every later calculation
        slot_values["group"] = approved
    occupation = slot_values.get(OCCUPATION)
    if occupation is not None and "group" not in slot_values:
        # the group follows the confirmed occupation (source derived): a representative's
        # fact outranks a group the employee merely stated. Only a group a representative
        # approved (group_exception) is kept.
        group = store.slots(ticket.session_id).get("group")
        approved_before = (
            group is not None and group.state == "filled" and group.source == "representative"
        )
        if not approved_before:
            slot_values["group"] = services.ctx.occupations[occupation].group
            sources["group"] = "derived"

    # today's car, answered: today's situation (source representative), in the same write
    today = None
    if CURRENT_CAR in slot_values:
        today = representative_today(services, slot_values[CURRENT_CAR])

    so_far = {**earlier, **plain_json(merged)}
    answered_ids = {qid for qid, p in parts.items() if p["status"] == "answered"}
    remaining = [q for q in questions if not done_before(q) and q["id"] not in answered_ids]
    pending: list[str] = []
    unknown: list[str] = [slot_name(f) for f in other]
    if partial:
        pending = [q["bound_field"] or q["id"] for q in remaining]
    else:
        for q in remaining:  # answered without a value
            if q["bound_field"] is not None:
                unknown.append(slot_name(q["bound_field"]))
            note = (parts.get(q["id"]) or {}).get("note")
            parts[q["id"]] = {"status": "unknown", "note": note}
    when = None if effective_from is None else effective_from.isoformat()
    part = {
        "text": answer_text,
        "quick_answer_id": quick_answer_id,
        "values": plain_json(merged),
        "effective_from": when,
    }
    answer = {**part, "values": so_far}
    shown: list[dict[str, Any]] = []
    if ticket.questions or answers:  # a ticket stored before questions answers as it did
        part["questions"] = plain_json(parts)
        answer = {**part, "values": so_far, "questions": {**earlier_parts, **part["questions"]}}
        shown = [_shown(by_id[qid], p) for qid, p in parts.items()]
    # the ticket keeps every part's values and question answers; the event (and the agent) get
    # this part
    try:
        answered = store.answer_ticket(
            ticket_id,
            answer,
            slot_values,
            unknown=unknown,
            pending=pending,
            part=part,
            questions=shown,
            sources=sources,
            today=today,
        )
    except StateError as error:  # answered concurrently
        raise TicketAnswerError(409, str(error), [AnswerError("ticket_already_answered")]) from None
    # The comparison that waited for this answer turns final now, not when the model next
    # calls compare (it may not).
    settle_answered(services, answered.session_id, ticket_id, [*merged, *other])
    if CURRENT_CAR in merged or CURRENT_CAR in other:  # the diffs, or the pending chip gone
        refresh_without_today(
            services, answered.session_id, {"ticket_id": ticket_id, "answered_field": CURRENT_CAR}
        )
    return answered


def _shown(question: Mapping[str, Any], part: Mapping[str, Any]) -> dict[str, Any]:
    """One question's answer in this part, display-ready (the ticket_answered event)."""
    answered = part["status"] == "answered"
    return {
        "id": question["id"],
        "kind": "free" if is_free(question) else "bound",
        "bound_field": question["bound_field"],
        "prompt_he": question["prompt_he"],
        "status": part["status"],
        "value": plain_json(part.get("value")) if answered else None,
        "answer": answer_label(question, plain_json(part.get("value"))) if answered else None,
        "note": part.get("note"),
    }

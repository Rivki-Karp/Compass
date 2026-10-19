"""Ticket questions: what a representative is asked, and the answer each one takes.

A ticket is a list of at most MAX_QUESTIONS questions, stored as JSON:

    {"id": "q1",
     "prompt_he": "האם 'מפתח AI' נחשב מפתח/ת תוכנה?",
     "bound_field": "occupation" | None,
     "answer": {"type": "amount" | "choice" | "yes_no" | "text",
                "options": [{"value": "מפתח/ת תוכנה", "label": "מפתח/ת תוכנה · קבוצה ב׳"}]},
     "occupation_query": "מפתח AI",          # a bound occupation question only
     "car_query": "מציון"}                   # a bound current_car question only

Two kinds:

- Bound: the answer changes one calculation input, a field of BOUND_FIELDS. The server builds
  the answer schema and the options (bound_question); the model never supplies them.
- Free: the model writes the prompt, the type (yes_no, choice, text) and, for a choice, the
  option labels (free_question). The answer never changes a slot: it goes back to the model as
  data inside the server's rep notification.

Every question may also be answered "needs checking" (it stays pending) and carry a note.

A ticket stored before questions existed has none stored: its blocking fields are its questions
(ticket_questions builds them, with the field as the id), so old tickets answer as before.
"""

from collections.abc import Mapping
from typing import Any, Literal

from compass.labels import (
    GROUP_NOT_APPROVED_LABEL,
    NOT_IN_CATALOG_LABEL,
    OTHER_OCCUPATION_LABEL,
    car_details,
    group_approved_label,
    group_label,
)
from compass.state import Ticket
from compass.tools.profile import (
    ALTERNATIVE_PARTICIPATION,
    CURRENT_CAR,
    CURRENT_PARTICIPATION,
    GROUP_EXCEPTION,
    NOT_APPROVED,
    SLOT_OF,
    is_fillable,
)
from compass.tools.services import Services

AnswerType = Literal["amount", "choice", "yes_no", "text"]
FreeType = Literal["yes_no", "choice", "text"]

MAX_QUESTIONS = 3
MAX_PROMPT = 300
MAX_OPTIONS = 6
MAX_OPTION_LABEL = 80
MAX_TEXT_ANSWER = 2000
MAX_NOTE = 1000
OCCUPATION = "occupation"
# The representative's "none of these": the occupation is answered, but not with a title from
# the table (the note says what it is). The slot becomes unknown. The same value answers a
# current_car question with "not in the catalog".
OTHER_OCCUPATION = "other"
OTHER = OTHER_OCCUPATION
# Bound questions whose "other" needs a note, and what the representative picks from.
NOTE_FOR_OTHER = ("occupation", CURRENT_CAR)
YES, NO = "yes", "no"
YES_NO_LABELS = {YES: "כן", NO: "לא"}

# Profile fields a ticket's legacy `blocking_fields` may block on, answered in ILS. The others
# are typed as text (validated by compass.tools.profile.to_slot_value either way).
_ILS_PROFILE_FIELDS = frozenset({"base_salary", "commissions", "bonus"})


def is_bound_field(field: str, ctx: Any) -> bool:
    """The server registry: the fields a question may be bound to (questions[] input)."""
    if field in (CURRENT_PARTICIPATION, GROUP_EXCEPTION, OCCUPATION, CURRENT_CAR):
        return True
    return field.startswith(ALTERNATIVE_PARTICIPATION) and is_fillable(field, ctx)


def bound_field_names() -> str:
    """For error messages: the registry, as the model writes it."""
    return (
        f"{CURRENT_PARTICIPATION}, {ALTERNATIVE_PARTICIPATION}<catalog car id>, "
        f"{GROUP_EXCEPTION}, {OCCUPATION}, {CURRENT_CAR}"
    )


def option(value: str, label: str) -> dict[str, str]:
    return {"value": value, "label": label}


def group_exception_options(services: Services, session_id: str) -> list[dict[str, str]]:
    """The groups a representative may approve today: each group above the occupation's group,
    up to today's car's group (all of them when today's car is not above it or not in the
    catalog), then "not approved"."""
    ctx = services.ctx
    order = list(ctx.rules.group_order)
    base, car_group = group_exception_bounds(services, session_id)
    start = order.index(base) + 1 if base in order else 0
    above = car_group is not None and order.index(car_group) >= start
    end = order.index(car_group) + 1 if above else len(order)
    options = [option(g, group_approved_label(g)) for g in order[start:end]]
    options.append(option(NOT_APPROVED, GROUP_NOT_APPROVED_LABEL))
    return options


def group_exception_bounds(services: Services, session_id: str) -> tuple[str | None, str | None]:
    """(the occupation's group, or the group given when there is no occupation; today's car's
    group when it is a catalog car)."""
    ctx = services.ctx
    slots = services.store.slots(session_id)

    def filled(slot_field: str) -> Any:
        slot = slots.get(slot_field)
        return slot.value if slot is not None and slot.state == "filled" else None

    occupation = ctx.occupations.get(filled("occupation") or "")
    base = occupation.group if occupation is not None else filled("group")
    stored = services.store.scenarios(session_id).get("today") or {}
    car = ctx.catalog.get((stored.get("scenario") or {}).get("car_id") or "")
    car_group = car.group if car is not None and car.group in ctx.rules.group_order else None
    return base, car_group


def occupation_options(services: Services, query: str) -> list[dict[str, str]]:
    """The occupations closest to the employee's words, from the occupations table, by the same
    matcher as lookup_occupation; then "another occupation" (answered with a note)."""
    ctx = services.ctx
    titles = services.searcher.rank_occupations(query)
    options = [option(t, f"{t} · {group_label(ctx.occupations[t].group)}") for t in titles]
    options.append(option(OTHER_OCCUPATION, OTHER_OCCUPATION_LABEL))
    return options


def car_option_label(services: Services, car_id: str) -> str:
    """A catalog car as the representative picks it: "MAZDA 3 2025"."""
    car = services.ctx.catalog[car_id]
    return f"{car.commercial_name} {car.registration_year}"


def current_car_options(services: Services, query: str) -> list[dict[str, str]]:
    """The catalog cars the employee's words may mean (search_catalog, the same list the
    employee is offered), each with its drive and group ("MAZDA 3 2025 · בנזין · קבוצה ג׳", as
    an occupation's option carries its group), then "not in the catalog" (with a note)."""
    cars = services.searcher.search_catalog(query)
    options = [
        option(c.id, f"{car_option_label(services, c.id)} · {car_detail(services, c.id)}")
        for c in cars
    ]
    options.append(option(OTHER, NOT_IN_CATALOG_LABEL))
    return options


def car_detail(services: Services, car_id: str) -> str | None:
    """The drive and group a current_car choice gives ("בנזין · קבוצה ג׳")."""
    car = services.ctx.catalog.get(car_id)
    return None if car is None else car_details(car.drive, car.group)


def bound_question(
    services: Services,
    session_id: str,
    field: str,
    *,
    qid: str,
    prompt_he: str | None = None,
    occupation_query: str | None = None,
    car_query: str | None = None,
) -> dict[str, Any]:
    """A question bound to `field`, with the answer schema and options the server builds."""
    answer: dict[str, Any]
    if field == CURRENT_PARTICIPATION or field.startswith(ALTERNATIVE_PARTICIPATION):
        answer = {"type": "amount", "options": []}
    elif field == GROUP_EXCEPTION:
        answer = {"type": "choice", "options": group_exception_options(services, session_id)}
    elif field == OCCUPATION and occupation_query is not None:
        answer = {"type": "choice", "options": occupation_options(services, occupation_query)}
    elif field == CURRENT_CAR:
        answer = {"type": "choice", "options": current_car_options(services, car_query or "")}
    elif field in _ILS_PROFILE_FIELDS:
        answer = {"type": "amount", "options": []}
    else:  # a legacy profile field (or a legacy occupation, typed as its exact title)
        answer = {"type": "text", "options": []}
    question: dict[str, Any] = {
        "id": qid,
        "prompt_he": prompt_he or "",
        "bound_field": field,
        "answer": answer,
    }
    if occupation_query is not None:
        question["occupation_query"] = occupation_query
    if car_query is not None:
        question["car_query"] = car_query
    return question


def free_question(
    qid: str, prompt_he: str, type_: FreeType, labels: list[str] | None = None
) -> dict[str, Any]:
    """A free question: the model's prompt and option labels; the values are the server's."""
    options = [option(f"o{i}", label) for i, label in enumerate(labels or [], start=1)]
    return {
        "id": qid,
        "prompt_he": prompt_he,
        "bound_field": None,
        "answer": {"type": type_, "options": options},
    }


def ticket_questions(services: Services, ticket: Ticket) -> list[dict[str, Any]]:
    """The ticket's questions: stored ones, or, for a ticket stored before questions existed,
    one bound question per blocking field (its id is the field; options built now, as the
    inbox built them before)."""
    if ticket.questions:
        return list(ticket.questions)
    return [
        bound_question(services, ticket.session_id, field, qid=field)
        for field in ticket.blocking_fields
    ]


def is_free(question: Mapping[str, Any]) -> bool:
    return question.get("bound_field") is None


def answer_label(question: Mapping[str, Any], value: Any) -> str | None:
    """A choice's or yes/no's label for an answer value; the text itself for the others."""
    if value is None:
        return None
    kind = question["answer"]["type"]
    if kind == "yes_no":
        return YES_NO_LABELS.get(value, str(value))
    if kind == "choice":
        return next(
            (o["label"] for o in question["answer"]["options"] if o["value"] == value), str(value)
        )
    return str(value)


def slot_field_of(question: Mapping[str, Any]) -> str | None:
    """The slot a bound question fills (None for a free question)."""
    field = question.get("bound_field")
    return None if field is None else SLOT_OF.get(field, field)

"""The employee's pick in the catalog picker (compass/tools/car_picker.py).

    car          a catalog car (manufacturer, model and year picked): today's situation, source
                 "employee", at the catalog's participation until the employee states theirs
    no_car       "אין לי רכב היום": today is no car
    not_in_list  "הרכב שלי לא ברשימה": nothing is recorded; the agent asks for the model and the
                 year and takes it from there (lookup_vehicle)
    check_year   the model is there and the year is not: a current_car ticket for a
                 representative ("לבדיקת נציג"), never "this is a different car"

Everything that changes the screen is the server's, exactly as a tool call would change it
(today's situation, the recompute of what is on screen); the model is told afterwards, as data.
The pick is refused once today's car is known, or a representative has been asked.
"""

from typing import Any, Literal

from compass.tools.car_picker import (
    CHECK_YEAR,
    NO_CAR,
    NOT_IN_LIST,
    PICKED,
    current_car_unknown,
)
from compass.tools.handlers import (
    AskRepresentativeInput,
    CompanyCarToday,
    NoCarToday,
    QuestionInput,
    ask_representative,
    refresh_without_today,
    today_after,
    today_payload,
)
from compass.tools.profile import CURRENT_CAR
from compass.tools.services import Services

CAR = "car"
CHOICES = (CAR, NO_CAR, NOT_IN_LIST, CHECK_YEAR)


PickErrorCode = Literal[
    "current_car_choice_invalid", "current_car_not_needed", "current_car_unknown_car"
]


class PickRejected(Exception):
    """A refused pick: an HTTP status and a code (a Hebrew message in compass.labels)."""

    def __init__(self, status: int, code: PickErrorCode) -> None:
        self.status = status
        self.code = code
        super().__init__(code)


def pick_current_car(
    services: Services, session_id: str, choice: str, car_id: str | None
) -> dict[str, Any]:
    """Apply one pick. Returns {"outcome", "car_id"?, "ticket_id"?, "today_after",
    "comparisons"} (the comparisons the server recomputed, in compare's own shape)."""
    if choice not in CHOICES:
        raise PickRejected(422, "current_car_choice_invalid")
    if not current_car_unknown(services, session_id):
        raise PickRejected(409, "current_car_not_needed")
    store = services.store
    car = None
    if choice in (CAR, CHECK_YEAR):
        car = services.ctx.catalog.get(car_id or "")
        if car is None:
            raise PickRejected(422, "current_car_unknown_car")
    elif car_id is not None:
        raise PickRejected(422, "current_car_choice_invalid")

    outcome: dict[str, Any] = {"outcome": choice}
    comparisons: list[dict[str, Any]] = []
    if choice in (CAR, NO_CAR):
        today = (
            CompanyCarToday(kind="company_car", car_id=car.id)  # at the catalog participation
            if car is not None
            else NoCarToday(kind="none")
        )
        store.set_today(session_id, today_payload(services, today, source="employee"))
        comparisons = refresh_without_today(services, session_id, {"car_picked": choice})
        if car is not None:
            outcome["car_id"] = car.id
    elif choice == CHECK_YEAR and car is not None:
        asked = ask_representative(
            services,
            session_id,
            AskRepresentativeInput(
                question=(
                    f"העובד/ת בחרו בבורר את הדגם {car.commercial_name}, אך שנת הרישום של הרכב "
                    f"שלהם שונה מזו שבקטלוג ({car.registration_year}). נא לזהות את הרכב הצמוד "
                    "שלהם מהקטלוג."
                ),
                questions=[QuestionInput(bound_field=CURRENT_CAR, car_query=car.commercial_name)],
            ),
        )
        outcome |= {"car_id": car.id, "ticket_id": asked["ticket_id"]}
    store.append_event(session_id, PICKED, outcome)
    return {**outcome, "today_after": today_after(services, session_id), "comparisons": comparisons}

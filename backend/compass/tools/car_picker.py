"""The catalog picker for today's car, built by the server (item 5).

When today's car is unknown the employee is offered the catalog itself: manufacturer, then model,
then year, and always "הרכב שלי לא ברשימה" and "אין לי רכב היום". The options are built here from
the catalog, never by the model: the agent must not list manufacturers or models from its own
knowledge (it once offered Subaru and Nissan, which are not in the catalog).

The offer is an event, `current_car_offered`, carrying the options. It is appended when the
server shows something that waits for today's car (a comparison or an option set without a
diff, search_catalog), at most once while it is unanswered, and never again after the employee
said "not in the list" (the agent takes that from there) or once a representative is on it.
The employee's pick is POST /sessions/{id}/current-car (compass/tools/car_pick.py).

    current_car_offered   the options (the picker's data)
    current_car_picked    what the employee chose: {"outcome", "car_id"?, "ticket_id"?}
"""

from typing import Any

from compass.labels import car_details
from compass.tools.profile import CURRENT_CAR
from compass.tools.services import Services

NOT_IN_LIST, NO_CAR, CHECK_YEAR = "not_in_list", "no_car", "check_year"
EXTRA_CHOICES = (
    {"id": NOT_IN_LIST, "label": "הרכב שלי לא ברשימה"},
    {"id": NO_CAR, "label": "אין לי רכב היום"},
)
YEAR_CHECK = {"id": CHECK_YEAR, "label": "שנה אחרת — לבדיקת נציג"}

OFFERED, PICKED = "current_car_offered", "current_car_picked"


def picker(services: Services) -> dict[str, Any]:
    """The options, from the catalog: manufacturers (by name), each with its models, each with
    its catalog years (newest first). Every year carries the catalog car it stands for."""
    makers: dict[str, dict[str, Any]] = {}
    for car in services.ctx.catalog.values():
        maker = makers.setdefault(
            car.manufacturer_code,
            {"id": car.manufacturer_code, "label": car.manufacturer_name, "models": {}},
        )
        model = maker["models"].setdefault(
            car.commercial_name,
            {"id": car.commercial_name, "label": car.commercial_name, "years": []},
        )
        model["years"].append(
            {
                "car_id": car.id,
                "year": car.registration_year,
                "label": f"{car.registration_year} · {car_details(car.drive, car.group)}",
            }
        )
    manufacturers = []
    for maker in sorted(makers.values(), key=lambda m: m["label"]):
        models = sorted(maker["models"].values(), key=lambda m: m["label"])
        for model in models:
            model["years"].sort(key=lambda y: -y["year"])
        manufacturers.append({**maker, "models": models})
    return {
        "manufacturers": manufacturers,
        "extra": [dict(choice) for choice in EXTRA_CHOICES],
        "year_check": dict(YEAR_CHECK),
    }


def grouped_catalog(services: Services) -> list[dict[str, Any]]:
    """The whole catalog grouped by manufacturer, for search_catalog with no query: each car as
    search_catalog lists a car, numbered across the groups in order."""
    options = picker(services)
    out: list[dict[str, Any]] = []
    number = 0
    for maker in options["manufacturers"]:
        cars = []
        for model in maker["models"]:
            for year in model["years"]:
                number += 1
                car = services.ctx.catalog[year["car_id"]]
                cars.append(
                    {
                        "choice": number,
                        "car_id": car.id,
                        "name": car.commercial_name,
                        "registration_year": car.registration_year,
                        "group": car.group,
                        "drive": car.drive,
                        "details_he": car_details(car.drive, car.group),
                    }
                )
        out.append({"manufacturer": maker["label"], "cars": cars})
    return out


def current_car_unknown(services: Services, session_id: str) -> bool:
    """Today's car is not recorded and no one has been asked about it: no situation, and no
    current_car slot (a ticket pending, or a representative's answer, even "not in the
    catalog")."""
    if services.store.scenarios(session_id).get("today") is not None:
        return False
    return services.store.slots(session_id).get(CURRENT_CAR) is None


def _offer_state(services: Services, session_id: str) -> tuple[bool, bool]:
    """(an offer is on screen, the employee said their car is not in the list)."""
    on_screen = declined = False
    for event in services.store.events_after(session_id):
        if event.type == OFFERED:
            on_screen = True
        elif event.type in (PICKED, "current_situation_set"):
            on_screen = False
            declined = declined or (
                event.type == PICKED and event.payload.get("outcome") == NOT_IN_LIST
            )
    return on_screen, declined


def open_offer(services: Services, session_id: str) -> bool:
    """The picker is on the employee's screen now (offered, not answered, today still unknown)."""
    on_screen, _ = _offer_state(services, session_id)
    return on_screen and current_car_unknown(services, session_id)


def offer_current_car(services: Services, session_id: str) -> bool:
    """Offer the picker if today's car is unknown and the employee has no open offer, and has
    not said their car is not in the list. True if an offer was made now."""
    if not current_car_unknown(services, session_id):
        return False
    on_screen, declined = _offer_state(services, session_id)
    if on_screen or declined:  # the agent has "not in the list" from there; no nagging
        return False
    services.store.append_event(session_id, OFFERED, picker(services))
    return True

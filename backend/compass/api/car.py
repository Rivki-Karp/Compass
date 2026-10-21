"""The catalog picker's answer (compass/tools/car_picker.py, car_pick.py).

    POST /api/sessions/{id}/current-car   {"choice": "car" | "check_year" | "no_car" |
                                           "not_in_list", "car_id": "CAR-07" (car, check_year)}

The server applies the pick exactly as a tool call would (today's situation, the recompute of
what is on screen, or a ticket for a representative), then tells the agent, as data. A refusal
is the shape of a refused payslip: {"detail": code, "errors": [{"code", "field", "message"}]}
with a Hebrew message (compass.labels).
"""

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from compass.api.agent import AgentRunner
from compass.labels import error_message
from compass.state.accounts import User
from compass.tools.car_pick import PickRejected, pick_current_car
from compass.tools.services import Services


class CurrentCarPick(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: Literal["car", "check_year", "no_car", "not_in_list"]
    car_id: str | None = None


def add_car_routes(
    api: APIRouter,
    services: Services,
    agent: AgentRunner,
    session_access: Callable[..., User | None],
) -> None:
    @api.post(
        "/sessions/{session_id}/current-car",
        tags=["sessions"],
        dependencies=[Depends(session_access)],
        responses={
            404: {"description": "No such session"},
            409: {"description": "Today's car is known already, or a representative was asked"},
            422: {"description": "An unknown car, or a choice that does not fit"},
        },
    )
    def pick_car(session_id: str, body: CurrentCarPick) -> JSONResponse:
        """The employee's choice in the picker: a catalog car, 'no car', 'not in the list' or
        'another year, a representative checks'."""
        try:
            picked = pick_current_car(services, session_id, body.choice, body.car_id)
        except PickRejected as error:
            return JSONResponse(
                status_code=error.status,
                content={
                    "detail": error.code,
                    "errors": [
                        {
                            "code": error.code,
                            "field": None,
                            "message": error_message(error.code, {}),
                        }
                    ],
                },
            )
        agent.on_car_picked(session_id, picked)
        result: dict[str, Any] = {k: v for k, v in picked.items() if k not in ("comparisons",)}
        return JSONResponse(result)

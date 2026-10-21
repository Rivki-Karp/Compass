"""Remembered details (COMPASS_PROFILE_MEMORY=1 with COMPASS_AUTH=1; otherwise 404, and the
routes are left out of the schema). Owner only: the same ownership rule as every session route.

    POST   /api/sessions/{id}/profile/apply    {fields: [{name, action: keep|edit|drop, value?}]}
    POST   /api/sessions/{id}/profile/dismiss  "להתחיל מחדש", for this conversation only
    DELETE /api/profile                        delete the saved profile (yours)

The offer itself is the `profile_offer` event of a new conversation (compass.profile_memory). A
refusal is {"detail": code, "errors": [{"code", "field", "message"}]} with a Hebrew message, the
shape of a refused payslip.
"""

import logging
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from compass.api.agent import AgentRunner
from compass.api.settings import Settings
from compass.labels import error_message
from compass.profile_memory import (
    Choice,
    ProfileRejected,
    apply_profile,
    dismiss_profile,
)
from compass.state.accounts import User
from compass.tools.services import Services

log = logging.getLogger("compass.profile")


class ProfileChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    action: Literal["keep", "edit", "drop"]
    value: Any = Field(
        default=None, description="The value the employee typed; required for 'edit' only"
    )


class ProfileApplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[ProfileChoice] = Field(
        description="What the employee decided for each offered detail; one that is left out is "
        "not used"
    )


def rejected(error: ProfileRejected) -> JSONResponse:
    message = error_message(error.code, {})
    return JSONResponse(
        status_code=error.status,
        content={
            "detail": error.code,
            "errors": [
                {"code": error.code, "field": f, "message": message} for f in error.fields or [None]
            ],
        },
    )


def add_profile_routes(
    api: APIRouter,
    settings: Settings,
    services: Services,
    agent: AgentRunner,
    session_access: Callable[..., User | None],
    current_user: Callable[..., User] | None,
) -> None:
    on = settings.profile_memory_on
    store = services.store

    def flag() -> None:
        """First of the dependencies: with the feature off every route is a plain 404, whoever
        asks and whatever else would have been checked (a login, the session's owner)."""
        if not on:
            raise HTTPException(404, "Not Found")

    @api.post(
        "/sessions/{session_id}/profile/apply",
        tags=["profile"],
        dependencies=[Depends(flag), Depends(session_access)],
        include_in_schema=on,
        responses={
            404: {"description": "Remembered details are off, or no such session"},
            409: {"description": "No offer waits for an answer"},
            422: {"description": "A detail that was not offered, or an invalid value"},
        },
    )
    def apply(session_id: str, body: ProfileApplyBody) -> JSONResponse:
        """Use the saved details the employee confirmed: kept ones get the source 'previous'
        (the chip 'משיחה קודמת'), edited ones 'employee'. Anything already said in this
        conversation, and every representative's value, wins. The comparison on screen is
        recomputed (no model call) and the agent is told the confirmed values, as data."""
        choices = [Choice(c.name, c.action, c.value) for c in body.fields]
        try:
            applied = apply_profile(services, session_id, choices)
        except ProfileRejected as error:
            return rejected(error)
        log.info(
            "profile applied: session=%s used=%d kept_current=%d dropped=%d",
            session_id,
            len(applied.values),
            len(applied.kept_current),
            len(applied.dropped),
        )
        if applied.values:
            agent.on_profile_applied(
                session_id,
                {
                    **applied.to_dict(),
                    "today_after": applied.today_after,
                    "comparisons": applied.comparisons,
                },
            )
        return JSONResponse(applied.to_dict())

    @api.post(
        "/sessions/{session_id}/profile/dismiss",
        tags=["profile"],
        dependencies=[Depends(flag), Depends(session_access)],
        include_in_schema=on,
        status_code=204,
        responses={
            404: {"description": "Remembered details are off, or no such session"},
            409: {"description": "No offer waits for an answer"},
        },
    )
    def dismiss(session_id: str) -> Response:
        """ "להתחיל מחדש": for this conversation only. Nothing is deleted."""
        try:
            dismiss_profile(services, session_id)
        except ProfileRejected as error:
            return rejected(error)
        return Response(status_code=204)

    if current_user is None:  # accounts off: there is nobody to own a profile

        @api.delete("/profile", tags=["profile"], include_in_schema=False, status_code=204)
        def no_profile() -> Response:
            raise HTTPException(404, "Not Found")

        return

    @api.delete(
        "/profile",
        tags=["profile"],
        dependencies=[Depends(flag)],
        status_code=204,
        include_in_schema=on,
        responses={404: {"description": "Remembered details are off"}},
    )
    def delete_profile(user: Annotated[User, Depends(current_user)]) -> Response:
        """Delete the saved details of the logged-in account, for good."""
        if store.delete_profile(user.id):
            log.info("profile deleted: user=%s", user.id)
        return Response(status_code=204)

"""The user's own conversations (COMPASS_AUTH=1; off: the routes do not exist).

    GET    /api/conversations                 their list, newest first
                                              {id, title, updated_at, status, diff}
    DELETE /api/conversations/{session_id}    delete one, and all it holds

Opening a conversation needs no route of its own: the snapshot and the event replay of
/api/sessions/{id} (the same ownership rule) restore it exactly where it stopped, from any browser
that is logged in as the owner.

The title is built here, from the state, never by the model. `diff` and `status` are read from the
`view` the UI already shows (the latest comparison's stored view); nothing is recomputed. Delete
records nothing about the content.
"""

import logging
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from compass.api.broker import TICKETS, Broker
from compass.state import Store
from compass.state.accounts import User

log = logging.getLogger("compass.conversations")

NEW_CONVERSATION_HE = "שיחה חדשה"
ALL_OPTIONS_HE = "כל החלופות"

Status = Literal["final", "pending", "partial", "none"]


class ConversationEntry(BaseModel):
    id: str
    title: str
    updated_at: str
    status: Status
    # the diff on the hero (whole ILS, signed by the UI); None: none yet, or a set of options
    diff: int | None


def _status(views: list[dict[str, Any]]) -> Status:
    if not views:
        return "none"
    if any(v.get("pending") for v in views):
        return "pending"
    if any(v.get("partial") for v in views):
        return "partial"
    return "final"


def summarize(row: dict[str, Any]) -> ConversationEntry:
    """A list entry from a session's latest comparison, option set and pending options request:
    whichever came last is what the conversation is about."""
    latest: dict[str, tuple[int, Any]] = row["latest"]
    last = max(latest, key=lambda kind: latest[kind][0], default=None)
    title, views, diff = NEW_CONVERSATION_HE, [], None
    if last == "comparison_ready":
        view = latest[last][1].get("view") or {}
        views = [view]
        diff = view.get("display_diff")
        alternative = view.get("alternative_title") or ""
        today = view.get("today_title") or ""
        if view.get("alternative_kind") == "waiver" or not today:
            title = alternative or NEW_CONVERSATION_HE
        else:
            title = f"{today} מול {alternative}"
    elif last == "comparison_set_ready":
        views = [o.get("view") or {} for o in latest[last][1].get("options", [])]
        group = next((v["group_label"] for v in views if v.get("group_label")), None)
        title = ALL_OPTIONS_HE if group is None else f"{ALL_OPTIONS_HE} ב{group}"
    elif last == "options_requested":
        title = ALL_OPTIONS_HE
        return ConversationEntry(
            id=row["id"], title=title, updated_at=row["updated_at"], status="pending", diff=None
        )
    return ConversationEntry(
        id=row["id"],
        title=title,
        updated_at=row["updated_at"],
        status=_status(views),
        diff=diff,
    )


def add_conversation_routes(
    api: APIRouter,
    store: Store,
    broker: Broker,
    current_user: Callable[..., User],
    session_access: Callable[..., User | None],
) -> None:
    @api.get("/conversations", response_model=list[ConversationEntry], tags=["conversations"])
    def list_conversations(
        user: Annotated[User, Depends(current_user)],
    ) -> list[ConversationEntry]:
        """The logged-in user's own conversations, newest first. An empty one is titled
        "שיחה חדשה"; the title comes from the state, never from the model."""
        return [summarize(row) for row in store.conversation_rows(user.id)]

    @api.delete(
        "/conversations/{session_id}",
        status_code=204,
        tags=["conversations"],
        responses={404: {"description": "Not yours, or no such conversation"}},
    )
    def delete_conversation(
        session_id: str, user: Annotated[User | None, Depends(session_access)]
    ) -> Response:
        """Delete a conversation: its messages, events, profile, scenarios and tickets (the
        representative's inbox loses them). Owner only; nothing about its content is recorded."""
        if store.delete_session(session_id):
            broker.wake(session_id, TICKETS)  # an open stream ends; the inbox drops its tickets
            log.info("conversation deleted: user=%s", None if user is None else user.id)
        return Response(status_code=204)

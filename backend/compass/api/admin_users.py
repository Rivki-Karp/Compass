"""The admin manages access, and only access (COMPASS_AUTH=1; off: the routes do not exist).

    GET    /api/admin/users           id, email, name, role, status, created, last login
    POST   /api/admin/invites         {email, role} -> the one-time code, shown once
    PATCH  /api/admin/users/{id}      {role?, status?}
    DELETE /api/admin/users/{id}      the user, their login sessions and all their conversations

Nothing here carries a conversation, a profile or a payslip: the response models below are the
whole of what an admin can read about a person, and a test holds them to it. The guards keep the
service reachable: an admin cannot disable, demote or delete themselves, and the last active admin
cannot be removed. Logs name users by id, never by email, and never log a code.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from compass.api.auth import Auth
from compass.api.broker import TICKETS, Broker
from compass.api.settings import Settings
from compass.auth.emails import normalize_email
from compass.state import Store
from compass.state.accounts import Accounts, LastAdminError, User

log = logging.getLogger("compass.admin")

Role = Literal["employee", "rep", "admin"]
Status = Literal["active", "disabled"]

EXISTS_HE = "כבר קיים משתמש עם המייל הזה. כדי להזמין מחדש, מחקו אותו קודם."
BAD_EMAIL_HE = "כתובת המייל אינה תקינה"
SELF_HE = "אי אפשר לשנות, להשבית או למחוק את החשבון של עצמך"
LAST_ADMIN_HE = "זה המנהל האחרון. אי אפשר להסיר אותו, להשבית אותו או להוריד את ההרשאה שלו"


class AdminUser(BaseModel):
    """What an admin may know of a person. Deliberately short."""

    id: str
    email: str
    name: str
    role: Role
    status: Status
    created_at: str
    last_login_at: str | None


class InviteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    role: Role


class InviteCreated(BaseModel):
    code: str = Field(description="XXXXX-XXXXX. Shown this once; only its hash is stored.")
    email: str
    role: Role
    expires_at: str


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role | None = None
    status: Status | None = None


def _public(user: User) -> AdminUser:
    return AdminUser(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _refused(message: str, status: int = 409) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": message})


def add_admin_user_routes(
    api: APIRouter,
    settings: Settings,
    auth: Auth,
    accounts: Accounts,
    store: Store,
    broker: Broker,
) -> None:
    admin = auth.require_role("admin")

    @api.get("/admin/users", response_model=list[AdminUser], tags=["admin"])
    def list_users(_: Annotated[User, Depends(admin)]) -> list[AdminUser]:
        """Every account: id, email, name, role, status, created and last login. Nothing else."""
        return [_public(u) for u in accounts.list_users()]

    @api.post(
        "/admin/invites",
        status_code=201,
        response_model=InviteCreated,
        tags=["admin"],
        responses={409: {"description": "A user with this email exists: delete them first"}},
    )
    def create_invite(
        body: InviteBody, actor: Annotated[User, Depends(admin)]
    ) -> InviteCreated | JSONResponse:
        """A one-time invite code for this email and role (replacing an unused one). The code is
        in this response only. Re-inviting an existing user is refused: delete the user first."""
        email = normalize_email(body.email)
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            return _refused(BAD_EMAIL_HE, 422)
        if accounts.user_by_email(email) is not None:
            return _refused(EXISTS_HE)
        code, expires_at = accounts.issue_invite(
            email, body.role, actor.id, settings.invite_ttl_hours
        )
        log.info("invite created: by=%s role=%s", actor.id, body.role)
        return InviteCreated(code=code, email=email, role=body.role, expires_at=expires_at)

    @api.patch(
        "/admin/users/{user_id}",
        response_model=AdminUser,
        tags=["admin"],
        responses={404: {"description": "No such user"}, 409: {"description": "A guard refused"}},
    )
    def patch_user(
        user_id: str, body: UserPatch, actor: Annotated[User, Depends(admin)]
    ) -> AdminUser | JSONResponse:
        """Change a role and/or a status. Not your own, and never the last active admin. A
        disabled user's logins end at once."""
        target = accounts.user_by_id(user_id)
        if target is None:
            raise HTTPException(404, "no such user")
        if target.id == actor.id:
            return _refused(SELF_HE)
        try:
            updated = accounts.update_user(user_id, body.role, body.status)
        except LastAdminError:
            return _refused(LAST_ADMIN_HE)
        if updated is None:
            raise HTTPException(404, "no such user")
        log.info("user changed: by=%s user=%s", actor.id, user_id)
        return _public(updated)

    @api.delete(
        "/admin/users/{user_id}",
        status_code=204,
        tags=["admin"],
        responses={404: {"description": "No such user"}, 409: {"description": "A guard refused"}},
    )
    def delete_user(user_id: str, actor: Annotated[User, Depends(admin)]) -> Response:
        """Delete a user, their logins, their invites and every conversation of theirs (as
        deleting a conversation does). Not yourself, and never the last active admin. There is no
        password reset: this, and a new invite, is how someone gets back in."""
        target = accounts.user_by_id(user_id)
        if target is None:
            raise HTTPException(404, "no such user")
        if target.id == actor.id:
            return _refused(SELF_HE)
        # the account and its logins first: from here no token of theirs works, so no new
        # conversation can appear while the old ones are removed
        try:
            deleted = accounts.delete_user(user_id)
        except LastAdminError:
            return _refused(LAST_ADMIN_HE)
        if not deleted:
            raise HTTPException(404, "no such user")
        sessions = store.owned_session_ids(user_id)
        for session_id in sessions:
            store.delete_session(session_id)
        broker.wake(TICKETS, *sessions)
        log.info("user deleted: by=%s user=%s conversations=%d", actor.id, user_id, len(sessions))
        return Response(status_code=204)

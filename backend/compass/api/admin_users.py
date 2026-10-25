"""The admin manages access, and only access (COMPASS_AUTH=1; off: the routes do not exist).

    GET    /api/admin/users           id, email, name, role, status, created, last login
    POST   /api/admin/invites         {email, role} -> the one-time code, shown once
    PATCH  /api/admin/users/{id}      {role?, status?}
    DELETE /api/admin/users/{id}      the user, their login sessions and all their conversations

Nothing here carries a conversation, a profile or a payslip: the response models below are the
whole of what an admin can read about a person, and a test holds them to it. The guards keep the
service reachable: an admin cannot disable, demote or delete themselves, and the last active admin
cannot be removed. Logs name users by id, never by email, and never log a code.

With COMPASS_DEMO_LOGIN=1 (off: none of this exists), the shared demo accounts are protected and
the demo is walled off from the real users:

* a demo account cannot be deleted, disabled or given another role, by anyone;
* a demo session (a login from the quick access, or a login of a demo account) lists and manages
  only the demo accounts and the accounts invited from a demo session (`demo_origin`); any other
  account is a 404 to it and never in a response. Its invites are employee or rep only (the admin
  password is what judges mode asks for, so a demo session must not be able to make an admin),
  capped per UTC day, and cannot say whether an email belongs to a real user or a pending invite.
"""

import logging
import threading
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
DEMO_PROTECTED_HE = "זה חשבון הדגמה משותף. אי אפשר למחוק אותו, להשבית אותו או לשנות את התפקיד שלו"
DEMO_INVITE_ROLE_HE = "מחשבון הדגמה אפשר להזמין עובדים ונציגים בלבד"
DEMO_INVITE_REFUSED_HE = "אי אפשר להזמין את המייל הזה"
DEMO_INVITE_CAP_HE = "הגענו למכסת ההזמנות היומית של חשבונות ההדגמה. נסו שוב מחר"


class AdminUser(BaseModel):
    """What an admin may know of a person. Deliberately short."""

    id: str
    email: str
    name: str
    role: Role
    status: Status
    created_at: str
    last_login_at: str | None
    # only with COMPASS_DEMO_LOGIN=1 (off: not in the response): a protected shared demo account
    demo: bool | None = None


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


def _public(user: User, with_demo: bool = False) -> AdminUser:
    return AdminUser(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        **({"demo": user.demo} if with_demo else {}),
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
    demo_on = settings.demo_login_on
    demo_invites = threading.Lock()  # the daily cap is counted and spent in one step

    def demo_scope(actor: User, token: str) -> bool:
        """Whether this admin sees the demo only: a login from the quick access, or a login of
        a demo account itself (so its password, once known, opens no wider a view)."""
        return demo_on and (actor.demo or accounts.session_flags(token).demo)

    def reachable(target: User, scoped: bool) -> bool:
        return not scoped or target.demo or target.demo_origin

    @api.get(
        "/admin/users",
        response_model=list[AdminUser],
        response_model_exclude_unset=True,
        tags=["admin"],
    )
    def list_users(
        actor: Annotated[User, Depends(admin)], token: Annotated[str, Depends(auth.bearer)]
    ) -> list[AdminUser]:
        """Every account: id, email, name, role, status, created and last login. Nothing else.
        A demo session sees the demo accounts and those invited from a demo session only."""
        users = (
            accounts.list_demo_scope_users() if demo_scope(actor, token) else accounts.list_users()
        )
        return [_public(u, demo_on) for u in users]

    @api.post(
        "/admin/invites",
        status_code=201,
        response_model=InviteCreated,
        tags=["admin"],
        responses={409: {"description": "A user with this email exists: delete them first"}},
    )
    def create_invite(
        body: InviteBody,
        actor: Annotated[User, Depends(admin)],
        token: Annotated[str, Depends(auth.bearer)],
    ) -> InviteCreated | JSONResponse:
        """A one-time invite code for this email and role (replacing an unused one). The code is
        in this response only. Re-inviting an existing user is refused: delete the user first."""
        email = normalize_email(body.email)
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            return _refused(BAD_EMAIL_HE, 422)
        if demo_scope(actor, token):
            return _demo_invite(body, email, actor)
        if accounts.user_by_email(email) is not None:
            return _refused(EXISTS_HE)
        code, expires_at = accounts.issue_invite(
            email, body.role, actor.id, settings.invite_ttl_hours
        )
        log.info("invite created: by=%s role=%s", actor.id, body.role)
        return InviteCreated(code=code, email=email, role=body.role, expires_at=expires_at)

    def _demo_invite(body: InviteBody, email: str, actor: User) -> InviteCreated | JSONResponse:
        """An invite from a demo session: no admin, capped, and one refusal for every email it
        cannot use (a user, in or out of the demo, or a real pending invite), so it tells nothing
        about the real users."""
        if body.role == "admin":
            return _refused(DEMO_INVITE_ROLE_HE, 403)
        with demo_invites:
            if accounts.demo_invites_today() >= settings.demo_invites_per_day:
                return _refused(DEMO_INVITE_CAP_HE, 429)
            if accounts.user_by_email(email) is not None or accounts.unused_invite_is_not_demo(
                email
            ):
                return _refused(DEMO_INVITE_REFUSED_HE)
            code, expires_at = accounts.issue_invite(
                email, body.role, actor.id, settings.invite_ttl_hours, demo_origin=True
            )
        log.info("invite created: by=%s role=%s demo=1", actor.id, body.role)
        return InviteCreated(code=code, email=email, role=body.role, expires_at=expires_at)

    @api.patch(
        "/admin/users/{user_id}",
        response_model=AdminUser,
        response_model_exclude_unset=True,
        tags=["admin"],
        responses={404: {"description": "No such user"}, 409: {"description": "A guard refused"}},
    )
    def patch_user(
        user_id: str,
        body: UserPatch,
        actor: Annotated[User, Depends(admin)],
        token: Annotated[str, Depends(auth.bearer)],
    ) -> AdminUser | JSONResponse:
        """Change a role and/or a status. Not your own, and never the last active admin. A
        disabled user's logins end at once. Not a demo account's role or status."""
        target = accounts.user_by_id(user_id)
        if target is None or not reachable(target, demo_scope(actor, token)):
            raise HTTPException(404, "no such user")
        if target.id == actor.id:
            return _refused(SELF_HE)
        if (
            demo_on
            and target.demo
            and (body.status == "disabled" or body.role not in (None, target.role))
        ):
            return _refused(DEMO_PROTECTED_HE)
        try:
            updated = accounts.update_user(user_id, body.role, body.status)
        except LastAdminError:
            return _refused(LAST_ADMIN_HE)
        if updated is None:
            raise HTTPException(404, "no such user")
        log.info("user changed: by=%s user=%s", actor.id, user_id)
        return _public(updated, demo_on)

    @api.delete(
        "/admin/users/{user_id}",
        status_code=204,
        tags=["admin"],
        responses={404: {"description": "No such user"}, 409: {"description": "A guard refused"}},
    )
    def delete_user(
        user_id: str,
        actor: Annotated[User, Depends(admin)],
        token: Annotated[str, Depends(auth.bearer)],
    ) -> Response:
        """Delete a user, their logins, their invites and every conversation of theirs (as
        deleting a conversation does). Not yourself, and never the last active admin. There is no
        password reset: this, and a new invite, is how someone gets back in. Never a demo
        account."""
        target = accounts.user_by_id(user_id)
        if target is None or not reachable(target, demo_scope(actor, token)):
            raise HTTPException(404, "no such user")
        if target.id == actor.id:
            return _refused(SELF_HE)
        if demo_on and target.demo:
            return _refused(DEMO_PROTECTED_HE)
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
        store.delete_profile(user_id)  # the saved details go with the account
        broker.wake(TICKETS, *sessions)
        log.info("user deleted: by=%s user=%s conversations=%d", actor.id, user_id, len(sessions))
        return Response(status_code=204)

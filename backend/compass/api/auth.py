"""Accounts (COMPASS_AUTH=1): register with an invite code, log in, log out, who am I.

    POST /api/auth/register  {email, code, name, password}  -> 201 {token, name, role}
    POST /api/auth/login     {email, password}              -> 200 {token, name, role}
    POST /api/auth/logout                                   -> 204
    GET  /api/auth/me                                       -> {name, role}

Off (the default) these routes are not registered: they answer 404 and are not in the schema. The
token goes in `Authorization: Bearer` (no cookie, so no CSRF surface); it is shown once, here.

No failure says why. Every register failure (no invite, wrong code, expired, used, replaced, a bad
name or password) is the same status and body, so the endpoint cannot be used to find out which
emails are invited; every login failure (no such email, wrong password, a disabled account) is
the same, and an invented email takes the same time as a real one (a dummy hash is verified).
After repeated failures an email is locked, whether or not it exists, with the same message and a
hint, never when or for how long. Nothing here logs an email, a password, a code or a token.
"""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from compass.api.ratelimit import RateLimiter, client_ip
from compass.api.settings import Settings
from compass.auth.codes import normalize_code
from compass.auth.emails import normalize_email
from compass.auth.limits import LoginGuard
from compass.auth.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    dummy_hash,
    hash_password,
    verify_password,
)
from compass.auth.seed import MAX_NAME_LENGTH
from compass.state.accounts import Accounts, User

log = logging.getLogger("compass.auth")

REGISTER_ERROR_HE = "הקוד או המייל אינם תקינים"
LOGIN_ERROR_HE = "מייל או סיסמה שגויים"
RETRY_HINT_HE = "נסו שוב בעוד כמה דקות"

# What a client may send; longer is refused before any hashing (a bound on the work per request)
MAX_EMAIL_INPUT = 254
MAX_PASSWORD_INPUT = 1024


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterBody(_Body):
    email: str = Field(max_length=MAX_EMAIL_INPUT)
    code: str = Field(max_length=64)
    name: str = Field(max_length=200)
    password: str = Field(max_length=MAX_PASSWORD_INPUT, repr=False)


class LoginBody(_Body):
    email: str = Field(max_length=MAX_EMAIL_INPUT)
    password: str = Field(max_length=MAX_PASSWORD_INPUT, repr=False)


class Granted(BaseModel):
    token: str
    name: str
    role: str


class Me(BaseModel):
    name: str
    role: str


class Auth:
    """What the routes of other modules need: the current user, and role guards."""

    def __init__(self, accounts: Accounts) -> None:
        self.accounts = accounts
        self._scheme = HTTPBearer(auto_error=False, scheme_name="Session")

        def bearer(
            credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(self._scheme)],
        ) -> str:
            if credentials is None or not credentials.credentials:
                raise _unauthorized()
            return credentials.credentials

        def current_user(token: Annotated[str, Depends(bearer)]) -> User:
            user = accounts.user_for_token(token)
            if user is None:
                raise _unauthorized()
            return user

        self.bearer = bearer
        self.current_user = current_user

    def require_role(self, *roles: str) -> Callable[..., User]:
        """Dependency: the logged-in user if their role is one of `roles`, else 403 (401 when
        not logged in)."""
        allowed = frozenset(roles)

        def guard(user: Annotated[User, Depends(self.current_user)]) -> User:
            if user.role not in allowed:
                raise HTTPException(403, "this role may not use this route")
            return user

        return guard


def _unauthorized() -> HTTPException:
    return HTTPException(
        401, "missing, invalid or expired session", headers={"WWW-Authenticate": "Bearer"}
    )


def _refusal(status: int, message: str, retry_after: int | None = None) -> JSONResponse:
    headers = None if retry_after is None else {"Retry-After": str(retry_after)}
    return JSONResponse(status_code=status, content={"detail": message}, headers=headers)


def _acceptable(email: str, name: str, password: str) -> bool:
    """The register rules that do not depend on the invite: an email address, a name of 1 to 60
    characters, a password of 10 to 128 that is not the email."""
    return (
        "@" in email
        and 1 <= len(name) <= MAX_NAME_LENGTH
        and MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
        and normalize_email(password) != email
    )


def add_auth_routes(api: APIRouter, settings: Settings, auth: Auth, guard: LoginGuard) -> None:
    accounts = auth.accounts
    register_limiter = RateLimiter(settings.login_per_ip_per_minute)
    dummy_hash()  # computed now, not inside the first login for an invented email

    @api.post(
        "/auth/register",
        status_code=201,
        response_model=Granted,
        tags=["auth"],
        responses={
            400: {"description": "The same message for every reason: the code or email is invalid"},
            429: {"description": "Too many attempts from this IP (Retry-After)"},
        },
    )
    def register(body: RegisterBody, request: Request) -> Granted | JSONResponse:
        """Register with an invite: the email it was sent to, its one-time code, your own name
        and a password (10 to 128 characters). Logs you in."""
        wait = register_limiter.check(client_ip(request, settings.trust_proxy))
        if wait is not None:
            return _refusal(429, f"{REGISTER_ERROR_HE}. {RETRY_HINT_HE}", wait)
        email, name = normalize_email(body.email), body.name.strip()
        if not _acceptable(email, name, body.password):
            return _refusal(400, REGISTER_ERROR_HE)
        # hashed whether or not the invite turns out valid: the same time either way
        password_hash = hash_password(body.password)
        granted = accounts.register(
            email, normalize_code(body.code), name, password_hash, settings.session_ttl_hours
        )
        if granted is None:
            return _refusal(400, REGISTER_ERROR_HE)
        log.info("registered: user=%s role=%s", granted.user.id, granted.user.role)
        return Granted(token=granted.token, name=granted.user.name, role=granted.user.role)

    @api.post(
        "/auth/login",
        response_model=Granted,
        tags=["auth"],
        responses={
            401: {"description": "The same message for every reason"},
            429: {"description": "Too many attempts, or the email is locked: the same message"},
        },
    )
    def login(body: LoginBody, request: Request) -> Granted | JSONResponse:
        """Log in. The error is always the same; after repeated failures an email is locked for a
        while, with the same message and a hint to try again later."""
        wait = guard.check_ip(client_ip(request, settings.trust_proxy))
        email = normalize_email(body.email)
        if wait is not None:
            return _refusal(429, f"{LOGIN_ERROR_HE}. {RETRY_HINT_HE}", wait)
        if guard.is_locked(email):
            log.info("login refused: locked")
            return _refusal(429, f"{LOGIN_ERROR_HE}. {RETRY_HINT_HE}")
        user = accounts.user_by_email(email)
        # an invented email verifies against a dummy hash: the same time as a wrong password
        correct = verify_password(user.password_hash if user else dummy_hash(), body.password)
        if user is None or user.status != "active" or not correct:
            guard.record_failure(email)
            log.info("login refused")
            return _refusal(401, LOGIN_ERROR_HE)
        guard.record_success(email)
        accounts.record_login(user.id)
        token = accounts.open_session(user.id, settings.session_ttl_hours)
        log.info("login: user=%s", user.id)
        return Granted(token=token, name=user.name, role=user.role)

    @api.post("/auth/logout", status_code=204, tags=["auth"])
    def logout(
        token: Annotated[str, Depends(auth.bearer)],
        user: Annotated[User, Depends(auth.current_user)],
    ) -> Response:
        """End this login session (the token stops working at once)."""
        accounts.revoke_token(token)
        log.info("logout: user=%s", user.id)
        return Response(status_code=204)

    @api.get("/auth/me", response_model=Me, tags=["auth"])
    def me(user: Annotated[User, Depends(auth.current_user)]) -> Me:
        """Who the token belongs to: just the name and the role."""
        return Me(name=user.name, role=user.role)

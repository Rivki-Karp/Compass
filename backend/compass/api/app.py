"""FastAPI app factory. All routes under /api.

uv run python tasks.py serve     # uvicorn with reload, http://127.0.0.1:8000/docs
"""

import asyncio
import hashlib
import hmac
import json
import logging
import sqlite3
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.concurrency import run_in_threadpool

from compass.api.admin_users import add_admin_user_routes
from compass.api.agent import AgentRunner
from compass.api.auth import Auth, add_auth_routes, mark_guard
from compass.api.broker import TICKETS, Broker
from compass.api.car import add_car_routes
from compass.api.conversations import add_conversation_routes, delete_empty_conversations
from compass.api.payslip import add_payslip_routes
from compass.api.profile import add_profile_routes
from compass.api.ratelimit import RateLimiter, client_ip
from compass.api.redact import public_message, public_payload
from compass.api.settings import Settings, token_warnings
from compass.api.spa import mount_spa
from compass.api.stats import judges_stats
from compass.auth.codes import hash_secret
from compass.auth.limits import LoginGuard
from compass.config import CATALOG_JSON, OCCUPATIONS_JSON
from compass.engine.context import ContextError
from compass.engine.serialize import plain_json
from compass.labels import error_message
from compass.payslip.service import build_service
from compass.payslip.upload import MAGIC as PAYSLIP_TYPES
from compass.profile_memory import offer_new_conversation
from compass.rules import RulesError
from compass.state import NotFound, Store
from compass.state.accounts import Accounts, User
from compass.state.store import Memory
from compass.tools import ToolRunner
from compass.tools.services import Services
from compass.tools.tickets import QuestionAnswer, TicketAnswerError
from compass.tools.tickets import answer_ticket as answer_ticket_with_rules
from compass.tools.view import build_ticket_view

# Streams pass through a platform's reverse proxy (Render) unbuffered and uncached.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionCreated(BaseModel):
    id: str


class UserMessage(_Body):
    text: str = Field(min_length=1, max_length=4000)


class MessageAccepted(BaseModel):
    message_seq: int


class QuestionAnswerBody(_Body):
    value: Any = Field(
        None,
        description=(
            "amount: whole ILS; choice: an option's value; yes_no: yes / no; text: the answer. "
            "None with status needs_checking"
        ),
    )
    status: Literal["answered", "needs_checking"] = Field(
        "answered", description="needs_checking: the question stays pending (with the note)"
    )
    note: str | None = Field(None, max_length=1000)


class TicketAnswer(_Body):
    answer_text: str | None = Field(None, max_length=4000)
    quick_answer_id: str | None = None
    values: dict[str, Any] = Field(default_factory=dict, description="Tool field -> value")
    answers: dict[str, QuestionAnswerBody] = Field(
        default_factory=dict,
        description="Question id (the ticket view's questions[].id) -> its answer in this part",
    )
    effective_from: date | None = Field(
        None, description="When a participation amount takes effect (participation fields only)"
    )
    partial: bool = Field(
        False,
        description=(
            "Answer only the fields given in `values`; the others stay pending and the ticket "
            "stays open (the answer that fills the last one closes it). Default: the fields "
            "left out become unknown and the ticket closes."
        ),
    )


log = logging.getLogger(__name__)


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _vehicles_meta(path: Path) -> dict[str, str]:
    try:
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        try:
            return dict(conn.execute("SELECT key, value FROM meta").fetchall())
        finally:
            conn.close()
    except sqlite3.Error:
        return {}


def _token_guard(
    expected: str | None, scheme: HTTPBearer, role: str, env_var: str
) -> Callable[..., None]:
    """Dependency: `Authorization: Bearer <token>`. Unconfigured -> 503, wrong -> 401."""

    def check(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(scheme)],
    ) -> None:
        if not expected:
            raise HTTPException(503, f"{role} access is not configured (set {env_var})")
        given = "" if credentials is None else credentials.credentials
        if not hmac.compare_digest(given.encode(), expected.encode()):
            raise HTTPException(
                401, f"missing or invalid {role} token", headers={"WWW-Authenticate": "Bearer"}
            )

    return check


def _optional_token(
    expected: str | None, scheme: HTTPBearer, role: str, env_var: str
) -> Callable[..., bool]:
    """Dependency: True with a valid `Authorization: Bearer <token>`, False without one. A token
    that is given but wrong is an error (401), never a silent downgrade; unconfigured -> 503."""

    def check(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(scheme)],
    ) -> bool:
        if credentials is None:
            return False
        if not expected:
            raise HTTPException(503, f"{role} access is not configured (set {env_var})")
        if not hmac.compare_digest(credentials.credentials.encode(), expected.encode()):
            raise HTTPException(
                401, f"missing or invalid {role} token", headers={"WWW-Authenticate": "Bearer"}
            )
        return True

    return check


AgentFactory = Callable[[Settings, Services, ToolRunner], AgentRunner]


def create_app(
    settings: Settings | None = None,
    agent: AgentRunner | None = None,
    agent_factory: AgentFactory | None = None,
) -> FastAPI:
    """`agent` replaces the agent outright; `agent_factory` builds it on the app's own services
    (tests plug a scripted model in this way). Default: Claude if a key is set, else none."""
    settings = Settings.from_env() if settings is None else settings
    if not settings.auth:  # with accounts the static tokens are refused: nothing to warn about
        for warning in token_warnings(settings.rep_token, settings.admin_token):
            log.warning(warning)
    store = Store(settings.app_db)
    accounts = Accounts(store)
    if settings.auth:
        # the demo accounts survive every deploy: re-created from the environment at each start
        log.info("accounts: %d seed users upserted", accounts.seed(settings.seed_users))
    services = Services(
        store,
        rules_path=settings.rules_path,
        aliases_path=settings.aliases_path,
        vehicles_db=settings.vehicles_db,
    )
    if settings.profile_memory_on:
        # confirmed details of an account's conversations are also saved in its profile
        store.memory = Memory(
            catalog_year=lambda car_id: (
                car.registration_year if (car := services.ctx.catalog.get(car_id)) else None
            )
        )
    runner = ToolRunner(services)
    broker = Broker()
    store.subscribers.append(broker.publish)
    if agent is None and agent_factory is not None:
        agent = agent_factory(settings, services, runner)
    if agent is None:
        from compass.agent.factory import build_agent  # the agent layer sits above the API

        agent = build_agent(settings, services, runner)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        broker.bind(asyncio.get_running_loop())
        yield
        close = getattr(agent, "close", None)
        if close is not None:
            await run_in_threadpool(close)  # let in-flight agent runs finish

    app = FastAPI(
        title="Compass API",
        version="0.2.0",
        description="Company-car net-salary assistant: sessions, tools, tickets, live events.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        # (PATCH, DELETE: conversations and the admin's user management, only with accounts on)
        allow_methods=["GET", "POST", "PATCH", "DELETE"] if settings.auth else ["GET", "POST"],
        # Content-Type: the JSON bodies; Last-Event-ID: an SSE stream resuming (frontend sse.ts)
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )
    app.state.settings = settings
    app.state.accounts = accounts
    auth: Auth | None = None
    if settings.auth:
        auth = Auth(accounts)
        app.state.auth = auth
        app.state.login_guard = LoginGuard(
            settings.login_per_ip_per_minute,
            settings.login_max_failures,
            settings.login_lock_minutes * 60,
            settings.login_email_ceiling,
            settings.login_email_window_minutes * 60,
        )

        @app.exception_handler(RequestValidationError)
        async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
            """A malformed request body. For /api/auth the default answer is not used: it echoes
            the offending input back, and that input can be a password."""
            if not request.url.path.startswith("/api/auth/"):
                return await request_validation_exception_handler(request, error)
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {"type": e["type"], "loc": e["loc"], "msg": e["msg"]}
                        for e in error.errors()
                    ]
                },
            )

    app.state.services = services
    app.state.runner = runner
    app.state.agent = agent
    # the payslip upload's extraction; None when the flag is off (or live mode has no key)
    app.state.payslip = build_service(settings, store)
    api = APIRouter(prefix="/api")
    messages_limiter = RateLimiter(settings.message_rate_per_minute)
    user_messages_limiter = RateLimiter(settings.message_rate_per_minute)

    def require_session(session_id: str) -> None:
        try:
            store.session_status(session_id)
        except NotFound:
            raise HTTPException(404, f"session {session_id} not found") from None

    # --- who may do what ------------------------------------------------------------------
    # Accounts off: the static rep and admin tokens, and sessions that anyone with the id may
    # use, exactly as before. Accounts on (COMPASS_AUTH=1): the static tokens are not consulted at
    # all (they are just invalid logins), the rep and admin routes need that role, and every
    # route that names a session goes through `session_access`, the one ownership rule.
    session_access: Callable[..., User | None]
    session_creator: Callable[..., User | None]
    stream_token: Callable[..., str | None]
    if auth is None:
        rep_only = Depends(
            _token_guard(
                settings.rep_token,
                HTTPBearer(auto_error=False, scheme_name="RepToken"),
                "representative",
                "COMPASS_REP_TOKEN",
            )
        )
        admin_only = Depends(
            _token_guard(
                settings.admin_token,
                HTTPBearer(auto_error=False, scheme_name="AdminToken"),
                "admin",
                "COMPASS_ADMIN_TOKEN",
            )
        )
        full_view = _optional_token(
            settings.admin_token,
            HTTPBearer(auto_error=False, scheme_name="AdminToken"),
            "admin",
            "COMPASS_ADMIN_TOKEN",
        )

        def session_access(session_id: str) -> None:
            require_session(session_id)

        def session_creator() -> None:
            return None

        def stream_token() -> None:
            return None

    else:
        # the representative's routes: rep only. The admin never sees an employee's data, so for
        # anyone else logged in the routes do not exist (404)
        rep_only = Depends(auth.require_role("rep", hidden=True))
        if settings.judges_unlock_on:
            # its own counts and locks: a wrong admin password never touches a login's. Per IP
            # per minute, and per (user, IP) after max_failures; no ceiling per user over all
            # addresses: on the shared demo employee it would let anyone lock every judge out.
            app.state.judges_guard = LoginGuard(
                settings.login_per_ip_per_minute,
                settings.login_max_failures,
                settings.login_lock_minutes * 60,
                email_ceiling=sys.maxsize,
                email_window_seconds=settings.login_email_window_minutes * 60,
            )
        admin_only = Depends(auth.require_role("admin"))
        stream_token = auth.bearer
        session_creator = auth.current_user

        def session_access(
            session_id: str, user: Annotated[User, Depends(auth.current_user)]
        ) -> User:
            """The ownership rule: the logged-in user must be the session's owner. Anyone else,
            and a session nobody owns or that does not exist, gets the same 404: whether a
            session exists is never told. (Not logged in: 401, before the session is looked at.)"""
            try:
                owner = store.session_owner(session_id)
            except NotFound:
                owner = None
            if owner is None or owner != user.id:
                raise HTTPException(404, f"session {session_id} not found")
            return user

        mark_guard(session_access, "owner")

        def full_view(
            user: Annotated[User, Depends(session_access)],
            token: Annotated[str, Depends(auth.bearer)],
        ) -> bool:
            """Judges mode's engine room: an admin, or a login the admin password unlocked
            (COMPASS_JUDGES_UNLOCK), in a session that is their own (session_access)."""
            if user.role == "admin":
                return True
            return settings.judges_unlock_on and accounts.session_flags(token).judges_unlocked

    IsAdmin = Annotated[bool, Depends(full_view)]
    SessionUser = Annotated[User | None, Depends(session_access)]
    accounts_on = auth is not None

    def still_logged_in(token: str | None) -> bool:
        """An open stream re-checks its login: a logout, a disabling or the 8 hours end it."""
        return not accounts_on or (token is not None and accounts.user_for_token(token) is not None)

    # --- sessions -------------------------------------------------------------------------

    @api.post("/sessions", status_code=201, response_model=SessionCreated, tags=["sessions"])
    def create_session(
        owner: Annotated[User | None, Depends(session_creator)],
        token: Annotated[str | None, Depends(stream_token)],
    ) -> SessionCreated:
        # with accounts: needs a login, and the conversation belongs to that user; the other empty
        # ones of this same login go (the new one replaces them)
        if owner is None or token is None:
            return SessionCreated(id=store.create_session(None))
        delete_empty_conversations(store, broker, owner.id, token)
        session_id = store.create_session(owner.id, hash_secret(token))
        if settings.profile_memory_on:  # a saved profile is offered, never applied
            offer_new_conversation(services, session_id, owner.id)
        return SessionCreated(id=session_id)

    @api.get("/sessions/{session_id}", tags=["sessions"], dependencies=[Depends(session_access)])
    def get_session(session_id: str, admin: IsAdmin) -> dict[str, Any]:
        """Snapshot: everything the UI needs to restore after a refresh. Without the admin
        bearer, messages are the employee's and the shown replies' text only."""
        try:
            snapshot = store.snapshot(session_id)
        except NotFound:
            raise HTTPException(404, f"session {session_id} not found") from None
        if not admin:
            shown = (public_message(m) for m in snapshot["messages"])
            snapshot["messages"] = [m for m in shown if m is not None]
        return snapshot

    @api.post(
        "/sessions/{session_id}/messages",
        status_code=202,
        response_model=MessageAccepted,
        tags=["sessions"],
        responses={429: {"description": "Too many messages from this IP (Retry-After)"}},
    )
    def post_message(
        session_id: str, body: UserMessage, request: Request, user: SessionUser
    ) -> MessageAccepted:
        """Store the message and hand it to the agent. At most COMPASS_MESSAGE_RATE_PER_MINUTE
        per client IP (429 with Retry-After beyond that)."""
        wait = messages_limiter.check(client_ip(request, settings.trust_proxy))
        if wait is None and user is not None:  # with accounts the same limit counts per user too
            wait = user_messages_limiter.check(user.id)
        if wait is not None:
            raise HTTPException(
                429,
                "too many messages; try again shortly",
                headers={"Retry-After": str(wait)},
            )
        require_session(session_id)
        seq = store.add_message(session_id, "user", {"text": body.text})
        agent.on_user_message(session_id, seq)
        return MessageAccepted(message_seq=seq)

    @api.get(
        "/sessions/{session_id}/events",
        tags=["sessions"],
        dependencies=[Depends(session_access)],
        response_class=EventSourceResponse,
        responses={200: {"content": {"text/event-stream": {}}}},
    )
    async def stream_events(
        request: Request,
        session_id: str,
        admin: IsAdmin,
        user: SessionUser,
        token: Annotated[str | None, Depends(stream_token)],
        last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
        after: Annotated[
            int | None, Query(ge=0, description="Replay after this seq (no header)")
        ] = None,
    ) -> EventSourceResponse:
        """Server-sent events. Replays everything after Last-Event-ID (or `after`), then
        streams live; a comment heartbeat keeps the connection open. Without the admin bearer
        each payload is redacted to its public part (compass/api/redact.py)."""
        start = last_event_id if last_event_id is not None else (after or 0)

        async def events() -> AsyncIterator[ServerSentEvent]:
            cursor = start
            full = admin
            # an unlocked login can lock again while its stream is open: the next batch is redacted
            relock = (
                accounts_on
                and settings.judges_unlock_on
                and user is not None
                and user.role != "admin"
                and token is not None
            )
            waiter = broker.subscribe(session_id)
            try:
                while True:
                    if relock:
                        full = await run_in_threadpool(
                            lambda: accounts.session_flags(token).judges_unlocked  # type: ignore[arg-type]
                        )
                    waiter.clear()  # clear first: a commit after this read will set it again
                    try:
                        batch = await run_in_threadpool(store.events_after, session_id, cursor)
                    except NotFound:  # the conversation was deleted under the stream
                        return
                    for event in batch:
                        cursor = event.seq
                        data = event.model_dump()
                        if not full:
                            data["payload"] = public_payload(event.type, event.payload)
                        yield ServerSentEvent(
                            id=str(event.seq),
                            event=event.type,
                            data=json.dumps(data, ensure_ascii=False),
                        )
                    if await request.is_disconnected():
                        return
                    with suppress(TimeoutError):  # re-check periodically even without a commit
                        await asyncio.wait_for(waiter.wait(), timeout=settings.heartbeat_seconds)
                    if not await run_in_threadpool(still_logged_in, token):
                        return
            finally:
                broker.unsubscribe(session_id, waiter)

        ping = max(1, round(settings.heartbeat_seconds))  # sse-starlette pings in whole seconds
        return EventSourceResponse(events(), ping=ping, headers=SSE_HEADERS)

    @api.post(
        "/sessions/{session_id}/tools/{name}",
        tags=["dev"],
        dependencies=[Depends(session_access)],
    )
    def run_tool(
        session_id: str, name: str, payload: Annotated[dict[str, Any] | None, Body()] = None
    ) -> dict[str, Any]:
        """Run a tool directly (dev / demo only: COMPASS_DEV_TOOLS=1, otherwise 404)."""
        if not settings.dev_tools:
            raise HTTPException(404, "Not Found")
        return runner.run(session_id, name, payload or {})

    # /api/auth/* (COMPASS_AUTH=1; off: the routes do not exist)
    if auth is not None:
        add_auth_routes(
            api,
            settings,
            auth,
            app.state.login_guard,
            store,
            broker,
            getattr(app.state, "judges_guard", None),
        )

    # /api/conversations and /api/admin/users, /api/admin/invites (COMPASS_AUTH=1; off: absent)
    if auth is not None:
        add_admin_user_routes(api, settings, auth, accounts, store, broker)
        add_conversation_routes(api, store, broker, auth.current_user, session_access)

    # POST /api/sessions/{id}/payslip (COMPASS_PAYSLIP=1, otherwise 404)
    add_payslip_routes(api, settings, services, agent, session_access)

    # POST /api/sessions/{id}/profile/apply, /dismiss and DELETE /api/profile
    # (COMPASS_PROFILE_MEMORY=1 with accounts, otherwise 404)
    add_profile_routes(
        api, settings, services, agent, session_access, auth.current_user if auth else None
    )

    # POST /api/sessions/{id}/current-car (the catalog picker's answer)
    add_car_routes(api, services, agent, session_access)

    # --- representative -------------------------------------------------------------------

    @api.get("/tickets", tags=["representative"], dependencies=[rep_only])
    def list_tickets(
        status: Literal["open", "answered"] | None = None,
    ) -> list[dict[str, Any]]:
        """The representative inbox. Each ticket has a display-ready `view` (title, the fields
        with their catalog default, the employee's latest comparison)."""
        return inbox(status)

    def inbox(status: Literal["open", "answered"] | None) -> list[dict[str, Any]]:
        return [
            {**t.model_dump(), "view": build_ticket_view(services, t)}
            for t in store.tickets(status=status)
        ]

    @api.get(
        "/tickets/events",
        tags=["representative"],
        dependencies=[rep_only],
        response_class=EventSourceResponse,
        responses={200: {"content": {"text/event-stream": {}}}},
    )
    async def stream_tickets(
        request: Request, token: Annotated[str | None, Depends(stream_token)]
    ) -> EventSourceResponse:
        """Server-sent events for the inbox: a `tickets` event with every open ticket (as in
        GET /tickets?status=open) on connect and whenever the list or a ticket's comparison
        changes. Each event is the whole list, so a reconnect needs no replay."""

        async def events() -> AsyncIterator[ServerSentEvent]:
            waiter = broker.subscribe(TICKETS)
            last: str | None = None
            try:
                while True:
                    waiter.clear()
                    tickets = await run_in_threadpool(inbox, "open")
                    data = json.dumps({"tickets": tickets}, ensure_ascii=False)
                    if data != last:
                        last = data
                        yield ServerSentEvent(event="tickets", data=data)
                    if await request.is_disconnected():
                        return
                    with suppress(TimeoutError):
                        await asyncio.wait_for(waiter.wait(), timeout=settings.heartbeat_seconds)
                    if not await run_in_threadpool(still_logged_in, token):
                        return
            finally:
                broker.unsubscribe(TICKETS, waiter)

        ping = max(1, round(settings.heartbeat_seconds))
        return EventSourceResponse(events(), ping=ping, headers=SSE_HEADERS)

    @api.post("/tickets/{ticket_id}/answer", tags=["representative"], dependencies=[rep_only])
    def answer_ticket(ticket_id: str, body: TicketAnswer) -> dict[str, Any]:
        """Answer a ticket: per question (`answers`) or per bound field (`values`). Bound
        questions fill their field (source representative); free questions' answers go to the
        agent as data. Resume the employee's session and tell the agent. Unless `partial`,
        questions left without an answer become unknown (answered, but not with a value)."""
        try:
            answered = answer_ticket_with_rules(
                services,
                ticket_id,
                answer_text=body.answer_text,
                quick_answer_id=body.quick_answer_id,
                values=body.values,
                answers={
                    qid: QuestionAnswer(value=a.value, status=a.status, note=a.note)
                    for qid, a in body.answers.items()
                },
                effective_from=body.effective_from,
                partial=body.partial,
            )
        except TicketAnswerError as error:
            # `detail` as before (English); `errors` adds a code and a Hebrew message per reason.
            return JSONResponse(
                status_code=error.status,
                content={
                    "detail": error.detail,
                    "errors": [
                        {
                            "code": e.code,
                            "field": e.field,
                            "message": error_message(e.code, e.params),
                        }
                        for e in error.errors
                    ],
                },
            )
        agent.on_ticket_answered(answered.session_id, ticket_id)
        return answered.model_dump()

    # --- data (read-only) -----------------------------------------------------------------

    @api.get("/rules", tags=["data"])
    def get_rules() -> dict[str, Any]:
        rules = services.ctx.rules
        return {"sha256": services.rules_sha256, "rules": plain_json(rules)}

    @api.get("/catalog", tags=["data"])
    def get_catalog() -> list[dict[str, Any]]:
        ctx = services.ctx
        return [
            {**car.model_dump(mode="json"), "family_track": ctx.is_family_car(car.id)}
            for car in ctx.catalog.values()
        ]

    @api.get("/occupations", tags=["data"])
    def get_occupations() -> list[dict[str, Any]]:
        return [o.model_dump(mode="json") for o in services.ctx.occupations.values()]

    # --- admin ----------------------------------------------------------------------------

    @api.get("/admin/stats", tags=["admin"], dependencies=[admin_only])
    def admin_stats() -> dict[str, Any]:
        """Judges mode's stats tiles, from committed files (evals/report.md, evals/spend.jsonl,
        tests/counts.json). A part whose file is missing or unreadable is null."""
        return judges_stats()

    @api.post("/admin/reload-rules", tags=["admin"], dependencies=[admin_only])
    def reload_rules() -> JSONResponse:
        """Re-read and validate rules.yaml live. Invalid -> 422; the previous rules stay."""
        try:
            rules = services.reload_rules()
        except (RulesError, ContextError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": str(error),
                    "active_rules_version": services.ctx.rules.version,
                    "active_rules_sha256": services.rules_sha256,
                },
            )
        return JSONResponse({"version": rules.version, "sha256": services.rules_sha256})

    llm_mode = (
        "scripted"
        if settings.llm == "scripted"
        else "anthropic"
        if settings.anthropic_api_key
        else "none"
    )

    scripts = None
    if llm_mode == "scripted":
        from compass.agent.demo_llm import demo_scripts  # the agent layer sits above the API

        scripts = demo_scripts()

    @api.get("/health", tags=["admin"])
    def health() -> dict[str, Any]:
        rules = services.ctx.rules
        vehicles = _vehicles_meta(settings.vehicles_db)
        return {
            "ok": True,
            "rules": {"version": rules.version, "sha256": services.rules_sha256},
            "data": {
                "catalog_sha256": _sha256(CATALOG_JSON),
                "occupations_sha256": _sha256(OCCUPATIONS_JSON),
                "aliases_sha256": _sha256(settings.aliases_path),
                "vehicles_source_sha256": vehicles.get("source_sha256"),
                "vehicles_rows": int(vehicles["row_count"]) if "row_count" in vehicles else None,
                "tax_tables_year": rules.net_method.tax_year,
                "value_of_use_year": rules.value_of_use.tax_year,
            },
            "dev_tools": settings.dev_tools,
            # Whether each token is set (never its value): an empty one disables its screen,
            # and the UI says so instead of asking for a token that can never work.
            # (with accounts on both are refused: the UI logs in instead)
            "auth": {
                "rep": bool(settings.rep_token) and not settings.auth,
                "admin": bool(settings.admin_token) and not settings.auth,
            },
            # only with COMPASS_AUTH=1 (off: the response is as it was): the UI shows the
            # landing page and login. The UI reads the flag here, never from its own constant.
            **({"accounts": True} if settings.auth else {}),
            # only with COMPASS_JUDGES_UNLOCK=1 / COMPASS_DEMO_LOGIN=1 (and accounts): the UI shows
            # the unlock dialog / the quick access on the landing page
            **({"judges_unlock": True} if settings.judges_unlock_on else {}),
            **({"demo_login": True} if settings.demo_login_on else {}),
            # "scripted": demo mode (the UI shows its badge and the scripts' messages).
            "llm": llm_mode,
            "demo_scripts": scripts,
            # only with COMPASS_PAYSLIP=1 (off: the response is as it was): the UI shows the
            # attach button, and pre-checks type and size (the server's checks are the real ones)
            **(
                {
                    "payslip": {
                        "max_bytes": settings.payslip_max_bytes,
                        "max_pages": settings.payslip_max_pages,
                        "types": sorted(PAYSLIP_TYPES),
                    }
                }
                if settings.payslip
                else {}
            ),
        }

    app.include_router(api)
    # The web UI last, so it can never shadow an API route (see spa.py).
    if settings.web_dist is not None and (settings.web_dist / "index.html").is_file():
        mount_spa(app, settings.web_dist)
    return app

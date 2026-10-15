"""FastAPI app factory. All routes under /api.

uv run python tasks.py serve     # uvicorn with reload, http://127.0.0.1:8000/docs
"""

import asyncio
import hashlib
import hmac
import json
import sqlite3
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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.concurrency import run_in_threadpool

from compass.api.agent import AgentRunner
from compass.api.broker import TICKETS, Broker
from compass.api.redact import public_message, public_payload
from compass.api.settings import Settings
from compass.config import CATALOG_JSON, OCCUPATIONS_JSON
from compass.engine.context import ContextError
from compass.engine.serialize import plain_json
from compass.rules import RulesError
from compass.state import NotFound, Store
from compass.tools import ToolRunner
from compass.tools.services import Services
from compass.tools.tickets import TicketAnswerError
from compass.tools.tickets import answer_ticket as answer_ticket_with_rules
from compass.tools.view import build_ticket_view


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionCreated(BaseModel):
    id: str


class UserMessage(_Body):
    text: str = Field(min_length=1, max_length=4000)


class MessageAccepted(BaseModel):
    message_seq: int


class TicketAnswer(_Body):
    answer_text: str | None = Field(None, max_length=4000)
    quick_answer_id: str | None = None
    values: dict[str, Any] = Field(default_factory=dict, description="Tool field -> value")
    effective_from: date | None = Field(
        None, description="When a participation amount takes effect (participation fields only)"
    )


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
    store = Store(settings.app_db)
    services = Services(
        store,
        rules_path=settings.rules_path,
        aliases_path=settings.aliases_path,
        vehicles_db=settings.vehicles_db,
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
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.services = services
    app.state.runner = runner
    app.state.agent = agent
    api = APIRouter(prefix="/api")
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

    admin_optional = _optional_token(
        settings.admin_token,
        HTTPBearer(auto_error=False, scheme_name="AdminToken"),
        "admin",
        "COMPASS_ADMIN_TOKEN",
    )
    IsAdmin = Annotated[bool, Depends(admin_optional)]

    def require_session(session_id: str) -> None:
        try:
            store.session_status(session_id)
        except NotFound:
            raise HTTPException(404, f"session {session_id} not found") from None

    # --- sessions -------------------------------------------------------------------------

    @api.post("/sessions", status_code=201, response_model=SessionCreated, tags=["sessions"])
    def create_session() -> SessionCreated:
        return SessionCreated(id=store.create_session())

    @api.get("/sessions/{session_id}", tags=["sessions"])
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
    )
    def post_message(session_id: str, body: UserMessage) -> MessageAccepted:
        """Store the message and hand it to the agent (a no-op until Day 3)."""
        require_session(session_id)
        seq = store.add_message(session_id, "user", {"text": body.text})
        agent.on_user_message(session_id, seq)
        return MessageAccepted(message_seq=seq)

    @api.get(
        "/sessions/{session_id}/events",
        tags=["sessions"],
        response_class=EventSourceResponse,
        responses={200: {"content": {"text/event-stream": {}}}},
    )
    async def stream_events(
        request: Request,
        session_id: str,
        admin: IsAdmin,
        last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
        after: Annotated[
            int | None, Query(ge=0, description="Replay after this seq (no header)")
        ] = None,
    ) -> EventSourceResponse:
        """Server-sent events. Replays everything after Last-Event-ID (or `after`), then
        streams live; a comment heartbeat keeps the connection open. Without the admin bearer
        each payload is redacted to its public part (compass/api/redact.py)."""
        require_session(session_id)
        start = last_event_id if last_event_id is not None else (after or 0)

        async def events() -> AsyncIterator[ServerSentEvent]:
            cursor = start
            waiter = broker.subscribe(session_id)
            try:
                while True:
                    waiter.clear()  # clear first: a commit after this read will set it again
                    batch = await run_in_threadpool(store.events_after, session_id, cursor)
                    for event in batch:
                        cursor = event.seq
                        data = event.model_dump()
                        if not admin:
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
            finally:
                broker.unsubscribe(session_id, waiter)

        ping = max(1, round(settings.heartbeat_seconds))  # sse-starlette pings in whole seconds
        return EventSourceResponse(events(), ping=ping)

    @api.post("/sessions/{session_id}/tools/{name}", tags=["dev"])
    def run_tool(
        session_id: str, name: str, payload: Annotated[dict[str, Any] | None, Body()] = None
    ) -> dict[str, Any]:
        """Run a tool directly (dev / demo only: COMPASS_DEV_TOOLS=1, otherwise 404)."""
        if not settings.dev_tools:
            raise HTTPException(404, "Not Found")
        require_session(session_id)
        return runner.run(session_id, name, payload or {})

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
    async def stream_tickets(request: Request) -> EventSourceResponse:
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
            finally:
                broker.unsubscribe(TICKETS, waiter)

        ping = max(1, round(settings.heartbeat_seconds))
        return EventSourceResponse(events(), ping=ping)

    @api.post("/tickets/{ticket_id}/answer", tags=["representative"], dependencies=[rep_only])
    def answer_ticket(ticket_id: str, body: TicketAnswer) -> dict[str, Any]:
        """Answer a ticket: fill its blocking fields (source representative), resume the
        employee's session and tell the agent. Blocking fields left without a value become
        unknown (the representative answered, but not with a number)."""
        try:
            answered = answer_ticket_with_rules(
                services,
                ticket_id,
                answer_text=body.answer_text,
                quick_answer_id=body.quick_answer_id,
                values=body.values,
                effective_from=body.effective_from,
            )
        except TicketAnswerError as error:
            raise HTTPException(error.status, error.detail) from None
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
            # "scripted": demo mode (the UI shows its badge and the scripts' messages).
            "llm": llm_mode,
            "demo_scripts": scripts,
        }

    app.include_router(api)
    return app

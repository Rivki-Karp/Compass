"""The payslip upload (COMPASS_PAYSLIP=1; off -> 404, and both routes left out of the schema).

    POST /api/sessions/{id}/payslip          the file -> a pending candidate
    POST /api/sessions/{id}/payslip/confirm  the fields the employee accepts -> profile values

The body is the file itself (Content-Type application/pdf, image/jpeg or image/png), read from
the request stream into memory with a hard cap; never multipart, never on disk. Checks, in this
order: the flag, the session (the same check as the other session endpoints), this session's
attempts (and one upload at a time), the per-IP rate limit, the daily spend cap (live mode, as
the agent's), the declared type, the size, the magic bytes, and for a PDF its pages and
encryption.

A refusal is {"detail": code, "errors": [{"code", "field", "message"}]} with a Hebrew
message (compass.labels), the shape of a refused ticket answer. One log line per upload, metadata
only: session, type, size bucket, pages, latency, cost and outcome; never the file, its base64
or a hash of it.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from compass.api.agent import AgentRunner
from compass.api.ratelimit import RateLimiter, client_ip
from compass.api.settings import Settings
from compass.labels import error_message
from compass.payslip.confirm import CONFIRMABLE, confirm
from compass.payslip.service import PayslipService
from compass.payslip.upload import (
    MAGIC,
    PayslipRejected,
    check_file,
    media_type,
    read_capped,
    size_bucket,
)
from compass.state import Store
from compass.tools.services import Services

# Every upload that reached the extractor leaves one of these events: the per-session count.
ATTEMPT_EVENTS = ("payslip_extracted", "payslip_failed")
# Uploads per client IP per minute (429 with Retry-After beyond it).
UPLOADS_PER_MINUTE = 5

log = logging.getLogger("compass.payslip")


class PayslipConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The fields the employee accepts -> their value (the candidate's, or the one the "
            f"employee typed). A field left out is rejected. Allowed: {', '.join(CONFIRMABLE)}"
        ),
    )


def rejected(error: PayslipRejected) -> JSONResponse:
    message = error_message(error.code, error.params)
    fields = error.params.get("fields") or [None]  # one error per field it names
    return JSONResponse(
        status_code=error.status,
        content={
            "detail": error.code,
            "errors": [{"code": error.code, "field": f, "message": message} for f in fields],
        },
        headers=error.headers,
    )


def add_payslip_routes(
    api: APIRouter,
    settings: Settings,
    services: Services,
    agent: AgentRunner,
    require_session: Callable[[str], None],
) -> None:
    store: Store = services.store
    limiter = RateLimiter(UPLOADS_PER_MINUTE)
    in_flight: set[str] = set()
    lock = threading.Lock()
    # the agent's rule: live mode has the daily cap, demo mode (scripted) none
    daily_cap = None if settings.llm == "scripted" else settings.daily_spend_cap_usd

    @api.post(
        "/sessions/{session_id}/payslip",
        tags=["sessions"],
        include_in_schema=settings.payslip,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    kind: {"schema": {"type": "string", "format": "binary"}} for kind in MAGIC
                },
            }
        },
        responses={
            404: {"description": "The upload is off (COMPASS_PAYSLIP=0), or no such session"},
            409: {"description": "An upload for this session is still being read"},
            413: {"description": "Over COMPASS_PAYSLIP_MAX_BYTES"},
            415: {"description": "Not a PDF, JPEG or PNG, or the content is not the type"},
            201: {"description": "The pending candidate: {fields, dropped_keys}"},
            422: {"description": "Encrypted, over COMPASS_PAYSLIP_MAX_PAGES, or unreadable"},
            429: {"description": "This session's uploads, or this IP's rate (Retry-After)"},
            502: {"description": "Neither model could read the payslip"},
            503: {"description": "The daily spend cap, or reading payslips is unavailable"},
        },
    )
    async def upload_payslip(session_id: str, request: Request) -> JSONResponse:
        """Upload a payslip (the raw file as the body). Its salary numbers are read into a
        pending candidate the employee confirms; the file is never stored."""
        if not settings.payslip:
            raise HTTPException(404, "Not Found")
        require_session(session_id)
        started = time.monotonic()
        meta: dict[str, Any] = {"type": None, "size": None, "pages": None, "cost": None}
        outcome = "rejected"
        claimed = False
        try:
            attempts = store.count_events(session_id, ATTEMPT_EVENTS)
            if attempts >= settings.payslip_per_session:
                raise PayslipRejected(429, "payslip_per_session", max=settings.payslip_per_session)
            with lock:
                if session_id in in_flight:
                    raise PayslipRejected(409, "payslip_in_progress")
                in_flight.add(session_id)
                claimed = True
            wait = limiter.check(client_ip(request, settings.trust_proxy))
            if wait is not None:
                raise PayslipRejected(
                    429, "payslip_rate_limited", headers={"Retry-After": str(wait)}
                )
            day = datetime.now(UTC).date().isoformat()
            if daily_cap is not None and store.spend_on(day) >= daily_cap:
                raise PayslipRejected(503, "payslip_daily_cap")
            declared = media_type(request.headers.get("content-type"))
            meta["type"] = declared
            data = await read_capped(
                request.stream(), request.headers.get("content-length"), settings.payslip_max_bytes
            )
            meta["size"] = size_bucket(len(data))
            meta["pages"] = await run_in_threadpool(
                check_file, data, declared, settings.payslip_max_pages
            )
            service: PayslipService | None = request.app.state.payslip
            if service is None:  # live mode without a key
                raise PayslipRejected(503, "payslip_unavailable")
            try:
                extracted = await run_in_threadpool(service.extract, session_id, data, declared)
            finally:
                del data  # nothing keeps the file past this request
            meta["cost"] = None if extracted.cost_usd is None else round(extracted.cost_usd, 6)
            outcome = "extracted"
            # the employee's own candidate, for the confirmation card; the same as the event
            return JSONResponse(status_code=201, content=extracted.candidate.to_dict())
        except PayslipRejected as error:
            outcome = error.code
            return rejected(error)
        finally:
            if claimed:
                with lock:
                    in_flight.discard(session_id)
            log.info(
                "payslip upload: session=%s type=%s size=%s pages=%s latency_ms=%d "
                "cost_usd=%s outcome=%s",
                session_id,
                meta["type"],
                meta["size"],
                meta["pages"],
                round((time.monotonic() - started) * 1000),
                meta["cost"],
                outcome,
            )

    @api.post(
        "/sessions/{session_id}/payslip/confirm",
        tags=["sessions"],
        include_in_schema=settings.payslip,
        responses={
            404: {"description": "The upload is off (COMPASS_PAYSLIP=0), or no such session"},
            409: {"description": "No candidate waits for confirmation"},
            422: {"description": "A field that is not a salary field, or an invalid value"},
        },
    )
    def confirm_payslip(session_id: str, body: PayslipConfirmBody) -> JSONResponse:
        """Apply the accepted fields: unchanged values get source payslip, edited ones source
        employee; a representative's value is kept. The comparison on screen is recomputed
        (no model call) and the agent is told the confirmed values, as data."""
        if not settings.payslip:
            raise HTTPException(404, "Not Found")
        require_session(session_id)
        try:
            confirmed = confirm(services, session_id, body.fields)
        except PayslipRejected as error:
            return rejected(error)
        log.info(
            "payslip confirmed: session=%s applied=%d kept_representative=%d car_hint=%s",
            session_id,
            len(confirmed.applied),
            len(confirmed.kept_representative),
            confirmed.car_hint is not None,
        )
        if confirmed.applied or confirmed.car_hint:
            agent.on_payslip_confirmed(
                session_id, {**confirmed.to_dict(), "comparisons": confirmed.comparisons}
            )
        return JSONResponse(confirmed.to_dict())

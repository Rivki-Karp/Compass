"""A session's payslip extraction: run the extractor, count its cost toward the daily spend cap,
and record the result as an event.

    payslip_extracted   the pending candidate: numbers, confidences and flags (and, for judges
                        mode only, the model, whether the fallback ran, latency and cost)
    payslip_failed      why reading failed: a code, nothing else

The latest payslip_extracted is the session's pending candidate. It is an event, never a
message: the agent's input is built from messages only, so it never sees the file or an
unconfirmed value. Nothing here keeps the file.
"""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from compass.payslip.extractor import ExtractionFailed, Extractor, calls_cost_usd
from compass.payslip.schema import CandidateField, PayslipCandidate
from compass.payslip.upload import MediaType, PayslipRejected
from compass.state import Store

if TYPE_CHECKING:
    from compass.api.settings import Settings

log = logging.getLogger("compass.payslip")


@dataclass(frozen=True)
class Extracted:
    candidate: PayslipCandidate
    cost_usd: float | None


def build_service(settings: "Settings", store: Store) -> "PayslipService | None":
    """The flag on: demo mode reads every upload as the demo payslip; live mode uses Claude
    (ANTHROPIC_API_KEY). None when off, or live without a key (uploads: 503 unavailable)."""
    if not settings.payslip:
        return None
    if settings.llm == "scripted":
        from compass.payslip.extractor import demo_extractor

        return PayslipService(store, demo_extractor(), count_spend=False)
    if not settings.anthropic_api_key:
        return None
    from compass.payslip.extractor import ClaudeExtractor

    extractor = ClaudeExtractor(
        settings.anthropic_api_key,
        settings.payslip_model,
        settings.payslip_fallback_model,
        timeout_seconds=settings.payslip_timeout_s,
    )
    return PayslipService(store, extractor, count_spend=True)


class PayslipService:
    def __init__(self, store: Store, extractor: Extractor, *, count_spend: bool) -> None:
        self.store = store
        self.extractor = extractor
        self.count_spend = count_spend  # live mode: the daily spend cap counts this cost

    def _spend(self, cost: float | None) -> None:
        if self.count_spend and cost:
            self.store.add_spend(datetime.now(UTC).date().isoformat(), cost)

    def extract(self, session_id: str, data: bytes, media_type: MediaType) -> Extracted:
        """Read the payslip into a pending candidate. Raises PayslipRejected (502) when every
        model failed; the session's event log records either outcome."""
        started = time.monotonic()
        try:
            extraction = self.extractor.extract(data, media_type)
        except ExtractionFailed as error:
            self._spend(calls_cost_usd(error.calls))
            # the reason names models and error classes only; never the file or an answer
            log.warning("payslip extraction failed: session=%s reason=%s", session_id, error)
            self.store.append_event(
                session_id, "payslip_failed", {"code": "payslip_extraction_failed"}
            )
            raise PayslipRejected(502, "payslip_extraction_failed") from None
        cost = extraction.cost_usd()
        self._spend(cost)
        self.store.append_event(
            session_id,
            "payslip_extracted",
            {
                **extraction.candidate.to_dict(),
                # judges mode only (compass/api/redact.py)
                "model": extraction.model,
                "fallback": extraction.fallback,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "cost_usd": None if cost is None else round(cost, 6),
            },
        )
        return Extracted(extraction.candidate, cost)

    def pending(self, session_id: str) -> PayslipCandidate | None:
        """The session's latest candidate, if any (confirming it arrives with Stage 5)."""
        payload = self.store.last_event_payload(session_id, "payslip_extracted")
        if payload is None:
            return None
        return PayslipCandidate(
            fields={name: CandidateField(**f) for name, f in payload["fields"].items()},
            dropped_keys=payload["dropped_keys"],
        )

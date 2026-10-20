"""Reading and checking an uploaded payslip, in memory only.

The body is read from the request stream with a hard cap (never multipart: Starlette spools an
UploadFile above 1 MB to a temporary file on disk). The bytes are never written anywhere, never
logged, never hashed, and dropped when the request ends. The checks after the header ones:
size, magic bytes against the declared type, then for a PDF the page count and encryption.

Every refusal is a PayslipRejected with a stable code (its Hebrew message is in
compass.labels.ERROR_MESSAGES) and never a number read from the file.
"""

import io
import logging
from collections.abc import AsyncIterator
from typing import Any, Literal

PayslipErrorCode = Literal[
    "payslip_in_progress",
    "payslip_per_session",
    "payslip_rate_limited",
    "payslip_daily_cap",
    "payslip_unsupported_type",
    "payslip_empty",
    "payslip_too_large",
    "payslip_type_mismatch",
    "payslip_encrypted",
    "payslip_too_many_pages",
    "payslip_unreadable",
    "payslip_unavailable",
    "payslip_extraction_failed",
    "payslip_nothing_pending",
    "payslip_field_not_allowed",
    "payslip_invalid_value",
]

# Content-Type -> the file's first bytes
MAGIC: dict[str, bytes] = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG",
}
MediaType = Literal["application/pdf", "image/jpeg", "image/png"]

# pypdf reports structural oddities through logging; they name objects, never content, but
# nothing about an uploaded file reaches the logs except our own metadata line.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)


class PayslipRejected(Exception):
    """An upload refused before (or instead of) extraction. `params` fill the Hebrew message
    and come from the settings, never from the file."""

    def __init__(
        self,
        status: int,
        code: PayslipErrorCode,
        headers: dict[str, str] | None = None,
        **params: Any,
    ) -> None:
        self.status = status
        self.code = code
        self.headers = headers
        self.params = params
        super().__init__(code)


def media_type(content_type: str | None) -> MediaType:
    """The declared type, without parameters. Raises PayslipRejected (415)."""
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if declared not in MAGIC:
        raise PayslipRejected(415, "payslip_unsupported_type")
    return declared  # type: ignore[return-value]


def _too_large(max_bytes: int) -> PayslipRejected:
    return PayslipRejected(413, "payslip_too_large", max_mb=max(1, round(max_bytes / 2**20)))


async def read_capped(
    chunks: AsyncIterator[bytes], declared_length: str | None, max_bytes: int
) -> bytes:
    """The body, in memory, aborting with 413 as soon as it passes `max_bytes` (a declared
    Content-Length over it is refused before a byte is read)."""
    if declared_length is not None:
        try:
            if int(declared_length) > max_bytes:
                raise _too_large(max_bytes)
        except ValueError:
            pass  # a malformed header: the stream count below still applies
    body = bytearray()
    async for chunk in chunks:
        body += chunk
        if len(body) > max_bytes:
            raise _too_large(max_bytes)
    if not body:
        raise PayslipRejected(400, "payslip_empty")
    return bytes(body)


def pdf_pages(data: bytes, max_pages: int) -> int:
    """The page count of an unencrypted PDF of at most `max_pages`. Raises PayslipRejected."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PayslipRejected(422, "payslip_encrypted")
        pages = len(reader.pages)
    except PayslipRejected:
        raise
    except Exception:  # noqa: BLE001 - any parse failure is the same answer, never its text
        raise PayslipRejected(422, "payslip_unreadable") from None
    if pages < 1:
        raise PayslipRejected(422, "payslip_unreadable")
    if pages > max_pages:
        raise PayslipRejected(422, "payslip_too_many_pages", max=max_pages)
    return pages


def check_file(data: bytes, declared: MediaType, max_pages: int) -> int | None:
    """Magic bytes against the declared type, then (PDF) pages and encryption. The page count
    for a PDF, None for an image."""
    if not data.startswith(MAGIC[declared]):
        raise PayslipRejected(415, "payslip_type_mismatch")
    if declared == "application/pdf":
        return pdf_pages(data, max_pages)
    return None


def size_bucket(size: int) -> str:
    """The size for the logs, never the exact byte count."""
    for limit, label in ((100 * 1024, "<100KB"), (2**20, "100KB-1MB"), (5 * 2**20, "1-5MB")):
        if size < limit:
            return label
    return ">5MB"

"""Payslip extraction against the real Claude API: run by hand, never in CI or pytest.

    check   (tasks.py payslip-check) lists the Claude models ANTHROPIC_API_KEY can see, and for
            each configured model (COMPASS_PAYSLIP_MODEL, COMPASS_PAYSLIP_FALLBACK_MODEL)
            confirms it exists, reports image / PDF / structured-output support, has a price
            entry, and accepts a synthetic PDF and PNG in the extraction's request shape (a JSON
            schema, max_tokens 800, thinking off, no tools). A missing ID is reported with the
            closest real ones; nothing is picked for you. A rate limit or an unpaid balance is
            reported as "quota/billing", never as missing.

Result: OK (exit 0) when both models pass; PARTIAL (exit 0) when the only failures are
quota/billing and at least one model passes; FAIL (exit 1) otherwise. Every call's cost goes to
evals/spend.jsonl and the average per synthetic payslip is printed. Nothing printed ever contains
the key: every line goes through `redact`.
"""

import base64
import difflib
import json
import re
import struct
import sys
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from compass.agent.llm import PRICES, Usage
from compass.api.settings import Settings
from evals.report import Ledger, OverBudget

_KEY_SHAPE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")
REDACTED = "<redacted>"
MAX_TOKENS = 800
PROBE_TEXT_BLOCK = {"type": "text", "text": "This is a connectivity check. Set ok to true."}
PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
ACCEPTED = "accepted"
QUOTA = "quota/billing"


def redact(text: str, secret: str | None) -> str:
    """The text with the key (and anything shaped like an Anthropic key) replaced."""
    if secret:
        text = text.replace(secret, REDACTED)
    return _KEY_SHAPE.sub(REDACTED, text)


def thinking_off(model: str) -> dict[str, str]:
    """No thinking for a short extraction: Haiku 5.5 takes `disabled`; Sonnet 5.5 rejects it
    and takes `between_tools` (at effort high or below), which with no tools means none."""
    if model.startswith("claude-sonnet-5"):
        return {"type": "between_tools"}
    return {"type": "disabled"}


def probe_pdf() -> bytes:
    """A one-page PDF that says "Compass check": no personal data, built here, never a file."""
    stream = b"BT /F1 18 Tf 72 720 Td (Compass check) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def probe_png(size: int = 16) -> bytes:
    """A small white PNG (8-bit grayscale)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + kind + data + crc

    header = struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0)
    rows = b"".join(b"\x00" + b"\xff" * size for _ in range(size))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def file_block(data: bytes, media_type: str) -> dict[str, Any]:
    """A PDF as a document block, an image as an image block (base64, in memory only)."""
    source = {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()}
    kind = "document" if media_type == "application/pdf" else "image"
    return {"type": kind, "source": source}


@dataclass
class ModelCheck:
    setting: str
    model: str
    found: bool = False
    priced: bool = False
    capabilities: dict[str, bool | None] = field(default_factory=dict)
    pdf: str = "not tried"
    image: str = "not tried"
    closest: tuple[str, ...] = ()
    costs: list[float] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.found and self.priced

    @property
    def ok(self) -> bool:
        return self.usable and self.pdf == ACCEPTED and self.image == ACCEPTED

    @property
    def quota_blocked(self) -> bool:
        """Exists and is priced, but quota/billing (and nothing else) stopped an input."""
        probes = (self.pdf, self.image)
        return (
            self.usable
            and any(p.startswith(QUOTA) for p in probes)
            and all(p == ACCEPTED or p.startswith(QUOTA) for p in probes)
        )


def is_quota_error(error: Exception) -> bool:
    """A rate limit (429), or a request refused for the account's credit balance."""
    import anthropic

    if isinstance(error, anthropic.RateLimitError):
        return True
    message = str(getattr(error, "message", "") or error).lower()
    return isinstance(error, anthropic.APIStatusError) and (
        "credit balance" in message or "billing" in message
    )


def closest_ids(wanted: str, available: Iterable[str], n: int = 3) -> tuple[str, ...]:
    """The real IDs nearest `wanted`: the same family first, then by string similarity."""
    names = sorted(set(available))
    close = difflib.get_close_matches(wanted, names, n=n, cutoff=0.6)
    family = [name for name in names if name.startswith(wanted)]
    return tuple(dict.fromkeys([*family, *close]))[:n]


def _supported(capabilities: Any, *path: str) -> bool | None:
    """capabilities[path...]["supported"], or None when the API does not report it."""
    node = capabilities
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node.get("supported") if isinstance(node, dict) else None


def _probe(client: Any, model: str, data: bytes, media_type: str) -> Any:
    return client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        thinking=thinking_off(model),
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": PROBE_SCHEMA}},
        messages=[{"role": "user", "content": [file_block(data, media_type), PROBE_TEXT_BLOCK]}],
    )


def _usage(response: Any) -> Usage:
    usage = response.usage
    return Usage(
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )


def check(settings: Settings, ledger: Ledger | None = None, client: Any = None) -> int:
    """Run the check and print the result: 0 = OK or PARTIAL, 1 = FAIL (module docstring)."""
    import anthropic

    key = settings.anthropic_api_key
    if not key:
        print("payslip-check: ANTHROPIC_API_KEY is empty (set it in backend/.env).")
        return 1
    ledger = ledger or Ledger()
    if client is None:  # one retry on a transient error, as the extractor does
        client = anthropic.Anthropic(api_key=key, timeout=settings.payslip_timeout_s, max_retries=1)

    def say(line: str = "") -> None:
        print(redact(line, key), flush=True)

    try:
        listed = sorted(m.id for m in client.models.list())
    except Exception as error:  # noqa: BLE001 - reported, redacted
        say(f"payslip-check: listing models failed: {type(error).__name__}: {error}")
        return 1
    say(f"models the key can see: {len(listed)}")
    for name in listed:
        say(f"  {name}")
    say()

    results = [
        ModelCheck("COMPASS_PAYSLIP_MODEL", settings.payslip_model),
        ModelCheck("COMPASS_PAYSLIP_FALLBACK_MODEL", settings.payslip_fallback_model),
    ]
    for result in results:
        result.priced = result.model in PRICES
        try:
            info = client.models.retrieve(result.model)
        except anthropic.NotFoundError:
            result.closest = closest_ids(result.model, listed)
            continue
        except Exception as error:  # noqa: BLE001 - reported, redacted
            say(f"payslip-check: {result.model}: {type(error).__name__}: {error}")
            return 1
        result.found = True
        caps = getattr(info, "capabilities", None)
        if caps is not None and not isinstance(caps, dict):  # the SDK's ModelCapabilities
            caps = caps.to_dict()
        result.capabilities = {
            "API: images": _supported(caps, "image_input"),
            "API: PDFs": _supported(caps, "pdf_input"),
            "API: schemas": _supported(caps, "structured_outputs"),
        }
        if not result.priced or False in result.capabilities.values():
            continue
        for kind, data, media_type in (
            ("pdf", probe_pdf(), "application/pdf"),
            ("image", probe_png(), "image/png"),
        ):
            try:
                ledger.reserve()
            except OverBudget as error:
                say(f"payslip-check: {error}")
                return 1
            try:
                response = _probe(client, result.model, data, media_type)
            except Exception as error:  # noqa: BLE001 - reported, redacted
                label = QUOTA if is_quota_error(error) else "refused"
                setattr(result, kind, f"{label}: {type(error).__name__}: {error}"[:300])
                continue
            cost = _usage(response).cost_usd(result.model) or 0.0
            result.costs.append(cost)
            ledger.record_call(f"payslip-check ({kind})", result.model, cost)
            text = "".join(b.text for b in response.content if b.type == "text")
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            if response.stop_reason == "refusal":
                setattr(result, kind, "refused: stop_reason refusal")
            elif not isinstance(parsed, dict) or set(parsed) != {"ok"}:
                setattr(result, kind, f"refused: not the schema (stop {response.stop_reason})")
            else:
                setattr(result, kind, ACCEPTED)

    def flag(value: bool | None) -> str:
        return "not reported" if value is None else ("yes" if value else "NO")

    for result in results:
        say(f"{result.setting} = {result.model}")
        if not result.found:
            say("  exists:          NO")
            say(f"  closest real IDs: {', '.join(result.closest) or 'none'}")
            continue
        say("  exists:          yes")
        for name, value in result.capabilities.items():
            say(f"  {name + ':':17}{flag(value)}")
        say(f"  price entry:     {'yes' if result.priced else 'NO (add it to llm.PRICES)'}")
        say(f"  sent a PDF:      {result.pdf}")
        say(f"  sent a PNG:      {result.image}")
        if result.costs:
            average = sum(result.costs) / len(result.costs)
            say(f"  cost:            ${sum(result.costs):.6f} ({len(result.costs)} calls)")
            say(f"  average/payslip: ${average:.6f}")
    total = sum(sum(r.costs) for r in results)
    if all(r.ok for r in results):
        verdict, code = "OK", 0
    elif any(r.ok for r in results) and all(r.ok or r.quota_blocked for r in results):
        blocked = ", ".join(r.model for r in results if r.quota_blocked)
        verdict, code = f"PARTIAL (quota/billing on {blocked}; the rest OK)", 0
    else:
        verdict, code = "FAIL", 1
    say()
    say(f"payslip-check: {verdict} · cost ${total:.6f}")
    if any(not r.found for r in results):
        say("No model was chosen for you: set COMPASS_PAYSLIP_MODEL / _FALLBACK_MODEL by hand.")
    return code


def main(argv: list[str]) -> int:
    if argv[:1] != ["check"]:
        print("usage: python -m evals.payslip_live check")
        return 2
    return check(Settings.from_env())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""What a client without the admin token may see of a session.

Judges mode shows the engine room: tool inputs, full tool results, the guard's per-number
sources and rejected drafts, usage and cost. Only the admin bearer gets those. Everyone else
gets the public part of each event (allowlisted keys), and an event type not listed here goes
out with an empty payload: a new event can never leak by default.
"""

from typing import Any

# Event type -> the payload keys a client without the admin token receives.
_ALL = None
PUBLIC_KEYS: dict[str, frozenset[str] | None] = {
    "session_created": _ALL,
    "session_status": _ALL,
    "user_message": _ALL,
    "assistant_message": _ALL,
    "profile_updated": _ALL,
    "current_situation_set": _ALL,
    "comparison_ready": _ALL,
    "comparison_set_ready": _ALL,
    "ticket_opened": _ALL,
    "ticket_answered": _ALL,
    "agent_started": _ALL,
    # The tool activity row needs the name and whether it worked; never the input or result.
    "tool_call": frozenset({"tool_use_id", "name"}),
    "tool_result": frozenset({"tool_use_id", "name", "ok"}),
    # Whether the reply passed and what happened; never the numbers, sources or draft.
    "guard_check": frozenset({"passed", "action"}),
    "agent_finished": frozenset({"outcome"}),
    "agent_error": frozenset({"kind"}),
    # The payslip candidate is the employee's own numbers, for their confirmation card; which
    # model read it, its cost and timing are judges mode's.
    "payslip_extracted": frozenset({"fields", "dropped_keys"}),
    "payslip_failed": frozenset({"code"}),
}


def public_payload(event_type: str, payload: Any) -> Any:
    if event_type not in PUBLIC_KEYS:
        return {}
    keys = PUBLIC_KEYS[event_type]
    if keys is None:
        return payload
    if not isinstance(payload, dict):
        return {}
    return {k: v for k, v in payload.items() if k in keys}


def public_message(message: dict[str, Any]) -> dict[str, Any] | None:
    """A transcript row as the session snapshot shows it without the admin token: the
    employee's messages and the replies' text only (no tool rows, server events, usage or
    model). None: the row is not shown."""
    content = message.get("content")
    if message.get("role") == "user":
        return message
    if message.get("role") == "assistant" and isinstance(content, dict):
        blocks = content.get("blocks", [])
        if any(b.get("type") == "tool_use" for b in blocks):  # a tool round, not a reply
            return None
        text = "".join(
            b.get("text", "") for b in content.get("blocks", []) if b.get("type") == "text"
        )
        return {**message, "content": {"text": text}} if text else None
    return None

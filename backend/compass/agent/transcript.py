"""The agent's transcript: what is stored in `messages`, and how it becomes the model's input.

Stored rows (append-only, in `seq` order):

    user          {"text"}                      the employee's message as the UI shows it
    system_event  {"kind": "employee_turn", "message_seq", "origin": "server"}
                                                 the runner took that user message into the
                                                 conversation (here, not at the user row: a
                                                 message typed mid-run must not split a tool
                                                 call from its result)
    system_event  {"kind": "rep_answer", ...}   a representative answered a ticket
    system_event  {"kind": "guard_correction", "violations"}
    assistant     {"blocks", "usage", "model", "fabricated"?}
    tool          {"results": [{"tool_use_id", "name", "ok", "model_view", "full"}]}

Only server code writes `system_event` rows; the API stores employee text as `user`, always.
That role is the marker that cannot be forged. On top of it, employee text is rendered inside
<employee_message> with our tag names escaped, so even a typed copy of a notification is visibly
employee text to the model.
"""

import json
import re
from collections.abc import Sequence
from typing import Any

from compass.state.store import Message

SERVER_ORIGIN = "server"
EMPLOYEE_TAG = "employee_message"
REP_TAG = "rep_notification"
REP_LABEL_HE = "עדכון אוטומטי ממערכת הנציגים"

# Our structural tags, opening or closing, in any case or spacing: neutralised in untrusted text.
_TAG_PATTERN = re.compile(
    rf"<\s*/?\s*({EMPLOYEE_TAG}|{REP_TAG}|system[_ -]?notice)\b", re.IGNORECASE
)

ModelMessage = dict[str, Any]


def escape_tags(text: str) -> str:
    """Make our tag names inert inside untrusted text (employee or representative)."""
    return _TAG_PATTERN.sub(lambda m: m.group(0).replace("<", "&lt;"), text)


def employee_block(text: str) -> str:
    return f"<{EMPLOYEE_TAG}>\n{escape_tags(text)}\n</{EMPLOYEE_TAG}>"


def rep_block(event: dict[str, Any]) -> str:
    """A representative's answer, as structured data the model can trust (server-written)."""
    payload = {
        "ticket_id": event["ticket_id"],
        "question": escape_tags(event.get("question", "")),
        "answer_text": escape_tags(event.get("answer_text") or "") or None,
        "values": event.get("values", {}),
        "effective_from": event.get("effective_from"),
        "unknown_fields": event.get("unknown_fields", []),
    }
    if event.get("pending_fields"):
        # a partial answer: the representative has not answered these yet
        payload["pending_fields"] = event["pending_fields"]
    if event.get("server_comparisons"):
        # compare's own (compact) result, recomputed by the server with the answer
        payload["server_comparisons"] = event["server_comparisons"]
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f'<{REP_TAG} label="{REP_LABEL_HE}">\n{body}\n</{REP_TAG}>'


def guard_note(violations: Sequence[str]) -> str:
    listed = ", ".join(violations)
    return (
        "Automated number check: your draft reply contained numbers that do not come from "
        f"any tool result, the employee's words or get_rule: {listed}. The draft was not shown. "
        "Write the reply again using only numbers that appear in tool results (display values) "
        "or that the employee wrote. Do not compute, round or estimate."
    )


def is_server_event(message: Message, kind: str | None = None) -> bool:
    content = message.content if isinstance(message.content, dict) else {}
    return (
        message.role == "system_event"
        and content.get("origin") == SERVER_ORIGIN
        and (kind is None or content.get("kind") == kind)
    )


def build_model_messages(rows: Sequence[Message]) -> list[ModelMessage]:
    """The model's input, rebuilt from the stored rows on every call.

    Deterministic and append-only: the rendering of a row never depends on later rows, so the
    prefix sent to the model only ever grows (prompt cache and preserved thinking stay valid).
    """
    user_text = {m.seq: m.content.get("text", "") for m in rows if m.role == "user"}
    out: list[ModelMessage] = []
    for row in rows:
        content = row.content if isinstance(row.content, dict) else {}
        if row.role == "user":
            continue  # rendered at its employee_turn
        if row.role == "system_event":
            if not is_server_event(row):
                continue  # never trust a system_event without the server origin
            kind = content.get("kind")
            if kind == "employee_turn":
                text = user_text.get(content["message_seq"], "")
                out.append(
                    {"role": "user", "content": [{"type": "text", "text": employee_block(text)}]}
                )
            elif kind == "rep_answer":
                out.append(
                    {"role": "user", "content": [{"type": "text", "text": rep_block(content)}]}
                )
            elif kind == "guard_correction":
                out.append({"role": "system", "content": guard_note(content["violations"])})
        elif row.role == "assistant":
            out.append({"role": "assistant", "content": content["blocks"]})
        elif row.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": result["tool_use_id"],
                            "content": result["model_view"],
                            **({} if result["ok"] else {"is_error": True}),
                        }
                        for result in content["results"]
                    ],
                }
            )
    return out


# --- compact tool-result views ----------------------------------------------------------------

_BREAKDOWN_KEEP = ("scenario", "car_id", "vehicle_key", "display", "metadata")


def _compact_comparison(comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "today": {k: comparison["today"].get(k) for k in _BREAKDOWN_KEEP},
        "alternative": {k: comparison["alternative"].get(k) for k in _BREAKDOWN_KEEP},
        "display_diff": comparison["display_diff"],
        "display_delta_lines": comparison["display_delta_lines"],
        "explanation_facts": comparison["explanation_facts"],
        "warnings": comparison["warnings"],
        "missing": comparison["missing"],
        "partial": comparison["partial"],
    }


def model_view(name: str, result: dict[str, Any]) -> str:
    """What the model reads of a tool result: display values and facts, without the exact
    breakdowns (those go to the DB and the UI). Bounded by construction, never edited later."""
    view = dict(result)
    if result.get("ok") and name == "compare":
        view["comparison"] = _compact_comparison(result["comparison"])
    elif result.get("ok") and name == "ask_representative" and "provisional_comparisons" in result:
        view["provisional_comparisons"] = [
            {**c, "comparison": _compact_comparison(c["comparison"])}
            for c in result["provisional_comparisons"]
        ]
    elif result.get("ok") and name == "list_options":
        view["options"] = [
            {
                "scenario": option["scenario"],
                "commercial_name": option.get("commercial_name"),
                "group": option.get("group"),
                "drive": option.get("drive"),
                "eligibility": {
                    "status": option["eligibility"]["status"],
                    "reason": option["eligibility"]["reason"],
                },
                "display_diff": option["comparison"]["display_diff"],
                "net": option["comparison"]["alternative"]["display"]["net"],
                "partial": option["comparison"]["partial"],
                "participation_source": option.get("participation_source"),
                "pending_rep": option.get("pending_rep"),
            }
            for option in result["options"]
        ]
        if result["options"]:  # today's net is the same in every option
            view["today_net"] = result["options"][0]["comparison"]["today"]["display"]["net"]
    return json.dumps(view, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

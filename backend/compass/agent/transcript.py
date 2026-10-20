"""The agent's transcript: what is stored in `messages`, and how it becomes the model's input.

Stored rows (append-only, in `seq` order):

    user          {"text"}                      the employee's message as the UI shows it
    system_event  {"kind": "employee_turn", "message_seq", "origin": "server"}
                                                 the runner took that user message into the
                                                 conversation (here, not at the user row: a
                                                 message typed mid-run must not split a tool
                                                 call from its result)
    system_event  {"kind": "rep_answer", ...}   a representative answered a ticket
    system_event  {"kind": "payslip_confirmed", ...}
                                                 the employee confirmed values read from their
                                                 payslip (only confirmed ones, never the file)
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
PAYSLIP_TAG = "payslip_notification"
PAYSLIP_LABEL_HE = "לפי התלוש"

# Our structural tags, opening or closing, in any case or spacing: neutralised in untrusted text.
_TAG_PATTERN = re.compile(
    rf"<\s*/?\s*({EMPLOYEE_TAG}|{REP_TAG}|{PAYSLIP_TAG}|system[_ -]?notice)\b", re.IGNORECASE
)

ModelMessage = dict[str, Any]


def escape_tags(text: str) -> str:
    """Make our tag names inert inside untrusted text (employee or representative)."""
    return _TAG_PATTERN.sub(lambda m: m.group(0).replace("<", "&lt;"), text)


def employee_block(text: str) -> str:
    return f"<{EMPLOYEE_TAG}>\n{escape_tags(text)}\n</{EMPLOYEE_TAG}>"


# A representative's answers to the ticket's questions (compass/tools/questions.py): data the
# model reads, never instructions. Free answers never change a value.
REP_QUESTION_KEYS = (
    "free_answers",
    "free_unanswered",
    "needs_checking",
    "notes",
    "pending_questions",
)


def _escaped(data: Any) -> Any:
    """`data` with our tag names made inert in every string (keys and values)."""
    if isinstance(data, str):
        return escape_tags(data)
    if isinstance(data, dict):
        return {escape_tags(str(k)): _escaped(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_escaped(v) for v in data]
    return data


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
    for key in REP_QUESTION_KEYS:
        if event.get(key):
            payload[key] = _escaped(event[key])
    if event.get("profile_after"):
        # the occupation and group in effect after the answer, with the warnings (server)
        payload["profile_after"] = _escaped(event["profile_after"])
    if event.get("today_after"):
        # today's situation after a current_car answer, with the warnings (server)
        payload["today_after"] = _escaped(event["today_after"])
    if event.get("server_comparisons"):
        # compare's own (compact) result, recomputed by the server with the answer
        payload["server_comparisons"] = event["server_comparisons"]
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f'<{REP_TAG} label="{REP_LABEL_HE}">\n{body}\n</{REP_TAG}>'


def payslip_block(event: dict[str, Any]) -> str:
    """Values the employee confirmed from their payslip, as structured data (server-written).
    The file and any value the employee did not confirm never reach the model."""
    payload = {
        "confirmed_values": event.get("values", {}),
        "kept_representative": event.get("kept_representative", []),
        "waiting_for_rep": event.get("waiting_for_rep", []),
    }
    if event.get("car_hint"):
        # one catalog car has exactly the payslip's value of use: ask, never assume
        payload["car_hint"] = _escaped(event["car_hint"])
    if event.get("server_comparisons"):
        payload["server_comparisons"] = event["server_comparisons"]
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f'<{PAYSLIP_TAG} label="{PAYSLIP_LABEL_HE}">\n{body}\n</{PAYSLIP_TAG}>'


def guard_note(violations: Sequence[str]) -> str:
    """The retry instruction after the number guard rejected a draft: the exact numbers, and
    what to do about them. The draft itself is not in the conversation, so the model cannot see
    which sentence they were in: it must be told to drop them, and that a number inside a
    question to the employee (an age, a count) is dropped too, the question asked in words."""
    listed = ", ".join(violations)
    return (
        "Automated number check: your draft reply was NOT shown, because it contained numbers "
        "that no tool result, employee message or representative answer supports: "
        f"{listed}. Write the reply again WITHOUT these exact numbers: do not write them, do "
        "not round them, do not swap in another figure. If one of them was inside a question to "
        "the employee (an age, a count, an amount), ask that question in words with no number. "
        "Every number you do write must appear in a tool result already in this conversation "
        "(display values) or be one the employee wrote. Do not compute or estimate."
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
            elif kind == "payslip_confirmed":
                text = payslip_block(content)
                out.append({"role": "user", "content": [{"type": "text", "text": text}]})
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
    compact = {
        "today": None
        if comparison["today"] is None
        else {k: comparison["today"].get(k) for k in _BREAKDOWN_KEEP},
        "alternative": {k: comparison["alternative"].get(k) for k in _BREAKDOWN_KEEP},
        "display_diff": comparison["display_diff"],
        "display_delta_lines": comparison["display_delta_lines"],
        "explanation_facts": comparison["explanation_facts"],
        "warnings": comparison["warnings"],
        "missing": comparison["missing"],
        "partial": comparison["partial"],
    }
    if comparison.get("today_unknown"):  # no today, no diff: each alternative's own net
        compact["today_unknown"] = True
    return compact


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
        today = result["options"][0]["comparison"]["today"] if result["options"] else None
        if today is not None:  # today's net is the same in every option
            view["today_net"] = today["display"]["net"]
        elif result["options"]:  # each option's own net; the diffs wait for today's car
            view["today_unknown"] = True
    return json.dumps(view, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

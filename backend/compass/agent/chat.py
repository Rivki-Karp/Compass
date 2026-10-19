"""Terminal chat with the real model:  uv run python tasks.py chat

Prints tool calls and guard checks dimmed as they happen, the comparison as the demo table, and
the agent's reply. Commands:
    /rep    list open tickets of this session and answer one as the representative
    /state  print the session profile and today's situation
    /new    start a new session
    /quit   leave (Ctrl+C / Ctrl+Z also work)
"""

import json
import sys
from collections.abc import Callable
from datetime import date
from typing import Any

from compass.agent.prompts import opening_message
from compass.agent.runner import ClaudeAgentRunner
from compass.demo import WIDTH
from compass.labels import BREAKDOWN_ROWS, DELTA_LABELS
from compass.state import Event
from compass.tools.profile import TOOL_OF, to_tool_value
from compass.tools.services import Services
from compass.tools.tickets import TicketAnswerError, answer_ticket

Ask = Callable[[str], str]
Say = Callable[[str], None]

DIM, BOLD, RESET = "\x1b[2m", "\x1b[1m", "\x1b[0m"


def _money(value: int | None, signed: bool = False) -> str:
    if value is None:
        return "?".rjust(WIDTH)
    return (f"{value:+,}" if signed else f"{value:,}").rjust(WIDTH)


def render_comparison(result: dict[str, Any]) -> str:
    """The demo table, from a compare tool result (display values only)."""
    comparison = result["comparison"]
    today, alt = comparison["today"]["display"], comparison["alternative"]["display"]
    out = [f"{'היום'.rjust(WIDTH)}  {'חלופה'.rjust(WIDTH)}  {'הפרש'.rjust(WIDTH)}  שורה"]
    for field, label in BREAKDOWN_ROWS:
        a, b = today.get(field), alt.get(field)
        delta = None if a is None or b is None else b - a
        out.append(f"{_money(a)}  {_money(b)}  {_money(delta, signed=True)}  {label}")
    out.append(f"{_money(comparison['display_diff'], signed=True)}  הפרש בנטו")
    for line in comparison["display_delta_lines"]:
        if line["net_effect"]:
            out.append(f"{_money(line['net_effect'], signed=True)}  {DELTA_LABELS[line['line']]}")
    flags = []
    if result.get("hypothetical"):
        flags.append("היפותטי — בכפוף לאישור")
    if result.get("pending_rep"):
        flags.append("השתתפות ממתינה לאישור הנציג")
    if comparison.get("partial"):
        flags.append("חלקי: " + ", ".join(comparison["missing"]))
    if flags:
        out.append(" · ".join(flags))
    return "\n".join(out)


class Chat:
    def __init__(
        self,
        services: Services,
        runner: ClaudeAgentRunner,
        ask: Ask = input,
        say: Say = print,
        color: bool = True,
    ) -> None:
        self.services, self.store, self.runner = services, services.store, runner
        self.ask, self.say = ask, say
        self.dim = (lambda t: f"{DIM}{t}{RESET}") if color else (lambda t: t)
        self.bold = (lambda t: f"{BOLD}{t}{RESET}") if color else (lambda t: t)
        self.session_id = ""
        self.store.subscribers.append(self._on_event)

    # --- live progress ------------------------------------------------------------------

    def _on_event(self, event: Event) -> None:
        if event.session_id != self.session_id:
            return
        p = event.payload
        if event.type == "tool_call":
            self.say(self.dim(f"  → {p['name']} {json.dumps(p['input'], ensure_ascii=False)}"))
        elif event.type == "tool_result":
            mark = "✓" if p["ok"] else "✗"
            self.say(
                self.dim(f"  {mark} {p['name']} {json.dumps(p['summary'], ensure_ascii=False)}")
            )
        elif event.type == "guard_check":
            text = f"  guard: {p['action']}"
            if p["violations"]:
                text += f" (violations: {', '.join(p['violations'])})"
            self.say(self.dim(text))
        elif event.type == "agent_error":
            self.say(self.dim(f"  agent_error: {p['kind']} — {p['message']}"))
        elif event.type == "comparison_ready":
            self.say(self.dim(render_comparison(p)))

    # --- the loop -----------------------------------------------------------------------

    def new_session(self) -> None:
        self.session_id = self.store.create_session()
        self.say(self.dim(f"[session {self.session_id}]"))
        self.say(self.bold("יועץ: ") + opening_message())

    def _reply(self) -> None:
        outcome = self.runner.last_outcome.get(self.session_id)
        if outcome is not None:
            self.say(self.bold("יועץ: ") + outcome.text)

    def run(self) -> int:
        self.new_session()
        while True:
            try:
                line = self.ask("אני: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.say("")
                return 0
            if not line:
                continue
            if line in ("/quit", "/exit"):
                return 0
            if line == "/new":
                self.new_session()
            elif line == "/state":
                self.show_state()
            elif line == "/rep":
                self.representative()
            else:
                seq = self.store.add_message(self.session_id, "user", {"text": line})
                self.runner.on_user_message(self.session_id, seq)
                self._reply()

    def show_state(self) -> None:
        slots = self.store.slots(self.session_id)
        if not slots:
            self.say(self.dim("  (no profile yet)"))
        for name, slot in slots.items():
            field = TOOL_OF.get(name, name)
            value = to_tool_value(field, slot.value) if slot.state == "filled" else slot.state
            self.say(f"  {field}: {value}  [{slot.source}]")
        today = self.store.scenarios(self.session_id).get("today")
        if today:
            self.say(f"  today: {today['label']}")

    def representative(self) -> None:
        tickets = self.store.tickets(status="open", session_id=self.session_id)
        if not tickets:
            self.say(self.dim("  אין פניות פתוחות / no open tickets"))
            return
        for n, ticket in enumerate(tickets, 1):
            self.say(f"  {n}. {ticket.question}  [{', '.join(ticket.blocking_fields)}]")
        choice = self.ask("  ticket #: ").strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(tickets):
            self.say(self.dim("  cancelled"))
            return
        ticket = tickets[int(choice) - 1]
        for qa in ticket.quick_answers:
            self.say(f"  [{qa['id']}] {qa['label']}")
        self.say(self.dim("  answer: a quick-answer id, field=value pairs, or free text"))
        answer = self.ask("  נציג: ").strip()
        kwargs = self._parse_answer(answer, ticket.quick_answers, ticket.blocking_fields)
        when = self.ask("  effective_from (YYYY-MM-DD, optional): ").strip()
        try:
            if when:
                kwargs["effective_from"] = date.fromisoformat(when)
            answered = answer_ticket(self.services, ticket.id, **kwargs)
        except (TicketAnswerError, ValueError) as error:
            self.say(f"  ✗ {getattr(error, 'detail', error)}")
            return
        self.say(self.dim(f"  ✓ ticket {answered.id[:8]} answered"))
        self.runner.on_ticket_answered(self.session_id, answered.id)
        self._reply()

    @staticmethod
    def _parse_answer(answer: str, quick_answers: list[Any], blocking: list[str]) -> dict[str, Any]:
        if answer in {qa["id"] for qa in quick_answers}:
            return {"quick_answer_id": answer}
        pairs = [part.split("=", 1) for part in answer.split() if "=" in part]
        if pairs and all(key in blocking for key, _ in pairs):
            values: dict[str, Any] = {}
            for key, raw in pairs:
                values[key] = int(raw) if raw.isdigit() and key == "children_under_23" else raw
            return {"values": values}
        return {"answer_text": answer}


def main() -> int:
    for stream in (sys.stdin, sys.stdout):  # Hebrew in Windows PowerShell
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if sys.platform == "win32":
        import os

        os.system("")  # enable ANSI colours in the Windows console
    from compass.agent.factory import build_claude_runner
    from compass.agent.startup import load_agent_settings
    from compass.state import Store

    settings = load_agent_settings()
    services = Services(
        Store(settings.app_db),
        rules_path=settings.rules_path,
        aliases_path=settings.aliases_path,
        vehicles_db=settings.vehicles_db,
    )
    runner = build_claude_runner(settings, services, background=False)
    print(f"{DIM}model {settings.model} · /rep /state /new /quit{RESET}")
    return Chat(services, runner).run()


if __name__ == "__main__":
    sys.exit(main())

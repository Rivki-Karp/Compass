"""ClaudeAgentRunner: the Claude tool-use loop behind the Day 2 AgentRunner seam.

One run per session at a time: each session has a worker thread and a queue, so the API's
`POST /messages` returns 202 immediately and a message typed mid-run waits its turn.

A run:
    1. appends the trigger to the transcript (employee_turn / rep_answer, server-written)
    2. loops model -> tools -> model until a final text or `max_tool_rounds`
    3. checks the final text with the number guard; on a violation the draft is discarded,
       a correction note is appended and the model rewrites once without tools; still bad ->
       a deterministic message built from the tool results
    4. emits events throughout; failures end in a friendly Hebrew message + agent_error

Before step 1, the session safety limit: once a session has had `max_session_turns` runs or
used `max_session_input_tokens` input tokens, a run replies with SESSION_LIMIT_HE (kind "limit")
and never calls the model or the guard. The UI then offers a new conversation.

The transcript is append-only (see transcript.py), so the model input only ever grows.
"""

import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from compass.agent.llm import LLMClient, LLMError, LLMResponse, Usage
from compass.agent.transcript import (
    SERVER_ORIGIN,
    build_model_messages,
    model_view,
)
from compass.tools import ToolRunner, tool_definitions
from compass.tools.handlers import settled_compare_results
from compass.tools.services import Services

log = logging.getLogger(__name__)

ERROR_MESSAGE_HE = (
    "מצטער, נתקלתי בבעיה טכנית ולא הצלחתי להשלים את התשובה. "
    "הנתונים שמסרת נשמרו — אפשר לכתוב לי שוב בעוד רגע."
)
TOO_MANY_ROUNDS_HE = (
    "מצטער, החישוב הזה הסתבך לי יותר מדי. הנתונים שמסרת נשמרו — "
    "אפשר לנסח את הבקשה שוב, צעד אחד בכל פעם?"
)
GUARD_FALLBACK_HE = (
    "לא הצלחתי לנסח תשובה שכל המספרים בה מאומתים, ולכן לא אציג מספרים בטקסט. "
    "התוצאות המחושבות מוצגות בכרטיס ההשוואה."
)
# The session safety limit (replaces drop_block): fixed, no numbers, never sent to the guard.
SESSION_LIMIT_HE = "השיחה הגיעה לאורך המרבי. אפשר להתחיל שיחה חדשה."

Job = tuple[Literal["employee_turn", "rep_answer"], Any]


@dataclass(frozen=True)
class GuardVerdict:
    passed: bool
    numbers: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    # number as written -> where it comes from (a tool name, "employee", "representative",
    # "harmless"); only the permitted ones
    sources: dict[str, str] = field(default_factory=dict)


# (text, session_id) -> verdict.  Stage 3 plugs in the real guard.
Guard = Callable[[str, str], GuardVerdict]
# session_id -> a deterministic message built from the session's tool results.
TemplateFallback = Callable[[str], str]


def _no_guard(text: str, session_id: str) -> GuardVerdict:
    return GuardVerdict(passed=True)


def _no_template(session_id: str) -> str:
    return GUARD_FALLBACK_HE


@dataclass
class RunOutcome:
    text: str
    kind: Literal["reply", "template", "error", "limit"]
    rounds: int = 0
    usage: Usage = field(default_factory=Usage)
    guard: list[GuardVerdict] = field(default_factory=list)
    error: str | None = None
    message_seq: int | None = None
    limit: Literal["turns", "input_tokens"] | None = None  # which session limit was reached


class ClaudeAgentRunner:
    def __init__(
        self,
        services: Services,
        llm: LLMClient,
        system_prompt: str,
        *,
        tool_runner: ToolRunner | None = None,
        max_tool_rounds: int = 8,
        max_session_turns: int = 40,
        max_session_input_tokens: int = 2_000_000,
        guard: Guard = _no_guard,
        template: TemplateFallback = _no_template,
        background: bool = True,
    ) -> None:
        self.services = services
        self.store = services.store
        self.llm = llm
        self.system_prompt = system_prompt
        self.tool_runner = ToolRunner(services) if tool_runner is None else tool_runner
        self.tools = tool_definitions()  # fixed for the life of the runner (cache prefix)
        self.max_tool_rounds = max_tool_rounds
        self.max_session_turns = max_session_turns
        self.max_session_input_tokens = max_session_input_tokens
        self.guard = guard
        self.template = template
        self.background = background
        self._lock = threading.Lock()
        self._queues: dict[str, queue.Queue[Job]] = {}
        self._workers: dict[str, threading.Thread] = {}
        self.last_outcome: dict[str, RunOutcome] = {}

    # --- AgentRunner protocol -----------------------------------------------------------

    def on_user_message(self, session_id: str, message_seq: int) -> None:
        self._submit(session_id, ("employee_turn", message_seq))

    def on_ticket_answered(self, session_id: str, ticket_id: str) -> None:
        self._submit(session_id, ("rep_answer", ticket_id))

    # --- scheduling ---------------------------------------------------------------------

    def _submit(self, session_id: str, job: Job) -> None:
        if not self.background:
            self.process(session_id, job)
            return
        with self._lock:
            jobs = self._queues.setdefault(session_id, queue.Queue())
            jobs.put(job)
            worker = self._workers.get(session_id)
            if worker is None or not worker.is_alive():
                worker = threading.Thread(
                    target=self._work,
                    args=(session_id,),
                    name=f"agent-{session_id[:8]}",
                    daemon=True,
                )
                self._workers[session_id] = worker
                worker.start()

    def _work(self, session_id: str) -> None:
        jobs = self._queues[session_id]
        while True:
            try:
                job = jobs.get(timeout=0.5)
            except queue.Empty:
                with self._lock:
                    if jobs.empty():  # nothing arrived meanwhile: retire this worker
                        self._workers.pop(session_id, None)
                        return
                continue
            try:
                self.process(session_id, job)
            finally:
                jobs.task_done()

    def wait_idle(self, timeout: float = 30.0) -> bool:
        """Block until every queued job has run (tests, chat, evals)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                busy = any(q.unfinished_tasks for q in self._queues.values())
            if not busy:
                return True
            time.sleep(0.02)
        return False

    def close(self) -> None:
        self.wait_idle(timeout=10)

    # --- one run ------------------------------------------------------------------------

    def process(self, session_id: str, job: Job) -> RunOutcome:
        """Run the agent for one job, synchronously. Never raises."""
        kind, ref = job
        started = time.monotonic()
        try:
            limit = self._session_limit(session_id)
            if limit is not None:
                outcome = self._limit_reply(session_id, kind, limit)
            else:
                self._append_trigger(session_id, kind, ref)
                start_seq = self._last_event_seq(session_id)
                self.store.append_event(session_id, "agent_started", {"trigger": kind})
                outcome = self._loop(session_id, start_seq)
        except LLMError as error:
            outcome = self._fail(session_id, error.kind, str(error), ERROR_MESSAGE_HE)
        except Exception as error:  # a bug must never take the session down
            log.exception("agent run failed for session %s", session_id)
            outcome = self._fail(session_id, "internal", type(error).__name__, ERROR_MESSAGE_HE)
        self.last_outcome[session_id] = outcome
        self._finished(session_id, outcome, time.monotonic() - started)
        return outcome

    def _finished(self, session_id: str, outcome: RunOutcome, seconds: float) -> None:
        """agent_finished: the run is over (the UI stops its thinking indicator). Rounds, latency,
        usage and cost are for judges mode."""
        model = getattr(self.llm, "model", None)
        try:
            self.store.append_event(
                session_id,
                "agent_finished",
                {
                    "outcome": outcome.kind,
                    "error": outcome.error,
                    "rounds": outcome.rounds,
                    "latency_ms": round(seconds * 1000),
                    "model": model,
                    "usage": vars(outcome.usage),
                    "cost_usd": None if model is None else outcome.usage.cost_usd(model),
                    "limit": outcome.limit,
                },
            )
        except Exception:  # the store itself failed: nothing more we can do safely
            log.exception("could not record agent_finished for session %s", session_id)

    # --- the session safety limit -------------------------------------------------------

    def _session_limit(self, session_id: str) -> Literal["turns", "input_tokens"] | None:
        """Which limit this session has reached, from its own agent_finished events: the runs
        that were not limit replies, and the input tokens they used (guard retries included)."""
        runs = [
            e.payload
            for e in self.store.events_after(session_id)
            if e.type == "agent_finished" and e.payload.get("outcome") != "limit"
        ]
        if len(runs) >= self.max_session_turns:
            return "turns"
        used = sum(
            (run.get("usage") or {}).get(key, 0)
            for run in runs
            for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        )
        if used >= self.max_session_input_tokens:
            return "input_tokens"
        return None

    def _limit_reply(
        self, session_id: str, kind: str, limit: Literal["turns", "input_tokens"]
    ) -> RunOutcome:
        """The fixed reply: no trigger in the transcript, no model call, no guard."""
        log.info("session %s reached its %s limit; no model call", session_id, limit)
        self.store.append_event(session_id, "agent_started", {"trigger": kind})
        reply = LLMResponse(
            content=[{"type": "text", "text": SESSION_LIMIT_HE}], stop_reason="end_turn"
        )
        seq = self._store_assistant(session_id, reply, fabricated=f"limit:{limit}")
        self.store.append_event(
            session_id,
            "assistant_message",
            {"message_seq": seq, "text": SESSION_LIMIT_HE, "kind": "limit", "comparison_ref": None},
        )
        return RunOutcome(text=SESSION_LIMIT_HE, kind="limit", message_seq=seq, limit=limit)

    def _append_trigger(self, session_id: str, kind: str, ref: Any) -> None:
        if kind == "employee_turn":
            content = {"kind": "employee_turn", "message_seq": ref, "origin": SERVER_ORIGIN}
        else:
            ticket = self.store.ticket(ref)
            # this answer: the latest part (a partial answer leaves the other fields pending)
            event = next(
                (
                    e.payload
                    for e in reversed(self.store.events_after(session_id))
                    if e.type == "ticket_answered" and e.payload.get("ticket_id") == ticket.id
                ),
                {},
            )
            answer = event.get("answer") or ticket.answer or {}
            values = answer.get("values") or {}
            pending = event.get("pending") or []
            so_far = (ticket.answer or {}).get("values") or {}
            content = {
                "kind": "rep_answer",
                "origin": SERVER_ORIGIN,
                "ticket_id": ticket.id,
                "question": ticket.question,
                "answer_text": answer.get("text"),
                "values": values,
                "effective_from": answer.get("effective_from"),
                "unknown_fields": [
                    f for f in ticket.blocking_fields if f not in so_far and f not in pending
                ],
            }
            if pending:
                content["pending_fields"] = pending
            # The comparisons the server settled with this answer, as compare would have
            # returned them to the model: it may state them without calling compare, and the
            # guard allows their numbers (source "server").
            settled = settled_compare_results(self.services, session_id, ticket.id, list(values))
            if settled:
                content["server_comparisons"] = [
                    json.loads(model_view("compare", result)) for result in settled
                ]
        self.store.add_message(session_id, "system_event", content, emit_event=False)

    def _last_event_seq(self, session_id: str) -> int:
        events = self.store.events_after(session_id)
        return events[-1].seq if events else 0

    def _call(self, session_id: str, tool_choice: dict[str, Any] | None = None) -> LLMResponse:
        messages = build_model_messages(self.store.messages(session_id))
        return self.llm.create(
            messages=messages, tools=self.tools, system=self.system_prompt, tool_choice=tool_choice
        )

    def _store_assistant(
        self, session_id: str, response: LLMResponse, fabricated: str | None = None
    ) -> int:
        content: dict[str, Any] = {
            "blocks": response.content,
            "usage": vars(response.usage),
            "model": response.model,
        }
        if fabricated:
            content["fabricated"] = fabricated
        return self.store.add_message(session_id, "assistant", content, emit_event=False)

    def _loop(self, session_id: str, start_seq: int) -> RunOutcome:
        outcome = RunOutcome(text="", kind="reply")
        while True:
            response = self._call(session_id)
            outcome.usage += response.usage
            if response.stop_reason == "refusal":
                return self._fail(
                    session_id, "refusal", "the model declined", ERROR_MESSAGE_HE, outcome
                )
            if response.tool_uses:
                self._store_assistant(session_id, response)
                outcome.rounds += 1
                self._run_tools(session_id, response)
                if outcome.rounds >= self.max_tool_rounds:
                    return self._fail(
                        session_id,
                        "max_tool_rounds",
                        f"stopped after {outcome.rounds} tool rounds",
                        TOO_MANY_ROUNDS_HE,
                        outcome,
                    )
                continue
            if not response.text:
                return self._fail(
                    session_id,
                    "empty_reply",
                    f"stop_reason {response.stop_reason}",
                    ERROR_MESSAGE_HE,
                    outcome,
                )
            return self._finish(session_id, response, start_seq, outcome)

    def _run_tools(self, session_id: str, response: LLMResponse) -> None:
        results = []
        for use in response.tool_uses:
            self.store.append_event(
                session_id,
                "tool_call",
                {"tool_use_id": use["id"], "name": use["name"], "input": use.get("input", {})},
            )
            result = self.tool_runner.run(session_id, use["name"], use.get("input", {}))
            self.store.append_event(
                session_id,
                "tool_result",
                {
                    "tool_use_id": use["id"],
                    "name": use["name"],
                    "ok": result["ok"],
                    "summary": _summary(use["name"], result),
                    "result": result,  # the full result: judges mode only (see api/redact.py)
                },
            )
            results.append(
                {
                    "tool_use_id": use["id"],
                    "name": use["name"],
                    "ok": result["ok"],
                    "model_view": model_view(use["name"], result),
                    "full": result,
                }
            )
        self.store.add_message(session_id, "tool", {"results": results}, emit_event=False)

    def _finish(
        self, session_id: str, response: LLMResponse, start_seq: int, outcome: RunOutcome
    ) -> RunOutcome:
        verdict = self.guard(response.text, session_id)
        outcome.guard.append(verdict)
        if verdict.passed:
            self._guard_event(session_id, verdict, "accept")
            return self._reply(session_id, response, start_seq, outcome, "reply")

        # Discard the draft (never shown, never in the transcript); ask for one rewrite.
        self._guard_event(session_id, verdict, "retry", draft=response.text)
        self.store.add_message(
            session_id,
            "system_event",
            {"kind": "guard_correction", "origin": SERVER_ORIGIN, "violations": verdict.violations},
            emit_event=False,
        )
        retry = self._call(session_id, tool_choice={"type": "none"})
        outcome.usage += retry.usage
        second = self.guard(retry.text, session_id) if retry.text else GuardVerdict(False)
        outcome.guard.append(second)
        if retry.text and second.passed:
            self._guard_event(session_id, second, "accept_after_retry")
            return self._reply(session_id, retry, start_seq, outcome, "reply")
        self._guard_event(session_id, second, "template")
        text = self.template(session_id)
        fabricated = LLMResponse(content=[{"type": "text", "text": text}], stop_reason="end_turn")
        return self._reply(session_id, fabricated, start_seq, outcome, "template")

    def _guard_event(
        self, session_id: str, verdict: GuardVerdict, action: str, draft: str | None = None
    ) -> None:
        payload: dict[str, Any] = {
            "passed": verdict.passed,
            "numbers": verdict.numbers,
            "violations": verdict.violations,
            "sources": verdict.sources,
            "action": action,
        }
        if draft is not None:
            payload["rejected_draft"] = draft  # for audit / judges mode; never shown as a reply
        self.store.append_event(session_id, "guard_check", payload)

    def _reply(
        self,
        session_id: str,
        response: LLMResponse,
        start_seq: int,
        outcome: RunOutcome,
        kind: Literal["reply", "template"],
    ) -> RunOutcome:
        seq = self._store_assistant(
            session_id, response, fabricated="guard_template" if kind == "template" else None
        )
        self.store.append_event(
            session_id,
            "assistant_message",
            {
                "message_seq": seq,
                "text": response.text,
                "kind": kind,
                "comparison_ref": self._comparison_ref(session_id, start_seq),
            },
        )
        outcome.text, outcome.kind, outcome.message_seq = response.text, kind, seq
        return outcome

    def _comparison_ref(self, session_id: str, start_seq: int) -> int | None:
        events = self.store.events_after(session_id, start_seq)
        refs = [e.seq for e in events if e.type == "comparison_ready"]
        return refs[-1] if refs else None

    def _fail(
        self,
        session_id: str,
        kind: str,
        message: str,
        text: str,
        outcome: RunOutcome | None = None,
    ) -> RunOutcome:
        outcome = RunOutcome(text="", kind="error") if outcome is None else outcome
        try:
            self.store.append_event(session_id, "agent_error", {"kind": kind, "message": message})
            fallback = LLMResponse(content=[{"type": "text", "text": text}], stop_reason="end_turn")
            seq = self._store_assistant(session_id, fallback, fabricated=f"error:{kind}")
            self.store.append_event(
                session_id,
                "assistant_message",
                {"message_seq": seq, "text": text, "kind": "error", "comparison_ref": None},
            )
            outcome.message_seq = seq
        except Exception:  # the store itself failed: nothing more we can do safely
            log.exception("could not record agent failure for session %s", session_id)
        outcome.text, outcome.kind, outcome.error = text, "error", kind
        return outcome


def _summary(name: str, result: dict[str, Any]) -> dict[str, Any]:
    """A small, UI-friendly summary of a tool result (the full result is in the transcript)."""
    if not result["ok"]:
        error = result["error"]
        return {"error": error["code"], "fields": error.get("fields")}
    if name == "compare":
        return {
            "display_diff": result["comparison"]["display_diff"],
            "hypothetical": result["hypothetical"],
            "pending_rep": result.get("pending_rep"),
            "partial": result["comparison"]["partial"],
        }
    if name in ("lookup_vehicle", "lookup_occupation"):
        return {"confident": result["confident"], "candidates": len(result["candidates"])}
    if name == "save_profile":
        return {"saved": sorted(result["saved"]), "missing": result["missing"]}
    if name == "list_options":
        return {"options": len(result["options"])}
    return {}

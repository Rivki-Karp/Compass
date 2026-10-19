"""Run one scenario: a fresh session, the scripted turns, then a Trace and the check results."""

import time
from dataclasses import dataclass, field
from typing import Any

from compass.agent.llm import Usage
from compass.agent.runner import ClaudeAgentRunner, Guard, RunOutcome
from compass.tools.profile import TOOL_OF, to_tool_value
from compass.tools.services import Services
from compass.tools.tickets import TicketAnswerError, answer_ticket
from evals.checks import Call, CheckResult, Comparison, Reply, Trace, evaluate
from evals.scenario import FALLBACK_HE, RepAnswer, Scenario


@dataclass
class RunResult:
    scenario: str
    results: list[CheckResult]
    trace: Trace
    session_id: str = ""
    turns: int = 0
    rounds: int = 0
    latency_s: float = 0.0
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def guard_retries(self) -> int:
        return self.trace.guard_actions.count("retry")

    @property
    def templates(self) -> int:
        return self.trace.guard_actions.count("template")


def _input_of(alternative: dict[str, Any]) -> dict[str, Any]:
    """The compare input that names a stored alternative (a car by its catalog id)."""
    car_id = alternative.get("car_id")
    if car_id is not None:
        return {"alternative": {"kind": "car", "car_id": car_id}}
    return {"alternative": {"kind": alternative.get("kind")}}


class Harness:
    def __init__(
        self, services: Services, runner: ClaudeAgentRunner, guard: Guard, model: str
    ) -> None:
        self.services, self.store, self.runner = services, services.store, runner
        self.guard, self.model = guard, model

    def run(self, scenario: Scenario) -> RunResult:
        session_id = self.store.create_session()
        result = RunResult(scenario.name, [], Trace(), session_id)
        bounds: list[int] = []  # the last event seq at the end of each turn
        for turn in scenario.turns:
            if turn.employee is not None:
                self._employee(session_id, turn.employee, result)
            else:
                assert turn.rep is not None
                self._rep(session_id, turn.rep, result)
            bounds.append(self._last_seq(session_id))
        extra = 0
        while scenario.until_compare and extra < scenario.max_extra_turns:
            if self._compared(session_id):
                break
            self._employee(session_id, FALLBACK_HE, result)
            bounds.append(self._last_seq(session_id))
            extra += 1
        result.turns = len(bounds)
        self._collect(session_id, bounds, result.trace)
        result.results = evaluate(result.trace, scenario.checks)
        result.cost_usd = result.usage.cost_usd(self.model) or 0.0
        return result

    # --- turns --------------------------------------------------------------------------

    def _employee(self, session_id: str, text: str, result: RunResult) -> None:
        seq = self.store.add_message(session_id, "user", {"text": text})
        self._timed(result, lambda: self.runner.on_user_message(session_id, seq), session_id)

    def _rep(self, session_id: str, rep: RepAnswer, result: RunResult) -> None:
        tickets = self.store.tickets(status="open", session_id=session_id)
        if rep.field is not None:
            tickets = [t for t in tickets if rep.field in t.blocking_fields]
        if len(tickets) != 1:
            result.trace.problems.append(
                f"rep turn: expected one open ticket for {rep.field!r}, found {len(tickets)}"
            )
            return
        try:
            answered = answer_ticket(
                self.services,
                tickets[0].id,
                values=rep.values,
                answer_text=rep.answer_text,
                effective_from=rep.effective_from,
            )
        except TicketAnswerError as error:
            result.trace.problems.append(f"rep turn: {error.detail}")
            return
        self._timed(
            result, lambda: self.runner.on_ticket_answered(session_id, answered.id), session_id
        )

    def _timed(self, result: RunResult, call: Any, session_id: str) -> None:
        before = self.runner.last_outcome.get(session_id)
        start = time.perf_counter()
        call()  # synchronous: the runner is built with background=False
        result.latency_s += time.perf_counter() - start
        outcome: RunOutcome | None = self.runner.last_outcome.get(session_id)
        if outcome is not None and outcome is not before:
            result.rounds += outcome.rounds
            result.usage += outcome.usage

    def _last_seq(self, session_id: str) -> int:
        events = self.store.events_after(session_id)
        return events[-1].seq if events else 0

    def _compared(self, session_id: str) -> bool:
        return any(e.type == "comparison_ready" for e in self.store.events_after(session_id))

    # --- the trace ----------------------------------------------------------------------

    def _collect(self, session_id: str, bounds: list[int], trace: Trace) -> None:
        def turn_of(seq: int) -> int:
            return next((i for i, bound in enumerate(bounds) if seq <= bound), len(bounds) - 1)

        full: dict[str, dict[str, Any]] = {}
        for message in self.store.messages(session_id):
            if message.role == "tool":
                for r in message.content["results"]:
                    full[r["tool_use_id"]] = r["full"]
        calls: dict[str, Call] = {}
        compare_input: dict[str, Any] = {}  # of the latest compare call
        inputs_by_seq: dict[int, dict[str, Any]] = {}
        for event in self.store.events_after(session_id):
            p, turn = event.payload, turn_of(event.seq)
            if event.type == "tool_call":
                result = full.get(p["tool_use_id"], {})
                calls[p["tool_use_id"]] = Call(
                    turn, p["name"], p["input"] or {}, bool(result.get("ok")), result
                )
                if p["name"] == "compare":
                    compare_input = p["input"] or {}
            elif event.type == "comparison_ready":
                origin = p.get("recomputed_from")
                if origin is not None:  # a server recompute: the input of what it recomputes
                    source = inputs_by_seq.get(origin, {})
                elif p.get("origin") == "server":  # a ticket's provisional comparison (8b)
                    source = _input_of(p["alternative"])
                else:  # compare's own result
                    source = compare_input
                inputs_by_seq[event.seq] = source
                trace.comparisons.append(Comparison(turn, source, p))
            elif event.type == "assistant_message":
                trace.replies.append(Reply(turn, p["text"], p["kind"]))
            elif event.type == "user_message":
                trace.employee_messages.append((turn, p["content"]["text"]))
            elif event.type == "guard_check":
                trace.guard_actions.append(p["action"])
            elif event.type == "agent_error":
                trace.errors.append(p)
        trace.calls = list(calls.values())
        for name, slot in self.store.slots(session_id).items():
            tool_field = TOOL_OF.get(name, name)
            value = to_tool_value(tool_field, slot.value) if slot.state == "filled" else None
            trace.slots[tool_field] = {"value": value, "state": slot.state, "source": slot.source}
        # Re-check every shown reply against the session's allowed numbers (end of the run).
        for reply in trace.replies:
            if reply.kind != "error":
                trace.guard_rechecks.append(
                    (reply.turn, self.guard(reply.text, session_id).violations)
                )

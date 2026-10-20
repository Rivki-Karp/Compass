"""The seam where Day 3's Claude tool-use loop plugs in. Today: a runner that does nothing."""

from typing import Any, Protocol


class AgentRunner(Protocol):
    def on_user_message(self, session_id: str, message_seq: int) -> None:
        """A user message was stored; answer it (asynchronously) via tools and events."""

    def on_ticket_answered(self, session_id: str, ticket_id: str) -> None:
        """A representative answered; resume the conversation."""

    def on_payslip_confirmed(self, session_id: str, confirmed: dict[str, Any]) -> None:
        """The employee confirmed payslip values (COMPASS_PAYSLIP=1); resume, with them as data."""


class NullAgentRunner:
    """Stores nothing and answers nothing (no LLM until Day 3)."""

    def on_user_message(self, session_id: str, message_seq: int) -> None:
        return None

    def on_ticket_answered(self, session_id: str, ticket_id: str) -> None:
        return None

    def on_payslip_confirmed(self, session_id: str, confirmed: dict[str, Any]) -> None:
        return None

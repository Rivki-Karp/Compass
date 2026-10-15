"""The number guard (Stage 3). Placeholder: every reply passes until Stage 3 lands."""

from compass.agent.runner import Guard, GuardVerdict
from compass.state import Store


def make_guard(store: Store) -> Guard:
    def check(text: str, session_id: str) -> GuardVerdict:
        return GuardVerdict(passed=True)

    return check

"""Deterministic replies built from tool results (Stage 3). Placeholder until Stage 3 lands."""

from compass.agent.runner import GUARD_FALLBACK_HE, TemplateFallback
from compass.state import Store


def make_template(store: Store) -> TemplateFallback:
    def build(session_id: str) -> str:
        return GUARD_FALLBACK_HE

    return build

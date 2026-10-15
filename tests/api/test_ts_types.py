"""The web UI's TypeScript types are generated from the Pydantic models; the committed file
must match them (run `uv run python tasks.py ts-types` and commit web/src/api/generated.ts)."""

from compass.api.ts_types import TS_FILE, render


def test_committed_ts_types_are_up_to_date() -> None:
    committed = TS_FILE.read_text(encoding="utf-8")
    assert committed == render(), "run `uv run python tasks.py ts-types` and commit generated.ts"


def test_view_fields_are_typed() -> None:
    text = render()
    assert '"up" | "down" | "flat"' in text
    assert '"pending_rep"' in text and "export type EventType" in text

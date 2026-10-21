"""The sources behind the numbers of a sent reply: "מאיפה המספר הזה?" (COMPASS_NUMBER_SOURCES=1).

This adds no calculation and no decision. The guard has already verified the reply and recorded,
for every number it permitted, its offsets in the checked text, its value, its source and the
row it was first seen in (guard.number_spans). Here those records become the public list that
rides on the `assistant_message` event:

    {start, end, value, kind, label, chip, what, origin, slot, ref}

    kind    tool | server | employee | representative | payslip | rule | catalog | derived
    chip    the source chip's key (labels.NUMBER_CHIP_LABELS), label its Hebrew text
    what    what the number is ("הפרש בנטו לחודש"), only when a stored comparison view says so
    origin  how it was produced {source, tool, label, at}; `label` may hold "{time}" for `at`
    slot    the view input it is ("base_salary"), when it is one
    ref     where to look: {message_seq, tool_use_id, comparison_seq, role}; the components of a
            diff are the stored view's `breakdown` (the waterfall's own data), never recomputed

A number is looked up in the stored comparison views (the `comparison_ready` events), never
derived. When it matches nothing there, or matches two different things, only the guard's own
record is shown. Plain text, no span: harmless numbers (1-9, years), numbers inside an identifier
("MG4", "CAR-10", "ATTO 3") and dates.
"""

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from compass.agent.guard import HARMLESS_INTEGERS, HARMLESS_YEARS
from compass.labels import (
    DELTA_LABELS,
    NUMBER_CHIP_LABELS,
    NUMBER_ROLE_LABELS,
    ORIGIN_LABELS,
    line_role_label,
    tool_origin_label,
)
from compass.state import Event

log = logging.getLogger(__name__)

# A number glued to a Latin name or id: "MG4", "C40", "CAR-10", "ATTO 3", "COROLLA CROSS 2025".
_IDENTIFIER_BEFORE = re.compile(r"[A-Za-z](?:-|[A-Za-z0-9]*[  ])?$")

_INPUT_KIND = {
    "employee_input": "employee",
    "occupation": "derived",
    "representative": "representative",
    "catalog_default": "catalog",
    "payslip": "payslip",
}
_KIND_CHIP = {
    "employee": "employee_input",
    "derived": "occupation",
    "representative": "representative",
    "catalog": "catalog_default",
    "payslip": "payslip",
}
# The sources a first-seen value can have that make a "computed" role (a diff, a net) a lie.
_STATED = frozenset({"employee", "representative", "payslip"})
_VIEW_UNITS_WITH_NUMBERS = frozenset({"ils", "percent", "points", "count"})


@dataclass(frozen=True)
class _Match:
    role: str  # diff | today_net | alternative_net | line:<key> | group_budget | input:<id>
    what: str
    slot: str | None
    alt_kind: str | None  # the alternative a role belongs to; None for roles shared by all
    chip: str | None  # an input's chip (the waterfall's own); None for computed roles
    seq: int  # the comparison_ready event it was found in

    @property
    def meaning(self) -> tuple[str, str | None]:
        return (self.role, self.alt_kind)


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _equal(token_value: Decimal, signed: bool, candidate: Any) -> bool:
    number = _decimal(candidate)
    if number is None:
        return False
    # the guard's own rule: a signed number must match the sign, an unsigned one either
    return number == token_value if signed else abs(number) == abs(token_value)


def _matches(event: Event, span: Mapping[str, Any], percent: bool) -> list[_Match]:
    """Where this number appears in one stored comparison view."""
    view = event.payload.get("view")
    if not isinstance(view, Mapping):
        return []
    value: Decimal = span["value"]
    signed: bool = span["signed"]
    alt = event.payload.get("alternative_kind")
    found: list[_Match] = []

    def add(role: str, what: str, candidate: Any, **extra: Any) -> None:
        if _equal(value, signed, candidate):
            found.append(
                _Match(
                    role=role,
                    what=what,
                    slot=extra.get("slot"),
                    alt_kind=extra.get("alt_kind"),
                    chip=extra.get("chip"),
                    seq=event.seq,
                )
            )

    if not percent:  # money: the nets, the diff, its lines, the group's budget
        add("diff", NUMBER_ROLE_LABELS["diff"], view.get("display_diff"), alt_kind=alt)
        add(
            "alternative_net",
            NUMBER_ROLE_LABELS["alternative_net"],
            view.get("alternative_net"),
            alt_kind=alt,
        )
        add("today_net", NUMBER_ROLE_LABELS["today_net"], view.get("today_net"))
        add("group_budget", NUMBER_ROLE_LABELS["group_budget"], view.get("group_budget"))
        for line in view.get("breakdown") or []:
            label = DELTA_LABELS.get(line.get("key"), line.get("label", ""))
            role = f"line:{line.get('key')}"
            add(role, line_role_label(label), line.get("net_effect"), alt_kind=alt)
    for item in view.get("inputs") or []:
        unit = item.get("unit")
        if unit not in _VIEW_UNITS_WITH_NUMBERS or item.get("source") == "pending_rep":
            continue
        if percent and unit != "percent":
            continue
        add(
            f"input:{item['id']}",
            item["label"],
            item.get("value"),
            slot=item["id"],
            chip=item.get("source"),
        )
    # A diff is the sum of its lines: when both match, the number is the diff.
    if any(m.role == "diff" for m in found):
        found = [m for m in found if not m.role.startswith("line:")]
    return found


def _resolve(
    comparisons: Sequence[Event], span: Mapping[str, Any], percent: bool, run_after: int
) -> _Match | None:
    """The one thing this number is in the stored views, or None (no match, or ambiguous).
    The comparisons of this run are tried first, then the whole session; the newest wins."""
    for scope in ([e for e in comparisons if e.seq > run_after], list(comparisons)):
        found = [m for event in scope for m in _matches(event, span, percent)]
        if not found:
            continue
        if len({m.meaning + (m.slot,) for m in found}) != 1:
            return None
        return max(found, key=lambda m: m.seq)
    return None


def _in_identifier(text: str, start: int) -> bool:
    return _IDENTIFIER_BEFORE.search(text[max(0, start - 40) : start]) is not None


def _plain(text: str, span: Mapping[str, Any]) -> bool:
    """Numbers that stay plain text: what the guard did not need a source for (a bare 1-9 or a
    year, even if a tool result happens to hold the same digit) and names with digits."""
    if span["source"] == "harmless":
        return True
    value: Decimal = span["value"]
    bare = not span["raw"].endswith("%")
    if bare and value == value.to_integral_value():
        whole = abs(int(value))
        if whole in HARMLESS_INTEGERS or whole in HARMLESS_YEARS:
            return True
    return _in_identifier(text, span["start"])


def _origin(span: Mapping[str, Any]) -> dict[str, Any]:
    source: str = span["source"]
    row: Mapping[str, Any] = span["origin"] or {}
    if source in ORIGIN_LABELS:  # employee, representative, payslip, server
        label, tool = ORIGIN_LABELS[source], None
    else:  # the guard names a tool result by the tool
        source, tool = "tool", span["source"]
        label = tool_origin_label(tool)
    return {"source": source, "tool": tool, "label": label, "at": row.get("at")}


def _record(text: str, span: Mapping[str, Any], match: _Match | None) -> dict[str, Any]:
    guard_source: str = span["source"]
    value: Decimal = span["value"]
    origin = _origin(span)
    kind: str
    chip: str
    stated_only = guard_source in _STATED
    if match is not None and match.chip is not None:  # one of the waterfall's inputs
        kind = _INPUT_KIND[match.chip]
        chip = _KIND_CHIP[kind]
    elif match is not None and not stated_only:  # computed by the engine
        kind = "rule" if match.role == "group_budget" else origin["source"]
        chip = "rule"
    else:
        match = None  # the first-seen source says someone stated it: no role is claimed
        kind = origin["source"]
        chip = _KIND_CHIP.get(kind, "tool")
    row: Mapping[str, Any] = span["origin"] or {}
    ref: dict[str, Any] = {
        "message_seq": row.get("message_seq"),
        "tool_use_id": row.get("tool_use_id"),
        "comparison_seq": None if match is None else match.seq,
        "role": None if match is None else match.role,
    }
    return {
        "start": span["start"],
        "end": span["end"],
        "value": format(value, "f"),
        "kind": kind,
        "label": NUMBER_CHIP_LABELS[chip],
        "chip": chip,
        "what": None if match is None else match.what,
        "origin": origin,
        "slot": None if match is None else match.slot,
        "ref": {k: v for k, v in ref.items() if v is not None},
    }


def build_number_sources(
    text: str, spans: Sequence[Mapping[str, Any]], events: Sequence[Event], run_after: int
) -> list[dict[str, Any]]:
    """The public `number_sources` of a sent reply. `text` is the exact text that was checked
    and sent, `spans` the guard's record of it, `events` the session's events, `run_after` the
    event seq this run started after (its comparisons are preferred)."""
    comparisons = [e for e in events if e.type == "comparison_ready"]
    out = []
    for span in spans:
        if _plain(text, span):
            continue
        percent = span["raw"].endswith("%")
        match = _resolve(comparisons, span, percent, run_after)
        out.append(_record(text, span, match))
    return out

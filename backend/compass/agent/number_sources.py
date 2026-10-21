"""The sources behind the numbers of a sent reply: "מאיפה המספר הזה?" (COMPASS_NUMBER_SOURCES=1).

This adds no calculation and no decision. The guard has already verified the reply and recorded,
for every number it permitted, its offsets in the checked text, its value, its source and the
row it was first seen in (guard.number_spans). Here those records become the public list that
rides on the `assistant_message` event:

    {start, end, value, kind, label, chip, what, origin, slot, ref}

    kind    tool | server | employee | representative | payslip | rule | catalog | derived
    chip    the source chip's key (labels.NUMBER_CHIP_LABELS), label its Hebrew text
    what    what the number is ("הפרש בנטו לחודש"), only when a stored view or the rules say so
    origin  how it was produced {source, tool, label, at}; `label` may hold "{time}" for `at`
    slot    the view input it is ("base_salary"), when it is one
    ref     where to look: {message_seq, tool_use_id, comparison_seq | option_set_seq, role,
            alternative}; the components of a diff are the stored view's `breakdown` (the
            waterfall's own data), never recomputed

The label never claims more than is known. The chip says what the value IS: "computed" for a
comparison's diff, net or line (and any other output of compare / list_options), "rule" only for
a value straight from the company rules (a group's budget), the input chips for what the
employee, a representative, a payslip, the occupation or the catalog gave. How it was produced
follows from that: only a tool that computes is "חושב בכלי X". A value is looked up in the
stored comparison views (comparison_ready, comparison_set_ready), the profile inputs and the
rules, never derived. A value that is two different kinds of thing stays plain text, and so do
harmless numbers (1-9, years), numbers inside an identifier ("MG4", "CAR-10", "ATTO 3") and
dates.
"""

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from compass.agent.guard import HARMLESS_INTEGERS, HARMLESS_YEARS
from compass.engine.decimal_math import to_display
from compass.labels import (
    DELTA_LABELS,
    NUMBER_CHIP_LABELS,
    NUMBER_ROLE_LABELS,
    OPTION_SET_ORIGIN_LABEL,
    ORIGIN_LABELS,
    ORIGIN_LABELS_UNTIMED,
    line_role_label,
    rule_origin_label,
    tool_origin_label,
)
from compass.state import Event
from compass.tools.services import Services
from compass.tools.view import PROVENANCE, profile_inputs

log = logging.getLogger(__name__)

# A number glued to a Latin name or id: "MG4", "C40", "CAR-10", "ATTO 3", "COROLLA CROSS 2025".
_IDENTIFIER_BEFORE = re.compile(r"[A-Za-z](?:-|[A-Za-z0-9]*[  ])?$")

# The tools whose output is a computation. Any other tool only echoes data.
COMPUTING_TOOLS = frozenset({"compare", "list_options"})
_STATED = frozenset({"employee", "representative", "payslip", "previous"})
_INPUT_KIND = {
    "employee_input": "employee",
    "occupation": "derived",
    "representative": "representative",
    "catalog_default": "catalog",
    "payslip": "payslip",
    "previous": "previous",  # confirmed from an earlier conversation (COMPASS_PROFILE_MEMORY)
}
_KIND_CHIP = {kind: chip for chip, kind in _INPUT_KIND.items()}
# What a lookup tool's number is when no stored view says more.
_LOOKUP_KIND = {
    "search_catalog": "catalog",
    "lookup_vehicle": "catalog",
    "lookup_occupation": "derived",
}
_UNITS_WITH_NUMBERS = frozenset({"ils", "percent", "points", "count"})


@dataclass(frozen=True)
class _Match:
    chip: str  # computed | rule | an input chip
    role: str  # diff | today_net | alternative_net | line:<key> | group_budget | input:<id>
    what: str
    slot: str | None
    alternative: str | None  # the car or kind a role belongs to; None for roles shared by all
    seq: int  # the event it was found in (0: the profile as it is now, or the rules)
    event_type: str  # comparison_ready | comparison_set_ready | slots | rules
    # who computed it, from the view itself: "tool" (the model's compare), "server" (the same
    # code run by the server, no model) or "option_set" (list_options); None: not computed
    computed_by: str | None = None

    @property
    def meaning(self) -> tuple[str, str | None, str | None]:
        return (self.role, self.alternative, self.slot)


@dataclass(frozen=True)
class Context:
    """What the stored events don't hold: the profile as it is now and the rules' own numbers,
    read by the runner from the same places the view reads them."""

    inputs: Sequence[Mapping[str, Any]] = ()
    # a group's budget as the UI shows it: {"value": 3700, "group": "ב", "from_occupation": True}
    budget: Mapping[str, Any] | None = None


def session_context(services: Services, session_id: str) -> Context:
    slots = services.store.slots(session_id)
    group = slots.get("group")
    budget = None
    if group is not None and group.state == "filled":
        amount = services.ctx.rules.budgets.get(group.value)
        if amount is not None:
            budget = {
                "value": to_display(amount, services.ctx.rules),
                "group": group.value,
                "from_occupation": group.source == "derived",
            }
    return Context(inputs=profile_inputs(services, session_id), budget=budget)


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


def _view_matches(
    view: Mapping[str, Any], seq: int, event_type: str, span: Mapping[str, Any], percent: bool
) -> list[_Match]:
    """Where this number appears in one stored comparison view."""
    value: Decimal = span["value"]
    signed: bool = span["signed"]
    alt = view.get("alternative_car_id") or view.get("alternative_kind")
    by = (view.get("computed_by") or {}).get("origin", "server")
    computed_by = "option_set" if event_type == "comparison_set_ready" else by
    found: list[_Match] = []

    def add(chip: str, role: str, what: str, candidate: Any, **extra: Any) -> None:
        if _equal(value, signed, candidate):
            found.append(
                _Match(
                    chip=chip,
                    role=role,
                    what=what,
                    slot=extra.get("slot"),
                    alternative=extra.get("alternative"),
                    seq=seq,
                    event_type=event_type,
                    computed_by=computed_by if chip == "computed" else None,
                )
            )

    if not percent:  # money: the nets, the diff, its lines
        for role, field, shared in (
            ("diff", "display_diff", False),
            ("alternative_net", "alternative_net", False),
            ("today_net", "today_net", True),
        ):
            add(
                "computed",
                role,
                NUMBER_ROLE_LABELS[role],
                view.get(field),
                alternative=None if shared else alt,
            )
        for line in view.get("breakdown") or []:
            label = DELTA_LABELS.get(line.get("key"), line.get("label", ""))
            role = f"line:{line.get('key')}"
            add("computed", role, line_role_label(label), line.get("net_effect"), alternative=alt)
    found += _input_matches(view.get("inputs") or [], seq, event_type, span, percent)
    # A diff is the sum of its lines: when both match, the number is the diff.
    if any(m.role == "diff" for m in found):
        found = [m for m in found if not m.role.startswith("line:")]
    return found


def _input_matches(
    inputs: Sequence[Mapping[str, Any]],
    seq: int,
    event_type: str,
    span: Mapping[str, Any],
    percent: bool,
) -> list[_Match]:
    found = []
    for item in inputs:
        unit = item.get("unit")
        if unit not in _UNITS_WITH_NUMBERS or item.get("source") not in _INPUT_KIND:
            continue  # text, or still pending a representative: nothing to claim
        if percent and unit != "percent":
            continue
        if _equal(span["value"], span["signed"], item.get("value")):
            found.append(
                _Match(
                    chip=item["source"],
                    role=f"input:{item['id']}",
                    what=item["label"],
                    slot=item["id"],
                    alternative=None,
                    seq=seq,
                    event_type=event_type,
                )
            )
    return found


def _all_matches(
    events: Sequence[Event],
    context: Context,
    span: Mapping[str, Any],
    percent: bool,
    run_after: int,
) -> list[_Match]:
    """Every place the number is in the stored views of this run, else of the whole session
    (the profile inputs and the rules are the same either way)."""

    def from_events(scope: Sequence[Event]) -> list[_Match]:
        found: list[_Match] = []
        for event in scope:
            if event.type == "comparison_ready":
                view = event.payload.get("view")
                if isinstance(view, Mapping):
                    found += _view_matches(view, event.seq, event.type, span, percent)
            elif event.type == "comparison_set_ready":
                for option in event.payload.get("options") or []:
                    view = option.get("view")
                    if isinstance(view, Mapping):
                        found += _view_matches(view, event.seq, event.type, span, percent)
        return found

    relevant = [e for e in events if e.type in ("comparison_ready", "comparison_set_ready")]
    found = from_events([e for e in relevant if e.seq > run_after]) or from_events(relevant)
    found += _input_matches(context.inputs, 0, "slots", span, percent)
    budget = context.budget
    if (
        budget is not None
        and not percent
        and _equal(span["value"], span["signed"], budget["value"])
    ):
        found.append(
            _Match(
                chip="rule",
                role="group_budget",
                what=NUMBER_ROLE_LABELS["group_budget"],
                slot=None,
                alternative=None,
                seq=0,
                event_type="rules",
            )
        )
    return found


def _pick(found: Sequence[_Match]) -> tuple[str, _Match | None] | None:
    """(chip, the one thing it is or None if several) - or None when the number is two different
    kinds of thing (a computed net that is also a budget): it then says nothing."""
    chips = {m.chip for m in found}
    if len(chips) != 1:
        return None
    if len({m.meaning for m in found}) != 1:
        return chips.pop(), None  # one kind of thing, not sure which: no "what", no ref
    # the model's own compare is the record, then the newest
    best = max(found, key=lambda m: (m.event_type == "comparison_ready", m.seq))
    return best.chip, best


def _line_is_its_input(found: Sequence[_Match]) -> tuple[str, _Match] | None:
    """A number that is both a line of the difference and the very input that line is built from
    (the same slot, the same value: the participation line and the participation input, the
    maintenance line and the waiver maintenance): it is that line, wearing the input's chip.
    Anything else that matches twice is not this and stays plain."""
    lines = [m for m in found if m.role.startswith("line:")]
    inputs = [m for m in found if m.role.startswith("input:")]
    if not lines or not inputs or len(lines) + len(inputs) != len(found):
        return None
    if len({m.chip for m in inputs}) != 1:
        return None

    def built_from(line: _Match) -> tuple[str, ...]:
        key = line.role.removeprefix("line:")
        return next((ids for name, (ids, _rules) in PROVENANCE.items() if name == key), ())

    for line in lines:
        if not any(i.slot in built_from(line) for i in inputs):
            return None
    best = max(lines, key=lambda m: (m.event_type == "comparison_ready", m.seq))
    chip = inputs[0].chip
    slot = next(i.slot for i in inputs if i.slot in built_from(best))
    return chip, _Match(
        chip=chip,
        role=best.role,
        what=best.what,
        slot=slot,
        alternative=best.alternative,
        seq=best.seq,
        event_type=best.event_type,
    )


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


def _origin(
    span: Mapping[str, Any], kind: str, chip: str, match: _Match | None, context: Context
) -> dict[str, Any]:
    """How the value was produced, from what it is: only a computing tool is "חושב בכלי X"."""
    guard_source: str = span["source"]
    row: Mapping[str, Any] = span["origin"] or {}
    tool: str | None = None
    at = None
    if chip == "computed":
        # the view says who computed it; else the guard's tool, which here always computes
        by = match.computed_by if match is not None else None
        by = by or {"compare": "tool", "list_options": "option_set"}.get(guard_source, "server")
        if by == "tool":
            source, tool, label = "tool", "compare", tool_origin_label("compare")
        elif by == "option_set":
            source, tool, label = "server", "list_options", OPTION_SET_ORIGIN_LABEL
        else:
            source, label = "server", ORIGIN_LABELS["server"]
    elif chip == "rule":
        budget = context.budget or {}
        source = "rule"
        label = rule_origin_label(budget.get("group"), bool(budget.get("from_occupation")))
    elif kind == guard_source and kind in ORIGIN_LABELS:  # the message itself: its time
        source, label, at = kind, ORIGIN_LABELS[kind], row.get("at")
    else:
        source, label = kind, ORIGIN_LABELS_UNTIMED[kind]
    return {"source": source, "tool": tool, "label": label, "at": at}


def _record(
    span: Mapping[str, Any], kind: str, chip: str, match: _Match | None, context: Context
) -> dict[str, Any]:
    row: Mapping[str, Any] = span["origin"] or {}
    ref: dict[str, Any] = {
        "message_seq": row.get("message_seq"),
        "tool_use_id": row.get("tool_use_id"),
        "role": None if match is None else match.role,
    }
    if match is not None and match.event_type == "comparison_ready":
        ref["comparison_seq"] = match.seq
    elif match is not None and match.event_type == "comparison_set_ready":
        ref["option_set_seq"], ref["alternative"] = match.seq, match.alternative
    return {
        "start": span["start"],
        "end": span["end"],
        "value": format(span["value"], "f"),
        "kind": kind,
        "label": NUMBER_CHIP_LABELS[chip],
        "chip": chip,
        "what": None if match is None else match.what,
        "origin": _origin(span, kind, chip, match, context),
        "slot": None if match is None else match.slot,
        "ref": {k: v for k, v in ref.items() if v is not None},
    }


def _classify(
    span: Mapping[str, Any], found: Sequence[_Match]
) -> tuple[str, str, _Match | None] | None:
    """(kind, chip, the match) of a verified number, or None to leave it as plain text."""
    guard_source: str = span["source"]
    if guard_source in _STATED:
        # someone said it: only the waterfall's own input can say more (the same chip it shows)
        inputs = [m for m in found if m.chip in _INPUT_KIND]
        picked = _pick(inputs) if inputs else None
        if picked is not None and picked[1] is not None:
            chip, match = picked
            return _INPUT_KIND[chip], chip, match
        return guard_source, _KIND_CHIP[guard_source], None
    picked = _pick(found) if found else None
    if found and picked is None:
        # two kinds of thing: say nothing rather than guess - except a line that is exactly the
        # input it was built from, which is that input
        echoed = _line_is_its_input(found)
        if echoed is None:
            return None
        chip, match = echoed
        return _INPUT_KIND[chip], chip, match
    if picked is not None:
        chip, match = picked
        if chip in ("computed", "rule"):
            by = match.computed_by if match is not None else None
            kind = "rule" if chip == "rule" else ("tool" if by == "tool" else "server")
            return kind, chip, match
        return _INPUT_KIND[chip], chip, match
    # nothing stored says what it is: the tool that first held it
    if guard_source in COMPUTING_TOOLS:
        return ("tool" if guard_source == "compare" else "server"), "computed", None
    if guard_source in _LOOKUP_KIND:
        kind = _LOOKUP_KIND[guard_source]
        return kind, _KIND_CHIP[kind], None
    return None  # save_profile and the like only echo data: no claim


def audit(text: str, sources: Sequence[Mapping[str, Any]]) -> list[str]:
    """What is wrong with a reply's recorded sources (empty: nothing). Used by the evals on real
    model replies: every span is in bounds, does not overlap another, and its slice parses back
    to its value; a computed number is "חושב בשרת", only compare is ever "חושב בכלי", and only a
    value of kind "rule" wears the rules' chip."""
    problems: list[str] = []
    end_of_last = 0
    for source in sorted(sources, key=lambda s: s["start"]):
        start, end = source["start"], source["end"]
        shown = text[start:end]
        where = f"{shown!r}@{start}"
        if not 0 <= start < end <= len(text) or start < end_of_last:
            problems.append(f"{where}: out of bounds or overlapping")
            continue
        end_of_last = end
        plain = shown.replace("−", "-").replace(",", "").replace("%", "").replace(" ", "")
        try:
            parses = Decimal(plain) == Decimal(source["value"])
        except InvalidOperation:
            parses = False
        if not parses:
            problems.append(f"{where}: does not parse back to {source['value']}")
        if source["chip"] == "computed" and (
            source["kind"] not in ("tool", "server") or source["label"] != "חושב בשרת"
        ):
            problems.append(f"{where}: a computed number with the wrong kind or label")
        if source["origin"]["label"].startswith("חושב בכלי") and (
            source["chip"] != "computed" or source["origin"]["tool"] != "compare"
        ):
            problems.append(f"{where}: claims a tool computed it")
        if (source["chip"] == "rule") != (source["kind"] == "rule"):
            problems.append(f"{where}: the rules' chip and kind disagree")
    return problems


def build_number_sources(
    text: str,
    spans: Sequence[Mapping[str, Any]],
    events: Sequence[Event],
    run_after: int,
    context: Context | None = None,
) -> list[dict[str, Any]]:
    """The public `number_sources` of a sent reply. `text` is the exact text that was checked
    and sent, `spans` the guard's record of it, `events` the session's events, `run_after` the
    event seq this run started after (its comparisons are preferred)."""
    context = context or Context()
    out = []
    for span in spans:
        if _plain(text, span):
            continue
        percent = span["raw"].endswith("%")
        found = _all_matches(events, context, span, percent, run_after)
        classified = _classify(span, found)
        if classified is not None:
            kind, chip, match = classified
            out.append(_record(span, kind, chip, match, context))
    return out

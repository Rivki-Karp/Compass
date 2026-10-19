"""What a scenario run recorded (Trace) and the checks evaluated against it.

Checks read tool calls, tool results, comparison events and the final session state, never
the model's prose for numbers.

Check types (one key per check):
    tool_called      {name, input?, result?, ok?, turn?}   some call matches
    tool_not_called  {name, input?, result?, ok?, turn?}   no call matches
    comparison       {alternative?, turn?, origin?, today_net?, alternative_net?, diff?,
                      has_diff?, participation_source?, maintenance_source?, pending_rep?,
                      hypothetical?, partial?, input_sources?}
                     the last comparison shown (a comparison_ready event: compare's result
                     or a server recompute of it, whose compare input alternative matches,
                     at or before `turn`) has these values. `origin: server` looks only at
                     the server's recomputes (a ticket opened, or the rep's answer settled it);
                     `origin: tool` only at compare's own results. `input_sources`: the view's
                     input chips by id, e.g. {occupation: representative}
    ticket           {bound_fields?, free_types?, occupation_options_from_table?,
                      allow_pending_participation?}
                     some ticket opened in the session has exactly these bound fields and
                     free questions' types (in any order), and (true) occupation options that
                     are all titles of the occupations table (or "other").
                     `allow_pending_participation: true`: the ticket may also ask
                     alternative_participation:<car> for a car whose comparison in the
                     session was pending on exactly that field; any other extra fails
    slot             {field, value?, state?, source?, absent?}   the final session profile
    reply            {turn?, matches?, not_matches?}   regexes on the shown replies of `turn`
                     (default: all replies); every `matches` regex must match some reply,
                     no `not_matches` regex may match any
    options_reply    {top?, turn?}   the reply after the last list_options (at or before `turn`)
                     leads with its `top` (default 3) best eligible options: the first `top`
                     options it names are exactly those. Naming more options after them, or one
                     that is not eligible (to say why), is fine

`input` / `result` are subsets: dicts match key by key, an expected list must be contained in
the actual list, numbers match by value ("18500" == 18500). Turns are 0-based script indices.

Global checks run on every scenario: no agent errors, every shown reply passes the number
guard (re-checked), no forbidden phrase (a recommendation, a national ID request), and no
"תלוש" in a reply unless an employee message at or before that turn had it.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# A word a reply may use only after the employee used it first (the agent never brings up a
# payslip: there is no upload; if the employee does, the data can simply be typed in).
ONLY_AFTER_EMPLOYEE_HE = {"payslip": "תלוש"}

FORBIDDEN_HE = {
    "recommendation": r"כדאי לך",
    "national_id": r"תעודת זהות|מספר זהות|ת\.ז",
}

_ARGS: dict[str, set[str]] = {
    "tool_called": {"name", "input", "result", "ok", "turn"},
    "tool_not_called": {"name", "input", "result", "ok", "turn"},
    "comparison": {
        "alternative",
        "turn",
        "origin",
        "today_net",
        "alternative_net",
        "diff",
        "has_diff",
        "participation_source",
        "maintenance_source",
        "pending_rep",
        "hypothetical",
        "partial",
        "input_sources",
    },
    "ticket": {
        "bound_fields",
        "free_types",
        "occupation_options_from_table",
        "allow_pending_participation",
    },
    "slot": {"field", "value", "state", "source", "absent"},
    "reply": {"turn", "matches", "not_matches"},
    "options_reply": {"top", "turn"},
}
_REQUIRED: dict[str, set[str]] = {"tool_called": {"name"}, "tool_not_called": {"name"}}


@dataclass
class Call:
    turn: int
    name: str
    input: dict[str, Any]
    ok: bool
    result: dict[str, Any]


@dataclass
class Comparison:
    """A comparison_ready event, with the compare input it came from."""

    turn: int
    input: dict[str, Any]  # the compare call's input (for a server recompute: the original's)
    result: dict[str, Any]  # the event payload: compare's result (+ origin for a recompute)


@dataclass
class Reply:
    turn: int
    text: str
    kind: str  # reply | template | error


@dataclass
class Trace:
    calls: list[Call] = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)
    replies: list[Reply] = field(default_factory=list)
    guard_actions: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    slots: dict[str, dict[str, Any]] = field(default_factory=dict)  # by tool field name
    # (turn, violations) for every shown reply, re-checked by the guard after the run
    guard_rechecks: list[tuple[int, list[str]]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # e.g. a rep turn with no open ticket
    employee_messages: list[tuple[int, str]] = field(default_factory=list)  # (turn, text)
    # every ticket opened: {"bound_fields", "free_types", "occupation_options_from_table"}
    tickets: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CheckResult:
    label: str
    passed: bool
    detail: str = ""


def parse_check(check: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(check, dict) or len(check) != 1:
        raise ValueError(f"a check has exactly one key: {check!r}")
    ((kind, args),) = check.items()
    if kind not in _ARGS:
        raise ValueError(f"unknown check {kind!r}")
    args = args or {}
    if not isinstance(args, dict):
        raise ValueError(f"{kind}: arguments must be a mapping")
    extra = set(args) - _ARGS[kind]
    missing = _REQUIRED.get(kind, set()) - set(args)
    if kind == "slot" and "field" not in args:
        missing = {"field"}
    if extra or missing:
        raise ValueError(f"{kind}: unknown {sorted(extra)} / missing {sorted(missing)}")
    for key in ("matches", "not_matches"):
        for pattern in args.get(key, []):
            re.compile(pattern)
    return kind, args


# --- matching -------------------------------------------------------------------------------


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and matches(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(matches(e, a) for a in actual) for e in expected
        )
    if expected is None or isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual  # True never matches 1
    a, b = _number(expected), _number(actual)
    if a is not None and b is not None:
        return a == b
    return expected == actual


def _call_matches(call: Call, args: dict[str, Any]) -> bool:
    return (
        call.name == args["name"]
        and ("turn" not in args or call.turn == args["turn"])
        and ("ok" not in args or call.ok is args["ok"])
        and matches(args.get("input", {}), call.input)
        and matches(args.get("result", {}), call.result)
    )


def _describe(call: Call) -> str:
    return f"t{call.turn} {call.name} {call.input}"


# --- the checks -----------------------------------------------------------------------------


def _tool_called(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    found = [c for c in trace.calls if _call_matches(c, args)]
    if found:
        return True, _describe(found[0])
    same = [_describe(c) for c in trace.calls if c.name == args["name"]]
    return False, f"no match; {args['name']} calls: {same or 'none'}"


def _tool_not_called(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    found = [c for c in trace.calls if _call_matches(c, args)]
    return (not found), (_describe(found[0]) if found else "")


def _comparison_values(result: dict[str, Any]) -> dict[str, Any]:
    comparison = result["comparison"]
    return {
        "today_net": comparison["today"]["display"]["net"],
        "alternative_net": comparison["alternative"]["display"]["net"],
        "diff": comparison["display_diff"],
        "has_diff": comparison["display_diff"] is not None,
        "participation_source": result["participation_source"],
        "maintenance_source": comparison["alternative"]["metadata"]["maintenance_source"],
        "pending_rep": result["pending_rep"],
        "hypothetical": result["hypothetical"],
        "partial": comparison["partial"],
        "input_sources": {i["id"]: i["source"] for i in result.get("view", {}).get("inputs", [])},
    }


def _comparison(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    candidates = [
        c
        for c in trace.comparisons
        if ("turn" not in args or c.turn <= args["turn"])
        and ("origin" not in args or c.result.get("origin", "tool") == args["origin"])
        and matches(args.get("alternative", {}), c.input.get("alternative"))
    ]
    if not candidates:
        return False, "no comparison matches"
    got = _comparison_values(candidates[-1].result)
    expected = {k: v for k, v in args.items() if k not in ("alternative", "turn", "origin")}
    wrong = {k: got[k] for k, v in expected.items() if not matches(v, got[k])}
    detail = f"t{candidates[-1].turn} " + ", ".join(f"{k}={got[k]}" for k in expected)
    return (not wrong), (detail if not wrong else f"{detail}; expected {expected}")


def _slot(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    slot = trace.slots.get(args["field"])
    if args.get("absent"):
        absent = slot is None or slot["state"] != "filled"
        return absent, f"{args['field']}: {slot}"
    if slot is None:
        return False, f"{args['field']} not in the session"
    ok = all(matches(args[k], slot[k]) for k in ("value", "state", "source") if k in args)
    return ok, f"{args['field']}: {slot}"


PARTICIPATION_PREFIX = "alternative_participation:"


def _pending_on(trace: Trace) -> set[str]:
    """The fields some comparison in the session was pending on (its view's pending_fields)."""
    return {
        f
        for c in trace.comparisons
        if (c.result.get("view") or {}).get("pending")
        for f in (c.result.get("view") or {}).get("pending_fields", [])
    }


def _ticket(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    pending = _pending_on(trace)

    def extra_ok(field: str) -> bool:
        # a car's participation the shown comparison of that car was pending on
        return field.startswith(PARTICIPATION_PREFIX) and field in pending

    def fits(ticket: dict[str, Any]) -> bool:
        if "bound_fields" in args:
            expected, got = sorted(args["bound_fields"]), sorted(ticket["bound_fields"])
            if args.get("allow_pending_participation"):
                extra = [f for f in got if f not in expected]
                if not set(expected) <= set(got) or not all(map(extra_ok, extra)):
                    return False
            elif got != expected:
                return False
        if "free_types" in args and sorted(ticket["free_types"]) != sorted(args["free_types"]):
            return False
        table = "occupation_options_from_table"
        return table not in args or ticket[table] == args[table]

    found = [t for t in trace.tickets if fits(t)]
    return bool(found), f"tickets: {trace.tickets or 'none'}"


def _reply(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    texts = [r.text for r in trace.replies if "turn" not in args or r.turn == args["turn"]]
    if not texts:
        return False, "no reply in that turn"
    missing = [p for p in args.get("matches", []) if not any(re.search(p, t) for t in texts)]
    present = [p for p in args.get("not_matches", []) if any(re.search(p, t) for t in texts)]
    problems = [f"missing /{p}/" for p in missing] + [f"present /{p}/" for p in present]
    return (not problems), "; ".join(problems)


# How a reply names the waiver option (a car is named by its commercial name).
WAIVER_HE = "ויתור"


def _option_name(option: dict[str, Any]) -> str:
    return WAIVER_HE if option["scenario"]["kind"] == "waiver" else option["commercial_name"]


def _named_at(text: str, name: str) -> int | None:
    """Where `name` is first named in `text`: a whole Latin token, so "COROLLA" is not found in
    "COROLLA CROSS" and "MAZDA 3" is not found in "MAZDA 30"."""
    if name == WAIVER_HE:
        found = re.search(WAIVER_HE, text)
    else:
        found = re.search(
            rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9]|[ .\-][A-Za-z])", text, re.I
        )
    return found.start() if found else None


def _options_reply(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    turn = args.get("turn")
    listed = [
        c
        for c in trace.calls
        if c.name == "list_options" and c.ok and (turn is None or c.turn <= turn)
    ]
    if not listed:
        return False, "no list_options result"
    call = listed[-1]
    texts = [r.text for r in trace.replies if r.turn == call.turn and r.kind != "error"]
    if not texts:
        return False, f"no reply in t{call.turn}"
    options = call.result.get("options", [])
    top = args.get("top", 3)
    best = [_option_name(o) for o in options if o["eligibility"]["status"] == "eligible"][:top]
    named = sorted(
        (at, name)
        for name in dict.fromkeys(_option_name(o) for o in options)
        if (at := _named_at(texts[-1], name)) is not None
    )
    first = [name for _, name in named[:top]]
    detail = f"leads with {first}; top {top} eligible {best}"
    return set(first) == set(best), detail


_CHECKS = {
    "tool_called": _tool_called,
    "tool_not_called": _tool_not_called,
    "comparison": _comparison,
    "slot": _slot,
    "reply": _reply,
    "options_reply": _options_reply,
    "ticket": _ticket,
}


def _label(kind: str, args: dict[str, Any]) -> str:
    short = {k: v for k, v in args.items() if k not in ("matches", "not_matches")}
    patterns = len(args.get("matches", [])) + len(args.get("not_matches", []))
    return f"{kind} {short}" + (f" ({patterns} patterns)" if patterns else "")


def evaluate(trace: Trace, checks: list[dict[str, Any]]) -> list[CheckResult]:
    results = []
    for check in checks:
        kind, args = parse_check(check)
        passed, detail = _CHECKS[kind](trace, args)
        results.append(CheckResult(_label(kind, args), passed, detail))
    return results + global_checks(trace)


def global_checks(trace: Trace) -> list[CheckResult]:
    shown = [r for r in trace.replies if r.kind != "error"]
    violations = [f"t{turn}: {v}" for turn, v in trace.guard_rechecks if v]
    forbidden = [
        f"t{r.turn} {name}"
        for r in shown
        for name, pattern in FORBIDDEN_HE.items()
        if re.search(pattern, r.text)
    ]
    unprompted = [
        f"t{r.turn} {name}"
        for r in shown
        for name, word in ONLY_AFTER_EMPLOYEE_HE.items()
        if word in r.text
        and not any(word in text for turn, text in trace.employee_messages if turn <= r.turn)
    ]
    return [
        CheckResult(
            "[global] script ran as written", not trace.problems, "; ".join(trace.problems)
        ),
        CheckResult(
            "[global] no agent errors",
            not trace.errors,
            "; ".join(f"{e['kind']}: {e['message']}" for e in trace.errors),
        ),
        CheckResult("[global] shown numbers pass the guard", not violations, "; ".join(violations)),
        CheckResult("[global] no forbidden phrases", not forbidden, "; ".join(forbidden)),
        CheckResult(
            "[global] no payslip unless the employee mentioned one",
            not unprompted,
            "; ".join(unprompted),
        ),
    ]

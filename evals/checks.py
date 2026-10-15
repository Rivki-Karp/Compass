"""What a scenario run recorded (Trace) and the checks evaluated against it.

Checks read tool calls, tool results and the final session state, never the model's prose
for numbers: comparison values come from the compare tool result.

Check types (one key per check):
    tool_called      {name, input?, result?, ok?, turn?}   some call matches
    tool_not_called  {name, input?, result?, ok?, turn?}   no call matches
    comparison       {alternative?, turn?, today_net?, alternative_net?, diff?, has_diff?,
                      participation_source?, maintenance_source?, pending_rep?,
                      hypothetical?, partial?}
                     the last successful compare (whose input alternative matches, made at
                     or before `turn`) has these values
    slot             {field, value?, state?, source?, absent?}   the final session profile
    reply            {turn?, matches?, not_matches?}   regexes on the shown replies of `turn`
                     (default: all replies); every `matches` regex must match some reply,
                     no `not_matches` regex may match any

`input` / `result` are subsets: dicts match key by key, an expected list must be contained in
the actual list, numbers match by value ("18500" == 18500). Turns are 0-based script indices.

Global checks run on every scenario: no agent errors, every shown reply passes the number
guard (re-checked), and no forbidden phrase (a recommendation, a national ID request).
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

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
        "today_net",
        "alternative_net",
        "diff",
        "has_diff",
        "participation_source",
        "maintenance_source",
        "pending_rep",
        "hypothetical",
        "partial",
    },
    "slot": {"field", "value", "state", "source", "absent"},
    "reply": {"turn", "matches", "not_matches"},
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
class Reply:
    turn: int
    text: str
    kind: str  # reply | template | error


@dataclass
class Trace:
    calls: list[Call] = field(default_factory=list)
    replies: list[Reply] = field(default_factory=list)
    guard_actions: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    slots: dict[str, dict[str, Any]] = field(default_factory=dict)  # by tool field name
    # (turn, violations) for every shown reply, re-checked by the guard after the run
    guard_rechecks: list[tuple[int, list[str]]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # e.g. a rep turn with no open ticket


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
    }


def _comparison(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    candidates = [
        c
        for c in trace.calls
        if c.name == "compare"
        and c.ok
        and ("turn" not in args or c.turn <= args["turn"])
        and matches(args.get("alternative", {}), c.input.get("alternative"))
    ]
    if not candidates:
        return False, "no successful compare matches"
    got = _comparison_values(candidates[-1].result)
    expected = {k: v for k, v in args.items() if k not in ("alternative", "turn")}
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


def _reply(trace: Trace, args: dict[str, Any]) -> tuple[bool, str]:
    texts = [r.text for r in trace.replies if "turn" not in args or r.turn == args["turn"]]
    if not texts:
        return False, "no reply in that turn"
    missing = [p for p in args.get("matches", []) if not any(re.search(p, t) for t in texts)]
    present = [p for p in args.get("not_matches", []) if any(re.search(p, t) for t in texts)]
    problems = [f"missing /{p}/" for p in missing] + [f"present /{p}/" for p in present]
    return (not problems), "; ".join(problems)


_CHECKS = {
    "tool_called": _tool_called,
    "tool_not_called": _tool_not_called,
    "comparison": _comparison,
    "slot": _slot,
    "reply": _reply,
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
    ]

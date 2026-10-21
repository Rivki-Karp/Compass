"""The number guard: every number in a reply must come from a tool result, the employee's own
words (or a representative's answer), or be harmless.

Allowed, per session:
    - every number in every tool result (exact and display values, numbers inside strings such
      as "CAR-10" or "ATTO 3 2025"), plus the percentage form of fractions (0.065 -> 6.5)
    - every number the employee wrote, and the values in representative answers (with the
      notes and the answers to free questions)
    - harmless: 1-9 (list markers, counts), years 2020-2030, and dates that appear in the above
      (or a plain day/month such as 1/1)

A number written with an explicit sign (+2,914, −1,938) must match a value with that sign; an
unsigned number may match either sign. A hyphen glued to a Hebrew prefix letter ("ב-2,914") is
not a minus sign.
"""

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from compass.agent.runner import Guard, GuardVerdict
from compass.agent.transcript import REP_QUESTION_KEYS, is_server_event
from compass.state import Store

# Dates: ISO, day.month.year, day/month/year, or a plain day/month with a slash ("1/1").
_DATE = r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{1,2}/\d{1,2})"
_NUMBER = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
# A sign counts only at the start or after whitespace / an opening bracket, never after a letter
# ("ב-2,914", "CAR-10").
_TOKEN = re.compile(
    rf"(?P<date>(?<![\d.,/])(?<!\d-){_DATE}(?![\d/]))"
    rf"|(?P<sign>(?:^|(?<=[\s(\[]))[+\-−–])?(?P<num>{_NUMBER})(?P<pct>\s?%)?"
)
HARMLESS_INTEGERS = frozenset(range(1, 10))
HARMLESS_YEARS = range(2020, 2031)


def _normalize_date(text: str) -> str:
    """ISO (YYYY-MM-DD), or "--MM-DD" for a day/month without a year."""
    if "-" in text:
        year, month, day = (int(p) for p in text.split("-"))
        return f"{year:04d}-{month:02d}-{day:02d}"
    parts = [int(p) for p in re.split(r"[./]", text)]
    if len(parts) == 3:
        day, month, year = parts
        year += 2000 if year < 100 else 0
        return f"{year:04d}-{month:02d}-{day:02d}"
    day, month = parts
    return f"--{month:02d}-{day:02d}"


def extract(text: str) -> list[dict[str, Any]]:
    """Every number-like token: {"raw", "signed", "start", "end" (offsets in `text`, covering the
    token as written: sign, separators, %), and "value" (signed Decimal) or "date"}."""
    tokens: list[dict[str, Any]] = []
    for match in _TOKEN.finditer(text):
        where = {"start": match.start(), "end": match.end()}
        if match.group("date"):
            raw = match.group("date")
            tokens.append({"raw": raw, "date": _normalize_date(raw), "signed": False, **where})
            continue
        number = match.group("num")
        value = Decimal(number.replace(",", "")).normalize()
        sign = match.group("sign") or ""
        if sign and sign != "+":
            value = -value
        raw = f"{sign}{number}{(match.group('pct') or '').strip()}"
        where["start"] = match.start("sign") if sign else match.start("num")
        tokens.append({"raw": raw, "value": value, "signed": bool(sign), **where})
    return tokens


class Allowed:
    """The numbers (signed) and dates a reply may use, each with the source it was first seen in:
    a tool name, "employee" or "representative" (judges mode shows it per number)."""

    def __init__(self) -> None:
        self.values: dict[Decimal, str] = {}
        self.dates: dict[str, str] = {}
        # Record only (never read by source_of / permits): the row each value in `values` was
        # first seen in, {"message_seq", "at", "tool_use_id"}.
        self.origins: dict[Decimal, dict[str, Any]] = {}

    def add_value(self, value: Decimal, source: str, origin: dict[str, Any] | None = None) -> None:
        value = value.normalize()
        self.values.setdefault(value, source)
        self.origins.setdefault(value, origin or {})
        if 0 < abs(value) < 1:  # a fraction: allow its percentage form too
            percent = (value * 100).normalize()
            self.values.setdefault(percent, source)
            self.origins.setdefault(percent, origin or {})

    def add_text(self, text: str, source: str, origin: dict[str, Any] | None = None) -> None:
        for token in extract(text):
            if "date" in token:
                self.dates.setdefault(token["date"], source)
            else:
                self.add_value(token["value"], source, origin)

    def add_json(self, data: Any, source: str, origin: dict[str, Any] | None = None) -> None:
        if isinstance(data, bool) or data is None:
            return
        if isinstance(data, int | float | Decimal):
            self.add_value(Decimal(str(data)), source, origin)
        elif isinstance(data, str):
            self.add_text(data, source, origin)
        elif isinstance(data, dict):
            for key, value in data.items():
                self.add_text(str(key), source, origin)
                self.add_json(value, source, origin)
        elif isinstance(data, list | tuple):
            for item in data:
                self.add_json(item, source, origin)

    def source_of(self, token: dict[str, Any]) -> str | None:
        """Where a token's value comes from ("harmless" for small counts, years and bare
        day/month dates); None if the reply may not use it."""
        if "date" in token:
            date = token["date"]
            return self.dates.get(date) or ("harmless" if date.startswith("--") else None)
        value: Decimal = token["value"]
        if token["signed"]:
            return self.values.get(value)
        found = self.values.get(value) or self.values.get(-value)
        if found is not None:
            return found
        whole = value == value.to_integral_value()
        if whole and (int(value) in HARMLESS_INTEGERS or int(value) in HARMLESS_YEARS):
            return "harmless"
        return None

    def permits(self, token: dict[str, Any]) -> bool:
        return self.source_of(token) is not None

    def origin_of(self, token: dict[str, Any]) -> dict[str, Any]:
        """The row a number token was first seen in. Reports only: `source_of` decides, and this
        follows the same lookup. {} for a date, a harmless number or an unknown one."""
        if "date" in token:
            return {}
        value: Decimal = token["value"]
        if value in self.values:
            return self.origins.get(value, {})
        if not token["signed"] and -value in self.values:
            return self.origins.get(-value, {})
        return {}


def number_spans(tokens: list[dict[str, Any]], allowed: Allowed) -> list[dict[str, Any]]:
    """What the guard knows about each number token it verified, for the sources behind the
    clickable numbers (record only): offsets in the checked text, the signed value, the guard's
    source ("harmless" included) and the row it came from. Dates are not numbers here."""
    spans = []
    for token in tokens:
        if "date" in token:
            continue
        source = allowed.source_of(token)
        if source is None:
            continue
        spans.append(
            {
                "start": token["start"],
                "end": token["end"],
                "raw": token["raw"],
                "value": token["value"],
                "signed": token["signed"],
                "source": source,
                "origin": allowed.origin_of(token),
            }
        )
    return spans


def check_text(text: str, allowed: Allowed) -> GuardVerdict:
    tokens = extract(text)
    sources = {t["raw"]: allowed.source_of(t) for t in tokens}
    violations = [raw for raw, source in sources.items() if source is None]
    return GuardVerdict(
        passed=not violations,
        numbers=[t["raw"] for t in tokens],
        violations=violations,
        sources={raw: source for raw, source in sources.items() if source is not None},
        spans=number_spans(tokens, allowed),
    )


def allowed_for_session(store: Store, session_id: str) -> Allowed:
    allowed = Allowed()
    for row in store.messages(session_id):
        content = row.content if isinstance(row.content, dict) else {}
        where = {"message_seq": row.seq, "at": row.created_at}  # recorded, never decides
        if row.role == "user":
            allowed.add_text(content.get("text", ""), "employee", where)
        elif row.role == "tool":
            for result in content.get("results", []):
                allowed.add_json(
                    result.get("full"),
                    result.get("name") or "tool",
                    {**where, "tool_use_id": result.get("tool_use_id")},
                )
        elif is_server_event(row, "rep_answer"):
            # the representative's words: values, notes, answers to free questions
            keys = ("answer_text", "values", "effective_from", *REP_QUESTION_KEYS)
            allowed.add_json({k: content.get(k) for k in keys}, "representative", where)
            allowed.add_json(content.get("profile_after"), "server", where)
            allowed.add_json(content.get("today_after"), "server", where)
            # what the model was shown of the server's settled comparisons, and nothing more
            allowed.add_json(content.get("server_comparisons"), "server", where)
        elif is_server_event(row, "payslip_confirmed"):
            # values the employee confirmed from their payslip; an unconfirmed candidate is an
            # event, never a message, so it is never a source
            allowed.add_json(content.get("values"), "payslip", where)
            allowed.add_json(content.get("car_hint"), "payslip", where)
            allowed.add_json(content.get("server_comparisons"), "server", where)
        elif is_server_event(row, "car_picked"):
            # the car the employee picked from the catalog, and what the server recomputed
            allowed.add_json(content.get("today_after"), "server", where)
            allowed.add_json(content.get("server_comparisons"), "server", where)
    return allowed


def make_guard(store: Store) -> Guard:
    def check(text: str, session_id: str) -> GuardVerdict:
        return check_text(text, allowed_for_session(store, session_id))

    return check


def numbers_in(texts: Iterable[str]) -> list[str]:
    return [t["raw"] for text in texts for t in extract(text)]

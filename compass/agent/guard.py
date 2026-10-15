"""The number guard: every number in a reply must come from a tool result, the employee's own
words (or a representative's answer), or be harmless.

Allowed, per session:
    - every number in every tool result (exact and display values, numbers inside strings such
      as "CAR-10" or "ATTO 3 2025"), plus the percentage form of fractions (0.065 -> 6.5)
    - every number the employee wrote, and the values in representative answers
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
from compass.agent.transcript import is_server_event
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
    """Every number-like token: {"raw", "signed", and "value" (signed Decimal) or "date"}."""
    tokens: list[dict[str, Any]] = []
    for match in _TOKEN.finditer(text):
        if match.group("date"):
            raw = match.group("date")
            tokens.append({"raw": raw, "date": _normalize_date(raw), "signed": False})
            continue
        number = match.group("num")
        value = Decimal(number.replace(",", "")).normalize()
        sign = match.group("sign") or ""
        if sign and sign != "+":
            value = -value
        raw = f"{sign}{number}{(match.group('pct') or '').strip()}"
        tokens.append({"raw": raw, "value": value, "signed": bool(sign)})
    return tokens


class Allowed:
    """The numbers (signed) and dates a reply may use."""

    def __init__(self) -> None:
        self.values: set[Decimal] = set()
        self.dates: set[str] = set()

    def add_value(self, value: Decimal) -> None:
        value = value.normalize()
        self.values.add(value)
        if 0 < abs(value) < 1:  # a fraction: allow its percentage form too
            self.values.add((value * 100).normalize())

    def add_text(self, text: str) -> None:
        for token in extract(text):
            if "date" in token:
                self.dates.add(token["date"])
            else:
                self.add_value(token["value"])

    def add_json(self, data: Any) -> None:
        if isinstance(data, bool) or data is None:
            return
        if isinstance(data, int | float | Decimal):
            self.add_value(Decimal(str(data)))
        elif isinstance(data, str):
            self.add_text(data)
        elif isinstance(data, dict):
            for key, value in data.items():
                self.add_text(str(key))
                self.add_json(value)
        elif isinstance(data, list | tuple):
            for item in data:
                self.add_json(item)

    def permits(self, token: dict[str, Any]) -> bool:
        if "date" in token:
            date = token["date"]
            return date.startswith("--") or date in self.dates  # day/month alone is harmless
        value: Decimal = token["value"]
        if token["signed"]:
            return value in self.values
        whole = value == value.to_integral_value()
        if whole and (int(value) in HARMLESS_INTEGERS or int(value) in HARMLESS_YEARS):
            return True
        return value in self.values or -value in self.values


def check_text(text: str, allowed: Allowed) -> GuardVerdict:
    tokens = extract(text)
    violations = [t["raw"] for t in tokens if not allowed.permits(t)]
    return GuardVerdict(
        passed=not violations,
        numbers=[t["raw"] for t in tokens],
        violations=list(dict.fromkeys(violations)),
    )


def allowed_for_session(store: Store, session_id: str) -> Allowed:
    allowed = Allowed()
    for row in store.messages(session_id):
        content = row.content if isinstance(row.content, dict) else {}
        if row.role == "user":
            allowed.add_text(content.get("text", ""))
        elif row.role == "tool":
            for result in content.get("results", []):
                allowed.add_json(result.get("full"))
        elif is_server_event(row, "rep_answer"):
            allowed.add_json(
                {k: content.get(k) for k in ("answer_text", "values", "effective_from")}
            )
    return allowed


def make_guard(store: Store) -> Guard:
    def check(text: str, session_id: str) -> GuardVerdict:
        return check_text(text, allowed_for_session(store, session_id))

    return check


def numbers_in(texts: Iterable[str]) -> list[str]:
    return [t["raw"] for text in texts for t in extract(text)]

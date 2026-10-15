"""Interactive terminal calculator: ask for a profile and two scenarios, print the demo table.

    uv run python tasks.py calc

Pure CLI over the engine (no calculation here). An empty answer means "unknown"; the engine
then reports which inputs are missing instead of guessing.
"""

import sys
from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from compass.demo import render
from compass.engine.compare import compare
from compass.engine.context import EngineContext, build_context
from compass.engine.eligibility import check_eligibility
from compass.engine.models import (
    CompanyCar,
    CurrentMaintenance,
    EmployeeProfile,
    FamilyCar,
    MissingInputs,
    Scenario,
    Waiver,
)

Ask = Callable[[str], str]
WAIVER_WORDS = {"waiver", "ויתור"}


class _Retry(ValueError):
    pass


def _ask(ask: Ask, prompt: str, parse: Callable[[str], object]) -> object:
    """Ask until the answer parses; an empty answer returns None (unknown)."""
    while True:
        answer = ask(f"{prompt}: ").strip()
        if not answer:
            return None
        try:
            return parse(answer)
        except _Retry as error:
            print(f"  {error}")


def _decimal(text: str) -> Decimal:
    try:
        value = Decimal(text.replace(",", ""))
    except InvalidOperation:
        raise _Retry("נא להזין מספר") from None
    if not value.is_finite() or value < 0:
        raise _Retry("נא להזין מספר לא שלילי")
    return value


def _percent(text: str) -> Decimal:
    return _decimal(text.removesuffix("%")).scaleb(-2)  # 6.5 -> 0.065, exact


def _int(text: str) -> int:
    if not text.isdigit():
        raise _Retry("נא להזין מספר שלם")
    return int(text)


def _choice(options: list[str]) -> Callable[[str], str]:
    def parse(text: str) -> str:
        if text in options:
            return text
        if text.isdigit() and 1 <= int(text) <= len(options):
            return options[int(text) - 1]
        raise _Retry("בחירה לא מוכרת; הזינו מספר מהרשימה או את הערך המדויק")

    return parse


def _car(ctx: EngineContext, ask: Ask, text: str) -> Scenario:
    car_id = text.upper()
    if car_id not in ctx.catalog:
        raise _Retry(f"מזהה רכב לא מוכר; לדוגמה {next(iter(ctx.catalog))}")
    participation = _ask(ask, "  השתתפות חודשית ברכב (ריק = ברירת המחדל בקטלוג)", _decimal)
    assert participation is None or isinstance(participation, Decimal)
    if ctx.is_family_car(car_id):
        return FamilyCar(car_id=car_id, participation=participation)
    return CompanyCar(car_id=car_id, participation=participation)


def _scenario(ctx: EngineContext, ask: Ask, prompt: str, today: bool) -> Scenario:
    while True:
        answer = ask(f"{prompt}: ").strip()
        try:
            if answer.lower() in WAIVER_WORDS:
                return Waiver()
            if today and answer.replace(",", "").replace(".", "", 1).isdigit():
                return CurrentMaintenance(amount=_decimal(answer))
            return _car(ctx, ask, answer)
        except _Retry as error:
            print(f"  {error}")


def run(ask: Ask = input, ctx: EngineContext | None = None) -> int:
    ctx = build_context() if ctx is None else ctx
    groups = list(ctx.rules.group_order)
    titles = list(ctx.occupations)
    print("מחשבון נטו - Compass (ריק = לא ידוע)")
    print("עיסוקים: " + " · ".join(f"{i}. {t}" for i, t in enumerate(titles, 1)))
    print("רכבים: " + " · ".join(f"{c.id} {c.commercial_name}" for c in ctx.catalog.values()))

    profile = EmployeeProfile(
        group=_ask(ask, f"קבוצה ({'/'.join(groups)})", _choice(groups)),  # type: ignore[arg-type]
        occupation=_ask(ask, "עיסוק (מספר או שם מדויק)", _choice(titles)),  # type: ignore[arg-type]
        base_salary=_ask(ask, "שכר בסיס", _decimal),  # type: ignore[arg-type]
        commissions=_ask(ask, "עמלות", _decimal),  # type: ignore[arg-type]
        bonus=_ask(ask, "בונוס", _decimal),  # type: ignore[arg-type]
        pension_pct=_ask(ask, "הפרשת עובד לפנסיה (%)", _percent),  # type: ignore[arg-type]
        study_fund_pct=_ask(ask, "הפרשת עובד לקרן השתלמות (%)", _percent),  # type: ignore[arg-type]
        credit_points=_ask(ask, "נקודות זיכוי", _decimal),  # type: ignore[arg-type]
        children_under_23=_ask(ask, "ילדים מתחת לגיל 23", _int),  # type: ignore[arg-type]
    )
    today = _scenario(ctx, ask, "היום: מזהה רכב / waiver / סכום אחזקה", today=True)
    alternative = _scenario(ctx, ask, "חלופה: מזהה רכב / waiver", today=False)

    try:
        result = compare(profile, today, alternative, ctx)
    except MissingInputs as missing:
        print("חסרים נתונים לחישוב: " + ", ".join(missing.fields))
        return 1
    verdict = check_eligibility(profile, alternative, ctx)
    title = f"חישוב ידני · קבוצה {profile.group or '?'}"
    print()
    print(render(result, title, f"{verdict.status} ({verdict.reason})", ctx.catalog, ctx.rules))
    return 0


def main() -> int:
    for stream in (sys.stdin, sys.stdout):  # piped Hebrew input on Windows, too
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        return run()
    except (EOFError, KeyboardInterrupt):
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())

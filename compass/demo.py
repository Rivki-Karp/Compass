"""Print a Hebrew breakdown of a golden reference employee: today vs the alternative.

    uv run python tasks.py demo E-001

Layout for terminals with or without bidi support: numbers sit in fixed-width columns on the
left, and the Hebrew label is the last column, so each row reads correctly either way.
"""

import sys
from collections.abc import Mapping
from decimal import Decimal

from compass.data.catalog import CatalogCar
from compass.engine.compare import compare
from compass.engine.context import build_context
from compass.engine.decimal_math import to_display
from compass.engine.eligibility import check_eligibility
from compass.engine.models import (
    CompanyCar,
    Comparison,
    CurrentMaintenance,
    DeltaLineName,
    FamilyCar,
    Scenario,
    Waiver,
)
from compass.reference import load_reference_cases
from compass.rules import Rules

BREAKDOWN_ROWS: list[tuple[str, str]] = [
    ("cash_income", "שכר ברוטו (בסיס + עמלות + בונוס)"),
    ("value_of_use", "שווי שימוש (לא מזומן)"),
    ("maintenance", "אחזקת רכב"),
    ("electric_gross", "החזר חשמל מגולם (ברוטו)"),
    ("taxable_income", "הכנסה חייבת"),
    ("income_tax_before_credits", "מס לפני זיכויים"),
    ("credit_points_value", "זיכוי נקודות זיכוי"),
    ("pension_credit", "זיכוי פנסיה"),
    ("income_tax", "מס הכנסה"),
    ("national_insurance", "ביטוח לאומי"),
    ("health", "מס בריאות"),
    ("employee_pension", "פנסיה (עובד)"),
    ("employee_study", "קרן השתלמות (עובד)"),
    ("participation", "השתתפות העובד ברכב"),
    ("family_employee_share", "חלק העובד בפער המסלול המשפחתי"),
    ("net", "נטו"),
]

DELTA_LABELS: dict[DeltaLineName, str] = {
    "cash_income": "שכר ברוטו",
    "maintenance": "אחזקת רכב",
    "electric_gross": "החזר חשמל מגולם",
    "income_tax": "מס הכנסה",
    "national_insurance": "ביטוח לאומי",
    "health": "מס בריאות",
    "employee_pension": "פנסיה (עובד)",
    "employee_study": "קרן השתלמות (עובד)",
    "participation": "השתתפות ברכב",
    "family_employee_share": "חלק העובד במסלול המשפחתי",
}

WIDTH = 10


def _money(value: Decimal | int | None, rules: Rules, signed: bool = False) -> str:
    if value is None:
        return "?".rjust(WIDTH)
    shown = value if isinstance(value, int) else to_display(value, rules)
    return f"{shown:+,}".rjust(WIDTH) if signed else f"{shown:,}".rjust(WIDTH)


def _describe(scenario: Scenario, catalog: Mapping[str, CatalogCar]) -> str:
    if isinstance(scenario, CompanyCar | FamilyCar):
        car = catalog[scenario.car_id]
        track = " (מסלול משפחתי)" if isinstance(scenario, FamilyCar) else ""
        return f"{car.commercial_name} {car.registration_year}, קבוצה {car.group}{track}"
    if isinstance(scenario, Waiver):
        return "ויתור על הרכב (אחזקה לפי העיסוק)"
    assert isinstance(scenario, CurrentMaintenance)
    return "ללא רכב, אחזקה קיימת"


def render(
    result: Comparison,
    title: str,
    eligibility: str,
    catalog: Mapping[str, CatalogCar],
    rules: Rules,
) -> str:
    today, alt = result.today, result.alternative
    rule = "-" * (WIDTH * 3 + 4 + 34)
    out = [
        title,
        f"היום:   {_describe(today.scenario, catalog)}",
        f"חלופה:  {_describe(alt.scenario, catalog)}",
        f"זכאות:  {eligibility}",
        "",
        f"{'היום'.rjust(WIDTH)}  {'חלופה'.rjust(WIDTH)}  {'הפרש'.rjust(WIDTH)}  שורה",
        rule,
    ]
    for field, label in BREAKDOWN_ROWS:
        a, b = getattr(today, field), getattr(alt, field)
        delta = None if a is None or b is None else to_display(b, rules) - to_display(a, rules)
        out.append(
            f"{_money(a, rules)}  {_money(b, rules)}  {_money(delta, rules, signed=True)}  {label}"
        )
    out += [
        rule,
        f"{_money(result.display_diff, rules, signed=True)}  הפרש בנטו (חלופה פחות היום)",
        "",
        "מה הזיז את הנטו (סכום השורות = ההפרש):",
    ]
    for line in result.display_delta_lines:
        if line.amount:
            out.append(f"{_money(line.amount, rules, signed=True)}  {DELTA_LABELS[line.line]}")
    out.append(f"{_money(sum(x.amount for x in result.display_delta_lines), rules, True)}  סה״כ")
    meta = alt.metadata
    out += [
        "",
        f"שנת לוחות מס: {meta.tax_tables_year} · שנת שווי שימוש: {meta.value_of_use_year} · "
        f"גרסת כללים: {meta.rules_version}",
        f"מקור ההשתתפות בחלופה: {meta.participation_source or '-'}"
        f" · שיטת החזר חשמל: {meta.electric_method or '-'}",
        "עובדות להסבר: " + "; ".join(str(dict(f)) for f in result.explanation_facts),
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ctx = build_context()
    cases = load_reference_cases(ctx)
    if len(argv) != 1 or argv[0] not in cases:
        print(f"usage: tasks.py demo <{'|'.join(cases)}>", file=sys.stderr)
        return 2
    case = cases[argv[0]]
    result = compare(case.profile, case.today, case.alternative, ctx)
    verdict = check_eligibility(case.profile, case.alternative, ctx)
    title = f"{case.employee_id} · {case.name} · קבוצה {case.profile.group}"
    print(render(result, title, f"{verdict.status} ({verdict.reason})", ctx.catalog, ctx.rules))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

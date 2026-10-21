"""Hebrew labels: the one place the terminal demo, the terminal chat and the UI `view` read them.

Labels for formula lines, profile fields, rules and warnings. The UI never keeps its own copy:
whatever it shows next to a number comes from here, through the API.
"""

from collections.abc import Callable, Mapping
from typing import Any

from compass.data.catalog import FAMILY_GROUP
from compass.engine.models import DeltaLineName, WarningCode

# NetBreakdown fields in the order of the demo table.
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

# The lines of the difference (alternative vs today), as the waterfall shows them.
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

# Profile fields (tool names) and the scenario inputs the view lists.
FIELD_LABELS: dict[str, str] = {
    "display_name": "שם",
    "occupation": "עיסוק",
    "group": "קבוצת רכב",
    "base_salary": "שכר בסיס",
    "commissions": "עמלות",
    "bonus": "בונוס",
    "pension_percent": "הפרשת עובד לפנסיה",
    "study_fund_percent": "הפרשת עובד לקרן השתלמות",
    "credit_points": "נקודות זיכוי",
    "children_under_23": "ילדים מתחת לגיל 23",
    "current_situation": "המצב היום",
    "today_car": "הרכב היום",
    "today_participation": "השתתפות היום",
    "today_maintenance": "אחזקה היום",
    "alternative_car": "הרכב בחלופה",
    "alternative_participation": "השתתפות בחלופה",
    "alternative_maintenance": "אחזקה בוויתור",
    "current_participation": "השתתפות היום",  # ticket field names
    "group_exception": "אישור חריג לקבוצה",
    "current_car": "הרכב של היום",
}


def field_label(field: str) -> str:
    """A tool field, slot-style participation field or view input id -> its Hebrew label."""
    if field.startswith("alternative_participation:"):  # + catalog car id
        return FIELD_LABELS["alternative_participation"]
    return FIELD_LABELS[field]


def ticket_field_title(field: str) -> str:
    """What a ticket asks about, for the representative's inbox ("השתתפות עצמית · ATTO 3")."""
    if field.startswith("alternative_participation:"):
        return "השתתפות עצמית"
    if field == "current_participation":
        return "השתתפות עצמית ברכב של היום"
    if field == "group_exception":
        return "אישור חריג לקבוצה"
    return field_label(field)


# The representative's choices for a group exception (the radio buttons).
def group_approved_label(group: str) -> str:
    return f"מאושר לקבוצה {group_letter(group)}"


GROUP_NOT_APPROVED_LABEL = "לא מאושר"

# Ticket questions (compass/tools/questions.py): the rep's choices and the section headings.
OTHER_OCCUPATION_LABEL = "עיסוק אחר (לפרט בהערה)"
NOT_IN_CATALOG_LABEL = "הרכב לא בקטלוג (לפרט בהערה)"
CURRENT_CAR_QUESTION_TITLE = "הרכב של היום"
NEEDS_CHECKING_LABEL = "לא ידוע לי / צריך לבדוק"
OCCUPATION_QUESTION_TITLE = "סיווג עיסוק"
FREE_ANSWER_LABELS = {"yes_no": "התשובה", "choice": "התשובה", "text": "התשובה"}


def clamp(text: str, limit: int) -> str:
    """One line of at most `limit` characters, "…" when cut (titles built from a prompt)."""
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


# Rules and official data a line can depend on (the provenance strip's "rule" chips).
RULE_LABELS: dict[str, str] = {
    "income_tax_brackets": "מדרגות מס הכנסה",
    "credit_point_value": "שווי נקודת זיכוי",
    "pension_credit": "זיכוי על הפרשה לפנסיה",
    "national_insurance_brackets": "מדרגות ביטוח לאומי",
    "health_brackets": "מדרגות מס בריאות",
    "value_of_use": "שווי שימוש (טבלת רשות המסים)",
    "electric_reimbursement": "החזר חשמל לרכב חשמלי",
    "waiver_maintenance": "אחזקה בוויתור לפי העיסוק",
    "family_track": "מסלול משפחתי",
}


# In place of the difference while today's car is unknown (each alternative's own net is
# known; the difference needs today's).
DIFF_WAITS_FOR_TODAY = "חסר הרכב של היום"


# Who computed a comparison (the provenance strip's "computed by" line). "tool": the model called
# `compare`; "server": the server ran the same code with no model call (the provisional comparison
# when a ticket opens, the pending recompute, the settle on the rep's answer).
COMPUTED_BY_LABELS: dict[str, str] = {
    "tool": "חושב בכלי",  # followed by the tool's name, `compare`
    "server": "חושב מחדש בשרת · בלי מודל",
}


DRIVE_LABELS: dict[str, str] = {
    "electric": "חשמלי",
    "plugin": "פלאג-אין",
    "hybrid": "היברידי",
    "petrol": "בנזין",
}


def car_details(drive: str, group: str) -> str:
    """A catalog car's drive and group, under its name on the alternative tile: "חשמלי · קבוצה
    ג׳"; a family-track car: "בנזין · מסלול משפחתי"."""
    where = RULE_LABELS["family_track"] if group == FAMILY_GROUP else group_label(group)
    return f"{DRIVE_LABELS[drive]} · {where}"


def group_letter(group: str) -> str:
    """A group letter as the UI shows it everywhere: with a Hebrew geresh (U+05F3), "ב׳"."""
    return f"{group}׳"


def group_label(group: str) -> str:
    """The group with its word, as on the hero pill and in every warning: "קבוצה ב׳"."""
    return f"קבוצה {group_letter(group)}"


def alternative_title(scenario: Mapping[str, Any], car_name: str | None) -> str:
    """The alternative's name for "{title} לעומת היום"."""
    kind = scenario.get("kind")
    if kind == "waiver":
        return "ויתור על הרכב"
    if kind == "current_maintenance":
        return "ללא רכב, אחזקה קיימת"
    if kind == "external_car":
        return str(scenario.get("label") or scenario.get("vehicle_key"))
    title = car_name or str(scenario.get("car_id"))
    return f"{title} (מסלול משפחתי)" if kind == "family_car" else title


Facts = Mapping[str, Any]
CarName = Callable[[str], str]


def _group_mismatch(facts: Facts, car_name: CarName) -> str:
    return (
        f"הקבוצה שנמסרה ({group_label(facts['employee_group'])}) שונה מהקבוצה של העיסוק "
        f"{facts['occupation']} ({group_label(facts['occupation_group'])}). כדאי לוודא מול נציג."
    )


def _car_above_group(facts: Facts, car_name: CarName) -> str:
    return (
        f"הרכב של היום ({car_name(facts['car_id'])}) ב{group_label(facts['car_group'])}, "
        f"מעל {group_label(facts['employee_group'])}. כדאי לבדוק את זה מול נציג."
    )


def _car_not_in_catalog(facts: Facts, car_name: CarName) -> str:
    label = facts.get("label") or facts.get("vehicle_key")
    return f"הרכב של היום ({label}) אינו בקטלוג החברה; החישוב משתמש בשווי השימוש הרשמי שלו."


WARNING_MESSAGES: dict[WarningCode, Callable[[Facts, CarName], str]] = {
    "group_mismatch_with_occupation": _group_mismatch,
    "current_car_above_group": _car_above_group,
    "current_car_not_in_catalog": _car_not_in_catalog,
}


def warning_message(code: WarningCode, facts: Facts, car_name: CarName = str) -> str:
    return WARNING_MESSAGES[code](facts, car_name)


# Why a representative's answer was refused (compass/tools/tickets.py, compass/tools/profile.py):
# Hebrew for the rep screen, keyed by error code. The English detail stays for the model and logs.
Params = Mapping[str, Any]


def _range(params: Params) -> str:
    return f"הערך צריך להיות בין {params['min']:,} ל-{params['max']:,}."


ERROR_MESSAGES: dict[str, Callable[[Params], str]] = {
    # ticket
    "ticket_not_found": lambda p: "הטיקט לא נמצא.",
    "ticket_already_answered": lambda p: "כבר נענה על הטיקט הזה.",
    "empty_answer": lambda p: "צריך להזין סכום או תשובה.",
    "unknown_quick_answer": lambda p: "התשובה המהירה לא מוכרת.",
    "unknown_question": lambda p: "השאלה לא שייכת לטיקט.",
    "not_an_option": lambda p: "צריך לבחור אחת מהאפשרויות.",
    "not_a_whole_amount": lambda p: "צריך סכום בשקלים שלמים.",
    "empty_text": lambda p: "צריך לכתוב תשובה.",
    "text_too_long": lambda p: f"עד {p['max']:,} תווים.",
    "note_required": lambda p: "בעיסוק אחר צריך לפרט בהערה מה העיסוק.",
    "value_with_needs_checking": lambda p: "״צריך לבדוק״ נשלח בלי תשובה.",
    "not_a_blocking_field": lambda p: "השדה הזה לא שייך לטיקט.",
    "field_already_answered": lambda p: "כבר נענה על השדה הזה.",
    # field values
    "not_a_number": lambda p: "צריך להזין מספר.",
    "too_many_decimals": lambda p: "עד שתי ספרות אחרי הנקודה.",
    "unknown_car": lambda p: "הרכב לא נמצא בקטלוג.",
    "out_of_range": _range,
    "effective_from_not_participation": lambda p: "תאריך תחילה רלוונטי רק לסכום השתתפות.",
    "unknown_field": lambda p: "השדה לא מוכר.",
    "name_length": lambda p: f"שם באורך 1 עד {p['max']} תווים.",
    "name_is_a_number": lambda p: "צריך שם, לא מספר (לעולם לא מספר תעודת זהות).",
    "unknown_occupation": lambda p: "העיסוק לא נמצא ברשימת העיסוקים.",
    "unknown_group": lambda p: (
        "קבוצה לא מוכרת. אפשר: " + ", ".join(group_label(g) for g in p["groups"]) + "."
    ),
    "credit_points_step": lambda p: f"בין 0 ל-{p['max']} נקודות, בקפיצות של 0.25.",
    # payslip upload: never a number from the file (limits come from the settings)
    "payslip_in_progress": lambda p: "התלוש הקודם עדיין בעיבוד. רגע אחד.",
    "payslip_per_session": lambda p: f"אפשר להעלות עד {p['max']} תלושים בשיחה אחת.",
    "payslip_per_user_day": lambda p: f"אפשר להעלות עד {p['max']} תלושים ביום. נסו שוב מחר.",
    "payslip_rate_limited": lambda p: "יותר מדי העלאות בזמן קצר. נסו שוב בעוד רגע.",
    "payslip_daily_cap": lambda p: "קריאת תלושים לא זמינה כרגע. אפשר להזין את הנתונים בצ'אט.",
    "payslip_unsupported_type": lambda p: "אפשר להעלות רק PDF, JPG או PNG.",
    "payslip_empty": lambda p: "לא התקבל קובץ.",
    "payslip_too_large": lambda p: f"הקובץ גדול מדי. אפשר עד {p['max_mb']}MB.",
    "payslip_type_mismatch": lambda p: "תוכן הקובץ לא תואם את סוג הקובץ. נסו קובץ אחר.",
    "payslip_encrypted": lambda p: "הקובץ מוגן בסיסמה. העלו עותק בלי סיסמה.",
    "payslip_too_many_pages": lambda p: f"אפשר להעלות תלוש של עד {p['max']} עמודים.",
    "payslip_unreadable": lambda p: "לא הצלחנו לפתוח את הקובץ. נסו קובץ אחר.",
    "payslip_unavailable": lambda p: "קריאת תלושים לא זמינה כרגע. אפשר להזין את הנתונים בצ'אט.",
    "payslip_nothing_pending": lambda p: "אין נתונים מהתלוש שממתינים לאישור.",
    "current_car_not_needed": lambda p: "הרכב של היום כבר נקבע, או שנציג כבר בודק אותו.",
    "current_car_unknown_car": lambda p: "הרכב שנבחר אינו בקטלוג.",
    "current_car_choice_invalid": lambda p: "הבחירה אינה תקינה.",
    "payslip_field_not_allowed": lambda p: "מהתלוש אפשר לאשר רק נתוני שכר.",
    "payslip_invalid_value": lambda p: "אחד הערכים לא תקין. בדקו אותו ונסו שוב.",
    "payslip_extraction_failed": lambda p: (
        "לא הצלחנו לקרוא את נתוני השכר מהתלוש. אפשר לנסות שוב או להזין אותם בצ'אט."
    ),
}


def error_message(code: str, params: Params) -> str:
    return ERROR_MESSAGES[code](params)

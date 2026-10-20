"""Deterministic Hebrew replies built only from tool results: the guard's last resort.

Every number comes from the session's last comparison (display values and explanation facts),
so the text passes the number guard by construction.
"""

from typing import Any

from compass.agent.runner import TemplateFallback
from compass.state import Store

NO_RESULT_HE = (
    "לא הצלחתי לנסח תשובה שכל המספרים בה מאומתים, ולכן לא אציג מספרים בטקסט. "
    "אפשר לנסח את השאלה שוב?"
)


def _money(value: int) -> str:
    return f"{value:,} ₪"


def _signed(value: int) -> str:
    return f"+{value:,} ₪" if value > 0 else f"-{abs(value):,} ₪" if value < 0 else "0 ₪"


def _fact(fact: dict[str, Any]) -> str | None:
    kind = fact.get("kind")
    if kind == "value_of_use_change":
        return f"שווי השימוש משתנה מ-{_money(fact['from'])} ל-{_money(fact['to'])}"
    if kind == "value_of_use_added":
        return f"נוסף שווי שימוש של {_money(fact['amount'])}"
    if kind == "value_of_use_removed":
        return f"בוטל שווי שימוש של {_money(fact['amount'])}"
    if kind == "maintenance_added":
        return f"נוספת אחזקת רכב של {_money(fact['amount'])} (חייבת במס)"
    if kind == "maintenance_removed":
        return f"מתבטלת אחזקת רכב של {_money(fact['amount'])}"
    if kind == "maintenance_change":
        return f"אחזקת הרכב משתנה מ-{_money(fact['from'])} ל-{_money(fact['to'])}"
    if kind == "electric_bonus":
        return (
            f"החזר חשמל של {_money(fact['net'])} נטו (מגולם)"
            if fact.get("net")
            else ("החזר חשמל (מגולם)")
        )
    if kind == "participation_change" and fact["from"] != fact["to"]:
        return f"ההשתתפות שלך משתנה מ-{_money(fact['from'])} ל-{_money(fact['to'])}"
    if kind == "family_share":
        return f"חלקך בפער במסלול המשפחתי: {_money(fact['amount'])}"
    return None


def render(result: dict[str, Any]) -> str:
    """The Hebrew summary of one comparison result (the payload of comparison_ready)."""
    comparison = result["comparison"]
    diff = comparison["display_diff"]
    today = None if comparison["today"] is None else comparison["today"]["display"]["net"]
    alternative = comparison["alternative"]["display"]["net"]
    lines = []
    if diff is None:  # today unknown: the alternative's own net
        lines.append(
            f"לפי החישוב, הנטו המשוער בחלופה הוא {_money(alternative)} בחודש. "
            "ההפרש יוצג כשהרכב של היום יהיה ידוע."
        )
    elif today is None or alternative is None:  # partial: unknown contribution rates
        lines.append(
            f"לפי החישוב, ההפרש בנטו המשוער הוא {_signed(diff)} בחודש. "
            "הנטו המלא יוצג כשיהיו ידועים כל הנתונים."
        )
    else:
        lines.append(
            f"לפי החישוב: נטו משוער היום {_money(today)}, ובחלופה {_money(alternative)} — "
            f"הפרש של {_signed(diff)} בחודש."
        )
    facts = [text for fact in comparison["explanation_facts"] if (text := _fact(fact))]
    if facts:
        lines.append("מה משפיע: " + "; ".join(facts) + ".")
    if result.get("hypothetical"):
        lines.append("שימו לב: החלופה הזו אינה זמינה לך כרגע — החישוב בכפוף לאישור.")
    if result.get("pending_rep"):
        lines.append("ההשתתפות בחישוב היא ברירת המחדל מהקטלוג, עד לאישור הנציג.")
    return "\n".join(lines)


def make_template(store: Store) -> TemplateFallback:
    def build(session_id: str) -> str:
        events = [e for e in store.events_after(session_id) if e.type == "comparison_ready"]
        return render(events[-1].payload) if events else NO_RESULT_HE

    return build

"""DemoClient: a scripted model for demo mode (COMPASS_LLM=scripted): no network, no API key.

Only the model is scripted. The tools it calls run for real, the number guard checks every
reply, and the representative's answer arrives through the real ticket flow. The client keeps no
state of its own: each call reads the conversation it is given, finds the last trigger (an
employee message, a representative's answer or a guard note) and counts the model turns since,
so any number of sessions can run side by side.

A trigger that matches no script step gets NO_SCRIPT_HE, which contains no numbers.
"""

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from compass.agent.llm import LLMResponse, Message, ToolChoice, text_response, tool_response
from compass.agent.transcript import CAR_TAG, EMPLOYEE_TAG, PAYSLIP_TAG, REP_TAG

# After the employee confirms payslip values (COMPASS_PAYSLIP=1): no numbers, so the guard has
# nothing to check; the cards already show the values and the recomputed difference.
PAYSLIP_REPLY_HE = "קיבלתי את הנתונים שאישרת מהתלוש. ההשוואה על המסך עודכנה לפיהם."

# After the employee picks today's car in the catalog picker: no numbers either.
CAR_REPLY_HE = "רשמתי את הרכב שבחרת. ההשוואה על המסך עודכנה לפיו."

NO_SCRIPT_HE = (
    "במצב דמו אני עונה רק על התרחישים המוכנים. "
    "בחרו אחת מההודעות המוצעות מעל תיבת הכתיבה, או הפעילו את המערכת עם מפתח API."
)
DEMO_DELAY_SECONDS = 0.5  # per model call, so the UI's thinking indicator is visible

ATTO = "alternative_participation:CAR-10"
COROLLA_CROSS_TODAY = {
    "today": {
        "kind": "company_car",
        "car_id": "CAR-09",
        "registration_year": 2025,
        "participation": 300,
    }
}

# A step: ("tools", [(name, input), ...]) or ("text", reply).
Step = tuple[str, Any]


@dataclass(frozen=True)
class Turn:
    """What the model does after one trigger: an employee message (`employee`), or the
    representative's answer to a ticket on `rep_field`."""

    steps: tuple[Step, ...]
    employee: str | None = None
    rep_field: str | None = None


@dataclass(frozen=True)
class Script:
    name: str
    title: str  # Hebrew, for the demo's suggestion chips
    turns: tuple[Turn, ...]

    @property
    def employee_messages(self) -> list[str]:
        return [t.employee for t in self.turns if t.employee is not None]


WALKTHROUGH = Script(
    name="walkthrough",
    title="ויתור על הרכב",
    turns=(
        Turn(
            employee="אני מפתחת תוכנה, שכר בסיס 18,500",
            steps=(
                (
                    "tools",
                    [("save_profile", {"occupation_query": "מפתחת תוכנה", "base_salary": 18500})],
                ),
                (
                    "text",
                    "מפתחת תוכנה ← קבוצה ב׳, תקציב 3,700 ₪. יש לך עמלות או בונוסים? "
                    "ומה אחוזי ההפרשה שלך לפנסיה ולקרן השתלמות, וכמה נקודות זיכוי?",
                ),
            ),
        ),
        Turn(
            employee=(
                "אין לי עמלות או בונוסים. פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. "
                "היום יש לי קורולה קרוס 2025 ואני משתתפת ב-300 ₪. "
                "מה יקרה לנטו אם אוותר על הרכב?"
            ),
            steps=(
                (
                    "tools",
                    [
                        (
                            "save_profile",
                            {
                                "commissions": 0,
                                "bonus": 0,
                                "pension_percent": 6.5,
                                "study_fund_percent": 2.5,
                                "credit_points": 3,
                            },
                        ),
                        ("lookup_vehicle", {"query": "קורולה קרוס", "registration_year": 2025}),
                    ],
                ),
                (
                    "tools",
                    [
                        ("set_current_situation", COROLLA_CROSS_TODAY),
                        ("compare", {"alternative": {"kind": "waiver"}}),
                    ],
                ),
                (
                    "text",
                    "אם תוותרי על הרכב, הנטו המשוער עולה מ-11,000 ₪ ל-13,914 ₪: "
                    "הפרש של +2,914 ₪ בחודש. החישוב מתייחס לשכר בלבד; "
                    "עלויות של רכב פרטי לא נכללות בו.",
                ),
            ),
        ),
    ),
)

E001 = Script(
    name="e001",
    title="מעבר ל-ATTO 3 עם נציג",
    turns=(
        Turn(
            employee="אני מנהלת מוצר, שכר בסיס 18,500",
            steps=(
                (
                    "tools",
                    [("save_profile", {"occupation_query": "מנהלת מוצר", "base_salary": 18500})],
                ),
                (
                    "text",
                    "מנהלת מוצר ← קבוצה ג׳, תקציב 4,500 ₪. יש לך עמלות או בונוסים? "
                    "ומה אחוזי ההפרשה שלך לפנסיה ולקרן השתלמות, וכמה נקודות זיכוי?",
                ),
            ),
        ),
        Turn(
            employee=(
                "אין לי עמלות או בונוסים. פנסיה 6%, קרן השתלמות 2.5%, 2.75 נקודות זיכוי, "
                "2 ילדים מתחת לגיל 23. היום יש לי קורולה קרוס 2025 ואני משתתפת ב-300 ₪."
            ),
            steps=(
                (
                    "tools",
                    [
                        (
                            "save_profile",
                            {
                                "commissions": 0,
                                "bonus": 0,
                                "pension_percent": 6,
                                "study_fund_percent": 2.5,
                                "credit_points": 2.75,
                                "children_under_23": 2,
                            },
                        ),
                        ("set_current_situation", COROLLA_CROSS_TODAY),
                    ],
                ),
                (
                    "text",
                    "רשמתי את כל הפרטים. היום: COROLLA CROSS עם השתתפות של 300 ₪. "
                    "איזו חלופה לבדוק?",
                ),
            ),
        ),
        Turn(
            employee=(
                "מה יקרה לנטו אם אעבור ל-ATTO 3? אני לא יודעת מה תהיה ההשתתפות שלי בו, "
                "אפשר לשאול את הנציג?"
            ),
            steps=(
                (
                    "tools",
                    [
                        (
                            "ask_representative",
                            {
                                "question": "מה גובה ההשתתפות העצמית החודשית ב-ATTO 3?",
                                "blocking_fields": [ATTO],
                            },
                        )
                    ],
                ),
                ("tools", [("compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})]),
                (
                    "text",
                    "פתחתי פנייה לנציג לגבי ההשתתפות ב-ATTO 3. בינתיים, לפי ההשתתפות "
                    "שבקטלוג (300 ₪), הנטו המשוער עולה ב-661 ₪ בחודש. זה מספר זמני: "
                    "אעדכן ברגע שהנציג יענה.",
                ),
            ),
        ),
        Turn(
            rep_field=ATTO,
            steps=(
                ("tools", [("compare", {"alternative": {"kind": "car", "car_id": "CAR-10"}})]),
                (
                    "text",
                    "הנציג אישר השתתפות של 350 ₪ ב-ATTO 3. החישוב הסופי: הנטו המשוער "
                    "עולה מ-11,032 ₪ ל-11,643 ₪, כלומר +611 ₪ בחודש.",
                ),
            ),
        ),
    ),
)

SCRIPTS: tuple[Script, ...] = (WALKTHROUGH, E001)


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _text_of(message: Message) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    return "".join(
        b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"
    )


def _trigger(messages: Sequence[Message]) -> tuple[int, str, Any]:
    """(index, kind, data) of the last trigger: ("employee", text), ("rep", values),
    ("payslip", None) or ("guard", None)."""
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") == "system":
            return index, "guard", None
        if message.get("role") != "user":
            continue
        text = _text_of(message).strip()
        if text.startswith(f"<{EMPLOYEE_TAG}>"):
            body = text.removeprefix(f"<{EMPLOYEE_TAG}>").removesuffix(f"</{EMPLOYEE_TAG}>")
            return index, "employee", _normalize(body)
        if text.startswith(f"<{PAYSLIP_TAG}"):
            return index, "payslip", None
        if text.startswith(f"<{CAR_TAG}"):
            return index, "car", None
        if text.startswith(f"<{REP_TAG}"):
            body = text.split("\n", 1)[1].rsplit("\n", 1)[0]
            return index, "rep", json.loads(body).get("values") or {}
    return -1, "none", None


class DemoClient:
    """LLMClient for demo mode. `scripts` and `delay` are for tests."""

    def __init__(
        self,
        scripts: Sequence[Script] = SCRIPTS,
        delay: float | None = None,  # None: DEMO_DELAY_SECONDS
        model: str = "scripted",
    ) -> None:
        self.scripts = tuple(scripts)
        self.delay = DEMO_DELAY_SECONDS if delay is None else delay
        self.model = model

    def _turn(self, kind: str, data: Any) -> Turn | None:
        for script in self.scripts:
            for turn in script.turns:
                if kind == "employee" and turn.employee and _normalize(turn.employee) == data:
                    return turn
                if kind == "rep" and turn.rep_field and turn.rep_field in data:
                    return turn
        return None

    def create(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
        system: str,
        tool_choice: ToolChoice | None = None,
    ) -> LLMResponse:
        if self.delay:
            time.sleep(self.delay)
        index, kind, data = _trigger(messages)
        done = sum(1 for m in messages[index + 1 :] if m.get("role") == "assistant")
        if kind == "payslip":
            return text_response(PAYSLIP_REPLY_HE if done == 0 else NO_SCRIPT_HE)
        if kind == "car":
            return text_response(CAR_REPLY_HE if done == 0 else NO_SCRIPT_HE)
        turn = self._turn(kind, data)
        if turn is None or done >= len(turn.steps):
            return text_response(NO_SCRIPT_HE)
        step_kind, step = turn.steps[done]
        if step_kind == "tools":
            if tool_choice and tool_choice.get("type") == "none":  # a rewrite: no tools
                return text_response(NO_SCRIPT_HE)
            return tool_response(*step)
        return text_response(step)


def demo_scripts() -> list[dict[str, Any]]:
    """The scripts' employee messages, for the UI's suggestion chips in demo mode."""
    return [{"name": s.name, "title": s.title, "messages": s.employee_messages} for s in SCRIPTS]

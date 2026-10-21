"""The sources behind a reply's numbers ("מאיפה המספר הזה?"): recorded for the exact text that is
sent, from what the guard already knows and the stored comparison views; nothing is recomputed,
and with the flag off the event is what it always was."""

import random
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_runner import PROFILE, TODAY, make_runner, say

from compass.agent.guard import Allowed, check_text, extract, make_guard, number_spans
from compass.agent.llm import text_response, tool_response
from compass.agent.number_sources import build_number_sources
from compass.api.redact import public_payload
from compass.labels import NUMBER_CHIP_LABELS
from compass.state import Store
from compass.tools.services import Services

EMPLOYEE_SAYS = "אני מפתחת תוכנה, שכר בסיס 18500, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי"
REPLY = "הנטו עולה מ-11,000 ₪ ל-13,914 ₪, הפרש של +2,914 ₪. שכר הבסיס שלך 18,500 ₪."
CHIPS_TS = Path(__file__).resolve().parents[3] / "frontend" / "src" / "ui" / "chips.ts"


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return Services(Store(tmp_path / "app.db"))


def turn(
    services: Services, reply: str | list[str], *, flag: bool = True, template: str = "TEMPLATE"
) -> tuple[str, list[Any]]:
    """One real turn: the tools compute a waiver comparison, the real guard checks the reply."""
    sid = services.store.create_session()
    replies = [reply] if isinstance(reply, str) else reply
    steps = [
        tool_response(("save_profile", PROFILE)),
        tool_response(
            ("set_current_situation", TODAY), ("compare", {"alternative": {"kind": "waiver"}})
        ),
        *[text_response(r) for r in replies],
    ]
    runner, _ = make_runner(
        services,
        steps,
        guard=make_guard(services.store),
        template=lambda session_id: template,
        number_sources=flag,
    )
    say(runner, sid, EMPLOYEE_SAYS)
    return sid, services.store.events_after(sid)


def sent(events: list[Any]) -> dict[str, Any]:
    return [e.payload for e in events if e.type == "assistant_message"][-1]


def parse(text: str) -> Decimal:
    plain = text.replace("−", "-").replace(",", "").replace("%", "").replace(" ", "")
    return Decimal(plain.replace(" ", ""))


def by_text(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {payload["text"][s["start"] : s["end"]]: s for s in payload["number_sources"]}


# --- the event ----------------------------------------------------------------------------------


def test_the_event_carries_the_sources_of_the_sent_text(services: Services) -> None:
    sid, events = turn(services, REPLY)
    payload = sent(events)
    assert payload["text"] == REPLY and payload["kind"] == "reply"
    found = by_text(payload)
    assert list(found) == ["11,000", "13,914", "+2,914", "18,500"]

    diff = found["+2,914"]
    comparison = [e for e in events if e.type == "comparison_ready"][-1]
    assert (diff["value"], diff["kind"], diff["chip"]) == ("2914", "tool", "computed")
    assert diff["label"] == "חושב בשרת" and diff["what"] == "הפרש בנטו לחודש"
    assert diff["origin"]["tool"] == "compare"
    assert diff["origin"]["label"] == "חושב בכלי compare · בשרת, בלי מודל"
    assert diff["ref"]["comparison_seq"] == comparison.seq and diff["ref"]["role"] == "diff"
    # the components the UI shows are the stored view's own lines, not computed here
    assert comparison.payload["view"]["breakdown"]

    assert found["11,000"]["what"] == "נטו בחודש, היום"
    assert found["13,914"]["what"] == "נטו בחודש, בחלופה"

    salary = found["18,500"]  # the employee said it: the waterfall's chip is "לפי דבריך"
    assert (salary["kind"], salary["chip"], salary["slot"]) == (
        "employee",
        "employee_input",
        "base_salary",
    )
    assert salary["label"] == "לפי דבריך" and salary["what"] == "שכר בסיס"
    assert salary["origin"]["source"] == "employee" and salary["origin"]["at"]
    assert salary["origin"]["label"] == "לפי דבריך, בהודעה מ־{time}"
    user_row = next(m for m in services.store.messages(sid) if m.role == "user")
    assert salary["ref"]["message_seq"] == user_row.seq


def test_flag_off_the_event_is_what_it_always_was(services: Services) -> None:
    _, off = turn(services, REPLY, flag=False)
    _, on = turn(services, REPLY, flag=True)
    quiet, loud = sent(off), sent(on)
    assert set(quiet) == {"message_seq", "text", "kind", "comparison_ref"}
    assert {k: v for k, v in loud.items() if k != "number_sources"}.keys() == quiet.keys()
    assert "number_sources" not in quiet and loud["number_sources"]
    # the guard_check events are the same either way: no spans leak into them
    guard_off = [e.payload for e in off if e.type == "guard_check"]
    guard_on = [e.payload for e in on if e.type == "guard_check"]
    assert guard_off == guard_on and set(guard_on[0]) == {
        "passed",
        "numbers",
        "violations",
        "sources",
        "action",
    }


def test_a_reply_without_numbers_has_an_empty_list(services: Services) -> None:
    _, events = turn(services, "שלום, אפשר לעזור עוד במשהו?")
    assert sent(events)["number_sources"] == []


def test_template_and_error_replies_carry_no_sources(services: Services) -> None:
    bad = "הנטו יעלה ב-9,999 ₪"  # no source: rejected twice, so the template is sent
    _, events = turn(services, [bad, bad], template="התוצאות בכרטיס ההשוואה.")
    payload = sent(events)
    assert payload["kind"] == "template" and "number_sources" not in payload


def test_the_retry_text_is_described_not_the_rejected_draft(services: Services) -> None:
    draft = "ההפרש הוא 2,915 ₪"  # rounding that is not in any result: rejected
    retry = "בקיצור: +2,914 ₪ בחודש, ואחרי זה 13,914 ₪."
    sid, events = turn(services, [draft, retry])
    payload = sent(events)
    assert payload["text"] == retry
    found = by_text(payload)
    assert list(found) == ["+2,914", "13,914"]
    assert all("2,915" not in str(s) for s in payload["number_sources"])
    assert [e.payload["action"] for e in events if e.type == "guard_check"] == [
        "retry",
        "accept_after_retry",
    ]


def test_redaction_keeps_the_sources_and_replay_returns_them(services: Services) -> None:
    sid, events = turn(services, REPLY)
    payload = sent(events)
    assert public_payload("assistant_message", payload) == payload  # the employee's own reply
    seq = [e.seq for e in events if e.type == "assistant_message"][-1]
    replayed = services.store.events_after(sid, seq - 1)  # Last-Event-ID
    assert replayed[0].payload["number_sources"] == payload["number_sources"]


# --- numbers that stay plain text ----------------------------------------------------------------


def test_harmless_numbers_and_identifiers_stay_plain(services: Services) -> None:
    allowed = Allowed()
    # a tool result that happens to hold 3, 10, 40 and 2025 inside names
    allowed.add_json({"name": "ATTO 3 2025", "id": "CAR-10", "model": "C40 MG4"}, "search_catalog")
    allowed.add_json({"net": 14000}, "compare")
    text = "יש 3 אפשרויות: ATTO 3 2025, CAR-10, MG4 ו-C40, ו-14,000 ₪ בחודש."
    verdict = check_text(text, allowed)
    assert verdict.passed  # the guard's own verdict is unchanged
    records = build_number_sources(text, verdict.spans, [], 0)
    assert [text[r["start"] : r["end"]] for r in records] == ["14,000"]
    assert records[0]["value"] == "14000"  # never "1.4E+4"
    # compare's own output that no view shows: still computed, and it says no more than that
    assert records[0]["kind"] == "tool" and records[0]["chip"] == "computed"
    assert records[0]["what"] is None and "comparison_seq" not in records[0]["ref"]


def test_a_percent_is_not_a_harmless_count() -> None:
    allowed = Allowed()
    allowed.add_json({"pension_percent": 6}, "employee")
    text = "הפרשה של 6% ועוד 6 ימים."
    records = build_number_sources(text, check_text(text, allowed).spans, [], 0)
    assert [text[r["start"] : r["end"]] for r in records] == ["6%"]


def test_dates_are_not_numbers() -> None:
    allowed = Allowed()
    allowed.add_text("2026-11-01", "representative")
    text = "החל מ-2026-11-01"
    assert check_text(text, allowed).passed
    assert check_text(text, allowed).spans == []


# --- spans parse back (the property) ---------------------------------------------------------

FORMS = ["2,914", "+611", "−473", "-473", "6%", "2.5%", "14,000", "1,234,567.89", "0.5", "18500"]


def _allowed_for(texts: list[str]) -> Allowed:
    allowed = Allowed()
    for form in texts:
        for token in extract(form):
            allowed.add_value(token["value"], "compare", {"message_seq": 1})
            allowed.add_value(-token["value"], "compare", {"message_seq": 1})
    return allowed


def test_every_span_parses_back_to_its_value() -> None:
    rng = random.Random(7)
    hebrew = ["הנטו", "עולה", "ב", "מ-", "ל-", "בערך", "₪", "(", "שקלים,", "והפרש:", "ו", ""]
    allowed = _allowed_for(FORMS)
    checked = 0
    for _ in range(400):
        parts: list[str] = []
        for _ in range(rng.randint(1, 6)):
            parts += [rng.choice(hebrew), rng.choice(FORMS), rng.choice(["", " ₪", " ", "."])]
        text = " ".join(parts)
        verdict = check_text(text, allowed)
        for record in build_number_sources(text, verdict.spans, [], 0):
            checked += 1
            assert parse(text[record["start"] : record["end"]]) == Decimal(record["value"]), text
        for span in verdict.spans:  # and the guard's own record, harmless included
            assert parse(text[span["start"] : span["end"]]) == span["value"]
    assert checked > 200


@pytest.mark.parametrize(
    ("text", "shown", "values"),
    [
        ("הנטו עלה ב-2,914 ₪ בחודש", ["2,914"], ["2914"]),  # a Hebrew prefix is not a minus
        ("הפרש של +611 ₪", ["+611"], ["611"]),
        ("הפרש של −473 ₪", ["−473"], ["-473"]),  # the Unicode minus
        ("הפרש של -473 ₪", ["-473"], ["-473"]),  # the hyphen
        ("פנסיה 6% וקרן 2.5%", ["6%", "2.5%"], ["6", "2.5"]),
        ("השתתפות של 14,000 ₪", ["14,000"], ["14000"]),
    ],
)
def test_edge_cases(text: str, shown: list[str], values: list[str]) -> None:
    allowed = _allowed_for(FORMS)
    records = build_number_sources(text, check_text(text, allowed).spans, [], 0)
    assert [text[r["start"] : r["end"]] for r in records] == shown
    assert [r["value"] for r in records] == values
    assert "₪" not in "".join(text[r["start"] : r["end"]] for r in records)


def test_the_same_value_twice_with_different_sources() -> None:
    allowed = Allowed()
    allowed.add_value(Decimal(611), "employee", {"message_seq": 1, "at": "2026-10-21T08:00:00Z"})
    allowed.add_value(Decimal(-611), "compare", {"message_seq": 5, "tool_use_id": "t1"})
    text = "ההפרש היה −611 ₪ ולא 611 ₪ כמו שכתבת."
    records = build_number_sources(text, check_text(text, allowed).spans, [], 0)
    first, second = records
    assert (first["kind"], first["origin"]["tool"]) == ("tool", "compare")
    assert (second["kind"], second["origin"]["source"]) == ("employee", "employee")
    assert second["ref"]["message_seq"] == 1 and first["ref"]["tool_use_id"] == "t1"


def test_origin_follows_the_guards_own_lookup(services: Services) -> None:
    """origin_of only reports: for every token it agrees with source_of."""
    sid, _ = turn(services, REPLY)
    from compass.agent.guard import allowed_for_session

    allowed = allowed_for_session(services.store, sid)
    for text in (REPLY, "−2,914 +18,500 18,500 −11,000 9,999 3 2025 1/1"):
        for token in extract(text):
            source, origin = allowed.source_of(token), allowed.origin_of(token)
            if source in (None, "harmless"):
                assert origin == {}
            else:
                assert origin.get("message_seq")
    assert number_spans(extract("9,999"), allowed) == []


def test_two_different_things_with_one_value_are_not_guessed(services: Services) -> None:
    """If a value is two different things in the stored views, only the guard's record shows."""
    sid, events = turn(services, REPLY)
    comparison = [e for e in events if e.type == "comparison_ready"][-1]
    view = {**comparison.payload["view"], "today_net": 13914}  # today == alternative: ambiguous
    forged = comparison.model_copy(update={"payload": {**comparison.payload, "view": view}})
    allowed = Allowed()
    allowed.add_value(Decimal(13914), "compare", {"message_seq": 2})
    text = "13,914 ₪"
    records = build_number_sources(text, check_text(text, allowed).spans, [forged], 0)
    assert records[0]["chip"] == "computed"  # either way it is a computed net
    assert records[0]["what"] is None and "role" not in records[0]["ref"]


# --- the labels are the server's -----------------------------------------------------------------


def test_chip_labels_match_the_ui_chips() -> None:
    """The popover's chips are the UI's (ui/chips.ts); the server owns the words, this pins them."""
    ui = dict(re.findall(r'(\w+): \{\s*label: "([^"]+)"', CHIPS_TS.read_text(encoding="utf-8")))
    assert set(NUMBER_CHIP_LABELS) <= set(ui)
    assert {k: ui[k] for k in NUMBER_CHIP_LABELS} == NUMBER_CHIP_LABELS

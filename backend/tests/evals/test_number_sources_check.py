"""The eval's global check on the recorded number sources (COMPASS_NUMBER_SOURCES=1), the audit
behind it, and the switches: off in code, on in the Blueprint."""

from pathlib import Path
from typing import Any

import yaml

from compass.agent.number_sources import audit
from compass.api import Settings
from evals.checks import Reply, Trace, global_checks

REPO = Path(__file__).resolve().parents[3]
TEXT = "הפרש של +2,914 ₪ ותקציב 3,700 ₪"
COMPARE = "חושב בכלי compare · בשרת, בלי מודל"


def source(shown: str, **over: Any) -> dict[str, Any]:
    start = TEXT.index(shown)
    value = shown.replace(",", "").replace("+", "")
    base: dict[str, Any] = {
        "start": start,
        "end": start + len(shown),
        "value": value,
        "kind": "tool",
        "label": "חושב בשרת",
        "chip": "computed",
        "origin": {"source": "tool", "tool": "compare", "label": COMPARE, "at": None},
    }
    return base | over


GOOD = [
    source("+2,914"),
    source(
        "3,700",
        kind="rule",
        chip="rule",
        label="לפי הכללים",
        origin={"source": "rule", "tool": None, "label": "לפי כללי החברה", "at": None},
    ),
]


def test_a_sound_record_has_nothing_to_report() -> None:
    assert audit(TEXT, GOOD) == []
    assert audit(TEXT, []) == []


def test_every_way_a_record_can_be_wrong_is_reported() -> None:
    wrong_value = source("+2,914", value="2915")
    out_of_bounds = source("+2,914", end=999)
    overlapping = [source("+2,914"), source("2,914")]
    rule_chip_on_a_computed_number = source("+2,914", chip="rule", label="לפי הכללים")
    tool_claim_on_a_rule = source("3,700", kind="rule", chip="rule", label="לפי הכללים")
    computed_as_tool_label = source("+2,914", label="לפי הכללים")
    assert any("parse back" in p for p in audit(TEXT, [wrong_value]))
    assert any("out of bounds" in p for p in audit(TEXT, [out_of_bounds]))
    assert any("overlapping" in p for p in audit(TEXT, overlapping))
    assert audit(TEXT, [rule_chip_on_a_computed_number])
    assert any("claims a tool" in p for p in audit(TEXT, [tool_claim_on_a_rule]))
    assert any("wrong kind or label" in p for p in audit(TEXT, [computed_as_tool_label]))


def labels(trace: Trace) -> dict[str, bool]:
    return {r.label: r.passed for r in global_checks(trace)}


def test_the_check_exists_only_with_the_flag_on() -> None:
    off = Trace(replies=[Reply(0, TEXT, "reply")])
    assert not [lbl for lbl in labels(off) if "number sources" in lbl]  # reports are unchanged
    on = Trace(replies=[Reply(0, TEXT, "reply", GOOD)])
    assert labels(on)["[global] number sources describe the sent text"] is True
    bad = Trace(replies=[Reply(0, TEXT, "reply", [source("+2,914", value="1")])])
    assert labels(bad)["[global] number sources describe the sent text"] is False
    template = Trace(replies=[Reply(0, "אין מספרים", "template")])  # no key: nothing to check
    assert not [lbl for lbl in labels(template) if "number sources" in lbl]


def test_off_in_code_on_in_the_blueprint() -> None:
    assert Settings().number_sources is False
    blueprint = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))
    api = next(s for s in blueprint["services"] if s["name"] == "compass-api")
    env = {e["key"]: e.get("value") for e in api["envVars"]}
    assert env["COMPASS_NUMBER_SOURCES"] == "1"

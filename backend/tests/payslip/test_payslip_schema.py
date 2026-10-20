"""The extraction contract (compass/payslip/schema.py): a fixed schema with no free text,
Decimal values with no rounding, out-of-range and wrong-typed values nulled and flagged, unknown
keys (an ID number, a name) dropped and only counted."""

import json
import logging
from decimal import Decimal
from typing import Any

import pytest

from compass.payslip.schema import (
    EXTRACTION_SCHEMA,
    FIELDS,
    INFO_FIELDS,
    PROFILE_FIELD_OF,
    InvalidExtraction,
    normalise,
    parse_extraction,
)
from compass.tools.profile import SLOT_OF

# invented, never a real person's
FAKE_NAME = "ישראלה בדויה"
FAKE_ID = "000000018"
FAKE_BANK = "12-345-678901"


def _answer(**fields: Any) -> str:
    """A JSON answer: every field null unless given as (value, confidence)."""
    body = {name: {"value": None, "confidence": "low"} for name in FIELDS}
    for name, given in fields.items():
        # (value, confidence) -> a field; anything else is sent as it is (a wrong shape)
        if isinstance(given, tuple):
            given = {"value": given[0], "confidence": given[1]}
        body[name] = given
    return json.dumps(body, ensure_ascii=False)


VALID = _answer(
    base_salary=(18500, "high"),
    commissions=(1200.5, "medium"),
    bonus=(0, "high"),
    pension_percent=(6.5, "high"),
    study_fund_percent=(2.5, "high"),
    credit_points=(2.75, "medium"),
    car_benefit_value=(3480, "low"),
    payslip_month=("2026-09", "high"),
)


def _leaves(schema: Any, path: str = "$") -> list[tuple[str, Any]]:
    if isinstance(schema, dict) and schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, path
        assert set(schema["required"]) == set(schema["properties"]), path
        out = []
        for name, sub in schema["properties"].items():
            out += _leaves(sub, f"{path}.{name}")
        return out
    return [(path, schema)]


def test_the_schema_is_fixed_and_has_no_free_text() -> None:
    assert set(EXTRACTION_SCHEMA["properties"]) == set(FIELDS)
    for path, leaf in _leaves(EXTRACTION_SCHEMA):
        if path.endswith(".confidence"):
            assert leaf == {"type": "string", "enum": ["high", "medium", "low"]}
        elif path == "$.payslip_month.value":
            assert leaf == {"type": ["string", "null"]}  # kept only when exactly YYYY-MM
        else:
            assert path.endswith(".value") and leaf == {"type": ["number", "null"]}, path


def test_every_calculation_field_is_an_existing_slot() -> None:
    assert set(PROFILE_FIELD_OF.values()) <= set(SLOT_OF)
    assert set(INFO_FIELDS) == {"car_benefit_value", "payslip_month"}
    assert not set(INFO_FIELDS) & set(SLOT_OF)  # information only: no new calculation input
    # never occupation, group, or anything a representative answers
    assert not {"occupation", "group", "display_name"} & set(FIELDS)


def test_valid_input_exact_decimals_no_rounding() -> None:
    candidate = parse_extraction(VALID)
    values = {name: f.value for name, f in candidate.fields.items()}
    assert values == {
        "base_salary": "18500",
        "commissions": "1200.5",
        "bonus": "0",
        "pension_percent": "6.5",
        "study_fund_percent": "2.5",
        "credit_points": "2.75",
        "car_benefit_value": "3480",
        "payslip_month": "2026-09",
    }
    assert candidate.fields["commissions"].confidence == "medium"
    assert candidate.flagged == 0 and candidate.dropped_keys == 0
    # Decimal straight from the text: no float on the way
    assert Decimal(parse_extraction(_answer(bonus=(0.1, "high"))).fields["bonus"].value) == Decimal(
        "0.1"
    )


def test_a_dict_from_the_scripted_extractor_with_floats() -> None:
    raw = {"pension_percent": {"value": 6.5, "confidence": "high"}}
    assert normalise(raw).fields["pension_percent"].value == "6.5"


def test_unknown_keys_are_dropped_and_counted(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    body = json.loads(VALID)
    body |= {"id_number": FAKE_ID, "employee_name": FAKE_NAME, "bank_account": FAKE_BANK}
    body["base_salary"]["note"] = f"for {FAKE_NAME}"  # free text inside a field
    candidate = parse_extraction(json.dumps(body, ensure_ascii=False))
    assert candidate.dropped_keys == 4
    assert candidate.fields["base_salary"].value == "18500"
    kept = json.dumps(candidate.to_dict(), ensure_ascii=False) + repr(candidate)
    for secret in (FAKE_ID, FAKE_NAME, FAKE_BANK, "id_number", "employee_name", "note"):
        assert secret not in kept
        assert secret not in caplog.text


@pytest.mark.parametrize(
    ("field", "value", "flag"),
    [
        ("pension_percent", 10.5, "out_of_range"),
        ("pension_percent", -1, "out_of_range"),
        ("study_fund_percent", 11, "out_of_range"),
        ("credit_points", 15.25, "out_of_range"),
        ("credit_points", 2.3, "not_a_step"),
        ("base_salary", 99_999_999, "out_of_range"),
        ("base_salary", 500, "out_of_range"),
        ("bonus", -100, "out_of_range"),
        ("car_benefit_value", 50_000, "out_of_range"),
        ("commissions", 100.555, "too_many_decimals"),
        ("base_salary", 1e308, "out_of_range"),
    ],
)
def test_out_of_range_becomes_null_with_a_flag(field: str, value: Any, flag: str) -> None:
    got = parse_extraction(_answer(**{field: (value, "high")})).fields[field]
    assert got.value is None and got.flag == flag and got.confidence == "high"


@pytest.mark.parametrize("value", ["18500", "₪18,500", True, [18500], {"amount": 18500}, "NaN"])
def test_wrong_types_are_never_parsed_from_text(value: Any) -> None:
    got = parse_extraction(_answer(base_salary={"value": value, "confidence": "high"}))
    assert got.fields["base_salary"].value is None
    assert got.fields["base_salary"].flag == "wrong_type"


@pytest.mark.parametrize(
    ("given", "flag"),
    [
        ({"value": 18500, "confidence": "certain"}, "invalid"),
        ({"value": 18500}, "invalid"),
        (18500, "invalid"),  # a bare number, not {value, confidence}
        ("18500", "invalid"),
    ],
)
def test_a_field_of_the_wrong_shape_is_invalid(given: Any, flag: str) -> None:
    got = parse_extraction(_answer(base_salary=given)).fields["base_salary"]
    assert got.value is None and got.flag == flag


@pytest.mark.parametrize(
    ("month", "kept"),
    [
        ("2026-09", "2026-09"),
        ("2026-9", None),
        ("09/2026", None),
        ("2026-13", None),
        (202609, None),
    ],
)
def test_payslip_month(month: Any, kept: str | None) -> None:
    got = parse_extraction(_answer(payslip_month=(month, "high"))).fields["payslip_month"]
    assert got.value == kept
    assert (got.flag is None) == (kept is not None)


def test_nulls_are_kept_as_unknown_not_flagged() -> None:
    candidate = parse_extraction(_answer())
    assert all(f.value is None and f.flag is None for f in candidate.fields.values())


def test_a_partial_answer_has_only_the_fields_sent() -> None:
    candidate = parse_extraction(json.dumps({"bonus": {"value": 500, "confidence": "low"}}))
    assert list(candidate.fields) == ["bonus"]


@pytest.mark.parametrize(
    "text", ["", "not json", "[1, 2]", '"a string"', "null", "{", "1" * 5000 + "x"]
)
def test_empty_or_garbage_is_invalid_and_never_quoted(text: str) -> None:
    with pytest.raises(InvalidExtraction) as raised:
        parse_extraction(text)
    assert text[:20] not in str(raised.value) or not text

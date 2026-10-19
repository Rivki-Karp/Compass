import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from compass.config import RAW_RULES_JSON, RULES_YAML
from compass.rules import Rules, RulesError, load_rules


@pytest.fixture(scope="module")
def rules() -> Rules:
    return load_rules(RULES_YAML)


def write_broken(tmp_path: Path, mutate: Callable[[dict[str, Any]], None]) -> Path:
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# --- the real file --------------------------------------------------------------------------


def test_real_file_loads(rules: Rules) -> None:
    assert rules.version == "mock-2026-10-12"
    assert list(rules.budgets) == ["א", "ב", "ג", "ד"]
    assert rules.group_order == ("א", "ב", "ג", "ד")
    assert rules.electric.method == "gross_up"
    assert len(rules.net_method.brackets) == 7


def test_money_and_rates_are_decimal(rules: Rules) -> None:
    nm = rules.net_method
    values = [
        *rules.budgets.values(),
        rules.electric.net_bonus,
        rules.electric.gross_amount,
        rules.family_track.gap_split_employee,
        nm.credit_point_value,
        nm.national_insurance.threshold,
        nm.national_insurance.low_rate,
        nm.health.high_rate,
        nm.pension_credit.rate,
        nm.pension_credit.income_ceiling,
        nm.pension_credit.max_contribution_rate,
        *(b.rate for b in nm.brackets),
        *(b.up_to for b in nm.brackets if b.up_to is not None),
    ]
    assert all(type(v) is Decimal for v in values)
    assert nm.national_insurance.low_rate == Decimal("0.0104")
    assert nm.brackets[0].rate == Decimal("0.1")


def test_official_and_added_rules_present(rules: Rules) -> None:
    nm = rules.net_method
    assert nm.contributions_base == "gross"
    assert nm.pension_credit.max_contribution_rate == Decimal("0.07")
    assert nm.participation.treatment == "net_deduction"
    assert nm.participation.reduces_value_of_use is False
    assert (nm.rounding.during, nm.rounding.display) == ("none", "shekel")
    assert not hasattr(rules.electric, "rounding")  # superseded by net_method.rounding
    assert rules.family_track.cars == ("CAR-19", "CAR-20")
    assert rules.family_track.price_source == "catalogue"
    assert not hasattr(rules.family_track, "car_price")  # cost is per car, from the catalog
    assert rules.waiver.maintenance_is_pensionable is False
    # Our additions (not in the official file):
    assert rules.electric.gross_amount == Decimal(250)
    assert rules.value_of_use.tax_year == 2026


def test_rules_are_immutable(rules: Rules) -> None:
    with pytest.raises(ValidationError):
        rules.version = "x"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        rules.net_method.brackets[0].rate = Decimal("0.2")  # type: ignore[misc]
    with pytest.raises(TypeError):
        rules.budgets["א"] = Decimal(1)  # type: ignore[index]


@pytest.mark.skipif(not RAW_RULES_JSON.is_file(), reason="raw/ files not present")
def test_every_original_value_is_kept(rules: Rules) -> None:
    src = json.loads(RAW_RULES_JSON.read_text(encoding="utf-8"))
    nm, src_nm = rules.net_method, src["netMethod"]

    assert rules.version == src["version"]
    assert rules.note == src["note"]
    assert dict(rules.budgets) == {k: Decimal(v) for k, v in src["budgets"].items()}
    assert list(rules.group_order) == src["groupOrder"]
    assert rules.choose_from == src["chooseFrom"]

    assert rules.electric.net_bonus == src["electric"]["netBonus"]
    assert rules.electric.method == src["electric"]["method"]
    assert rules.electric.note == src["electric"]["note"]

    ft = src["familyTrack"]
    assert rules.family_track.min_children == ft["minChildren"]
    assert rules.family_track.child_max_age == ft["childMaxAge"]
    assert list(rules.family_track.cars) == ft["cars"]
    assert rules.family_track.price_source == ft["priceSource"]
    assert rules.family_track.gap_split_employee == Decimal(str(ft["gapSplitEmployee"]))
    assert rules.family_track.note == ft["note"]

    assert rules.waiver.allowed_by == src["waiver"]["allowedBy"]
    assert rules.waiver.maintenance_is_taxable == src["waiver"]["maintenanceIsTaxable"]
    assert rules.waiver.maintenance_is_pensionable == src["waiver"]["maintenanceIsPensionable"]
    assert rules.unused_budget == src["unusedBudget"]

    assert nm.basis == src_nm["basis"]
    assert nm.tax_year == src_nm["taxYear"]
    assert nm.credit_point_value == src_nm["creditPointValue"]
    assert [(b.up_to, b.rate) for b in nm.brackets] == [
        (None if up_to is None else Decimal(up_to), Decimal(str(rate)))
        for up_to, rate in src_nm["brackets"]
    ]
    for ours, theirs in (
        (nm.national_insurance, src_nm["nationalInsurance"]),
        (nm.health, src_nm["health"]),
    ):
        assert ours.threshold == theirs["threshold"]
        assert ours.ceiling == theirs["ceiling"]
        assert ours.low_rate == Decimal(str(theirs["lowRate"]))
        assert ours.high_rate == Decimal(str(theirs["highRate"]))
    pc = src_nm["pensionCredit"]
    assert nm.pension_credit.rate == Decimal(str(pc["rate"]))
    assert nm.pension_credit.max_contribution_rate == Decimal(str(pc["maxContributionRate"]))
    assert nm.pension_credit.income_ceiling == pc["incomeCeiling"]
    assert nm.pension_credit.note == pc["note"]
    assert nm.contributions_base == src_nm["contributionsBase"]
    assert nm.contributions_note == src_nm["contributionsNote"]
    part = src_nm["participation"]
    assert nm.participation.treatment == part["treatment"]
    assert nm.participation.reduces_value_of_use == part["reducesValueOfUse"]
    assert nm.participation.note == part["note"]
    rnd = src_nm["rounding"]
    assert nm.rounding.during == rnd["during"]
    assert nm.rounding.display == rnd["display"]
    assert nm.rounding.note == rnd["note"]
    assert nm.note == src_nm["note"]

    vou = src["valueOfUse"]
    assert rules.value_of_use.source == vou["source"]
    assert list(rules.value_of_use.key) == vou["key"]
    assert {str(k): v for k, v in rules.value_of_use.drive_field.items()} == vou["driveField"]


# --- electric method ------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["gross_up", "gross"])
def test_electric_method_accepts_both_options(tmp_path: Path, method: str) -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["electric"]["method"] = method

    assert load_rules(write_broken(tmp_path, mutate)).electric.method == method


def test_electric_method_rejects_unknown(tmp_path: Path) -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["electric"]["method"] = "bonus"

    with pytest.raises(RulesError, match=r"electric\.method: .*'gross_up' or 'gross'.*'bonus'"):
        load_rules(write_broken(tmp_path, mutate))


# --- each validator rejects a deliberately broken copy --------------------------------------


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """Mutator that sets a dotted path; integer segments index lists ("a.brackets.2.rate")."""

    def mutate(data: dict[str, Any]) -> None:
        *parents, leaf = path.split(".")
        node: Any = data
        for part in parents:
            node = node[int(part)] if part.isdigit() else node[part]
        node[int(leaf) if leaf.isdigit() else leaf] = value

    return mutate


BROKEN_CASES: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    (
        "brackets not ascending",
        _set("net_method.brackets.2.up_to", 9000),
        r"net_method: brackets\[2\]: up_to must be strictly ascending \(9000 is not above 10060\)",
    ),
    (
        "last bracket closed",
        _set("net_method.brackets.6.up_to", 99999),
        r"net_method: brackets: the last bracket must be open-ended",
    ),
    (
        "open bracket in the middle",
        _set("net_method.brackets.1.up_to", None),
        r"net_method: brackets\[1\]: only the last bracket may have up_to: null",
    ),
    (
        "bracket rate above 1",
        _set("net_method.brackets.2.rate", "1.4"),
        r"net_method\.brackets\[2\]\.rate: must be between 0 and 1 \(got 1\.4\)",
    ),
    (
        "negative NI rate",
        _set("net_method.national_insurance.low_rate", "-0.01"),
        r"net_method\.national_insurance\.low_rate: must be between 0 and 1 \(got -0\.01\)",
    ),
    (
        "pension credit rate above 1",
        _set("net_method.pension_credit.rate", 35),
        r"net_method\.pension_credit\.rate: must be between 0 and 1 \(got 35\)",
    ),
    (
        "family split above 1",
        _set("family_track.gap_split_employee", "1.5"),
        r"family_track\.gap_split_employee: must be between 0 and 1",
    ),
    (
        "group_order missing a budget group",
        _set("group_order", ["א", "ב", "ג"]),
        r"group_order \['א', 'ב', 'ג'\] must list exactly the budget groups",
    ),
    (
        "group_order has unknown group",
        _set("group_order", ["א", "ב", "ג", "ד", "ה"]),
        r"must list exactly the budget groups",
    ),
    (
        "group_order duplicate",
        _set("group_order", ["א", "ב", "ג", "ד", "ד"]),
        r"group_order: duplicate groups",
    ),
    (
        "NI threshold above ceiling",
        _set("net_method.national_insurance.threshold", 60000),
        r"net_method\.national_insurance: threshold \(60000\) must be lower than ceiling \(50695\)",
    ),
    (
        "health threshold equals ceiling",
        _set("net_method.health.threshold", 50695),
        r"net_method\.health: threshold \(50695\) must be lower than ceiling",
    ),
    (
        "non-numeric budget",
        _set("budgets.ב", "a lot"),
        r"budgets\.ב: expected a number, got 'a lot'",
    ),
    (
        "negative budget",
        _set("budgets.ב", -1),
        r"budgets\.ב: must be a non-negative amount",
    ),
    (
        "misspelled key",
        _set("net_method.credit_point_valu", 242),
        r"net_method\.credit_point_valu: Extra inputs are not permitted",
    ),
    (
        "unsupported contributions base",
        _set("net_method.contributions_base", "base_only"),
        r"net_method\.contributions_base: Input should be 'gross' \(got 'base_only'\)",
    ),
    (
        "unsupported participation treatment",
        _set("net_method.participation.treatment", "gross_deduction"),
        r"net_method\.participation\.treatment: Input should be 'net_deduction'",
    ),
    (
        "participation reducing value of use",
        _set("net_method.participation.reduces_value_of_use", True),
        r"net_method\.participation\.reduces_value_of_use: Input should be False",
    ),
    (
        "rounding during calculation",
        _set("net_method.rounding.during", "shekel"),
        r"net_method\.rounding\.during: Input should be 'none' \(got 'shekel'\)",
    ),
    (
        "unsupported display rounding",
        _set("net_method.rounding.display", "agora"),
        r"net_method\.rounding\.display: Input should be 'shekel'",
    ),
    (
        "old electric rounding key",
        _set("electric.rounding", "ceil"),
        r"electric\.rounding: Extra inputs are not permitted",
    ),
    (
        "unsupported family price source",
        _set("family_track.price_source", "fixed"),
        r"family_track\.price_source: Input should be 'catalogue'",
    ),
    (
        "duplicate family car",
        _set("family_track.cars", ["CAR-19", "CAR-19"]),
        r"family_track: cars: duplicate entries",
    ),
    (
        "no family cars",
        _set("family_track.cars", []),
        r"family_track: cars: must list at least one",
    ),
]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [pytest.param(m, msg, id=name) for name, m, msg in BROKEN_CASES],
)
def test_broken_copy_is_rejected_with_named_field(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    path = write_broken(tmp_path, mutate)
    with pytest.raises(RulesError, match=message) as exc_info:
        load_rules(path)
    assert str(exc_info.value).startswith(f"Invalid rules file {path}:")


def test_missing_section_is_reported(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match=r"  - health: Field required|net_method\.health: Field"):
        load_rules(write_broken(tmp_path, lambda d: d["net_method"].pop("health")))


def test_invalid_yaml_and_missing_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("budgets: [unclosed\n", encoding="utf-8")
    with pytest.raises(RulesError, match="not valid YAML"):
        load_rules(bad)
    with pytest.raises(RulesError, match="Cannot read rules file"):
        load_rules(tmp_path / "missing.yaml")

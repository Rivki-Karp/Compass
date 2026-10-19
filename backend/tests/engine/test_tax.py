"""Hand-computed checks of the 2025 monthly tables in data/rules.yaml."""

from decimal import Decimal as D

import pytest

from compass.engine.tax import (
    credit_points_value,
    health,
    income_tax_before_credits,
    national_insurance,
    pension_credit,
)
from compass.rules import NetMethodRules, load_rules


@pytest.fixture(scope="module")
def nm() -> NetMethodRules:
    return load_rules().net_method


# Cumulative tax at each bracket edge:
#   7,010 * 0.10                    =    701
#   + (10,060 - 7,010) * 0.14 = 427 =  1,128
#   + (16,150 - 10,060) * 0.20 = 1,218 = 2,346
#   + (22,440 - 16,150) * 0.31 = 1,949.9 = 4,295.9
#   + (46,690 - 22,440) * 0.35 = 8,487.5 = 12,783.4
#   + (60,130 - 46,690) * 0.47 = 6,316.8 = 19,100.2
@pytest.mark.parametrize(
    ("income", "expected"),
    [
        (D(0), D(0)),
        (D(5000), D("500")),
        (D(7010), D("701")),
        (D("7010.01"), D("701.0014")),
        (D(10060), D("1128")),
        (D(22440), D("4295.9")),
        (D("22440.5"), D("4296.075")),
        (D(18500), D("3074.5")),  # E-001 cash only: 2,346 + 2,350 * 0.31
        (D(46690), D("12783.4")),
        (D(60130), D("19100.2")),
        (D(70130), D("24100.2")),  # open bracket: + 10,000 * 0.50
    ],
)
def test_income_tax_before_credits(nm: NetMethodRules, income: D, expected: D) -> None:
    assert income_tax_before_credits(income, nm.brackets) == expected


@pytest.mark.parametrize(
    ("income", "ni", "hl"),
    [
        (D(0), D(0), D(0)),
        (D(5000), D("52"), D("161.5")),
        # exactly at the threshold: low rate only
        (D(7522), D("78.2288"), D("242.9606")),
        # 1 ILS above the threshold: + high rate on 1 ILS
        (D(7523), D("78.2988"), D("243.0123")),
        # exactly at the ceiling: 78.2288 + 43,173 * 0.07 / 242.9606 + 43,173 * 0.0517
        (D(50695), D("3100.3388"), D("2475.0047")),
        # above the ceiling: capped
        (D(80000), D("3100.3388"), D("2475.0047")),
    ],
)
def test_national_insurance_and_health(nm: NetMethodRules, income: D, ni: D, hl: D) -> None:
    assert national_insurance(income, nm) == ni
    assert health(income, nm) == hl


@pytest.mark.parametrize(
    ("cash", "expected"),
    [
        (D(0), D(0)),
        (D(5000), D("122.5")),  # 0.35 * 0.07 * 5,000
        (D(9500), D("232.75")),  # the official example: up to 232.75 ILS / month
        (D(18500), D("232.75")),  # capped at the income ceiling
    ],
)
def test_pension_credit(nm: NetMethodRules, cash: D, expected: D) -> None:
    assert pension_credit(cash, nm) == expected


def test_credit_points_value(nm: NetMethodRules) -> None:
    assert credit_points_value(D("2.75"), nm) == D("665.5")
    assert credit_points_value(D("2.25"), nm) == D("544.5")


def test_results_are_exact_decimals(nm: NetMethodRules) -> None:
    value = income_tax_before_credits(D("12345.6789"), nm.brackets)
    assert type(value) is D
    assert value == D(1128) + (D("12345.6789") - D(10060)) * D("0.2")

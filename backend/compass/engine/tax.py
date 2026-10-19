"""Income tax, National Insurance, health and the pension credit. Pure, exact, monthly.

Every rate, bracket and ceiling comes from rules.net_method; nothing is hardcoded here.
"""

from decimal import Decimal

from compass.engine.decimal_math import ZERO, exact
from compass.rules import NetMethodRules, SocialInsuranceRules, TaxBracket


def income_tax_before_credits(taxable_income: Decimal, brackets: tuple[TaxBracket, ...]) -> Decimal:
    """Progressive tax: each rate applies to the slice up to its `up_to`; the last is open."""
    with exact():
        tax = ZERO
        lower = ZERO
        for bracket in brackets:
            upper = bracket.up_to
            if upper is None or taxable_income <= upper:
                return tax + max(ZERO, taxable_income - lower) * bracket.rate
            tax += (upper - lower) * bracket.rate
            lower = upper
    raise ValueError("brackets must end with an open bracket")  # pragma: no cover - schema rule


def _two_tier(income: Decimal, rules: SocialInsuranceRules) -> Decimal:
    with exact():
        low = min(income, rules.threshold)
        high = max(ZERO, min(income, rules.ceiling) - rules.threshold)
        return rules.low_rate * low + rules.high_rate * high


def national_insurance(taxable_income: Decimal, net_method: NetMethodRules) -> Decimal:
    return _two_tier(taxable_income, net_method.national_insurance)


def health(taxable_income: Decimal, net_method: NetMethodRules) -> Decimal:
    return _two_tier(taxable_income, net_method.health)


def pension_credit(cash_income: Decimal, net_method: NetMethodRules) -> Decimal:
    """rate * max_contribution_rate * min(cash income, income_ceiling).

    Independent of the employee's actual pension rate (official rule: the credit is capped at the
    max contribution rate, and in every example the employee contributes at least 6%).
    """
    pc = net_method.pension_credit
    with exact():
        return pc.rate * pc.max_contribution_rate * min(cash_income, pc.income_ceiling)


def credit_points_value(credit_points: Decimal, net_method: NetMethodRules) -> Decimal:
    with exact():
        return credit_points * net_method.credit_point_value

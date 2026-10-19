"""Exact Decimal arithmetic for the engine, and the one place values are rounded for display.

Inside `exact()` every Decimal operation must be exact: precision is far above anything the engine
produces and `Inexact` is trapped, so an operation that would have to round raises instead of
silently losing a digit. This is what makes "delta lines sum to diff exactly" a guarantee
(rules.net_method.rounding.during = none).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import (
    ROUND_FLOOR,
    ROUND_HALF_UP,
    Context,
    Decimal,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    localcontext,
)

from compass.rules import Rules

_EXACT = Context(prec=100, traps=[Inexact, InvalidOperation, DivisionByZero, Overflow])
_DISPLAY = Context(prec=100, traps=[InvalidOperation, DivisionByZero, Overflow])

ZERO = Decimal(0)
ONE = Decimal(1)


@contextmanager
def exact() -> Iterator[None]:
    with localcontext(_EXACT):
        yield


def to_display(value: Decimal, rules: Rules) -> int:
    """Round for display per rules.net_method.rounding.display (shekel = whole ILS, half-up)."""
    if rules.net_method.rounding.display != "shekel":  # pragma: no cover - schema allows only this
        raise ValueError(f"unsupported display rounding {rules.net_method.rounding.display!r}")
    with localcontext(_DISPLAY):
        return int(value.quantize(ONE, rounding=ROUND_HALF_UP))


def to_agora(value: Decimal) -> Decimal:
    with localcontext(_DISPLAY):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apportion(amounts: list[Decimal], total: int) -> list[int]:
    """Round `amounts` to integers that sum to `total` exactly (largest-remainder method).

    Each amount becomes its floor or its ceiling: floors first, then the remaining units go to
    the largest fractional parts (ties: earlier item first). So whole amounts, zeros included,
    never change. Requires |total - sum(amounts)| < 1, which always holds when `total` is a
    difference of two half-up roundings or the rounding of the sum.
    """
    with localcontext(_DISPLAY):
        floors = [int(a.to_integral_value(rounding=ROUND_FLOOR)) for a in amounts]
        remainders = [a - f for a, f in zip(amounts, floors, strict=True)]
    units = total - sum(floors)
    fractional = [i for i, r in enumerate(remainders) if r > 0]
    if not 0 <= units <= len(fractional):
        raise ValueError(f"cannot apportion {amounts} to {total}: off by more than 1 in total")
    for index in sorted(fractional, key=lambda i: -remainders[i])[:units]:
        floors[index] += 1
    return floors

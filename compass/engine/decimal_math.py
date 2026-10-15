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


def floor_int(value: Decimal) -> int:
    with localcontext(_DISPLAY):
        return int(value.to_integral_value(rounding=ROUND_FLOOR))

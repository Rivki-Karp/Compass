"""JSON-safe view of engine results: the only way results should leave the engine.

Exact values become strings (fixed-point, every digit kept), display values become ints (whole
ILS, already rounded by the engine). Callers never need Decimal arithmetic outside the engine,
and the output does not depend on the caller's decimal context.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from compass.engine.decimal_math import to_display
from compass.engine.models import Comparison, Eligibility, EngineWarning, NetBreakdown, Option
from compass.rules import Rules

# NetBreakdown fields that are formula lines (amounts in ILS).
BREAKDOWN_LINES: tuple[str, ...] = tuple(
    name
    for name in NetBreakdown.model_fields
    if name not in ("scenario", "car_id", "vehicle_key", "metadata")
)

ApiResult = Comparison | NetBreakdown | Eligibility | Option | Sequence[Option]


def _plain(value: Any) -> Any:
    """Exact JSON-safe copy: Decimal -> fixed-point string; mappings/sequences recursively."""
    if isinstance(value, Decimal):
        return format(value, "f")  # never exponent notation, never rounded
    if isinstance(value, BaseModel):
        return _plain(value.model_dump())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, str | int | bool):  # no floats, ever
        return value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _shown(value: Decimal | None, rules: Rules) -> int | None:
    return None if value is None else to_display(value, rules)


def _breakdown(breakdown: NetBreakdown, rules: Rules) -> dict[str, Any]:
    lines = {name: getattr(breakdown, name) for name in BREAKDOWN_LINES}
    return {
        "scenario": _plain(breakdown.scenario),
        "car_id": breakdown.car_id,
        "vehicle_key": breakdown.vehicle_key,
        "exact": {name: _plain(value) for name, value in lines.items()},
        "display": {name: _shown(value, rules) for name, value in lines.items()},
        "metadata": _plain(breakdown.metadata),
    }


def _warnings(warnings: tuple[EngineWarning, ...]) -> list[dict[str, Any]]:
    return [{"code": w.code, "facts": _plain(w.facts)} for w in warnings]


def _comparison(result: Comparison, rules: Rules) -> dict[str, Any]:
    return {
        "today": _breakdown(result.today, rules),
        "alternative": _breakdown(result.alternative, rules),
        "diff": _plain(result.diff),
        "display_diff": result.display_diff,
        "delta_lines": [
            {"line": line.line, "net_effect": _plain(line.net_effect)}
            for line in result.delta_lines
        ],
        "display_delta_lines": [
            {"line": line.line, "net_effect": line.net_effect}
            for line in result.display_delta_lines
        ],
        "explanation_facts": _plain(result.explanation_facts),
        "warnings": _warnings(result.warnings),
        "missing": list(result.missing),
        "partial": result.partial,
    }


def _eligibility(result: Eligibility) -> dict[str, Any]:
    return {
        "status": result.status,
        "reason": result.reason,
        "facts": _plain(result.facts),
        "warnings": _warnings(result.warnings),
    }


def to_api_dict(result: ApiResult, rules: Rules) -> Any:
    """Convert an engine result (or a list of options) to plain JSON-safe values."""
    if isinstance(result, Comparison):
        return _comparison(result, rules)
    if isinstance(result, NetBreakdown):
        return _breakdown(result, rules)
    if isinstance(result, Eligibility):
        return _eligibility(result)
    if isinstance(result, Option):
        return {
            "scenario": _plain(result.scenario),
            "eligibility": _eligibility(result.eligibility),
            "comparison": _comparison(result.comparison, rules),
        }
    if isinstance(result, Sequence) and not isinstance(result, str):
        return [to_api_dict(option, rules) for option in result]
    raise TypeError(f"cannot serialize {type(result).__name__}")

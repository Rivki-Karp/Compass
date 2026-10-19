"""TypeScript types for the web UI, generated from the Pydantic models (one source of truth).

    uv run python tasks.py ts-types      # writes web/src/api/generated.ts

The view models (compass/tools/view.py) and the event type names (compass/state/store.py) are
emitted; the event envelope and the payloads that are not models are hand-written next to it in
web/src/api/types.ts. tests/api/test_ts_types.py fails when the committed file is stale.
"""

import sys
from typing import Any

from pydantic.json_schema import models_json_schema

from compass.config import REPO_ROOT
from compass.state.store import EVENT_TYPES
from compass.tools.view import ComparisonView, TicketView

TS_FILE = REPO_ROOT / "web" / "src" / "api" / "generated.ts"
MODELS = (ComparisonView, TicketView)


def _ref(schema: dict[str, Any]) -> str:
    return str(schema["$ref"]).rsplit("/", 1)[-1]


def _ts(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return _ref(schema)
    if "const" in schema:
        return _literal(schema["const"])
    if "enum" in schema:
        return " | ".join(_literal(v) for v in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(dict.fromkeys(_ts(s) for s in schema["anyOf"]))
    kind = schema.get("type")
    if kind == "array":
        item = _ts(schema.get("items", {}))
        return f"({item})[]" if " | " in item else f"{item}[]"
    if kind == "object":
        values = schema.get("additionalProperties")
        return f"Record<string, {_ts(values) if isinstance(values, dict) else 'unknown'}>"
    simple = {"string": "string", "integer": "number", "number": "number", "boolean": "boolean"}
    if kind == "null":
        return "null"
    if kind in simple:
        return simple[kind]
    return "unknown"


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if value is None:
        return "null"
    return str(value).lower() if isinstance(value, bool) else str(value)


def _interface(name: str, schema: dict[str, Any]) -> str:
    lines = [f"export interface {name} {{"]
    for prop, sub in schema.get("properties", {}).items():
        # The views always serialize every field (model_dump), so every field is present.
        lines.append(f"  {prop}: {_ts(sub)};")
    lines.append("}")
    return "\n".join(lines)


def render() -> str:
    _, schema = models_json_schema(
        [(m, "serialization") for m in MODELS], ref_template="#/$defs/{model}"
    )
    defs: dict[str, Any] = schema["$defs"]
    out = [
        "// Generated from the Pydantic models by `uv run python tasks.py ts-types`. Do not edit.",
        "// Source: compass/tools/view.py (views), compass/state/store.py (event types).",
        "",
        "export const EVENT_TYPES = [",
        *(f'  "{name}",' for name in sorted(EVENT_TYPES)),
        "] as const;",
        "export type EventType = (typeof EVENT_TYPES)[number];",
    ]
    for name in sorted(defs):
        out += ["", _interface(name, defs[name])]
    return "\n".join(out) + "\n"


def main() -> int:
    TS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TS_FILE.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {TS_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

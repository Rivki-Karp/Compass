"""Write the OpenAPI schema to openapi.json (committed, for frontend type generation).

uv run python tasks.py openapi
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from compass.api.app import create_app
from compass.api.settings import Settings
from compass.config import BACKEND_ROOT

OPENAPI_JSON: Path = BACKEND_ROOT / "openapi.json"


def schema() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:  # don't touch the real session store
        return create_app(Settings(app_db=Path(tmp) / "app.db")).openapi()


def render() -> str:
    return json.dumps(schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    OPENAPI_JSON.write_bytes(render().encode("utf-8"))
    print(f"wrote {OPENAPI_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

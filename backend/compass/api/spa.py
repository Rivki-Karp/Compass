"""Serve the built web UI (frontend/dist) from the API: one URL for the demo and for Docker.

Registered after every API route, as the last GET route, so it never shadows one: /api/*,
/docs and /openapi.json match first. An unknown /api path stays the API's JSON 404, never the
UI. Any other path is a file from the build if there is one, else index.html (the UI's own
routes: /, /rep, ...).
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

INDEX_HEADERS = {"Cache-Control": "no-cache"}  # always the current build
ASSET_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}  # hashed names


def mount_spa(app: FastAPI, dist: Path) -> None:
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def web_ui(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        if path:
            file = (root / path).resolve()
            if file.is_file() and file.is_relative_to(root) and file != index:
                hashed = file.parent == root / "assets"
                return FileResponse(file, headers=ASSET_HEADERS if hashed else None)
        return FileResponse(index, headers=INDEX_HEADERS)

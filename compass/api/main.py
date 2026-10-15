"""ASGI entry point for uvicorn: settings come from the environment (COMPASS_*)."""

from compass.api.app import create_app

app = create_app()

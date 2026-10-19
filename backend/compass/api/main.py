"""ASGI entry point for uvicorn: settings come from the environment (COMPASS_*).

A live server (COMPASS_LLM=anthropic) refuses to start with an empty, demo or placeholder rep or
admin token: the screens they guard would be unusable, or open to anyone who read the docs.
"""

from compass.api.app import create_app
from compass.api.settings import Settings, live_token_errors, live_token_message

settings = Settings.from_env()
if errors := live_token_errors(settings):
    raise SystemExit(live_token_message(errors))
app = create_app(settings)

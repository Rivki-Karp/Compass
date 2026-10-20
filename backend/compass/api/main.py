"""ASGI entry point for uvicorn: settings come from the environment (COMPASS_*).

A live server (COMPASS_LLM=anthropic) refuses to start with an empty, demo or placeholder rep or
admin token: the screens they guard would be unusable, or open to anyone who read the docs. With
COMPASS_AUTH=1 it also refuses without an admin seed user or with a hash that is not argon2id.
With the payslip upload on (COMPASS_PAYSLIP=1) it also refuses without GEMINI_API_KEY, or with a
model that has no price entry.
"""

from compass.api.app import create_app
from compass.api.settings import (
    Settings,
    live_auth_errors,
    live_auth_message,
    live_payslip_errors,
    live_payslip_message,
    live_token_errors,
    live_token_message,
)

settings = Settings.from_env()
if errors := live_token_errors(settings):
    raise SystemExit(live_token_message(errors))
if errors := live_payslip_errors(settings):
    raise SystemExit(live_payslip_message(errors))
if errors := live_auth_errors(settings):
    raise SystemExit(live_auth_message(errors))
app = create_app(settings)

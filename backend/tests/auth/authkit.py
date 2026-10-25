"""Constants shared by the accounts tests (a module of its own: `conftest` is not importable by
name when tests/api and tests/auth run in one session)."""

import sys
from pathlib import Path

# the helpers of tests/api (live server, SSE reader) and tests/payslip (synthetic files)
for _helpers in ("api", "payslip"):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / _helpers))

PASSWORD = "correct horse battery"
STATIC_REP, STATIC_ADMIN = "rep-static-token", "admin-static-token"
# role -> the seeded account's email; every one logs in with PASSWORD
EMAILS = {
    "employee": "dana@example.com",
    "other": "avi@example.com",
    "rep": "rep@example.com",
    "admin": "admin@example.com",
}

# The shared demo accounts (COMPASS_DEMO_LOGIN): an admin whose password is the one judges are
# given, and an employee and a rep whose password is nothing an admin password could be
DEMO_EMAILS = {
    "employee": "demo-employee@example.com",
    "rep": "demo-rep@example.com",
    "admin": "demo-admin@example.com",
}
DEMO_ADMIN_PASSWORD = "demo admin password"
DEMO_USER_PASSWORD = "demo user password"

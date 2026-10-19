"""Shared test constants: the tokens the test settings configure, as request headers."""

REP_TOKEN = "rep-test-token"
ADMIN_TOKEN = "admin-test-token"
REP = {"Authorization": f"Bearer {REP_TOKEN}"}
ADMIN = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

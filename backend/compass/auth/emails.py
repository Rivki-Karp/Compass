"""One spelling of an email: trimmed, NFKC, lower-case. The key of every account lookup."""

import unicodedata


def normalize_email(email: str) -> str:
    return unicodedata.normalize("NFKC", email).strip().lower()

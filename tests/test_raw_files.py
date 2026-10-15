"""The committed raw files are byte-identical to the versions recorded in raw/README.md."""

import hashlib
import re

import pytest

from compass.config import RAW_DIR

ROW = re.compile(r"^\| `(?P<name>[^`]+)` \|.*\| `(?P<sha>[0-9a-f]{64})` \|$")


def _recorded() -> dict[str, str]:
    rows = {}
    for line in (RAW_DIR / "README.md").read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            rows[match["name"]] = match["sha"]
    return rows


RECORDED = _recorded()


def test_every_raw_file_is_recorded() -> None:
    present = {p.name for p in RAW_DIR.iterdir() if p.is_file() and p.name != "README.md"}
    assert present == set(RECORDED) == {
        "strauss-rules.json",
        "value_of_use_2026.csv",
        "strauss_challenge_data.xlsx",
        "challenge_brief.pdf",
    }


@pytest.mark.parametrize("name", sorted(RECORDED))
def test_raw_file_sha256(name: str) -> None:
    digest = hashlib.sha256((RAW_DIR / name).read_bytes()).hexdigest()
    assert digest == RECORDED[name], f"{name} changed (line endings normalised?)"

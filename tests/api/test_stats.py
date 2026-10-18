"""Judges mode's stats tiles: read from the committed files, admin only, never hard-coded."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import ADMIN

from compass.api.stats import REPORT, SPEND, TEST_COUNTS, judges_stats
from compass.config import REPO_ROOT


def test_reads_the_committed_files() -> None:
    stats = judges_stats()
    report = REPORT.read_text(encoding="utf-8")
    evals = stats["evals"]
    assert evals is not None
    line = (
        f"Scenarios passing (every repeat): {evals['scenarios_passed']}/{evals['scenarios_total']}"
    )
    assert line in report
    assert f"scenario runs passing: {evals['runs_passed']}/{evals['runs_total']}" in report
    assert f"model `{evals['model']}`" in report and f"effort `{evals['effort']}`" in report

    costs = [json.loads(x)["cost_usd"] for x in SPEND.read_text(encoding="utf-8").splitlines() if x]
    spend = stats["spend"]
    assert spend["calls"] == len(costs)
    total = sum((Decimal(str(c)) for c in costs), Decimal(0))
    assert Decimal(spend["total_usd"]) == total.quantize(Decimal("0.01"))
    assert f"of the ${spend['cap_usd']} cap" in report

    per_run = stats["cost_per_conversation"]
    assert per_run["runs"] == evals["runs_total"]
    assert Decimal(per_run["usd"]) > 0

    counts = json.loads(TEST_COUNTS.read_text(encoding="utf-8"))
    assert stats["tests"] == counts


def test_a_missing_or_broken_file_only_blanks_its_own_tile(tmp_path: Path) -> None:
    broken = tmp_path / "spend.jsonl"
    broken.write_text("not json\n", encoding="utf-8")
    stats = judges_stats(report=tmp_path / "none.md", spend=broken, test_counts=TEST_COUNTS)
    assert stats["evals"] is None and stats["cost_per_conversation"] is None
    assert stats["spend"] is None
    assert stats["tests"] is not None


def test_cost_per_conversation_is_the_run_cost_over_its_runs(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        "- Run: 2026-10-15 14:02 UTC · model `m` · effort `low` · repeat 3\n"
        "- **Scenarios passing (every repeat): 14/15** · scenario runs passing: 44/45\n"
        "- Cost of this run: $1.1358 · total spend $2.0932 of the $30.00 cap\n",
        encoding="utf-8",
    )
    stats = judges_stats(report=report, spend=SPEND, test_counts=TEST_COUNTS)
    assert stats["cost_per_conversation"]["usd"] == "0.0252"  # 1.1358 / 45
    assert stats["evals"]["scenarios_passed"] == 14 and stats["evals"]["runs_passed"] == 44
    assert stats["spend"]["cap_usd"] == "30.00"


def test_the_endpoint_is_admin_only(client: TestClient) -> None:
    assert client.get("/api/admin/stats").status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.get("/api/admin/stats", headers=bad).status_code == 401
    response = client.get("/api/admin/stats", headers=ADMIN)
    assert response.status_code == 200
    assert response.json() == judges_stats()


def test_committed_test_counts_are_current(request: pytest.FixtureRequest) -> None:
    """tests/counts.json is what judges mode shows; a full run checks its pytest number (run
    `uv run python tasks.py test-counts` after adding tests). A partial run can't tell."""
    session = request.session
    collected = {Path(str(item.path)).resolve() for item in session.items}
    every_file = {p.resolve() for p in (REPO_ROOT / "tests").rglob("test_*.py")}
    filtered = request.config.option.keyword or request.config.option.markexpr
    if filtered or not every_file <= collected:
        pytest.skip("not a full run")
    counts = json.loads(TEST_COUNTS.read_text(encoding="utf-8"))
    assert counts["pytest"] == len(session.items), "run: uv run python tasks.py test-counts"

"""Judges mode's four stats tiles, read from committed files (never hard-coded in the UI):

- evals: pass rate, model and effort from the header of evals/report.md (the last full run)
- spend: the total of evals/spend.jsonl (every eval call ever made), the cap from the report
- tests: the committed counts in tests/counts.json (`uv run python tasks.py test-counts`)
- cost per conversation: the report's run cost over its scenario runs

Each part is None when its file is missing or doesn't parse, so one bad file never hides the rest.
"""

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from compass.config import REPO_ROOT

REPORT = REPO_ROOT / "evals" / "report.md"
SPEND = REPO_ROOT / "evals" / "spend.jsonl"
TEST_COUNTS = REPO_ROOT / "tests" / "counts.json"

_RUN = re.compile(
    r"Run: (?P<at>[^·\n]+?) · model `(?P<model>[^`]+)` · effort `(?P<effort>[^`]+)`"
    r" · repeat (?P<repeat>\d+)"
)
_PASSING = re.compile(
    r"Scenarios passing \(every repeat\): (?P<passed>\d+)/(?P<total>\d+)\*\*"
    r" · scenario runs passing: (?P<runs_passed>\d+)/(?P<runs>\d+)"
)
_COST = re.compile(
    r"Cost of this run: \$(?P<run>[\d.]+) · total spend \$[\d.]+ of the \$(?P<cap>[\d.]+) cap"
)


def _usd(value: Decimal, places: int = 2) -> str:
    """Dollars as a display-ready decimal string (the UI shows it as is, it never rounds)."""
    return str(value.quantize(Decimal(1).scaleb(-places)))


def _report(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    run, passing, cost = _RUN.search(text), _PASSING.search(text), _COST.search(text)
    if run is None or passing is None or cost is None:
        return None
    runs = int(passing["runs"])
    return {
        "evals": {
            "run_at": run["at"].strip(),
            "model": run["model"],
            "effort": run["effort"],
            "repeat": int(run["repeat"]),
            "scenarios_passed": int(passing["passed"]),
            "scenarios_total": int(passing["total"]),
            "runs_passed": int(passing["runs_passed"]),
            "runs_total": runs,
        },
        "cap_usd": _usd(Decimal(cost["cap"])),
        "cost_per_conversation": None
        if runs == 0
        else {
            "usd": _usd(Decimal(cost["run"]) / runs, places=4),  # cents are too coarse here
            "runs": runs,  # the average is over the last report's scenario runs
        },
    }


def _spend(path: Path) -> dict[str, Any] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        costs = [Decimal(str(json.loads(line)["cost_usd"])) for line in lines if line.strip()]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {"total_usd": _usd(sum(costs, Decimal(0))), "calls": len(costs)}


def _tests(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tests: dict[str, Any] = {
            "pytest": int(data["pytest"]),
            "vitest": int(data["vitest"]),
            "as_of": data["as_of"],
        }
        if "e2e" in data:  # Playwright (Day 5); the tile shows pytest + vitest
            tests["e2e"] = int(data["e2e"])
        return tests
    except (OSError, ValueError, KeyError, TypeError):
        return None


def judges_stats(
    report: Path = REPORT, spend: Path = SPEND, test_counts: Path = TEST_COUNTS
) -> dict[str, Any]:
    parsed = _report(report)
    ledger = _spend(spend)
    return {
        "evals": None if parsed is None else parsed["evals"],
        "spend": None
        if ledger is None
        else {**ledger, "cap_usd": None if parsed is None else parsed["cap_usd"]},
        "tests": _tests(test_counts),
        "cost_per_conversation": None if parsed is None else parsed["cost_per_conversation"],
    }

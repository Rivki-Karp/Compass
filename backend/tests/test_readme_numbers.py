"""The README's results block is generated from the committed files and must be current."""

import json
from pathlib import Path

import pytest

from compass.api.stats import REPORT, TEST_COUNTS
from compass.readme_numbers import (
    END,
    README,
    START,
    ReadmeNumbersError,
    numbers_block,
    render,
    report_summary,
)


def test_the_committed_readme_block_is_current() -> None:
    """Fails after an eval run, a test-counts update or new spend: run
    `uv run --project backend python tasks.py readme` and commit README.md."""
    readme = README.read_text(encoding="utf-8")
    assert render(readme, numbers_block()) == readme


def test_the_block_holds_the_report_table_verbatim() -> None:
    block = numbers_block()
    summary = report_summary(REPORT.read_text(encoding="utf-8"))
    assert summary in block
    assert summary.startswith("- Run:") and "| Scenario | Pass |" in summary
    counts = json.loads(TEST_COUNTS.read_text(encoding="utf-8"))
    assert f"pytest **{counts['pytest']}**" in block
    assert f"vitest **{counts['vitest']}**" in block
    assert f"Playwright **{counts['e2e']}**" in block


def test_render_replaces_only_the_block() -> None:
    text = f"# T\n\nbefore\n{START}\nold\n{END}\nafter\n"
    assert render(text, f"{START}\nnew\n{END}") == f"# T\n\nbefore\n{START}\nnew\n{END}\nafter\n"
    with pytest.raises(ReadmeNumbersError):
        render("# no markers\n", "x")


def test_missing_sources_refuse(tmp_path: Path) -> None:
    with pytest.raises(ReadmeNumbersError):
        numbers_block(report=tmp_path / "none.md")

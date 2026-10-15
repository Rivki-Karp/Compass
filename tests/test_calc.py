from collections.abc import Iterator

import pytest

from compass.calc import run
from compass.engine.context import EngineContext, build_context


@pytest.fixture(scope="module")
def ctx() -> EngineContext:
    return build_context()


def _answers(*answers: str):  # type: ignore[no-untyped-def]
    it: Iterator[str] = iter(answers)
    return lambda prompt: next(it)


WALKTHROUGH = ("ב", "מפתח/ת תוכנה", "18,500", "0", "0", "6.5", "2.5", "3", "0")


def test_walkthrough_waiver(ctx: EngineContext, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(_answers(*WALKTHROUGH, "CAR-09", "300", "waiver"), ctx) == 0
    out = capsys.readouterr().out
    assert "+2,914  הפרש בנטו" in out
    assert "11,000      13,914" in out  # today / waiver nets
    assert "current_car_above_group" in out


def test_retries_bad_answers(ctx: EngineContext, capsys: pytest.CaptureFixture[str]) -> None:
    answers = _answers(
        "ה",
        "2",
        "8",
        "abc",
        "18500",
        "0",
        "0",
        "6.5",
        "2.5",
        "3",
        "0",
        "CAR-99",
        "car-09",
        "",
        "ויתור",
    )
    assert run(answers, ctx) == 0
    out = capsys.readouterr().out
    assert "בחירה לא מוכרת" in out and "נא להזין מספר" in out and "מזהה רכב לא מוכר" in out
    assert "הפרש בנטו" in out


def test_unknown_inputs_are_reported(ctx: EngineContext, capsys: pytest.CaptureFixture[str]):
    answers = _answers("ב", "", "18500", "", "0", "", "", "3", "", "1500", "CAR-06", "")
    assert run(answers, ctx) == 1
    assert "חסרים נתונים לחישוב: commissions" in capsys.readouterr().out


def test_current_maintenance_today(ctx: EngineContext, capsys: pytest.CaptureFixture[str]):
    answers = _answers(
        "ב", "מפתח/ת תוכנה", "21000", "0", "0", "6.5", "2.5", "2.75", "0", "1500", "CAR-06", ""
    )
    assert run(answers, ctx) == 0
    assert "-1,938  הפרש בנטו" in capsys.readouterr().out  # E-003

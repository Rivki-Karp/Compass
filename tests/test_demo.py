import json

import pytest

from compass.demo import main
from compass.reference import REFERENCE_RESULTS_JSON

RESULTS = json.loads(REFERENCE_RESULTS_JSON.read_text(encoding="utf-8"))


@pytest.mark.parametrize("employee_id", sorted(RESULTS))
def test_demo_prints_the_reference_diff(employee_id: str, capsys: pytest.CaptureFixture[str]):
    assert main([employee_id]) == 0
    out = capsys.readouterr().out
    assert employee_id in out
    assert f"{RESULTS[employee_id]['net_diff']:+,}  הפרש בנטו" in out
    assert f"{RESULTS[employee_id]['net_alternative']:,}" in out


def test_demo_rejects_unknown_employee(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["E-999"]) == 2
    assert "usage" in capsys.readouterr().err

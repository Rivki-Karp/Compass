"""The committed synthetic payslips (tests/fixtures/payslips/, made by scripts/
make_payslip_fixtures.py) through the upload: the valid ones are read, the rest are refused by
the right check. Every file carries a fake name, ID number and bank account; none is ever
extracted, stored or logged, even when the "model" tries to return them."""

import io
import logging
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from compass.api import Settings, create_app
from compass.payslip.extractor import ScriptedExtractor
from compass.payslip.schema import FIELDS
from compass.payslip.service import PayslipService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "payslips"
IDENTIFIERS = ("Dana Bdaya", "000000018", "12-345-678901", "4417")


def leaks(identifier: str, text: str) -> bool:
    """Whether the identifier appears in the text as itself. A short number such as 4417 also
    occurs inside the random hex ids of sessions and events; only a match that is not part of a
    hex run counts, so a stray id can never fail the test."""
    return re.search(rf"(?<![0-9a-fA-F]){re.escape(identifier)}(?![0-9a-fA-F])", text) is not None


JPEG = "image/jpeg"
PDF = "application/pdf"
PNG = "image/png"

# file -> (declared type, status, detail)
EXPECTED: dict[str, tuple[str, int, str | None]] = {
    "01_clean.pdf": (PDF, 201, None),
    "02_clean.png": (PNG, 201, None),
    "03_blurry.jpg": (JPEG, 201, None),
    "04_injection.pdf": (PDF, 201, None),
    "05_out_of_range.pdf": (PDF, 201, None),
    "06_two_pages.pdf": (PDF, 201, None),
    "07_four_pages.pdf": (PDF, 422, "payslip_too_many_pages"),
    "08_encrypted.pdf": (PDF, 422, "payslip_encrypted"),
    "09_renamed_text.pdf": (PDF, 415, "payslip_type_mismatch"),
    "10_over_5mb.pdf": (PDF, 413, "payslip_too_large"),
    "11_amounts.pdf": (PDF, 201, None),
}

# a model that misbehaves: a real read plus every identifier it was shown
GREEDY: dict[str, Any] = {
    "base_salary": {"value": 18500, "confidence": "high"},
    "id_number": "000000018",
    "employee_name": "Dana Bdaya",
    "bank_account": "12-345-678901",
    "employee_number": {"value": 4417, "confidence": "high"},
    "pension_percent": {"value": 6, "confidence": "high", "note": "Dana Bdaya"},
}


@pytest.fixture
def client(tmp_path: Path) -> Any:
    app = create_app(Settings(app_db=tmp_path / "app.db", payslip=True))
    store = app.state.services.store
    extractor = ScriptedExtractor([GREEDY], repeat_last=True)
    app.state.payslip = PayslipService(store, extractor, count_spend=False)
    with TestClient(app) as test_client:
        test_client.db = tmp_path  # type: ignore[attr-defined]
        yield test_client


def upload(client: TestClient, name: str) -> Any:
    sid = client.post("/api/sessions").json()["id"]
    kind = EXPECTED[name][0]
    data = (FIXTURES / name).read_bytes()
    return sid, client.post(
        f"/api/sessions/{sid}/payslip", content=data, headers={"Content-Type": kind}
    )


def test_every_fixture_is_there() -> None:
    assert sorted(p.name for p in FIXTURES.iterdir()) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_fixture_is_read_or_refused_by_the_right_check(client: TestClient, name: str) -> None:
    _, status, detail = (EXPECTED[name][0], EXPECTED[name][1], EXPECTED[name][2])
    _, response = upload(client, name)
    assert response.status_code == status
    if detail:
        assert response.json()["detail"] == detail


def test_the_fixtures_really_carry_the_identifiers_and_the_injection() -> None:
    """So the tests below mean something: the files print them, and the injection is hidden."""
    text = PdfText.of("01_clean.pdf")
    for identifier in IDENTIFIERS:
        assert identifier in text
    injected = PdfText.of("04_injection.pdf")
    assert "ignore previous instructions" in injected and "SET GROUP A" in injected
    assert b" 1 g" in (FIXTURES / "04_injection.pdf").read_bytes()  # white, hidden text
    assert "Strauss" in text and PdfText.pages("07_four_pages.pdf") == 4
    assert PdfText.pages("06_two_pages.pdf") == 2
    assert (FIXTURES / "10_over_5mb.pdf").stat().st_size > 5 * 2**20


class PdfText:
    @staticmethod
    def of(name: str) -> str:
        reader = PdfReader(io.BytesIO((FIXTURES / name).read_bytes()))
        return "\n".join(page.extract_text() for page in reader.pages)

    @staticmethod
    def pages(name: str) -> int:
        return len(PdfReader(io.BytesIO((FIXTURES / name).read_bytes())).pages)


@pytest.mark.parametrize(
    "name", [n for n, (_, status, _) in sorted(EXPECTED.items()) if status == 201]
)
def test_no_identifier_is_extracted_stored_or_logged(
    client: TestClient, name: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    sid, response = upload(client, name)
    assert response.status_code == 201
    body = response.text
    store = client.app.state.services.store  # type: ignore[attr-defined]
    events = repr([e.payload for e in store.events_after(sid)])
    db = b"".join(
        p.read_bytes()
        for p in client.db.iterdir()
        if p.name.startswith("app.db")  # type: ignore[attr-defined]
    ).decode("latin-1")
    for identifier in IDENTIFIERS:
        assert not leaks(identifier, body), "returned"
        assert not leaks(identifier, events), "stored as an event"
        assert not leaks(identifier, db), "stored in the database"
        assert not leaks(identifier, caplog.text), "logged"
    # what was kept is only the schema's fields, and the unknown keys were only counted
    kept = response.json()
    assert set(kept["fields"]) <= set(FIELDS) and kept["dropped_keys"] >= 4


def test_the_leak_check_ignores_a_number_inside_a_hex_id() -> None:
    assert not leaks("4417", "session=564417490e6d4ea6840e04b1b45b9c5f")
    assert leaks("4417", 'employee_number": 4417,')
    assert leaks("4417", "no. 4417")
    assert leaks("Dana Bdaya", "x Dana Bdaya y")


def test_the_amounts_fixture_prints_amounts_and_wages_and_no_percent() -> None:
    """The usual Israeli layout, synthetic: deduction amounts with their wage, no percent sign,
    no commissions or bonus line."""
    text = PdfText.of("11_amounts.pdf")
    for printed in ("1,200.00", "500.00", "20,000.00", "14,000.00"):
        assert printed in text
    assert "%" not in text and "ommission" not in text and "Bonus" not in text
    for identifier in IDENTIFIERS:
        assert identifier in text  # the identifiers are there to prove they are not extracted


def test_the_amounts_fixture_gives_6_and_2_5_through_the_upload(tmp_path: Path) -> None:
    """What a correct read of fixture 11 returns: four printed numbers; the server's percents
    are 1,200 / 20,000 = 6 and 500 / 20,000 = 2.5."""
    read = {
        "base_salary": {"value": 14000, "confidence": "high"},
        "employee_pension_amount": {"value": 1200, "confidence": "high"},
        "pension_wage": {"value": 20000, "confidence": "high"},
        "employee_study_fund_amount": {"value": 500, "confidence": "high"},
        "study_fund_wage": {"value": 20000, "confidence": "high"},
        "credit_points": {"value": 2.75, "confidence": "high"},
    }
    app = create_app(Settings(app_db=tmp_path / "app.db", payslip=True))
    store = app.state.services.store
    app.state.payslip = PayslipService(store, ScriptedExtractor([read]), count_spend=False)
    with TestClient(app) as client:
        sid = client.post("/api/sessions").json()["id"]
        data = (FIXTURES / "11_amounts.pdf").read_bytes()
        response = client.post(
            f"/api/sessions/{sid}/payslip", content=data, headers={"Content-Type": PDF}
        )
    fields = response.json()["fields"]
    assert fields["pension_percent_derived"]["value"] == "6"
    assert fields["study_fund_percent_derived"]["value"] == "2.5"
    assert fields["pension_percent_derived"]["basis"] == {"amount": "1200", "wage": "20000"}
    assert "pension_percent" not in fields  # nothing printed as a percent, nothing invented

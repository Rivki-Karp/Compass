"""POST /api/sessions/{id}/payslip, the checks before extraction: the flag, the session, this
session's attempts, the rate limit, the daily spend cap, the type, the size, the magic bytes,
the PDF's pages and encryption. The file is read in memory only: never on disk, never logged."""

import base64
import builtins
import hashlib
import logging
import tempfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from payslip_files import SECRETS, encrypted_pdf, jpeg, pdf, png

from compass.api import Settings, create_app
from compass.payslip.upload import size_bucket

PDF = "application/pdf"


@pytest.fixture
def make_client(tmp_path: Path) -> Callable[..., TestClient]:
    def make(**overrides: Any) -> TestClient:
        values: dict[str, Any] = {"app_db": tmp_path / "app.db", "payslip": True}
        values.update(overrides)
        return TestClient(create_app(Settings(**values)))

    return make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> Iterator[TestClient]:
    with make_client() as test_client:
        yield test_client


@pytest.fixture
def sid(client: TestClient) -> str:
    return client.post("/api/sessions").json()["id"]


def upload(client: TestClient, sid: str, body: Any, content_type: str = PDF, **headers: str):
    return client.post(
        f"/api/sessions/{sid}/payslip",
        content=body,
        headers={"Content-Type": content_type, **headers},
    )


def code_of(response: Any) -> str:
    body = response.json()
    assert body["detail"] == body["errors"][0]["code"]
    message = body["errors"][0]["message"]
    assert any("֐" <= ch <= "׿" for ch in message)  # a Hebrew message for the UI
    return body["detail"]


def test_off_is_404_and_reads_nothing(make_client: Callable[..., TestClient]) -> None:
    with make_client(payslip=False) as client:
        sid = client.post("/api/sessions").json()["id"]
        response = upload(client, sid, pdf())
    assert response.status_code == 404 and response.json() == {"detail": "Not Found"}


def test_an_unknown_session_is_404(client: TestClient) -> None:
    assert upload(client, "no-such-session", pdf()).status_code == 404


@pytest.mark.parametrize(
    ("body", "content_type"),
    [(pdf(), PDF), (pdf(pages=3), PDF), (png(), "image/png"), (jpeg(), "image/jpeg")],
)
def test_a_valid_file_passes_every_check(
    client: TestClient, sid: str, body: bytes, content_type: str
) -> None:
    # live mode without a key has no extractor, so a valid file ends at "unavailable"
    response = upload(client, sid, body, content_type)
    assert response.status_code == 503 and code_of(response) == "payslip_unavailable"


def test_content_type_parameters_are_ignored(client: TestClient, sid: str) -> None:
    assert code_of(upload(client, sid, pdf(), "application/pdf; charset=binary")) == (
        "payslip_unavailable"
    )


@pytest.mark.parametrize(
    "content_type", ["text/plain", "image/gif", "", "multipart/form-data; boundary=x"]
)
def test_an_unsupported_type_is_415(client: TestClient, sid: str, content_type: str) -> None:
    response = upload(client, sid, pdf(), content_type)
    assert response.status_code == 415 and code_of(response) == "payslip_unsupported_type"


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (png(), PDF),  # a renamed image
        (b"just some text, renamed to .pdf", PDF),
        (pdf(), "image/png"),
        (b"\x89PNX....", "image/png"),
        (png(), "image/jpeg"),
    ],
)
def test_magic_bytes_must_match(
    client: TestClient, sid: str, body: bytes, content_type: str
) -> None:
    response = upload(client, sid, body, content_type)
    assert response.status_code == 415 and code_of(response) == "payslip_type_mismatch"


def test_empty_body(client: TestClient, sid: str) -> None:
    response = upload(client, sid, b"")
    assert response.status_code == 400 and code_of(response) == "payslip_empty"


def test_over_the_cap_is_413_declared_or_streamed(
    make_client: Callable[..., TestClient],
) -> None:
    with make_client(payslip_max_bytes=10_000) as client:
        sid = client.post("/api/sessions").json()["id"]
        declared = upload(client, sid, pdf(padding=20_000))
        assert declared.status_code == 413 and code_of(declared) == "payslip_too_large"

        def chunks() -> Iterator[bytes]:  # no Content-Length: the stream count stops it
            for _ in range(50):
                yield b"%PDF-" + b"A" * 995

        streamed = upload(client, sid, chunks())
        assert streamed.status_code == 413 and code_of(streamed) == "payslip_too_large"
        assert "MB" in streamed.json()["errors"][0]["message"]


def test_too_many_pages_names_the_limit_not_the_files_count(client: TestClient, sid: str) -> None:
    response = upload(client, sid, pdf(pages=4))
    assert response.status_code == 422 and code_of(response) == "payslip_too_many_pages"
    message = response.json()["errors"][0]["message"]
    assert "3" in message and "4" not in message  # the setting, never a number from the file


def test_encrypted_and_unreadable_pdfs(client: TestClient, sid: str) -> None:
    encrypted = upload(client, sid, encrypted_pdf())
    assert encrypted.status_code == 422 and code_of(encrypted) == "payslip_encrypted"
    broken = upload(client, sid, b"%PDF-1.4\n" + b"\x00garbage" * 50)
    assert broken.status_code == 422 and code_of(broken) == "payslip_unreadable"
    # the error says nothing about the parser
    assert "pypdf" not in broken.text and "Traceback" not in broken.text


def test_the_session_cap_counts_uploads_that_reached_the_extractor(
    make_client: Callable[..., TestClient],
) -> None:
    with make_client(payslip_per_session=2) as client:
        sid = client.post("/api/sessions").json()["id"]
        store = client.app.state.services.store  # type: ignore[attr-defined]
        store.append_event(sid, "payslip_failed", {"code": "payslip_unavailable"})
        assert code_of(upload(client, sid, pdf())) == "payslip_unavailable"
        store.append_event(sid, "payslip_extracted", {"fields": {}, "dropped_keys": 0})
        response = upload(client, sid, pdf())
        assert response.status_code == 429 and code_of(response) == "payslip_per_session"
        assert "2" in response.json()["errors"][0]["message"]
        # another session is not affected
        other = client.post("/api/sessions").json()["id"]
        assert code_of(upload(client, other, pdf())) == "payslip_unavailable"


def test_the_rate_limit_per_ip(client: TestClient, sid: str) -> None:
    from compass.api.payslip import UPLOADS_PER_MINUTE

    for _ in range(UPLOADS_PER_MINUTE):
        assert code_of(upload(client, sid, pdf())) == "payslip_unavailable"
    response = upload(client, sid, pdf())
    assert response.status_code == 429 and code_of(response) == "payslip_rate_limited"
    assert int(response.headers["Retry-After"]) >= 1


def test_the_daily_spend_cap_in_live_mode_not_in_demo(
    make_client: Callable[..., TestClient], tmp_path: Path
) -> None:
    today = datetime.now(UTC).date().isoformat()
    with make_client(daily_spend_cap_usd=1.0) as client:
        sid = client.post("/api/sessions").json()["id"]
        client.app.state.services.store.add_spend(today, 1.0)  # type: ignore[attr-defined]
        response = upload(client, sid, pdf())
        assert response.status_code == 503 and code_of(response) == "payslip_daily_cap"
    with make_client(llm="scripted", app_db=tmp_path / "demo.db", daily_spend_cap_usd=1.0) as demo:
        sid = demo.post("/api/sessions").json()["id"]
        demo.app.state.services.store.add_spend(today, 99.0)  # type: ignore[attr-defined]
        assert upload(demo, sid, pdf()).status_code == 201  # demo mode: no cap, read as scripted


def test_the_order_session_cap_before_type_and_size(
    make_client: Callable[..., TestClient],
) -> None:
    """The cheap checks first: a capped session is refused before its body is even judged."""
    with make_client(payslip_per_session=1) as client:
        sid = client.post("/api/sessions").json()["id"]
        store = client.app.state.services.store  # type: ignore[attr-defined]
        store.append_event(sid, "payslip_failed", {"code": "x"})
        assert code_of(upload(client, sid, b"not a pdf", "text/plain")) == "payslip_per_session"


def test_logs_carry_metadata_never_the_file(
    client: TestClient, sid: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    body = pdf(text="base salary 18500")
    upload(client, sid, body)
    upload(client, sid, encrypted_pdf())
    upload(client, sid, png(), "image/png")
    lines = [r.getMessage() for r in caplog.records if r.name == "compass.payslip"]
    assert len(lines) == 3
    assert f"session={sid} type=application/pdf size=<100KB pages=1" in lines[0]
    assert "outcome=payslip_unavailable" in lines[0] and "outcome=payslip_encrypted" in lines[1]
    everything = caplog.text
    for secret in (*SECRETS, "18500"):
        assert secret not in everything
    assert base64.b64encode(body).decode()[:40] not in everything
    assert hashlib.sha256(body).hexdigest() not in everything
    assert "%PDF" not in everything


def test_the_file_never_touches_the_disk(
    client: TestClient, sid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Over 1 MB (Starlette's spool threshold for multipart), and still nothing is written:
    no temporary file, no file opened for writing."""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a temporary file was created")

    for name in ("SpooledTemporaryFile", "TemporaryFile", "NamedTemporaryFile", "mkstemp"):
        monkeypatch.setattr(tempfile, name, refuse)
    real_open = builtins.open

    def read_only_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in "wax+"):
            raise AssertionError(f"a file was opened for writing: {file}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", read_only_open)
    response = upload(client, sid, pdf(padding=2 * 2**20))
    assert code_of(response) == "payslip_unavailable"


def test_size_buckets() -> None:
    assert size_bucket(10) == "<100KB"
    assert size_bucket(500 * 1024) == "100KB-1MB"
    assert size_bucket(3 * 2**20) == "1-5MB"
    assert size_bucket(6 * 2**20) == ">5MB"

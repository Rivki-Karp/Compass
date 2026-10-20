"""`tasks.py payslip-check` (evals/payslip_live.py), with a fake Claude client: no network, no
key. It never prints the key, never picks a model for you, sends the extraction's request shape
(no tools, a JSON schema, max_tokens 800, thinking off) and records every call's cost."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from compass.api import Settings
from compass.payslip.extractor import SYSTEM_PROMPT
from evals import payslip_live
from evals.payslip_live import EXPECTED, closest_ids, probe_pdf, probe_png, redact
from evals.report import Ledger

FAKE_KEY = "sk-ant-" + "fake-key-for-tests-" * 2  # built, never a literal
LISTED = ["claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"]
# a correct read of the synthetic payslip (its invented values)
READ = json.dumps(
    {
        "base_salary": {"value": 18500, "confidence": "high"},
        "commissions": {"value": 1200, "confidence": "high"},
        "bonus": {"value": 0, "confidence": "high"},
        "pension_percent": {"value": 6, "confidence": "high"},
        "study_fund_percent": {"value": 2.5, "confidence": "high"},
        "credit_points": {"value": 2.25, "confidence": "medium"},
        "car_benefit_value": {"value": 3480, "confidence": "high"},
        "payslip_month": {"value": "2026-09", "confidence": "high"},
    }
)
CAPS = {
    "image_input": {"supported": True},
    "pdf_input": {"supported": True},
    "structured_outputs": {"supported": True},
}


def _status_error(cls: type[anthropic.APIStatusError], status: int, text: str) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(text, response=httpx2.Response(status, request=request), body=None)


class FakeClient:
    def __init__(
        self,
        listed: list[str] = LISTED,
        errors: dict[str, Exception] | None = None,
        reply: str = READ,
        caps: dict[str, Any] = CAPS,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.errors = errors or {}  # model -> error to raise
        self.reply = reply
        self.models = SimpleNamespace(
            list=lambda: [SimpleNamespace(id=name) for name in listed],
            retrieve=lambda name: self._retrieve(name, listed, caps),
        )
        self.messages = SimpleNamespace(create=self._create)

    @staticmethod
    def _retrieve(name: str, listed: list[str], caps: dict[str, Any]) -> Any:
        if name not in listed:
            raise _status_error(anthropic.NotFoundError, 404, f"model: {name}")
        return SimpleNamespace(id=name, capabilities=caps)

    def _create(self, **params: Any) -> Any:
        self.calls.append(params)
        if params["model"] in self.errors:
            raise self.errors[params["model"]]
        usage = SimpleNamespace(
            input_tokens=1500,
            output_tokens=10,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.reply)],
            stop_reason="end_turn",
            usage=usage,
        )


def _settings(
    tmp_path: Path, model: str = "claude-haiku-5-5", fallback: str = "claude-sonnet-5-5"
) -> Settings:
    return Settings(
        app_db=tmp_path / "a.db",
        anthropic_api_key=FAKE_KEY,
        payslip_model=model,
        payslip_fallback_model=fallback,
    )


def _run(tmp_path: Path, client: FakeClient, **settings: str) -> tuple[int, Ledger]:
    ledger = Ledger(tmp_path / "spend.jsonl", cap_usd=1.0)
    return payslip_live.check(_settings(tmp_path, **settings), ledger, client=client), ledger


def test_both_models_usable_and_the_request_shape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient()
    code, ledger = _run(tmp_path, client)
    out = capsys.readouterr().out
    assert code == 0 and "payslip-check: OK" in out
    assert [(c["model"], c["messages"][0]["content"][0]["type"]) for c in client.calls] == [
        ("claude-haiku-5-5", "document"),
        ("claude-haiku-5-5", "image"),
        ("claude-sonnet-5-5", "document"),
        ("claude-sonnet-5-5", "image"),
    ]
    for call in client.calls:
        # the extraction's own request: no tools, no conversation, its fixed system prompt
        assert "tools" not in call and "tool_choice" not in call
        assert call["system"] == SYSTEM_PROMPT
        assert call["max_tokens"] == 800 and len(call["messages"]) == 1
        assert call["output_config"]["format"]["type"] == "json_schema"
    assert client.calls[0]["thinking"] == {"type": "disabled"}  # Haiku 5.5
    assert client.calls[2]["thinking"] == {"type": "between_tools"}  # Sonnet 5.5 rejects disabled
    entries = [json.loads(line) for line in ledger.path.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 4 and "provider" not in entries[0]
    # Haiku 5.5: 1500 in at $0.10/M, 10 out at $0.50/M
    assert entries[0]["cost_usd"] == pytest.approx((1500 * 0.10 + 10 * 0.50) / 1e6, abs=1e-6)
    assert "cost/payslip:    $0.000155 (the PDF read)" in out
    assert out.count(f"read correctly:  {len(EXPECTED)} of {len(EXPECTED)} fields") == 2
    assert FAKE_KEY not in out


def test_a_missing_id_names_the_closest_and_picks_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient()
    code, _ = _run(tmp_path, client, model="claude-haiku-5", fallback="claude-sonnet-5-5")
    out = capsys.readouterr().out
    assert code == 1 and "payslip-check: FAIL" in out
    assert "closest real IDs: claude-haiku-5-5" in out
    assert "No model was chosen for you" in out
    assert all(c["model"] != "claude-haiku-5" for c in client.calls)  # never probed


def test_a_rate_limited_primary_is_quota_billing_and_partial(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    limited = _status_error(anthropic.RateLimitError, 429, f"slow down {FAKE_KEY}")
    code, _ = _run(tmp_path, FakeClient(errors={"claude-haiku-5-5": limited}))
    out = capsys.readouterr().out
    assert code == 0
    assert "payslip-check: PARTIAL (quota/billing on claude-haiku-5-5; the rest OK)" in out
    assert "sent a PDF:      quota/billing: RateLimitError" in out
    assert "exists:          NO" not in out and FAKE_KEY not in out


def test_a_low_balance_is_quota_billing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broke = _status_error(anthropic.BadRequestError, 400, "Your credit balance is too low")
    code, _ = _run(tmp_path, FakeClient(errors={"claude-sonnet-5-5": broke}))
    assert code == 0 and "quota/billing on claude-sonnet-5-5" in capsys.readouterr().out


def test_a_refused_input_or_off_schema_reply_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = _status_error(anthropic.BadRequestError, 400, "unsupported media type")
    code, _ = _run(tmp_path, FakeClient(errors={"claude-haiku-5-5": bad}))
    assert code == 1 and "sent a PDF:      refused: BadRequestError" in capsys.readouterr().out
    code, _ = _run(tmp_path, FakeClient(reply="not json at all"))
    assert code == 1 and "refused: the answer is not JSON" in capsys.readouterr().out


def test_a_model_without_pdf_support_is_not_probed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(caps={**CAPS, "pdf_input": {"supported": False}})
    code, _ = _run(tmp_path, client)
    out = capsys.readouterr().out
    assert code == 1 and "API: PDFs:       NO" in out and client.calls == []


def test_no_key_no_call(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    settings = Settings(app_db=tmp_path / "a.db")
    assert payslip_live.check(settings, Ledger(tmp_path / "s.jsonl"), client=client) == 1
    assert "ANTHROPIC_API_KEY is empty" in capsys.readouterr().out and client.calls == []


def test_a_wrong_read_is_reported_field_by_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wrong = READ.replace('"value": 18500', '"value": 99999')
    code, _ = _run(tmp_path, FakeClient(reply=wrong))
    out = capsys.readouterr().out
    assert code == 0  # the models work; how well they read is reported, not a failure
    assert "base_salary          99999 (expected 18500)" in out


def test_redact() -> None:
    assert redact(f"x {FAKE_KEY} y", FAKE_KEY) == "x <redacted> y"
    other = "sk-ant-" + "B" * 20  # shaped like a key, not this one
    assert redact(f"key: {other}", None) == "key: <redacted>"


def test_probe_files_are_what_they_claim() -> None:
    pdf = probe_pdf()
    assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
    start = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    assert pdf[start:].startswith(b"xref")  # the xref offset points at the table
    assert probe_png().startswith(b"\x89PNG\r\n\x1a\n")


def test_closest_ids() -> None:
    assert closest_ids("claude-haiku-5", LISTED)[0] == "claude-haiku-5-5"
    assert closest_ids("totally-else", LISTED) == ()


def test_ledger_call_entry_matches_claude_entries(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "spend.jsonl", cap_usd=1.0)
    ledger.record_call("payslip-check (pdf)", "claude-haiku-5-5", 0.0001234567)
    entry = json.loads(ledger.path.read_text(encoding="utf-8"))
    assert set(entry) == {"at", "scenario", "model", "cost_usd"}
    assert entry["cost_usd"] == 0.000123 and ledger.spent() == pytest.approx(0.000123)

"""A refused ticket answer carries an error code per reason, each with a Hebrew message for the
rep screen; the English detail is unchanged (the model and logs read it)."""

from typing import Any, get_args

import pytest

from compass.labels import ERROR_MESSAGES, error_message
from compass.payslip.upload import PayslipErrorCode
from compass.profile_memory import ProfileErrorCode
from compass.state import Store
from compass.tools import Services, ToolRunner
from compass.tools.car_pick import PickErrorCode
from compass.tools.profile import FieldErrorCode
from compass.tools.tickets import TicketAnswerError, TicketErrorCode, answer_ticket

ATTO = "alternative_participation:CAR-10"


def test_every_error_code_has_a_hebrew_message() -> None:
    codes = set(get_args(TicketErrorCode)) | set(get_args(FieldErrorCode))
    codes |= set(get_args(PayslipErrorCode)) | set(get_args(PickErrorCode))
    codes |= set(get_args(ProfileErrorCode))
    assert set(ERROR_MESSAGES) == codes
    params = {"min": 0, "max": 20_000, "groups": ["א", "ב"], "max_mb": 5}
    for code in codes:
        message = error_message(code, params)
        assert message and any("֐" <= ch <= "׿" for ch in message), code


@pytest.fixture
def ticket(tmp_path: Any) -> tuple[Services, str]:
    services = Services(Store(tmp_path / "app.db"))
    sid = services.store.create_session()
    # the employee names the car (a ticket may ask only about such cars)
    services.store.add_message(sid, "user", {"text": "מה יקרה לנטו אם אעבור ל-ATTO 3?"})
    result = ToolRunner(services).run(
        sid, "ask_representative", {"question": "?", "blocking_fields": [ATTO]}
    )
    return services, result["ticket_id"]


@pytest.mark.parametrize(
    ("values", "code", "hebrew"),
    [
        ({ATTO: "abc"}, "not_a_number", "צריך להזין מספר."),
        ({ATTO: 99999}, "out_of_range", "הערך צריך להיות בין 0 ל-20,000."),
        ({ATTO: 350.555}, "too_many_decimals", "עד שתי ספרות אחרי הנקודה."),
        ({"bonus": 1}, "not_a_blocking_field", "השדה הזה לא שייך לטיקט."),
    ],
)
def test_refused_answers_are_coded(
    ticket: tuple[Services, str], values: dict[str, Any], code: str, hebrew: str
) -> None:
    services, ticket_id = ticket
    with pytest.raises(TicketAnswerError) as caught:
        answer_ticket(services, ticket_id, values=values)
    (error,) = caught.value.errors
    assert error.code == code
    assert error_message(error.code, error.params) == hebrew
    assert isinstance(caught.value.detail, list)  # the English detail, unchanged


def test_api_returns_hebrew_next_to_the_english_detail(tmp_path: Any) -> None:
    from fastapi.testclient import TestClient

    from compass.api import Settings, create_app

    rep = {"Authorization": "Bearer r"}
    settings = Settings(app_db=tmp_path / "a.db", dev_tools=True, rep_token="r")
    with TestClient(create_app(settings)) as client:
        sid = client.post("/api/sessions").json()["id"]
        client.post(f"/api/sessions/{sid}/messages", json={"text": "ומה עם ATTO 3?"})
        client.post(
            f"/api/sessions/{sid}/tools/ask_representative",
            json={"question": "?", "blocking_fields": [ATTO]},
        )
        (open_ticket,) = client.get("/api/tickets", headers=rep).json()
        url = f"/api/tickets/{open_ticket['id']}/answer"
        response = client.post(url, json={"values": {ATTO: -5}}, headers=rep)
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == [f"{ATTO}: must be 0-20,000 (got -5)"]
        assert body["errors"] == [
            {"code": "out_of_range", "field": ATTO, "message": "הערך צריך להיות בין 0 ל-20,000."}
        ]
        missing = client.post("/api/tickets/nope/answer", json={"values": {}}, headers=rep)
        assert missing.status_code == 404
        assert missing.json()["errors"][0]["message"] == "הטיקט לא נמצא."

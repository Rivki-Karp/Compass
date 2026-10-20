"""`tasks.py hash-password`: two no-echo prompts, only the hash on stdout."""

import pytest
import tasks

from compass.auth.passwords import verify_password

PASSWORD = "correct horse battery"


def _answers(monkeypatch: pytest.MonkeyPatch, *given: str) -> list[str]:
    prompts: list[str] = []
    remaining = list(given)

    def fake_getpass(prompt: str = "") -> str:
        prompts.append(prompt)
        return remaining.pop(0)

    monkeypatch.setattr("getpass.getpass", fake_getpass)
    return prompts


def test_prints_only_the_hash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prompts = _answers(monkeypatch, PASSWORD, PASSWORD)
    tasks.hash_password()
    out = capsys.readouterr().out.strip()
    assert len(prompts) == 2
    assert out.startswith("$argon2id$") and "\n" not in out and PASSWORD not in out
    assert verify_password(out, PASSWORD)


def test_differing_entries_print_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _answers(monkeypatch, PASSWORD, PASSWORD + "x")
    with pytest.raises(SystemExit) as caught:
        tasks.hash_password()
    assert capsys.readouterr().out == "" and PASSWORD not in str(caught.value)


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_a_password_outside_the_length_rule_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], password: str
) -> None:
    _answers(monkeypatch, password)
    with pytest.raises(SystemExit):
        tasks.hash_password()
    assert capsys.readouterr().out == ""


def test_it_is_a_task_that_takes_no_arguments() -> None:
    assert "hash-password" in tasks.TASKS and "hash-password" not in tasks.TAKES_ARGS

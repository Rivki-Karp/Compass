"""Scenario files: scripted turns and the checks a run must pass.

```yaml
name: walkthrough
description: one line for the report
turns:
  - employee: "אני מפתחת תוכנה, שכר בסיס 18,500"
  - rep:
      field: "alternative_participation:CAR-10"
      values: {"alternative_participation:CAR-10": 350}
until_compare: true   # after the script, answer FALLBACK_HE until a compare succeeds
checks:
  - comparison: {alternative: {kind: waiver}, diff: 2914}
```

Facts are front-loaded in the employee turns. When the script runs out and `until_compare`
is set, the employee answers FALLBACK_HE (at most `max_extra_turns` times).
"""

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.checks import parse_check

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
FALLBACK_HE = "זה כל המידע שיש לי"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionReply(_Model):
    value: Any = None
    status: Literal["answered", "needs_checking"] = "answered"
    note: str | None = None


class RepAnswer(_Model):
    """The representative answers the open ticket blocking `field` (None: the only one).
    `answers` by question id, by bound field, or `free` (the ticket's only free question)."""

    field: str | None = None
    values: dict[str, Any] | None = None
    answers: dict[str, QuestionReply] | None = None
    answer_text: str | None = None
    effective_from: date | None = None


class PayslipTurn(_Model):
    """The employee uploads a payslip and confirms some of what it says (flag on; the scripted
    extractor "reads" `read`, as the model's JSON object: a field is a number or {value,
    confidence}; extra keys play a model that goes beyond the schema). `confirm`: the fields
    the employee accepts, as POST /payslip/confirm takes them ({} accepts nothing)."""

    read: dict[str, Any]
    confirm: dict[str, Any] = Field(default_factory=dict)


class ProfileTurn(_Model):
    """The employee answers the offer of the saved profile (flag on): `apply` keeps everything
    offered, `dismiss` starts fresh. Needs `saved` on the scenario."""

    action: Literal["apply", "dismiss"]


class Turn(_Model):
    employee: str | None = None
    rep: RepAnswer | None = None
    payslip: PayslipTurn | None = None
    profile: ProfileTurn | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> "Turn":
        kinds = (self.employee, self.rep, self.payslip, self.profile)
        if sum(x is not None for x in kinds) != 1:
            raise ValueError(
                "a turn is either `employee: <text>`, `rep: {...}`, `payslip: {read, confirm}` "
                "or `profile: {action}`"
            )
        return self


class Scenario(_Model):
    name: str
    description: str
    turns: list[Turn] = Field(min_length=1)
    until_compare: bool = False
    max_extra_turns: int = Field(2, ge=0, le=5)
    checks: list[dict[str, Any]] = Field(min_length=1)
    # runs only with the upload on (evals --payslip), even with no payslip turn: the scenario is
    # about what the agent does when the upload exists
    payslip_on: bool = False
    # about the upload being OFF (the default): skipped when the run has it on (evals --payslip)
    payslip_off: bool = False
    # Remembered details (evals --profile): an earlier conversation of the same account said
    # `saved.profile` (save_profile's input) and `saved.today` (set_current_situation's); this
    # one starts with the offer of them. Skipped when the run has the flag off.
    saved: dict[str, Any] | None = None

    @property
    def needs_profile(self) -> bool:
        return self.saved is not None or any(turn.profile is not None for turn in self.turns)

    @property
    def needs_payslip(self) -> bool:
        return self.payslip_on or any(turn.payslip is not None for turn in self.turns)

    @model_validator(mode="after")
    def _valid_checks(self) -> "Scenario":
        for check in self.checks:
            parse_check(check)  # raises ValueError on an unknown check or argument
        return self


def load(path: Path) -> Scenario:
    with path.open(encoding="utf-8") as f:
        return Scenario.model_validate(yaml.safe_load(f))


def load_all(only: list[str] | None = None, directory: Path = SCENARIO_DIR) -> list[Scenario]:
    scenarios = [load(path) for path in sorted(directory.glob("*.yaml"))]
    names = [s.name for s in scenarios]
    if len(set(names)) != len(names):
        raise ValueError("duplicate scenario names")
    if only:
        unknown = sorted(set(only) - set(names))
        if unknown:
            raise ValueError(f"unknown scenario(s): {', '.join(unknown)}")
        scenarios = [s for s in scenarios if s.name in only]
    return scenarios

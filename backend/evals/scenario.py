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


class Turn(_Model):
    employee: str | None = None
    rep: RepAnswer | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> "Turn":
        if (self.employee is None) == (self.rep is None):
            raise ValueError("a turn is either `employee: <text>` or `rep: {...}`")
        return self


class Scenario(_Model):
    name: str
    description: str
    turns: list[Turn] = Field(min_length=1)
    until_compare: bool = False
    max_extra_turns: int = Field(2, ge=0, le=5)
    checks: list[dict[str, Any]] = Field(min_length=1)

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

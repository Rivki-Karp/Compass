"""The spend ledger (evals/spend.jsonl) and the Markdown report (evals/report.md)."""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from evals.harness import RunResult

EVALS_DIR = Path(__file__).resolve().parent
LEDGER = EVALS_DIR / "spend.jsonl"
REPORT = EVALS_DIR / "report.md"
CAP_USD = 30.0
# A scenario run costs ~$0.03-0.10; refuse to start one that could cross the cap.
ESTIMATE_PER_RUN_USD = 0.20


class OverBudget(Exception):
    pass


@dataclass
class Ledger:
    path: Path = LEDGER
    cap_usd: float = CAP_USD

    def spent(self) -> float:
        if not self.path.exists():
            return 0.0
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return sum(json.loads(line)["cost_usd"] for line in lines if line.strip())

    def reserve(self) -> None:
        """Raise OverBudget unless one more scenario run fits under the cap."""
        spent = self.spent()
        if spent + ESTIMATE_PER_RUN_USD > self.cap_usd:
            raise OverBudget(
                f"spent ${spent:.2f} of the ${self.cap_usd:.2f} cap; one more run could "
                f"exceed it (estimate ${ESTIMATE_PER_RUN_USD:.2f}). Ask before raising --cap."
            )

    def record(self, run: RunResult, effort: str, model: str) -> None:
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "scenario": run.scenario,
            "model": model,
            "effort": effort,
            "passed": run.passed,
            "cost_usd": round(run.cost_usd, 6),
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render(
    runs: list[RunResult],
    *,
    model: str,
    effort: str,
    repeat: int,
    spent_before: float,
    spent_after: float,
    cap_usd: float,
    stopped: str | None = None,
) -> str:
    by_name: dict[str, list[RunResult]] = defaultdict(list)
    for run in runs:
        by_name[run.scenario].append(run)
    passed = sum(all(r.passed for r in rs) for rs in by_name.values())
    shown_violations = sum(
        1 for run in runs for _, v in run.trace.guard_rechecks if v
    )  # numbers that reached the user despite the guard
    cost = sum(run.cost_usd for run in runs)
    out = [
        "# Compass agent evals",
        "",
        f"- Run: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · model `{model}` · effort `{effort}` "
        f"· repeat {repeat}",
        f"- **Scenarios passing (every repeat): {passed}/{len(by_name)}** · "
        f"scenario runs passing: {sum(r.passed for r in runs)}/{len(runs)}",
        f"- **Shown replies failing the guard: {shown_violations}** · guard retries: "
        f"{sum(r.guard_retries for r in runs)} · template fallbacks: "
        f"{sum(r.templates for r in runs)}",
        f"- Cost of this run: ${cost:.4f} · total spend ${spent_after:.4f} of the "
        f"${cap_usd:.2f} cap (before this run: ${spent_before:.4f})",
    ]
    if stopped:
        out.append(f"- **Stopped early:** {stopped}")
    out += [
        "",
        "| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read"
        " | Cost $ | Guard retries / templates |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, rs in by_name.items():
        n = len(rs)
        tokens_in = sum(r.usage.input_tokens + r.usage.cache_creation_input_tokens for r in rs)
        out.append(
            f"| {name} | {sum(r.passed for r in rs)}/{n} | {sum(r.turns for r in rs) / n:.1f} "
            f"| {sum(r.rounds for r in rs) / n:.1f} | {sum(r.latency_s for r in rs) / n:.1f} "
            f"| {tokens_in // n:,} / {sum(r.usage.output_tokens for r in rs) // n:,} / "
            f"{sum(r.usage.cache_read_input_tokens for r in rs) // n:,} "
            f"| {sum(r.cost_usd for r in rs) / n:.4f} "
            f"| {sum(r.guard_retries for r in rs)} / {sum(r.templates for r in rs)} |"
        )
    out += ["", "Per-scenario figures are averages over the repeats.", "", "## Checks"]
    for name, rs in by_name.items():
        for i, run in enumerate(rs, 1):
            mark = "PASS" if run.passed else "FAIL"
            suffix = f" (repeat {i})" if len(rs) > 1 else ""
            out += ["", f"### {name}{suffix}: {mark}", ""]
            for r in run.results:
                detail = f" — {_cell(r.detail)}" if r.detail else ""
                out.append(f"- {'✅' if r.passed else '❌'} {_cell(r.label)}{detail}")
            if not run.passed:
                out += ["", "<details><summary>Replies</summary>", ""]
                for reply in run.trace.replies:
                    out.append(f"- t{reply.turn} [{reply.kind}] {_cell(reply.text)}")
                out += ["", "</details>"]
    return "\n".join(out) + "\n"

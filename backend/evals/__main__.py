"""uv run python tasks.py eval [--only a,b] [--repeat N] [--effort low|medium] [--out PATH]

Runs the scenarios against the real model (needs ANTHROPIC_API_KEY in .env), each in a fresh
temporary session store, and writes the report. Refuses to start a run that could take the
total spend (evals/spend.jsonl) over the cap.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from compass.agent.factory import build_claude_runner
from compass.agent.guard import make_guard
from compass.agent.llm import AnthropicClient
from compass.agent.startup import load_agent_settings
from compass.api.settings import Settings
from compass.state import Store
from compass.tools.services import Services
from evals.harness import Harness, RunResult
from evals.report import CAP_USD, REPORT, Ledger, OverBudget, render
from evals.scenario import Scenario, load_all


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tasks.py eval")
    parser.add_argument("--only", default="", help="comma-separated scenario names")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--effort", choices=["low", "medium"], default="low")
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--cap", type=float, default=CAP_USD, help="total spend cap, USD")
    return parser.parse_args(argv)


def run_one(settings: Settings, scenario: Scenario, effort: str) -> RunResult:
    services = Services(
        Store(Path(tempfile.mkdtemp(prefix="compass-eval-")) / "app.db"),
        rules_path=settings.rules_path,
        aliases_path=settings.aliases_path,
        vehicles_db=settings.vehicles_db,
    )
    assert settings.anthropic_api_key
    llm = AnthropicClient(settings.anthropic_api_key, settings.model, effort=effort)
    runner = build_claude_runner(settings, services, llm=llm, background=False)
    return Harness(services, runner, make_guard(services.store), settings.model).run(scenario)


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parse(argv)
    if args.repeat < 1:
        print("--repeat must be at least 1", file=sys.stderr)
        return 2
    try:
        scenarios = load_all([n for n in args.only.split(",") if n] or None)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    settings = load_agent_settings()
    ledger = Ledger(cap_usd=args.cap)
    spent_before = ledger.spent()
    runs: list[RunResult] = []
    stopped = None
    try:
        for scenario in scenarios:
            for i in range(args.repeat):
                ledger.reserve()
                run = run_one(settings, scenario, args.effort)
                ledger.record(run, args.effort, settings.model)
                runs.append(run)
                failed = [r.label for r in run.results if not r.passed]
                mark = "PASS" if run.passed else f"FAIL ({len(failed)})"
                print(
                    f"{scenario.name} #{i + 1}: {mark} · {run.rounds} rounds · "
                    f"{run.latency_s:.1f}s · ${run.cost_usd:.4f}",
                    flush=True,
                )
                for label in failed:
                    print(f"    ✗ {label}", flush=True)
    except OverBudget as error:
        stopped = str(error)
        print(stopped, file=sys.stderr)
    except KeyboardInterrupt:
        stopped = "interrupted"
    report = render(
        runs,
        model=settings.model,
        effort=args.effort,
        repeat=args.repeat,
        spent_before=spent_before,
        spent_after=ledger.spent(),
        cap_usd=args.cap,
        stopped=stopped,
    )
    args.out.write_text(report, encoding="utf-8", newline="\n")
    print(f"report: {args.out} · total spend ${ledger.spent():.4f} of ${args.cap:.2f}")
    return 0 if runs and not stopped and all(r.passed for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""uv run python tasks.py eval [--only a,b] [--repeat N] [--effort low|medium] [--out PATH]
                            [--payslip] [--prompt PATH]

Runs the scenarios against the real model (needs ANTHROPIC_API_KEY in .env), each in a fresh
temporary session store, and writes the report. Refuses to start a run that could take the
total spend (evals/spend.jsonl) over the cap.

--payslip runs with the payslip upload on (COMPASS_PAYSLIP=1): the prompt gets its payslip
section, the scenarios with a `payslip` turn run (scripted extractor, no network), and the
global "no mention of תלוש" check is off. Without it those scenarios are skipped.
--prompt PATH runs with that system prompt file instead of the one in the repository (the
flag's section is still added with --payslip).
"""

import argparse
import dataclasses
import sys
import tempfile
from pathlib import Path

from compass.agent.factory import build_claude_runner
from compass.agent.guard import make_guard
from compass.agent.llm import AnthropicClient
from compass.agent.prompts import load_system_prompt
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
    parser.add_argument("--payslip", action="store_true", help="run with COMPASS_PAYSLIP=1")
    parser.add_argument("--prompt", type=Path, default=None, help="a system prompt file")
    return parser.parse_args(argv)


def run_one(
    settings: Settings, scenario: Scenario, effort: str, prompt: Path | None = None
) -> RunResult:
    services = Services(
        Store(Path(tempfile.mkdtemp(prefix="compass-eval-")) / "app.db"),
        rules_path=settings.rules_path,
        aliases_path=settings.aliases_path,
        vehicles_db=settings.vehicles_db,
    )
    assert settings.anthropic_api_key
    llm = AnthropicClient(settings.anthropic_api_key, settings.model, effort=effort)
    runner = build_claude_runner(settings, services, llm=llm, background=False)
    if prompt is not None:
        runner.system_prompt = load_system_prompt(prompt, payslip=settings.payslip)
    harness = Harness(services, runner, make_guard(services.store), settings.model)
    harness.payslip = settings.payslip
    return harness.run(scenario)


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
    if args.payslip:
        settings = dataclasses.replace(settings, payslip=True)
        scenarios = [s for s in scenarios if not s.payslip_off]
    else:  # flag off: the payslip scenarios cannot run
        scenarios = [s for s in scenarios if not s.needs_payslip]
    ledger = Ledger(cap_usd=args.cap)
    spent_before = ledger.spent()
    runs: list[RunResult] = []
    stopped = None
    try:
        for scenario in scenarios:
            for i in range(args.repeat):
                ledger.reserve()
                run = run_one(settings, scenario, args.effort, args.prompt)
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

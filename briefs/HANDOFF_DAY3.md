# Handoff — Day 3 (the agent), complete pending review

Updated 2026-10-15 from the real repo state (git, a full test run, the eval reports and the
session event logs), not from memory. The brief and the approved plan decisions are in
`briefs/day3-agent.md`.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` | `1f114a9` | unchanged; identical to `origin/main`. **Do not merge `day3/agent` before review.** |
| `day3/agent` | the `docs: Day 3 handoff` commit, on `3b50995` | pushed to `origin/day3/agent` |

## Stages (all done)

| Stage | Commit | What |
|---|---|---|
| brief | `b24ea24` | the Day 3 brief with the approved plan decisions |
| 0 | `08f6be1` | `.env` settings, key check for chat/eval (Hebrew + English, exit 2) |
| 1 | `9be82d1` | `LLMClient`, `AnthropicClient` (caching, effort, fallbacks), `ScriptedClient` |
| — | `c16aec5` | additive tool fields: `group`, `group_source`, `group_budget`; option car facts |
| 2 | `0ff740d` | the loop, per-session workers, transcript, events, failures, rep resume |
| 3 | `a2c2dca` | the number guard and deterministic templates |
| 4 | `13d64c6` (wip) + `7d1bbd5` | Hebrew system prompt, tool descriptions, `tasks.py chat`, `compass/tools/tickets.py`; fixes from live runs (below) |
| 5 | `dc7b01e` | `evals/`: harness, 15 scenarios, report, spend ledger; README Agent section |
| — | `e28a7a6` | `evals/report-medium.md`; low vs medium in the README |
| — | `3b50995` | tool-side pending fix (below) |

## Fixes found by live runs and evals (all approved)

- **Waiver maintenance source** (`7d1bbd5`). A waiver `maintenance` equal to the
  occupation's amount is source `occupation`; a different amount, or any amount without an
  occupation, is `representative`.
  - Tests: `test_waiver_maintenance_equal_to_the_occupation_is_the_occupation`,
    `test_waiver_maintenance_without_an_occupation_is_the_representatives`.
  - Live: 6 `comparison_ready` events at +2,914 (11,000 → 13,914), all `occupation`.
- **Participation source** (`7d1bbd5`). An explicit participation equal to the rep's answer
  for that field is `representative`, with its effective date; a different amount stays
  `employee_input`.
  - Test: `test_repeating_the_representatives_amount_keeps_it_the_representatives`.
  - Live: the 12:44 UTC run before the fix labelled +611 `employee_input`; every run since
    (12:47 UTC onwards, 12 events) labels it `representative`.
- **Pending regardless of tool order** (`3b50995`). When `ask_representative` opens a ticket
  for a participation, the latest comparison that used it at the catalog default is
  recomputed without a model call and re-emitted as `comparison_ready` with
  `pending_rep: true`, `origin: "server"`, `recomputed_from`, `ticket_id` and
  `pending_field`. compare's result contract is unchanged.
  - Tests: `tests/tools/test_pending_recompute.py` (7) and the scripted
    `test_rep_flow_with_compare_before_ask_representative`.
- **Prompt lines added during tuning** (`system_he.md`):
  - waiver: `{"kind": "waiver"}` only;
  - no `lookup_occupation` after `save_profile` has derived the group;
  - after a rep answer, call compare without `participation`;
  - ask the representative first, then compare.
- **`tasks.py serve` runs `--workers 1`**: per-session workers live in memory (README).

## Evals

All on `claude-sonnet-5-5`:

| Run | Result | Guard | Cost |
|---|---|---|---|
| `evals/report.md`, effort low, 15 × 3 | **45/45**, every scenario 3/3 | 0 shown violations, 0 retries, 0 templates | $0.025 / run |
| `evals/report-medium.md`, effort medium, 15 × 1 | 15/15 | 0 / 0 / 0 | $0.028 / run |
| `evals/report-rep-flow.md`, e001_rep_flow × 3 after the pending fix | 3/3 | 0 / 0 / 0 | $0.062 / run |

- Effort stays `low`.
- Spend: **$2.70 of the $30 cap** (`evals/spend.jsonl`, committed: it is the cap's record).

## Open

- **Manual PowerShell run of `tasks.py chat`: pending the developer's report.** Hebrew
  rendering and dim lines have only been checked programmatically. The DoD item "works in
  PowerShell with only `.env`" stays open until then.
- **`drop_block` is not implemented.** Input stays bounded through compact tool views on a
  1M context, but a very long session has no backstop.
- **Risks:**
  - In-process workers mean a single uvicorn process only.
  - Scripted evals can pass on lucky phrasing: the `reply` regex checks are coarse.
  - The pending recompute uses the current profile; if the profile changed between the
    compare and the ticket, the re-emitted numbers follow the current profile.
  - Eval latency includes one API outage (13:00–13:44 UTC on 15/10), excluded by the re-runs.

## Next

Review the final Day 3 report, then merge `day3/agent` into `main` (`--no-ff`). Day 4 starts
from `main` with its own brief, handed over after the merge.

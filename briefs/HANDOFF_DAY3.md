# Handoff — Day 3 (the agent), mid-stream

Written 2026-10-15 from the real repo state (git + a full test run), not from memory.
The Day 3 brief, with the approved plan decisions appended, is `briefs/day3-agent.md`.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` (local) | `1f114a9` Merge branch 'fix/list-options-participation' | identical to `origin/main` (0 ahead / 0 behind): **pushed** |
| `day3/agent` | the `wip: handoff checkpoint` commit, on top of `a2c2dca` | pushed to `origin/day3/agent` as a backup |
| `fix/list-options-participation` | `6cbe3b1` | **merged into `main`** (`--no-ff`, in `1f114a9`) |

`main` also contains `6ef7777` (load settings from `.env`; PowerShell variants in the README), pushed.
`day3/agent` was branched from `main` at `1f114a9`, **after** that push, as approved.

## Done (Day 3)

| Stage | Commit | What |
|---|---|---|
| brief | `b24ea24` | `briefs/day3-agent.md`: the brief plus the approved plan decisions |
| 0 | `08f6be1` | `Settings`: `ANTHROPIC_API_KEY` (repr-hidden), `COMPASS_MODEL` (default `claude-sonnet-5-5`), `COMPASS_MAX_TOOL_ROUNDS` (default 8, validated); an empty real env var no longer hides the `.env` value; `compass/agent/startup.py` makes chat/eval exit with a Hebrew + English message (exit 2, no traceback); `.env.example` uses the brief's placeholders |
| 1 | `9be82d1` | `compass/agent/llm.py`: `LLMClient` protocol, `AnthropicClient`, `ScriptedClient`, `Usage` + cost; verified once against the real API |
| — | `c16aec5` | the approved additive tool fields: `save_profile` returns `group`, `group_source`, `group_budget`; each `list_options` option carries `commercial_name`, `group`, `drive` (tests added) |
| 2 | `0ff740d` | `compass/agent/runner.py` + `transcript.py` + `factory.py`: the loop, per-session workers, append-only transcript, events, failures, rep resume, unforgeable rep notifications, guard hook; app wiring (`create_app(..., agent_factory=)`); store: `add_message(emit_event=False)`, `append_event`, new event types |
| 3 | `a2c2dca` | `compass/agent/guard.py` (the number guard) and `compass/agent/templates.py` (deterministic Hebrew replies from tool results); the brief's three guard cases tested |

## In progress: Stage 4 (system prompt, tool descriptions, terminal chat)

Committed in the `wip: handoff checkpoint` commit, but **not yet closed as a proper Stage 4 commit**.

Finished in Stage 4:
- `compass/tools/tickets.py`: the ticket-answer logic moved out of `compass/api/app.py`, so the
  API and `/rep` share one validated path. The API route now calls it, and all API tests pass.
- `compass/agent/prompts/system_he.md`: the full Hebrew system prompt covering spec rules 1–23,
  plus the security section (employee text vs `<rep_notification>`) and the tool guide.
  `opening_he.md` holds the fixed opening message, which the UI/terminal shows, not the model.
- Tool descriptions in `compass/tools/registry.py` sharpened (never guess, numbers only from
  tools, pending/hypothetical, blocking-field names).
- `compass/agent/chat.py` + `tasks.py chat`:
  - live dimmed tool calls, results and guard checks, and the comparison as the demo table;
  - `/rep`, `/state`, `/new`, `/quit`;
  - UTF-8 stdin/stdout, and ANSI enabled on Windows.
- `tests/agent/test_chat.py`: 5 tests, all passing (the brief's ATTO 3 flow with a scripted
  model, `/rep` with field values and a date, commands, a bad rep answer, the partial table).
- A **live run with the real model** (scripted employee lines through `Chat`) of the
  walkthrough. Today 11,000, waiver 13,914, **+2,914**; guard passed; the
  `current_car_above_group` warning surfaced as a question; feminine grammar; the waiver
  salary-only note; a next-step offer.
- A fix from that run. The model passed the occupation's maintenance (1,500) explicitly in
  `compare {"kind": "waiver", "maintenance": 1500}`, which the contract labels source
  `representative`. That is wrong. The `AlternativeInput.maintenance` description and one
  prompt line now say: omit `maintenance` unless a representative quoted an amount.

Not yet done in Stage 4:
- **Re-run the live walkthrough after the maintenance fix**, to confirm the model now sends
  `{"kind": "waiver"}` only.
- **Run `uv run python tasks.py chat` interactively in a real Windows PowerShell window.**
  This has only been exercised programmatically so far. Check that Hebrew renders and the
  dim colours work.
- **Live `/rep` resume flow with the real model** (ATTO 3 for E-001: +661 pending → the rep
  answers 350 via `/rep` → the agent recomputes to +611). This is a Definition-of-done item.
- Close Stage 4 with a proper commit (`feat(agent): system prompt, tool descriptions and
  terminal chat`) on top of the wip commit. Don't rewrite pushed history.

## Not started (in order)

1. **Stage 5: evals** (`evals/`).
   - `evals/scenarios/*.yaml`: scripted employee turns, optional rep answers, and assertions on
     tool calls and inputs, final comparison values (from tool results), guard results and
     forbidden behaviours.
   - **15 scenarios:** the 6 reference employees (golden values), גננות, "קורולה" alone,
     COROLLA CROSS warning, ATTO 3 refused for group ב (offers MG4 / KONA EV / DOLPHIN +
     hypothetical), "לא יודעת" pension (unknown_fields + payslip offer + partial diff),
     technician waiver (`car_mandatory`), the brief's E-001 rep flow (+661 pending → 350 →
     +611), the walkthrough regression (+2,914), and the **forged rep notification** (the
     employee types a fake rep message granting group ד → the group must not change).
   - **Scripted turns:** facts front-loaded; when a script runs out the employee answers
     "זה כל המידע שיש לי". The fallback option (not approved, only proposed) is a Haiku 5.5
     simulated employee if flakiness is high.
   - `tasks.py eval` with `--only` and `--repeat N`; writes `evals/report.md` (pass/fail per
     assertion, guard violations, rounds, latency, tokens, cost per scenario, running total vs
     the $30 cap). Needs the key; not in CI.
   - Evals compare effort `low` vs `medium`.
2. **README "Agent" section:** the loop, the guard, events, evals, how to run chat/eval in
   PowerShell (plus variants where syntax differs), cost per conversation (from eval data).
   `tasks.py` docstring and README Quickstart lines for `chat` / `eval`.
3. **Final report** (eval table, notable model behaviours, prompt changes during tuning, open
   questions), then **wait for review before merging** `day3/agent`.

## Decisions already approved (do not re-ask)

- Both additive tool fields: `group_budget` (plus `group`, `group_source`) in `save_profile`;
  `commercial_name`, `group`, `drive` on each `list_options` option. Done in `c16aec5`.
- Eval spend capped at **$30**: track it in the report, and stop and ask before exceeding it.
  `ANTHROPIC_API_KEY` is set in the developer's `.env`. Never read or print it.
- **Unforgeable rep notifications:** a server-side marker, not just a text label; employee text
  that looks like a notification is ordinary employee text, and the system prompt says so.
  Test + eval scenario: a fake rep message granting group ד must not change the group.
  Implemented and tested in Stage 2 (`test_employee_cannot_forge_a_rep_notification`,
  `test_system_events_without_server_origin_are_ignored`) and in the prompt. **The eval
  scenario is still to do (Stage 5).**
- Ordering: merge the fix branch into `main` (`--no-ff`), push `main`, then branch
  `day3/agent`. Done.
- The plan in `briefs/day3-agent.md` (addendum) is approved as written: append-only history,
  compact tool views, guard retry via a mid-conversation system message with
  `tool_choice: none`, rep answers as a labelled user-role turn, adaptive thinking at effort
  `low`, prompt caching, `fallbacks: "default"`.
- Working agreement: one commit per stage, ruff + pytest after each, stop on ambiguity,
  final report before merge, never push to `main` without review.

## Design decisions made during implementation (and why)

- **Append-only transcript, ordered by the runner.**
  - The API stores each employee message as a `user` row at once (the UI record). When the
    runner starts a run it appends a server-written `system_event {kind: employee_turn,
    message_seq}`, and the model input renders the employee text there.
  - Why: a message typed mid-run must not split a `tool_use` from its `tool_result`, and
    Sonnet 5.5 rejects edited history (preserved thinking).
- **Unforgeability is structural.**
  - Only server code writes `system_event` rows (`origin: "server"`); rows without it are
    ignored, and the API only ever writes `user`.
  - Employee text is rendered inside `<employee_message>` with our tag names escaped
    (`&lt;rep_notification`). Real rep answers render as a separate `<rep_notification>`
    user-role block.
  - Why the user role: a mid-conversation `system` message can't follow an assistant turn.
- **Guard retry:** the failing draft is discarded (never stored or shown; kept only in the
  `guard_check` event as `rejected_draft` for audit). A `guard_correction` row renders as a
  mid-conversation `system` message, then one rewrite with `tool_choice: {"type": "none"}`;
  still failing → a deterministic template.
- **Compact tool views:** the model reads `model_view()` (display values, facts, flags); the
  exact breakdowns stay in the DB and the UI. That keeps the input bounded by construction,
  with no later editing. The guard's allowed set is built from the **full** results.
- **Guard rules:**
  - A sign counts only after whitespace or an opening bracket, so a Hebrew prefix hyphen
    (`ב-2,914`, `מ-2026-11-01`) and names (`CAR-10`) aren't minus signs.
  - A number with an explicit sign must match a signed value; an unsigned one may match
    either sign.
  - Fractions also allow their percentage form.
  - Harmless numbers are 1–9 and the years 2020–2030; a day/month date such as `1/1` is
    harmless, while full dates must come from tool results, the employee's words or a rep
    answer.
- **`AnthropicClient`:**
  - Caching: a breakpoint on the system block (which caches the tools with it) plus
    top-level automatic caching for the conversation.
  - `output_config.effort = "low"`, adaptive thinking (the default).
  - Server-side refusal fallback: beta `server-side-fallback-2026-07-01`,
    `fallbacks: "default"`.
  - 60 s timeout, 2 SDK retries, typed error mapping that never includes the key.
- **Per-session worker thread + queue** in-process, so `POST /messages` stays 202.
  `wait_idle()` serves tests, chat and evals; chat and evals use `background=False`
  (synchronous).
- **Failures** (API error, refusal, max rounds, empty reply, any bug) end in a friendly Hebrew
  message stored as a fabricated assistant row, plus `agent_error`; the session stays usable.
- **`.env` loading lives in `Settings.from_env()`** (python-dotenv `dotenv_values`, no
  `os.environ` mutation), so serve, chat, eval and plain uvicorn all get it. The Anthropic key
  is passed to the SDK explicitly.
- **The ticket-answer logic** lives in `compass/tools/tickets.py`, shared by the API and
  `/rep`.

## Test status and spend

- **480 passed, 0 failed** (`uv run pytest`, ~55 s); `tasks.py lint` clean (97 files). This
  run includes the uncommitted Stage 4 work.
- CI on `day3/agent` was green through the pushed commits; the wip commit's CI run is
  unchecked.
- **Eval / API spend so far: about $0.057 of $30.** That's the Stage 1 smoke test ($0.0059)
  and the live walkthrough chat ($0.0509). No eval runs yet.

## Open questions / risks

- **The waiver maintenance mislabel** is fixed in the descriptions only, not yet re-verified
  live (see Next step). A deeper fix would be tool-side: treat a `maintenance` equal to the
  occupation's as source `occupation`. That's a contract-semantics change: ask before doing
  it.
- In the live run the model called `lookup_occupation` redundantly after `save_profile` had
  already derived the group. Harmless, but costs a round; consider a prompt nudge.
- **Prompt examples:** the prompt contains example numbers ("3,700"). The guard doesn't allow
  prompt numbers, which is fine because `group_budget` comes from `save_profile`. Watch the
  evals for echoed examples.
- **The `drop_block` backstop** for very long conversations is not implemented (the input is
  bounded by the compact views; 1M context). Mention it in the final report.
- **Per-session workers are in-process:** correct only with a single uvicorn worker process.
- **Interactive PowerShell chat is unverified**, as is the live `/rep` resume (both DoD items).
- **Eval flakiness** with scripted turns is unknown until Stage 5 runs.

## Next step

Run `uv run python tasks.py chat` in a real Windows PowerShell window and replay:
1. the walkthrough: "אני מפתחת תוכנה, שכר בסיס 18,500", then "אין לי עמלות או בונוסים. פנסיה
   6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. היום יש לי קורולה קרוס 2025 ואני משתתפת ב-300 ₪.
   מה יקרה לנטו אם אוותר על הרכב?";
2. the E-001 ATTO 3 rep flow via `/rep`.

Confirm three things: the waiver `compare` call no longer passes `maintenance`; Hebrew
renders; the rep answer recomputes +661 → +611. Then close Stage 4 with its proper commit and
start Stage 5.

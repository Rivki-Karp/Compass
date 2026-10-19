# Compass — Day 3: The Agent

> **Layout note (2026-10-19, after v1.1):** the repo is now split into `backend/` and
> `frontend/` (formerly `web/`). The commands below are updated to run from the repo root
> (`uv run --project backend python tasks.py ...`); the narrative and file names describe the
> repo as it was on the day.

## Where we are

`main` has: the data layer (Day 0), the exact engine (Day 1), search, 9 tools, the SQLite session store, the FastAPI app with SSE, the representative ticket flow with token auth, and participation as a rep-fillable field (Day 2), plus the `list_options` participation fix. ~409 tests, CI green.

The full walkthrough was verified by hand through `/docs` (dev-tools endpoint): developer in group ב, 18,500, pension 6.5%, study fund 2.5%, 3 credit points, commissions 0, bonus 0; today CAR-09 (2025, participation 300) → warning `current_car_above_group`; `compare` waiver → today **11,000**, waiver **13,914**, `display_diff` **+2,914**.

Today we plug in the brain: a **Claude tool-use loop** that talks Hebrew with the employee, calls our existing tools, and never invents a number. The tools, their input shapes and their error codes already exist — **do not change tool contracts** unless a stage below says so; if you must, stop and ask.

## Working agreement (unchanged)

Plan first and wait for approval; branch `day3/agent`; one commit per stage; ruff + pytest after each; stop on ambiguity or contradictions; final report before merge. Commit this brief to `briefs/` as the first commit if it isn't there yet.

New dependency: `anthropic` (official SDK). Configuration (all via `.env`, see Stage 0): `ANTHROPIC_API_KEY`, `COMPASS_MODEL` (default `claude-sonnet-5-5`), `COMPASS_MAX_TOOL_ROUNDS` (default 8). Never log or print the key.

**Out of scope today:** the React UI, payslip upload (placeholder note only), deployment.

---

## Product behaviour (the spec the system prompt must encode)

We designed this in a walkthrough; these rules **are** the product. Write the system prompt **in Hebrew**, in `compass/agent/prompts/system_he.md` (a versioned file, not a Python string), with clear headings.

**Role & tone**
1. Hebrew, warm, short, professional. Match the employee's grammatical gender as they write it; if unknown, use neutral phrasing.
2. Not a financial or legal advisor: results are an *estimate* ("נטו משוער"); never say "כדאי לך" / "לא כדאי לך".
3. Out-of-scope requests → one polite sentence and back to the topic.

**Collecting information**
4. Ask for the **occupation**, not the eligibility group; derive the group via tools and **state what was derived** ("מפתחת תוכנה ← קבוצה ב', תקציב 3,700 ₪") so the employee can correct it.
5. Ask only for what is missing — drive this from the tools' `missing` lists, not from memory. Note that `commissions` and `bonus` are required inputs: ask explicitly ("יש לך עמלות או בונוסים?"); a "no" is saved as 0. Never assume 0 silently.
6. At most ~4 short, related questions per message; the most important question goes **last**. If the employee skipped a question, re-ask it briefly in the next message.
7. Confirm what was recorded ("רשמתי: …"). When an answer is ambiguous (e.g. a bare "כן"), take the most reasonable reading, **say which reading you took**, and invite correction — don't ask a third time.
8. **Never guess** a value. "I don't know" → `save_profile` with `unknown_fields`.
9. For unknown **payslip fields**: one simple sentence explaining *why* the value is needed, then offer to upload a payslip. Don't explain where it appears on the payslip or go into calculations unless asked. (The UI shows the upload button from `payslip_fields_unknown`; the text only mentions it.)
10. Never ask for a national ID number.

**Search results**
11. When `lookup_vehicle` / `lookup_occupation` returns `confident: false` with candidates, ask the employee to choose between the top candidates by name (e.g. "קורולה רגילה או קורולה קרוס?"). Never pick one yourself. `not_found` → ask for another wording; for occupations, also offer the representative.
12. Vehicle registration year matters (value of use depends on it). Confirm it when the employee didn't say it; a catalog id with a different year is a different vehicle (`not_found` → use `lookup_vehicle` with the year).

**Consistency, eligibility and exceptions**
13. Surface engine **warnings** (`current_car_above_group`, `group_mismatch_with_occupation`, `current_car_not_in_catalog`) as a gentle question with options — e.g. "your group may actually be ג / you may have a special approval / I can ask the transport representative". Never resolve it by assumption.
14. An exception the employee declares applies **only to what they said** (e.g. today's car), not to new choices.
15. Ineligible request → a clear "no" with a one-sentence reason (from the reason code), then: eligible alternatives of the same kind (same drive type; include lower groups), and an offer to compute the requested car **hypothetically, clearly labelled as conditional on approval** (`compare` returns `hypothetical: true`), and/or to ask the representative for approval.

**Representative**
16. Ask the employee first; use `ask_representative` only for what only the company knows: participation for a new car, group disputes, exceptions, policy questions. Phrase the ticket as one self-contained sentence with quick answers when possible, and use the right `blocking_fields` (e.g. `alternative_participation:CAR-10`).
17. While a result has `pending_rep: true`, say clearly that the participation is the catalog default pending the representative's confirmation. Tell the employee they can keep going and that the answer will appear in the chat even if they leave.

**Numbers & results**
18. **Every number in your text must come from a tool result, the employee's own words, or `get_rule`.** Never compute, re-round, or estimate.
19. After `compare`, the UI renders the comparison card from the tool result. **Do not repeat the table.** Write a two-line explanation of the *mechanism* from `explanation_facts`.
20. Partial results (unknown pension / study fund): give the difference and say the full net will appear once the missing values are known.
21. Waiver results: add one sentence that the calculation covers salary only — private-car costs are not included. No recommendation.
22. "Why" questions about policy → answer only from `get_rule`; never invent a rationale; offer the representative for policy questions.
23. After a result, offer one natural next step (e.g. "להשוות לכל החלופות?").

---

## Stages

### Stage 0 — Windows/PowerShell & `.env`
The developer runs Windows PowerShell, where `VAR=1 command` doesn't work.
- `tasks.py serve`, `chat` and `eval` load `.env` automatically (python-dotenv or `uv run --env-file`). Real environment variables override `.env`.
- `.env.example`: `ANTHROPIC_API_KEY=`, `COMPASS_MODEL=claude-sonnet-5-5`, `COMPASS_DEV_TOOLS=1`, `COMPASS_REP_TOKEN=rep-demo-change-me`, `COMPASS_ADMIN_TOKEN=admin-demo-change-me` (placeholders only).
- README: every command works in PowerShell; add PowerShell variants wherever syntax differs (e.g. `$env:VAR="1"`).
- If `chat`/`eval` start without `ANTHROPIC_API_KEY`, print a clear Hebrew+English message and exit — no stack trace.

### Stage 1 — LLM client abstraction (`compass/agent/llm.py`)
- `LLMClient` protocol: `create(messages, tools, system) -> Response` (content blocks: text / tool_use, stop_reason, usage).
- `AnthropicClient`: the real SDK, with **prompt caching** on the system prompt and tool definitions, timeouts, limited retries on transient errors.
- `ScriptedClient`: replays pre-written responses — for unit tests and CI (no key, no network).

### Stage 2 — The agent loop (`compass/agent/runner.py`)
`ClaudeAgentRunner` implements the Day 2 `AgentRunner` protocol and replaces `NullAgentRunner` when a key is configured.
- On `user_message`: load the session transcript, call the model, execute `tool_use` blocks via the existing `ToolRunner`, append tool results, loop until a final text or `COMPASS_MAX_TOOL_ROUNDS`.
- Persist the **full transcript** (user, assistant incl. tool_use, tool results) in `messages`; rebuild the model input from it every turn. Keep the input bounded (e.g. collapse old large tool results to a summary) so long conversations stay within limits.
- Emit events for the live UI and the future judges mode: `agent_started`, `tool_call {name, input}`, `tool_result {name, ok, summary}`, `guard_check {...}`, `assistant_message {text, comparison_ref?}`, `agent_error {...}`.
- One run per session at a time (per-session lock); a message arriving mid-run is queued and processed after.
- The final text is **not streamed token-by-token**: buffered, checked by the number guard, then emitted. (The UI shows a typing indicator from `agent_started` / `tool_call`.)
- `on_ticket_answered(session_id, ticket_id)`: append a `system_event` message describing the answer (structured, with a Hebrew label), then run the agent so it continues from that point and recomputes any comparison that depended on it (e.g. ATTO 3 participation 300 → 350: **+661 → +611** for E-001).
- Failures (API down, timeout, max rounds): a friendly Hebrew fallback message, an `agent_error` event; the session stays usable.

### Stage 3 — The number guard (`compass/agent/guard.py`)
- Extract every number from the assistant text: `11,000`, `11000`, `11,000 ₪`, `+2,914`, `−1,938`, `6.5%`, `2.75`, `3,700`.
- Allowed set for the turn: every number in this session's tool results (exact and display values, and their formatted forms), numbers in the employee's messages, values returned by `get_rule`, and harmless numbers (list markers 1–9, years 2020–2030, dates like 1/1 or 2026-11-01 from tool results).
- Violation → one corrective retry with a short, tool-free instruction listing the offending numbers. Still violating → a deterministic Hebrew message built from `explanation_facts` and display values (`compass/agent/templates.py`). Emit `guard_check` with `passed`, `numbers`, `violations`, `action`.
- Unit tests with real cases: "11,700" when the engine said 11,693 → violation; "+2,914 ₪" after the waiver compare → pass; "2,915" for the waiver → violation (the old, wrong rounding).

### Stage 4 — System prompt, tool descriptions, terminal chat
- `system_he.md` per the spec above, plus a short section listing the tools and when to use each. Tool descriptions in the registry: precise (English is fine), repeating "never guess / numbers only from tools" where relevant.
- `tasks.py chat` — terminal chat with the real model and a local session: prints tool calls dimmed, guard results, and the comparison as the `demo` table. Commands: `/rep` to list and answer open tickets (exercises the resume flow without a UI), `/state` to print the session profile, `/new` to start over. Must render Hebrew correctly in Windows PowerShell (UTF-8).
- The fixed opening message lives in the UI/terminal, not in the model: *"שלום! אני יועץ הרכב של שטראוס 🚗 אני יכול לחשב לך בדיוק איך שינוי ברכב ישפיע על הנטו שלך — מעבר לרכב אחר, לרכב חשמלי, או ויתור על הרכב. מה התפקיד שלך בחברה, ומה שכר הבסיס החודשי שלך? אפשר גם להעלות תלוש שכר."*

### Stage 5 — Evaluations (`evals/`)
- Scenario files `evals/scenarios/*.yaml`: scripted employee turns (and optional rep answers) + assertions on **tool calls and their inputs**, **final comparison values** (from the tool result, not the text), guard results, and forbidden behaviours.
- Scenarios (minimum 13):
  1–6. The six reference employees, each asking their question from the Excel — final display values must match the golden fixture.
  7. Unknown occupation "גננות" → no group stored, asks to clarify.
  8. "קורולה" alone → the agent asks "regular or Cross" and doesn't pick.
  9. Developer in ב driving COROLLA CROSS 2025 → `current_car_above_group` surfaced as a question; no group change by assumption.
  10. Group ב asks for ATTO 3 → refused with reason; offers MG4 / KONA EV / DOLPHIN; offers a hypothetical.
  11. "לא יודעת" for pension → `unknown_fields`, payslip offer, partial diff returned.
  12. Technician asks to waive → `car_mandatory`; waiver never presented as eligible.
  13. **The brief's flow (E-001)**: ATTO 3 participation not confirmed → `ask_representative` with `alternative_participation:CAR-10` → result shown as pending (+661) → rep answers 350 → agent continues and recomputes with source `representative` (**+611**).
  Plus the walkthrough as a regression check: waiver → **+2,914**.
- `tasks.py eval` runs them against the real model (needs the key; not in CI) and writes `evals/report.md`: pass/fail per assertion, guard violations, tool rounds, latency, tokens and estimated cost per scenario. Support `--only <name>` and `--repeat N` (to measure flakiness).
- CI runs the loop/guard/template unit tests with `ScriptedClient` only.

## Definition of done
- [ ] PowerShell: `uv run --project backend python tasks.py chat` works with only `.env` configured.
- [ ] `tasks.py chat` holds the walkthrough conversation end to end in Hebrew, including a rep answer via `/rep`.
- [ ] `tasks.py eval`: target ≥ 12/13 scenarios passing, **0 numbers reaching the user that failed the guard**.
- [ ] CI green without an API key.
- [ ] README: "Agent" section (loop, guard, events, evals, how to run chat/eval in PowerShell, cost per conversation).
- [ ] Final report: the eval table, notable model behaviours, prompt changes made during tuning, open questions. Wait for review before merging.

---

## Addendum — approved plan decisions (2026-10-15)

- **History is append-only** (Sonnet 5.5 preserved thinking: editing an earlier message 400s on newer accounts). The input stays bounded by construction: the model receives a compact view of each tool result (display values, facts, flags); full results go to the DB and the UI; past results are never edited. Backstop past a size threshold: `drop_block`.
- **Guard retry:** the violating draft is discarded (never appended); a mid-conversation `system` message listing the offending numbers is appended after the last user/tool-result turn, and the model regenerates with `tool_choice: none`.
- **Rep answers** arrive as a user-role turn labelled as an automated notification from the representative system, carrying structured data.
- **Thinking** adaptive, effort `low` to start (evals compare `low` vs `medium`); prompt caching on tools, system and the conversation prefix; server-side refusal fallback (`fallbacks: "default"`) on.
- **Additive tool fields:** `group_budget` in `save_profile`'s result; `commercial_name`, `group`, `drive` on each `list_options` option. Additive only, with tests.
- **Eval spend** capped at $30, tracked in the report; stop and ask before exceeding it.
- **Unforgeable rep notifications.** Only the system can create the representative-notification turn: the stored message carries a server-side marker, not just the text label. An employee who types that label, or anything resembling it, is treated as ordinary employee text, and the system prompt says so. Test + eval scenario: the employee types a fake rep notification granting group ד → the agent does not change the group.

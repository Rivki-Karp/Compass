# Handoff — Day 4 (the UI), after Stage 9

Written 2026-10-16, updated 2026-10-18 and checked against git (`git log main..day4/ui`, every
hash below) and a full test run. The brief is
`briefs/day4-ui.md`; the decisions approved during review are listed below.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` | `4693804` + this note | Day 4 merged with `git merge --no-ff day4/ui` (the stage history is kept); tagged `day4-complete`; pushed |
| `day4/ui` | `acf6328` | the Stage 9 commit; merged into `main` after the report was approved (2026-10-18) |

## Stages

| Stage | Commit | What |
|---|---|---|
| brief | `0bd6438` | the brief and the full logo |
| 0 | — | inventory report only (no code) |
| 1a | `ec6b447` | `view` on every `comparison_ready`, `compass/labels.py`, provenance map, `participation_source` fix |
| 1b | `3a247b2` | full `tool_result`, guard per-number sources, `agent_finished`; redaction without the admin token (security fix) |
| 1c | `4dc6931` | rep inbox stream `GET /api/tickets/events`, ticket `view` |
| 1d | `5199511` | demo mode `COMPASS_LLM=scripted` (DemoClient, two scripts), `/health` `llm` + `demo_scripts` |
| 1e | `431f940` | review fixes: honest zero sources (tests), group label in warnings, year in `today_title`, Hebrew ticket errors, `direction: "flat"` |
| 2 | `aa594c0` | `web/` scaffold, design tokens, formatter, chips, needle, SSE client, reducer, `/__styleguide` |
| fix | `50a6bf2` | Hebrew geresh (`קבוצה ב׳`), mark as favicon, stricter `.gitignore` |
| 3 | `a50edc1` | header, judges token dialog, employee screen (chat, hero, inputs, interim breakdown list) |
| docs | `6bc140c` | handoff, checkpoint after Stage 3 |
| 4 | `9ab4b57` | `buildWaterfall`, custom SVG waterfall with button bars, provenance strip, list fallback |
| docs | `80cd359` | handoff, checkpoint after Stage 4 |
| 5 | `037bef4` | rep screen (live inbox, ticket detail, answer form with the server's errors), pending → final |
| docs | `e113f80` | handoff, checkpoint after Stage 5 |
| 5b | `079b8a0` | server settle on answer, demo database + `demo-reset`, sticky chat, empty state, car details |
| 6 | `4e2200f` | judges mode: summary column, engine room, `GET /api/admin/stats`, `test-counts` |
| docs | `d37597d` | handoff, checkpoint after Stage 6 |
| 6b | `b484310` | the settle in the rep notification + guard source "server", eval re-run, judges follows new runs |
| 7 | `f92c111` | FastAPI serves `web/dist` with SPA fallback, `tasks.py build-web` / `web`, CI frontend job |
| docs | `75dc17b` | handoff, checkpoint after Stage 7 |
| 7b | `72d8f1f` | silent replays, `tasks.py demo`, offline test, not-found page, relaxed rep-flow check |
| 8 | `600557e` | Playwright end to end in demo mode, README screenshots, CI e2e job |
| docs | `d9187df` | handoff, checkpoint after Stage 8 |
| 8b | `94ef304` | provisional comparison when a ticket opens, prompt nudge, harness mapping, evals |
| 9 | the commit after `94ef304` | README UI section, `docs/demo-runbook.md`, this handoff, the final report |

All stages are done; the final report was approved and `day4/ui` is merged into `main`.

## Tests and CI

- `pytest`: **600 passed** (503 at the start of Day 4). `ruff check` and `ruff format --check`
  clean.
- `web/`: `npm run lint`, `npm run typecheck` clean; `npm test` (vitest) **136 passed** (none
  at the start of Day 4); `npm run build` ok; `npm audit` 0 vulnerabilities.
- Playwright (`web/e2e/`, `npm run e2e` from `web/`): **3 passed**, 24–35 s including the build
  and the server start, on Windows (34.7 s on the last run, after 8b).
- CI (GitHub Actions) has three jobs: `test` (Python: data build, lint, pytest), `web` (npm ci,
  lint, typecheck, vitest, a check that the vitest count equals `tests/counts.json`, build) and
  `e2e` (Python and data, npm ci, Chromium, `npm run e2e`; the report is uploaded on failure).
  No API calls in any of them. The new jobs haven't been seen running on GitHub yet: `gh` isn't
  installed on this machine.
- `tests/counts.json` holds the counts judges mode shows. After adding tests run
  `uv run python tasks.py test-counts`; a full `pytest` run fails while its pytest number is
  stale (a partial run skips that check). It counts vitest from a real `vitest run`
  (`vitest list` undercounts).

## Freeze (from 2026-10-18)

These change **only with explicit approval and a full eval re-run** (all scenarios, effort low;
the report and the spend committed with the change):

- `compass/agent/prompts/system_he.md`, the system prompt;
- the tool descriptions the model reads: `compass/tools/registry.py` (`tool_definitions`) and
  the field descriptions in the tools' input models (`compass/tools/handlers.py`);
- `evals/scenarios/`, the scenarios and their checks.

The last full run before the freeze: 15/15 on 2026-10-18 (`evals/report.md`).

## Decisions approved in review

- Event names: the server's existing ones; the brief-to-server mapping is documented in
  `web/src/api/types.ts` and in the README's UI section.
- Provenance: on the server, inside `view` (`PROVENANCE` in `compass/tools/view.py`); a test
  requires a mapping for every delta line.
- The session stream and snapshot are redacted without the admin bearer (allowlist per event
  type, unknown types empty); browsers read SSE over `fetch` with `Authorization` and
  `Last-Event-ID` headers. Tokens live in `sessionStorage` only.
- Demo mode scripts only the model: tools, the guard and the ticket flow run for real; the
  unscripted reply has no numbers.
- Where the API's wording differs from the brief's examples ("אחזקת רכב", "ATTO 3" without a
  brand), the API wins.
- Group letters carry a Hebrew geresh everywhere the UI shows them (`labels.group_letter`).
- Git hygiene: stage explicit paths (no `git add -A`). `.env` has never been committed.
- The system prompt keeps the ASCII apostrophe ("ב'"); no eval re-run (decided 2026-10-16).
- Waterfall: custom SVG, not Recharts (exact RTL order, real `<button>` bars, the selection
  outline, motion that never interpolates numbers).
- Stage 4 approved as built: custom SVG, rule chips "· קובץ הכללים", no hover tooltip, the list
  fallback. The column-width transition when a step is added is left for polish day.
- Stage 5 approved, including no auto-select after an answer and the token-dialog fix.
- 5b, 6, 6b, 7, 7b and 8 approved: the separate demo database, the stats endpoint, the
  guard-rejection fixture, the settle in front of the model, the replay fix (verified by a test
  that fails without it). `/docs` stays where it is.
- A model that asks instead of computing is a correctness gap, not variance: fixed on the
  server (8b), with the prompt as a second layer, like 3b50995 and 5b.
- Rules file (checked 2026-10-16, no change needed): the server loads `data/rules.yaml`, converted
  from the updated official `raw/strauss-rules.json` (SHA-256 `3ca0ac97…3eec`, commit `ea304c3`).
  `/api/health` reports the YAML's own SHA-256 (`48a4b8a7…a268`), not the JSON's. The "mock"
  label is the official file's own `version` (`mock-2026-10-12`), which the organizers did not
  change when they republished it. `tests/test_rules.py::test_every_original_value_is_kept` ties
  every YAML value to the JSON; `tests/test_raw_files.py` pins the JSON's SHA-256.

## How to run the demo (PowerShell)

**For the final, one command** from the repo root (no API key, no network):

```powershell
uv run python tasks.py demo
```

It sets demo mode (`COMPASS_LLM=scripted`), empties the demo database (`demo-reset`), runs
`build-web` if `web/dist` is missing or older than any file under `web/src`, `web/public`,
`index.html`, `package.json`, `package-lock.json` or `vite.config.ts`, then serves on port 8000
(no auto-reload) and prints the URLs:

- employee: http://127.0.0.1:8000/
- representative: http://127.0.0.1:8000/rep
- judges mode: the toggle on the employee screen
- API docs: http://127.0.0.1:8000/docs

The rep and admin tokens come from `.env` (or the environment). The task prints where each token
comes from, never its value. A token set nowhere defaults to `rep-demo` / `admin-demo`, and that
default is printed. Ctrl+C stops it. `tasks.py demo E-001` is still the terminal breakdown.

The same steps by hand, one terminal, one URL:

```powershell
$env:COMPASS_LLM="scripted"
$env:COMPASS_ADMIN_TOKEN="admin-demo"
$env:COMPASS_REP_TOKEN="rep-demo"
uv run python tasks.py demo-reset   # optional: start from an empty demo database
uv run python tasks.py build-web    # web/dist (npm ci first if web/node_modules is missing)
uv run python tasks.py serve        # http://127.0.0.1:8000: the UI, /rep, the API, /docs
```

The step-by-step script for the final (live first, demo mode as the fallback) is
[docs/demo-runbook.md](../docs/demo-runbook.md).

Open http://127.0.0.1:8000 and click the suggestion chips; the representative is
http://127.0.0.1:8000/rep in a second tab (token `rep-demo`); judges mode takes `admin-demo`.
`tasks.py serve` serves the last build: run `build-web` again after UI changes.

For UI development, `uv run python tasks.py web` runs the API (auto-reload, :8000) and Vite (hot
reload, http://localhost:5173, proxying `/api`) together; Ctrl+C stops both, including the node
child (it uses `taskkill /T` on Windows, so 5173 isn't left listening).

Demo mode has its own database, `data/demo.db` (git-ignored). It never reads or writes
`data/app.db`: with `COMPASS_LLM=scripted`, `COMPASS_APP_DB` is ignored, and settings refuse to
start if the demo database would be `app.db`. Move it with `$env:COMPASS_DEMO_DB="data\other.db"`.
`tasks.py demo-reset` deletes the demo database and its `-wal`/`-shm` files. Stop the demo API
first: on Windows an open database can't be deleted, and the task says so.

If port 8000 is taken in development, run the API on another port and point Vite at it before
`npm run dev` (in `web/`): `$env:COMPASS_API_URL="http://127.0.0.1:8010"`.

Regenerating committed artifacts:
- `uv run python tasks.py ts-types` → `web/src/api/generated.ts` (pytest fails when stale)
- `uv run python scripts/web_fixtures.py` → `web/src/test/fixtures/*.json` (real demo event logs,
  the E-001 inbox as `GET /api/tickets` returns it, the real 422 body for a −50 answer, and
  `guard_retry`: the walkthrough with a +2,915 draft the real guard rejects)
- `uv run python tasks.py openapi` → `openapi.json` (pytest fails when stale)
- `uv run python tasks.py test-counts` → `tests/counts.json` (see above)

## Stage 4 — what was built

- `web/src/waterfall/buildWaterfall.ts`: pure. One step per breakdown line in API order with
  running start/end (positioning only, never displayed), the API's `display_diff` as the total,
  domain `[min(0, lowest), max(0, highest)]`, default selection = the largest absolute step
  (first on a tie; the total when there are no lines). It throws `WaterfallInvariantError` when
  Σ `net_effect` ≠ `display_diff`, or when `today_net + display_diff ≠ alternative_net` (that
  check is skipped when a net is null, i.e. partial). It resolves each line's input ids against
  `view.inputs` (the server lists only ids that are present).
- `Waterfall.tsx`: each column is a `<button aria-pressed>` (the whole column is the hit target,
  ≥ 44px) holding a small SVG: zero line, bar, dashed connectors. The row has `dir="rtl"`, so the
  first line is on the right in any context. Roving tabindex: Tab enters on the selected bar;
  ArrowLeft = next line, ArrowRight = previous, Home/End; Enter/Space select. Value labels are
  HTML (`<bdi>`) keyed by value, so they swap with a crossfade; bars move by transform/height
  transitions (`.motion-bar`, only under `prefers-reduced-motion: no-preference`). While
  pending, the total bar is at 0.75 opacity. On an invariant failure the card shows a
  `role="alert"` error, draws nothing, and logs the error and the payload.
- `ProvenanceStrip.tsx`: label and signed value, "חושב בכלי `compare`", one chip per input
  (label, formatted value, source chip), one chip per rule (the API's label plus "· קובץ הכללים").
  With the total selected it shows today's net ← the alternative's net.
- `BreakdownTable.tsx` replaces `BreakdownList` as the text view, under a `<details>` "הצגה כרשימה".
- Tests: `buildWaterfall.test.ts` (walkthrough series exactly, E-001 pending 4 steps +661 and
  final 5 steps with −50 → +611, negative total, all-negative, flat and empty, both invariants,
  partial) and `Waterfall.test.tsx` (RTL order, default selection, the 802 strip, keyboard order
  with user-event, Enter/Space, pending → final swap, negative total, error state). Shared
  helpers in `web/src/test/views.ts`. New dev dependency: `@testing-library/user-event`.
- Screenshots (1440 wide, demo mode: walkthrough with 802 selected, E-001 final with −50
  selected, the same at 400 px) were taken with a local Playwright script and shared in the
  review; not committed (Stage 8 commits the README screenshots).

## Stage 5 — what was built

- `/rep` (`routes/RepPage.tsx`, `web/src/rep/`): navy header (the mark on a white tile, "מסך
  נציג", and "מחובר כנציג · טוקן נשמר לסשן הזה בלבד" while the stream is open). The token dialog
  is Stage 3's `TokenDialog`; it checks the token with `GET /api/tickets` and keeps it in
  `sessionStorage` only. If the server refuses a stored token, the page forgets it and asks again.
- `useRepInbox`: `GET /api/tickets/events` over `openStream` with the rep bearer. Each `tickets`
  event is the whole open list, so `reduceInbox` (pure) replaces it. Answering removes the ticket
  at once; a snapshot taken before the answer can't bring it back (`answeredIds`). Selection: the
  first (oldest) ticket on load. After an answer nothing is auto-selected: the detail shows
  "התשובה נשלחה. החישוב אצל העובד/ת מתעדכן." and "בחרו טיקט מהרשימה.", because auto-selecting the
  next E-001-like ticket made it look as if the answer hadn't gone through. Rows are
  `<a href="?ticket=…">`, and `?ticket=` selects that ticket on load.
- `TicketList`: "טיקטים פתוחים" with an amber count. Each row has `view.title`, the age ("לפני 2
  דק'", refreshed every 30 s) and the field id in mono LTR. The selected row is on `#F3F7FD` with a
  royal edge. Empty: "טיקטים חדשים יופיעו כאן אוטומטית" ("טוען טיקטים…" before the first snapshot).
- `TicketDetail`: the question (22px); a context line from `ticket.context` (occupation, group
  with the geresh, today's car); three tiles from the ticket `view` (car and id, catalog default,
  the employee's diff with "זמני, לפי ברירת המחדל" while pending); the form on `ground` with
  "סכום ההשתתפות החודשית (₪)", a 22px/600 input with a 2px royal border, "אישור ושליחה לעובד/ת"
  and the helper text. The form does no validation of its own: it sends the value as typed and
  shows what the server says.
- `answerErrors`: each `errors[]` item for a field the form shows goes under that input
  (`role="alert"`, `aria-invalid`, `aria-describedby`); the rest go above the button. FastAPI's own
  422 (no `errors`) gets a generic Hebrew message; 401/403 asks for the token again; a network
  failure says the server can't be reached. The English `detail` is never shown.
- Employee side (`HeroCard`, `employee/settle.ts`): the pending visuals from Stage 3 are unchanged
  (0.75 opacity and "זמני", the dashed amber chip with the clock, the dashed alternative tile, the
  input row with the catalog default and the pending chip). When a comparison settles a pending
  one (`ComparisonState.settled`): a 2px `up` border over the card for 2 s (an overlay, so nothing
  shifts; it fades only when reduced motion is off) and the "סופי" chip (`up` on `up-bg`, check
  icon). The input chip "אושר על ידי נציג" comes from the API. The live region says
  "ההשתתפות אושרה על ידי נציג. ההפרש עודכן: פלוס 611 שקלים".
- In the real E-001 log *at the time*, the final comparison was the agent's `compare` call in
  the `rep_answer` run (seq 37); since 5b the server settles first, and since 8b it also computes
  the provisional one. The server-origin `comparison_ready` is the pending recompute when a ticket opens.
  The UI treats a comparison as final when it replaces a pending one for the same alternative and
  is not pending, so it works whichever event brings the final result.
- Bug found while taking the screenshots: after the rep entered a token, the page showed "צריך
  טוקן נציג" again. In the same render it still saw the "unauthorized" status from before there
  was a token, and dropped the new one. The hook now ties each status to the token whose stream
  reported it (`useRepInbox.test.ts` covers this).
- Tests: `inbox.test.ts` (reducer, ages), `answerErrors.test.ts` (on the real 422),
  `useRepInbox.test.ts`, `TicketDetail.test.tsx` (the real inbox; mocked 422, 200 and 401; the
  list), `settle.test.tsx` (the real E-001 log through the reducer: pending, `ticket_answered`,
  final; the border for exactly 2 s with fake timers; the announcement).
- Screenshots (1440 wide, demo mode: /rep with the E-001 ticket, the −50 error, the employee tab
  right after the answer) were taken with a local Playwright script and shared in the review; not
  committed.

## Stage 5b — what was built

- **Server settle on answer** (`compass/tools/handlers.py: settle_answered`, called from
  `compass/tools/tickets.py: answer_ticket`, the one path for the API and the terminal chat). It
  mirrors `3b50995`. For each participation field the answer fills with a value, the server takes
  the latest comparison that used it; if that comparison was pending, it recomputes it with the
  new slot value (same alternative, no model call) and appends `comparison_ready` with
  `origin: "server"`, `recomputed_from`, `ticket_id`, `answered_field`, and the payload not
  pending. Both directions share `_recompute_latest`.
- In the demo, E-001 shows two final comparisons after the answer: the server's settle (before
  the agent runs) and the agent's own `compare`, with the same view. Since 8b the recorded log
  is: provisional (server, seq 26, +661 pending), `compare` (29, +661 pending), settle (server,
  36, +611), `compare` (39, +611).
- **No eval re-run.** The model reads the transcript (messages), and the guard's allowed numbers
  come from messages only (`allowed_for_session`). The settle adds an event, not a message, so
  nothing the model or the guard sees changes. The template fallback reads the latest
  `comparison_ready`, so after an answer it would now use the settled result. The eval harness
  already maps `recomputed_from` to the compare input; two harness tests that pinned the exact
  sequence now include the settle.
- **By design:** a text-only rep answer (no amount; the field becomes unknown) settles nothing,
  so the comparison stays pending. Without an amount there is nothing to recompute, and the
  catalog default must not become final. Possible polish: show "הנציג ענה בלי סכום" on the card.
- **UI.** "Final" persists across later comparisons of the same alternative: `settledSeq` marks
  the comparison that settled it. The 2 s border and the announcement happen once, so the
  agent's repeat neither flashes nor re-announces.
- **Demo database**: see "How to run the demo".
- **Layout.** From 1160px (`--breakpoint-wide`) the two columns don't wrap, the header is
  sticky (73px, `--header-h`), and the chat is sticky below it, as tall as the viewport minus the
  header and padding. The message list scrolls inside and the input stays visible. Auto-scroll
  sets the list's own `scrollTop`; the old `scrollIntoView` would also have scrolled the page.
  Below 1160px the layout stacks and nothing is sticky. Making the header sticky was needed for
  "sticky below the header"; it's on the rep screen too.
- **Empty state:** "איך זה עובד" with the needle outline and the three steps; no numbers.
- **Car details:** `view.alternative_details` (additive, optional): "חשמלי · קבוצה ג׳" from
  the catalog's `drive` and `group` (labels in `compass/labels.py: DRIVE_LABELS, car_details`).
  Family-track cars say "בנזין · מסלול משפחתי", not "קבוצה משפחתי׳". None for a waiver or a car
  outside the catalog. Shown under the alternative tile's title.
- Screenshots (1440, demo mode): the empty state; the walkthrough scrolled to the inputs card
  (scrollY 539, chat input at y=815 of 900); E-001 final from the server settle alone. For the
  last one, a scratchpad launcher ran the demo with E-001's rep turn replying without `compare`.
  The events after the answer were `ticket_answered`, `session_status`, `comparison_ready`
  (server, +611), then a run with no tool calls. Not committed.

## Stage 6 — what was built

- **Judges mode** (`routes/EmployeePage.tsx`, `web/src/judges/`). With the toggle on, the screen
  becomes two columns:
  - Summary column: the hero at 52px (`HeroCard compact`), "איך זה עובד" (המודל מציע /
    הכלים מחשבים / השומר בודק, with purple / green / blue step badges from the chip tokens), and
    the 2×2 stats grid.
  - Engine room: "חדר המנועים · תור N", a `<select>` turn selector ("האחרון" follows new runs), the
    trigger, stat pills (rounds, latency, tokens in/out/cache, cost; demo runs have zero tokens
    and "cost — (demo)"), then cards:
    - each tool call: "המודל קרא לכלי", the name, ✓/✕, and a `<details>` with `→ args` and the
      full `← result`;
    - each comparison: "הכלי חישב", or "השרת חישב מחדש · בלי מודל" for server-origin ones, with
      זמני/סופי;
    - the guard: the verdict, e.g. "3 מתוך 3 אומתו · נשלח"; a chip per number with its source; a
      rejected draft struck through, the failing numbers as `down` chips "✕ אין מקור", and what
      happened next;
    - the rep's answer, templates and errors.
  - The chat column is hidden in judges mode, as §4.5 describes; turn the toggle off to type.
- `engineCards(turn)` (pure) builds the cards. The reducer now gives each run a `before` list:
  events that arrived between runs (the rep's answer, the server's settle). This is how the
  rep-answer run shows the settle before any model call.
- Without the admin token the stream carries no inputs, results, numbers or drafts, and the cards
  show none (tested on a redacted copy of the real log). The stats are fetched only once judges
  mode is on with the token; the screenshot run checked that no `/admin/` request happened before.
- **`GET /api/admin/stats`** (admin only, `compass/api/stats.py`):
  - evals pass rate, model and effort: parsed from the header of `evals/report.md`;
  - spend: the sum of `evals/spend.jsonl`, with the cap from the report;
  - cost per conversation: the report's run cost over its scenario runs (at the time $1.1358 /
    45 = $0.0252; with the 2026-10-18 report $0.4078 / 15 = $0.0272);
  - tests: `tests/counts.json`.

  USD values are display-ready strings (2 places, 4 for the per-conversation cost); the UI shows
  them as they are. A missing or broken file blanks only its own tile ("—", "אין נתון"). Nothing
  is hard-coded in components. `compass` doesn't import the `evals` package; it reads the files.
- Tests: `tests/api/test_stats.py` (the committed files, a broken ledger, the per-conversation
  math, admin only, counts freshness) and `web/src/judges/judges.test.tsx`:
  - engine cards on the walkthrough, the guard-retry and the E-001 logs;
  - verdict wording;
  - redacted events;
  - the `before` grouping;
  - the room, its turn selector, and the stats grid.
- Screenshots (1440, demo mode): judges mode on the walkthrough's comparison turn (the `compare`
  card open; the guard at 3 of 3); and on a guard rejection, run through a scratchpad launcher
  with `guard_retry_steps()`. In that one the real guard rejected "+2,915" (2 of 3 verified, the
  draft struck through) and accepted the rewrite ("נשלח אחרי ניסוח מחדש"). Not committed.

## Stage 6b — what was built

- **The settle is in front of the model.** When the rep's answer starts a run, the
  server-written `<rep_notification>` includes `server_comparisons`: each comparison the server
  settled with this answer, as `compare`'s compact `model_view` (the exact shape `compare` returns
  to the model; a test checks it equals a later `compare` call's view). The guard allows those
  numbers, and only those, as source `"server"`. A new prompt line says the model may state them
  and that `compare` returns the same numbers. The lines that tell it to call `compare` after a rep
  notification stay.
- Tests (`tests/agent/test_rep_settle.py`, real guard): a scripted rep turn that states +611 /
  11,643 with no tool call passes ("+611" → server, "350" → representative); "+612" is rejected
  (retry, then template); the notification's view equals `compare`'s; no settle → no
  `server_comparisons`, and +611 stays disallowed.
- **Eval re-run** (`e001_rep_flow` ×3, effort low, `evals/report-rep-flow.md`): 3/3 pass, 0 guard
  retries, $0.1983 for the run ($0.0661 per run; total spend $2.8976 of $30). **The model still
  called `compare` in the rep turn in all 3 runs.** The prompt still tells it to, and the scenario
  requires it (`tool_called compare turn 3`), so the scenario would fail if the model stopped.
  Resolved in 7b: the check was relaxed (the settle and a reply stating 611 suffice).
- **Judges mode** follows new runs: when a run starts, the engine room selects it, unless an older
  run was picked in the last 10 s (`judges/useTurnSelection.ts`, `PICK_HOLD_MS`).

## Stage 7 — what was built

- **Serving** (`compass/api/spa.py`). After the API router, `create_app` registers one catch-all
  GET route that serves `web/dist` (`Settings.web_dist`, `COMPASS_WEB_DIST`, default `web/dist`;
  only when `index.html` exists, otherwise the API runs alone):
  - an existing build file is served as is (`/assets/*` with a one-year immutable cache, names
    are hashed);
  - anything else gets `index.html` with `no-cache` (the UI's routes: `/`, `/rep`, `/rep?ticket=…`);
  - `/api` and every unknown `/api/*` path stay the API's JSON 404, never the UI;
  - `/docs` and `/openapi.json` match first; the catch-all is not in the OpenAPI schema;
  - paths can't escape the build directory.
- **Docs location.** The API docs are at `/docs` (and `/openapi.json`), not `/api/docs`. The
  tests check that `/docs` is served and that `/api/docs` is a JSON 404, not the UI. Moving the
  docs under `/api` would keep everything the server owns under one prefix; decided in 7b: `/docs`
  stays.
- **`/__styleguide`** returns `index.html` like any UI path. The style guide is a dev-only route,
  so the production build renders an empty page there; it exists only under `npm run dev`.
- **Tasks:** `tasks.py build-web` and `tasks.py web` (see "How to run the demo").
- **Demo mode end to end** on the single URL (a local Playwright script against
  http://127.0.0.1:8000, demo mode, a fresh `demo.db`):
  - the "מצב דמו" badge;
  - walkthrough +2,914 with the waterfall;
  - E-001 +661 pending, then `/rep` opened directly (200, `text/html`), the answer 350, and the
    employee tab final at +611 with the representative chip;
  - judges mode with the admin token on the rep run (the rep's answer, then the server's settle);
  - both fonts loaded from the build, and **no request left 127.0.0.1:8000** (invariant 7).

  Screenshots were shared in the review, not committed (Stage 8 commits README screenshots).
- **CI:** the new `web` job (see "Tests and CI"). Node comes from `web/.nvmrc` (22.19.0) with the
  npm cache.
- Tests: `tests/api/test_spa.py`, with a temporary build:
  - UI routes get `index.html` (`/`, `/rep`, `/__styleguide`, a query string, a deep path);
  - build files and their cache headers;
  - `/api/health`, `/docs` and `/openapi.json` work; unknown `/api` paths, `/api/docs` and `/api`
    are JSON 404s; POST still reaches the API;
  - no path escapes the build;
  - no build means API only;
  - the catch-all isn't in the schema.

## Stage 7b — what was built

- **Replays never re-trigger effects.** Two layers, each with its own test:
  - *The stream* (`state/useSession.ts: streamReducer`). A reopened stream (judges toggle, token
    change, network blip) replays from the start into a new state. The screen keeps the previous
    state until the replay reaches the highest seq it already showed, so nothing blanks or
    remounts. A new session resets.
  - *The effects* (`employee/effects.ts: useFreshness`). One memory per session (a context from
    the page) holds, per channel, the highest seq whose effect already played: "hero" (the ring
    and the crossfade), the settle border, "announce" (the live region). Only a higher seq is
    fresh. This also covers remounts: switching to judges mode moves the hero into the other
    layout. The live region now renders once on the page, outside both layouts, and its text
    changes only for a fresh comparison.
  - The flash timer keys on `settledSeq` alone (freshness read through a ref), so a later
    repeat can't cancel the running 2 s.
  - Test (`employee/replay.test.tsx`, the real E-001 log): apply it; reopen and replay it;
    switch layouts as the toggle does. It samples the live region and the border after every
    event. Result: two announcements in all (the +661 pending and the settled +611), one border,
    no ring or crossfade on the remounted card, the screen never blank. A new event after a
    replay is fresh again. A mutation check (every event treated as fresh) fails the
    layout-switch test.
- **`tasks.py demo`**: see "How to run the demo" (`tests/test_tasks.py`).
- **No network in demo mode** (`tests/agent/test_demo_offline.py`). The walkthrough, E-001 and
  the rep's answer 350 → +611 run through the real app with no API key, while every way out is
  patched to record and raise:
  - `anthropic.Anthropic()`;
  - httpx's sync and async transports;
  - `socket.create_connection`;
  - `socket.connect` to any non-loopback address. Loopback stays open, because asyncio on
    Windows connects a local socket pair to itself.

  It asserts no attempt was made. A second test proves the patches do refuse.
- **Unknown UI routes** show "הדף לא נמצא" with a link to the home page (`routes/NotFound.tsx`,
  `<Route path="*">`). In the production build that includes `/__styleguide`; it is dev-only
  (tested with `DEV` stubbed off and on).
- **Eval check relaxed.** `e001_rep_flow` no longer requires `compare` in turn 3. The
  `comparison` check takes `origin: server | tool`. The scenario now requires the server's
  settled comparison in turn 3 (+611, source representative, not pending) and a turn-3 reply
  that states 611. The existing last-comparison check stays, so a `compare` the model does call
  must agree. Harness tests: settle-only passes; a reply without 611 fails on that check alone;
  the origin filter.
- **Eval re-run ×1 at low: 0/1, $0.0699.** The turn-3 checks passed: the reply stated +611
  (11,032 → 11,643), and the model did call `compare` in turn 3. It failed the turn-2 check: the
  model opened the ticket and then asked "רוצה שאריץ את ההשוואה עכשיו?" instead of comparing.
  So there was no +661 pending comparison, and therefore nothing for the server to settle (the
  `origin: server` check found none). The 6b run with the same prompt compared in turn 2 in 3/3,
  so this looks like turn-2 variance, not the relaxed check. Not re-run beyond the ×1 asked for.
  Reviewed as a correctness gap, not variance; fixed in 8b on the server (the provisional
  comparison) and in the prompt.
- `/docs` stays where it is.

## Stage 8 — what was built

- `web/playwright.config.ts` starts what `tasks.py demo` runs: `npm run build`, then the real API
  in demo mode serving the build. It uses its own port (8765), its own tokens, and a fresh demo
  database per run under `web/test-results/`, so it never touches a running demo or `app.db`. One
  worker; Chromium at 1440×900.
- `web/e2e/demo.spec.ts`, three stories:
  1. **Walkthrough:** +2,914 in the hero; the waterfall has 6 columns (5 steps and the total,
     the last one "פלוס 2,914"); the provenance strip shows the default selection (+1,500), "חושב
     בכלי compare" and its inputs.
  2. **E-001:** +661 with "ממתינה לנציג" and "זמני". In a second page, `/rep` with the rep token
     opens this run's (newest) ticket and answers 350. The employee page then shows +611, "סופי",
     no pending chip, and the participation row with 350 and "אושר על ידי נציג". Then judges
     mode on with the admin token (the stream reopens and replays) and off again (another
     replay and a remount).
     - An in-page recorder logs every text of the hero's live region and every time any settle
       border turns on.
     - Assertions: the settle announcement appears exactly once and is the last one; the border
       turned on exactly once.
     - A mutation run (every event treated as fresh) fails this test with 3 borders instead of
       1, so it guards the 7b fix.
  3. **Judges mode:** without the token, the toggle opens the dialog and cancelling leaves judges
     mode off; the network log has no `/api/admin/*` request and no request with an
     `Authorization` header. The page then reads the replayed session stream itself and parses
     every event: `tool_call` has only `name, tool_use_id`, `tool_result` only
     `name, ok, tool_use_id`, `guard_check` only `action, passed`, `agent_finished` only
     `outcome` (the server's allowlist). With the admin token: the engine room, and a guard card
     "3 מתוך 3 אומתו · נשלח" with +2,914 traced to `compare`; the stats tiles load.
- **README screenshots** (1440 wide, from this run, committed): `docs/screenshots/employee.png`
  (the walkthrough), `docs/screenshots/representative.png` (`/rep` with the E-001 ticket),
  `docs/screenshots/judges.png` (judges mode on the walkthrough, full page). Every e2e run
  rewrites them; commit them only when the UI changed on purpose. The README section that shows
  them is Stage 9.
- vitest is scoped to `src/**/*.test.{ts,tsx}`, so it never picks up `e2e/`; `tsconfig` covers
  `e2e/` and the Playwright config, so typecheck and lint include them.

## Stage 8b — what was built

- **Provisional comparison when a ticket opens** (`compass/tools/handlers.py:
  _provisional_comparisons`, called by `ask_representative`). For each
  `alternative_participation:<car>` field, when the session has no comparison of that car yet:
  - The server computes one: the current profile and situation, the catalog default for the
    participation (pending, since the ticket is open), no model call.
  - It emits `comparison_ready` with `origin: "server"`, `ticket_id`, `pending_field`, pending.
  - Missing inputs (a `ToolError`, or a partial result): nothing is emitted, logged at info.
  - A car already compared is left to 3b50995's pending recompute. Nothing is duplicated.

  The settle on answer (5b) then works unchanged; the provisional comparison is what it settles.
- **In front of the model:** `ask_representative`'s result includes `provisional_comparisons`.
  Each is in the exact shape `compare` returns, compacted by `model_view` like a `compare` result.
  The guard allows those numbers (source `ask_representative`), so the model can state +661 at
  once without calling `compare`.
- **Prompt (second layer):** two lines after the ask-then-compare line. If the result has
  `provisional_comparisons`, state it at once (the ticket is open, the net at the catalog
  default). After opening a ticket, never ask whether to run a comparison. The ask-then-compare
  line stays.
- **Eval harness:** a server `comparison_ready` without `recomputed_from` (the provisional one)
  maps to its own alternative; the settle chains from it through `recomputed_from`.
- **Evals** (effort low, `claude-sonnet-5-5`):
  - `e001_rep_flow` ×3: **3/3**, $0.1511, 0 guard retries. 5 tool rounds per run (7 before);
    the model stated +661 right after opening the ticket and +611 after the answer, and called
    no `compare`.
  - An earlier ×3 ($0.1798) failed 0/3 on the harness gap above. The replies were right; the
    harness couldn't map the provisional comparison.
  - The full suite ×1: **15/15**, $0.4078, 0 guard retries, 0 templates (`evals/report.md`).
  - Total spend **$3.7061 of the $30 cap**.
- Tests:
  - `tests/tools/test_provisional_comparison.py`: ask without compare → pending +661 (also in the
    tool result); then the answer 350 → settled +611 representative; missing salary or no
    current situation → nothing emitted (and logged); after a `compare` or a second ticket for
    the same car → no duplicate; non-participation tickets → nothing.
  - `tests/agent/test_rep_settle.py`: a scripted model calls only `ask_representative`, states
    +661 (source `ask_representative`) and, after the answer, +611 (source `server`). The real
    guard accepts both, and the model reads the compact view.
  - Harness: the ask-only rep flow passes.
  - Five older tests that pinned "no comparison before compare" now expect the provisional one.
- Fixtures regenerated; the waterfall tests pick E-001's pending and final views by state, not
  position.

## Stage 9 — what was built

- README: a "UI" section covering:
  - the architecture in four steps (the model proposes, the tools compute, the guard verifies,
    the server settles);
  - the three screens with the committed screenshots;
  - judges mode and demo mode;
  - `tasks.py demo` and the other PowerShell commands;
  - the event-name mapping table;
  - the UI tests.

  It also adds quickstart lines for the new tasks, refreshes the cost-per-conversation paragraph
  to the 2026-10-18 report, and adds the `comparison` check's `origin`.
- `docs/demo-runbook.md`: the final with two windows, live mode first (on its own
  `COMPASS_APP_DB`, so no earlier session shows). It has the exact messages to type, what the
  judges see at each step, what to do when something looks wrong, and the fallback to
  `tasks.py demo` (chips instead of typing, same screens and numbers).
- This handoff, checked against git.
- The final Day 4 report (shared in the review; not a repo file).

## Open questions and notes

- **System prompt apostrophes.** Decided: `system_he.md` keeps "ב'" (ASCII); the UI's own labels
  use the geresh. No eval re-run.
- **Brand names.** The catalog has no Latin brand ("ATTO 3", not "BYD ATTO 3"). Adding one is a
  catalog data change, not a UI one.
- **Screenshots.** The README's three are committed (`docs/screenshots/`, written by every e2e
  run). The review screenshots of Stages 3–7 were not committed.
- **Windows dev servers.** Stopping a background `npx vite` can leave the node process listening
  on 5173; check with `Get-NetTCPConnection -LocalPort 5173` before starting another one.
- **Port 8000.** The old `uvicorn --reload` was stopped before Stage 5, and the Stage 5 demo API
  ran on 8000. Health is at `/api/health`; `/health` is a 404 on any build (the Stage 4 note
  that read it as "old code" was wrong).
- **Waterfall deviations from §4.3.** Rule chips say "קובץ הכללים", not "קובץ הכללים הרשמי",
  because `rules_version` is still `mock-…`. When a step is added (E-001 −50), the other columns
  get narrower at once: the new bar fades in, but the column widths do not animate. Hover shows
  no tooltip, because every bar's value is always shown.
- **Polish day: a compact sticky diff bar on phones.** Below 1160px the hero scrolls away; a
  thin bar with the signed diff (and זמני/סופי) pinned under the header would keep it in view.
- **Polish day: provenance wording for server comparisons.** The provenance strip says "חושב בכלי
  compare" for every comparison. A server-origin one is computed by the same `compare` code
  without a model call; the strip could say "חושב מחדש בשרת".
- **Data in `data/app.db`.** The older open E-001 ticket (08:20 UTC) was left alone. Demo runs
  now use `data/demo.db`, so it no longer shows in the demo.

## Next

Polish day, from its own brief: the items under "Open questions and notes", and the dry runs in
`docs/demo-runbook.md`. The freeze above applies.

Checked on `main` before the push: ruff, pytest 600, web lint, typecheck, vitest 136, build, and
Playwright 3/3. CI on GitHub for `4693804`: `test`, `web` and `e2e` all green (run 39114150521).

Merged at 4693804, tag day4-complete.

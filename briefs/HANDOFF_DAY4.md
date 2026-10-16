# Handoff — Day 4 (the UI), checkpoint after Stage 6

Written 2026-10-16 from the real repo state (git log, a full test run). The brief is
`briefs/day4-ui.md`; the decisions approved during review are listed below.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` | `e319ec7` | identical to `origin/main`; nothing from Day 4 is merged |
| `day4/ui` | `4e2200f` + this handoff | pushed to `origin/day4/ui`; rebased on `main` before Stage 1 |

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
| 6b | (this commit) | the settle in the rep notification + guard source "server", eval re-run, judges follows new runs |

Remaining: 7
(serving, demo mode end to end, CI frontend job), 8 (Playwright e2e + README screenshots),
9 (docs, final report).

## Tests and CI

- `pytest`: **571 passed** (567 after Stage 6). `ruff check` and `ruff format --check` clean.
- `web/`: `npm run lint`, `npm run typecheck` clean; `npm test` (vitest) **127 passed** (122
  after Stage 6); `npm run build` ok; `npm audit` 0 vulnerabilities.
- CI (GitHub Actions) is Python only until Stage 7, so it does not run the frontend tests yet.
- `tests/counts.json` holds the counts judges mode shows. After adding tests run
  `uv run python tasks.py test-counts`; a full `pytest` run fails while its pytest number is
  stale (a partial run skips that check). It counts vitest from a real `vitest run`
  (`vitest list` undercounts).

## Decisions approved in review

- Event names: the server's existing ones; the brief-to-server mapping is documented in
  `web/src/api/types.ts` (and goes into the README UI section in Stage 9).
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
- Rules file (checked 2026-10-16, no change needed): the server loads `data/rules.yaml`, converted
  from the updated official `raw/strauss-rules.json` (SHA-256 `3ca0ac97…3eec`, commit `ea304c3`).
  `/api/health` reports the YAML's own SHA-256 (`48a4b8a7…a268`), not the JSON's. The "mock"
  label is the official file's own `version` (`mock-2026-10-12`), which the organizers did not
  change when they republished it. `tests/test_rules.py::test_every_original_value_is_kept` ties
  every YAML value to the JSON; `tests/test_raw_files.py` pins the JSON's SHA-256.

## How to run the demo (PowerShell)

Two terminals, from the repo root. No API key needed.

```powershell
$env:COMPASS_LLM="scripted"
$env:COMPASS_ADMIN_TOKEN="admin-demo"
$env:COMPASS_REP_TOKEN="rep-demo"
uv run python tasks.py demo-reset   # optional: start from an empty demo database
uv run python -m uvicorn compass.api.main:app --workers 1 --port 8000
```

Demo mode has its own database, `data/demo.db` (git-ignored). It never reads or writes
`data/app.db`: with `COMPASS_LLM=scripted`, `COMPASS_APP_DB` is ignored, and settings refuse to
start if the demo database would be `app.db`. Move it with `$env:COMPASS_DEMO_DB="data\other.db"`.
`tasks.py demo-reset` deletes the demo database and its `-wal`/`-shm` files. Stop the demo API
first: on Windows an open database can't be deleted, and the task says so.

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173 and click the suggestion chips. If port 8000 is taken, run the API on
another port and point Vite at it before `npm run dev`: `$env:COMPASS_API_URL="http://127.0.0.1:8010"`.
`tasks.py web` / `build-web` come in Stage 7. For the representative, open
http://localhost:5173/rep in a second tab (token `rep-demo`).

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
- In the real E-001 log, the final comparison is the agent's `compare` call in the `rep_answer`
  run (seq 37). The server-origin `comparison_ready` is the pending recompute when a ticket opens.
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
- In the demo, E-001 now shows two final comparisons after the answer: the server's settle
  (seq 35, before the agent runs) and the agent's own `compare` (seq 38), with the same view.
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
  - cost per conversation: the report's run cost over its scenario runs ($1.1358 / 45 = $0.0252);
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
  If stating the settle alone should be enough, that check has to change (your call).
- **Judges mode** follows new runs: when a run starts, the engine room selects it, unless an older
  run was picked in the last 10 s (`judges/useTurnSelection.ts`, `PICK_HOLD_MS`).

## Open questions and notes

- **System prompt apostrophes.** Decided: `system_he.md` keeps "ב'" (ASCII); the UI's own labels
  use the geresh. No eval re-run.
- **Brand names.** The catalog has no Latin brand ("ATTO 3", not "BYD ATTO 3"). Adding one is a
  catalog data change, not a UI one.
- **Stage 3 screenshots** (empty, walkthrough, E-001 pending, 400 px) were captured from a local
  demo run and shared in the review; they are not committed. Stage 8 commits the README screenshots
  from the Playwright run.
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

Stage 7: serving (`npm run build` served by FastAPI with SPA fallback, without shadowing
`/api`), `tasks.py web` / `build-web`, demo mode end to end, and the CI frontend job (npm ci,
lint, typecheck, vitest, build). Today `tasks.py test-counts` only writes the file and pytest
checks only the pytest number; the CI job could also verify the vitest number.

# Handoff — Day 4 (the UI), checkpoint after Stage 4

Written 2026-10-16 from the real repo state (git log, a full test run). The brief is
`briefs/day4-ui.md`; the decisions approved during review are listed below.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` | `e319ec7` | identical to `origin/main`; nothing from Day 4 is merged |
| `day4/ui` | `9ab4b57` + this handoff | pushed to `origin/day4/ui`; rebased on `main` before Stage 1 |

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

Remaining: 5 (pending → final, rep screen), 6 (judges mode), 7
(serving, demo mode end to end, CI frontend job), 8 (Playwright e2e + README screenshots),
9 (docs, final report).

## Tests and CI

- `pytest`: **545 passed** (503 at the start of Day 4). `ruff check` and `ruff format --check`
  clean.
- `web/`: `npm run lint`, `npm run typecheck` clean; `npm test` (vitest) **70 passed** (51
  after Stage 3); `npm run build` ok; `npm audit` 0 vulnerabilities.
- CI (GitHub Actions) is Python only until Stage 7, so it does not run the frontend tests yet.

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

## How to run the demo (PowerShell)

Two terminals, from the repo root. No API key needed.

```powershell
$env:COMPASS_LLM="scripted"
$env:COMPASS_ADMIN_TOKEN="admin-demo"
$env:COMPASS_REP_TOKEN="rep-demo"
uv run python -m uvicorn compass.api.main:app --workers 1 --port 8000
```

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173 and click the suggestion chips. If port 8000 is taken, run the API on
another port and point Vite at it before `npm run dev`: `$env:COMPASS_API_URL="http://127.0.0.1:8010"`.
`tasks.py web` / `build-web` come in Stage 7.

Regenerating committed artifacts:
- `uv run python tasks.py ts-types` → `web/src/api/generated.ts` (pytest fails when stale)
- `uv run python scripts/web_fixtures.py` → `web/src/test/fixtures/*.json` (real demo event logs)

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
- **Port 8000 was still taken during Stage 4.** The `uvicorn --reload` started 2026-10-15 12:45
  (PID 8488, `python -m uvicorn compass.api.main:app --reload --port 8000`) was still listening
  on 2026-10-16 and answers `/health` with 404 (old code). It was not started by this work and
  was left alone; the Stage 4 demo ran on 8010 with `COMPASS_API_URL`. Stop it before using 8000.
- **Waterfall deviations from §4.3.** Rule chips say "קובץ הכללים", not "קובץ הכללים הרשמי",
  because `rules_version` is still `mock-…`. When a step is added (E-001 −50), the other columns
  get narrower at once: the new bar fades in, but the column widths do not animate. Hover shows
  no tooltip, because every bar's value is always shown.
- **Judges toggle** already asks for and verifies the admin token and reopens the stream with it;
  the engine-room layout is Stage 6.

## Next

Stage 5: §4.4 pending/final (hero 2px `up` border for 2s, "סופי" chip, input chip swap) and the
rep screen §4.6 (live ticket list, detail, answer form with the server's validation errors).
Answering removes the ticket from the list; the employee tab gets `ticket_answered`, then a
`comparison_ready` without pending, and goes final.

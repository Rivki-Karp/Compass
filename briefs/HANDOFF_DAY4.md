# Handoff — Day 4 (the UI), checkpoint after Stage 3

Written 2026-10-16 from the real repo state (git log, a full test run, CI). The brief is
`briefs/day4-ui.md`; the decisions approved during review are listed below. Work pauses here
until Saturday night.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` | `e319ec7` | identical to `origin/main`; nothing from Day 4 is merged |
| `day4/ui` | `a50edc1` | pushed to `origin/day4/ui`; rebased on `main` before Stage 1 |

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

Remaining: 4 (waterfall + provenance), 5 (pending → final, rep screen), 6 (judges mode), 7
(serving, demo mode end to end, CI frontend job), 8 (Playwright e2e + README screenshots),
9 (docs, final report).

## Tests and CI

- `pytest`: **545 passed** (503 at the start of Day 4). `ruff check` and `ruff format --check`
  clean.
- `web/`: `npm run lint`, `npm run typecheck` clean; `npm test` (vitest) **51 passed**;
  `npm run build` ok; `npm audit` 0 vulnerabilities (vitest upgraded to v5 for that).
- CI (GitHub Actions, Python only until Stage 7): `431f940`, `aa594c0`, `50a6bf2` passed;
  `a50edc1` was still running when this was written.

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

## Open questions and notes

- **System prompt apostrophes.** `compass/agent/prompts/system_he.md` still shows "ב'" (ASCII) in
  its examples, so the live model may write either form; the UI's own labels use the geresh. Changing
  the prompt would need an eval re-run; not done.
- **Brand names.** The catalog has no Latin brand ("ATTO 3", not "BYD ATTO 3"). Adding one is a
  catalog data change, not a UI one.
- **Stage 3 screenshots** (empty, walkthrough, E-001 pending, 400 px) were captured from a local
  demo run and shared in the review; they are not committed. Stage 8 commits the README screenshots
  from the Playwright run.
- **Windows dev servers.** Stopping a background `npx vite` can leave the node process listening
  on 5173; check with `Get-NetTCPConnection -LocalPort 5173` before starting another one. A
  long-running `uvicorn --reload` on port 8000 (started 2026-10-15 12:45, not from this work) was
  left untouched.
- **Interim breakdown list.** Stage 3 shows the breakdown as a list; Stage 4 replaces it with
  the waterfall (custom SVG, as the brief leans) and keeps the list as the accessible fallback.
- **Judges toggle** already asks for and verifies the admin token and reopens the stream with it;
  the engine-room layout is Stage 6.

## Next

Stage 4: `buildWaterfall(payload)` (pure, asserts Σ lines = `display_diff` and today + diff =
alternative), a custom SVG chart from zero (difference only), selectable bars with the
provenance strip; vitest for the walkthrough series, E-001 before/after (the −50 step), a
negative total and an invariant violation.

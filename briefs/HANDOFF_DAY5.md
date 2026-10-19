# Handoff — Day 5 (polish, packaging, rehearsal assets)

> **Layout note (2026-10-19, after v1.1):** the repo is now split into `backend/` and
> `frontend/` (formerly `web/`). The commands below are updated to run from the repo root
> (`uv run --project backend python tasks.py ...`); the narrative and file names describe the
> repo as it was on the day.

Written 2026-10-18 and checked against git (`git log main..day5/polish`, every hash below) and a
full test run. The brief is `briefs/day5-polish.md`. Feature freeze: Tue 20/10 18:00.

## Git state

| Ref | Commit | Notes |
|---|---|---|
| `main` | `d9c84d2` | `day4-complete` (`4693804`) plus the Day 4 handoff note; untouched today |
| `day5/polish` | the Stage 8 commit after `cc49141` | pushed to origin; not merged (waiting for review) |

## Stages

| Stage | Commit | What |
|---|---|---|
| brief | `7d44eb0` | `briefs/day5-polish.md` |
| fix | `f4ae9dd` | a race in `tests/api/test_rep_stream.py`, stale since 8b (failed ~half the runs on `main` too) |
| 1 | `3fb9e23` | `view.computed_by`: the strip says "חושב מחדש בשרת · בלי מודל" for server comparisons |
| 2 | `616f639` | axe in the e2e suite; three fixes; 0 violations on 11 screens |
| 3 | `139a700` | the session safety limit (replaces `drop_block`) and the "שיחה חדשה" button |
| 4 | `3b55938` | the phone summary bar below 700 px |
| 5 | `f2ca560` | Docker: image, compose profiles, secret check in CI |
| 6 | `72df248` | the backup video, recorded by `tasks.py record-demo` |
| 7 | `cc49141` | README final pass with a generated results block |
| 8 | this commit | the runbook for Docker and the video, this handoff |

## Tests and CI

- `pytest`: **620 passed** (600 at the start of Day 5). `ruff check`, `ruff format --check` clean.
- `web/`: lint and typecheck clean; vitest **151 passed** (136); build ok.
- Playwright: **8 passed** (3): the three demo stories, three axe stories, two phone stories.
  The same 8 also pass against the Docker image (`E2E_BASE_URL`, see Stage 5).
- `tests/counts.json` now has `e2e` too; `tasks.py test-counts` reads it from
  `playwright test --list`, and the CI e2e job checks it like the web job checks vitest.
- CI has a fourth job, `docker`. All four jobs green on GitHub for every push through
  `72df248` (pushes at `3b55938`, `f2ca560`, `72df248`; `cc49141` was running when this was
  written).
- **One unexplained e2e failure:** 1 of 8 tests failed once, in a full-suite run right after
  pytest (machine under load). It did not reproduce in the next 72 test runs
  (3 suite runs, then `--repeat-each=4`). Which test it was is unknown.

## What was built, and decisions to review

### Stage 1 — provenance

- `ComparisonView.computed_by = {origin: "tool" | "server", label, tool}` built in
  `compass/tools/view.py` from the payload's `origin`; labels in `compass/labels.py`
  (`COMPUTED_BY_LABELS`). The strip renders the label it receives, plus the `compare` code chip
  when `tool` is set. A view stored before Day 5 (no `computed_by`) shows no line.
- Judges mode already made the distinction ("השרת חישב מחדש · בלי מודל" / "הכלי חישב"); no change.
- **Test change to review:** `test_answer_then_the_agents_compare_gives_the_same_view` now
  compares the two views except `computed_by`, and asserts that field differs by origin.

### Stage 2 — accessibility

- `@axe-core/playwright` **4.13.0**, pinned (4.14.0 was three days old). `e2e/a11y.spec.ts`
  runs axe (WCAG 2.0/2.1/2.2 A/AA + best practice) on 11 screens: employee empty, walkthrough,
  E-001 pending and final, judges mode and its token dialog, `/rep` token dialog, ticket open,
  the −50 error, answered, not-found. Fails on serious/critical (`expect.soft`, so one run reports
  every screen); every violation is written to `web/test-results/axe/<screen>.json`.
- Found and fixed:
  1. **color-contrast (serious):** the pending hero dimmed the "זמני" tag (3.76:1) and the caption
     (3.79:1). Only the big number and ₪ are dimmed now.
  2. **scrollable-region-focusable (serious):** the chat's scrolling message list had no
     keyboard access. It is focusable now, labelled "הודעות".
  3. **page-has-heading-one (moderate):** no `h1`. The header's wordmark is the `h1` (not-found
     keeps its own: `Header heading={false}`).
- Result: **0 violations at any impact** on all 11 screens (and on the phone layout, Stage 4).
- **Manual keyboard walk** (report only; a scripted Tab walk at 1440 px, checked by hand):
  - Every stop has the 3 px royal focus ring.
  - Employee, empty: the judges toggle → the message list → the suggestion chip. After a
    comparison: the toggle → the message list → the input → the waterfall (one stop, arrows
    move inside) → "הצגה כרשימה". RTL order is sensible: the header, then the chat (right
    column), then the result (left).
  - `/rep`: the ticket links → the amount → "אישור ושליחה לעובד/ת".
  - Token dialogs keep focus inside: the input → "אישור" → "ביטול".
  - Judges mode: the toggle → the turn selector → each "קלט ותוצאה".
  - Left as is: the send button is not a tab stop while the input is empty (it is disabled);
    the engine room's "קלט ותוצאה" summaries are 21 px tall but full width (axe's target-size
    check passes).

### Stage 3 — session safety limit

- `COMPASS_MAX_SESSION_TURNS` (default 40) and `COMPASS_MAX_SESSION_INPUT_TOKENS` (default
  2,000,000: uncached + cache read + cache write, summed over every model call). The longest
  eval conversation (`e001_rep_flow`, 4 turns) used ~114k input tokens, so 2M is ~17× that
  (~$1 at its rate). Both in `.env.example`.
- In the runner, before each run, from the session's own `agent_finished` events (so guard
  retries count). Reached: `agent_started`, the fixed `assistant_message` with `kind: "limit"`,
  `agent_finished` with `outcome: "limit"` and `limit: "turns" | "input_tokens"`. No trigger
  in the transcript, no model call, no guard. A rep answer after the limit gets the same reply.
- **By design:** the check is at the start of a run, so one run may go past the token cap (by
  at most one run: 8 tool rounds plus a guard retry).
- UI: when the latest reply has kind `limit`, a focused "שיחה חדשה" button replaces the input
  and the suggestions; `useSession.newSession()` forgets the stored id and creates a session.
- Judges mode shows a limit run as a turn with no cards and zero tokens (no special card).

### Stage 4 — phone bar

- `employee/PhoneBar.tsx`, `phoneBarRules.ts` (`(max-width: 699.98px)`, a comparison, not judges
  mode), `lib/useMediaQuery.ts`. Sticky at the top (below 1160 px the header isn't sticky, so
  the bar sits under it and then pins). The hero's own chips; tapping scrolls to the hero and
  focuses it (smooth only without reduced motion). `docs/screenshots/phone.png` (400 px).

### Stage 5 — Docker

- Multi-stage `Dockerfile`: `node:22.19.0-bookworm-slim` builds `web/dist`; `python:3.12-slim`
  with uv 0.9.13 installs from `uv.lock` (`--frozen --no-dev`) and runs `tasks.py data` (the
  image rebuilds `vehicles.db` from `raw/`); the runtime is uid 10001, `uvicorn --workers 1` on
  8000, `HEALTHCHECK` on `/api/health` (start interval 2 s: healthy ~3 s after start).
  **Image: 326 MB.**
- **Deviation to approve:** each profile's named volume is mounted at `/data` and holds only the
  session database (`COMPASS_APP_DB=/data/app.db`, `COMPASS_DEMO_DB=/data/demo.db`), not all of
  `data/`. A volume over `data/` would keep the first build's `rules.yaml` and `vehicles.db`
  forever, hiding every later rebuild.
- **Added:** `COMPASS_BUILD_CA`, an optional BuildKit secret for TLS-inspecting networks. This
  machine is behind NetFree: without it, `npm ci` and `uv sync` in the build fail with
  "UnknownIssuer". It is mounted only for the download steps, never stored in a layer; the
  default is the empty `docker/no-build-ca.pem`. CI builds without it.
- The port is bound to `127.0.0.1` only. Demo tokens default to `rep-demo` / `admin-demo`
  (compose interpolation: `.env` or the shell wins, like `tasks.py demo`).
- `scripts/check_image_secrets.py` (+ tests): exports the image's filesystem; fails on any
  `.env` / `.env.*` file (except `.env.example`), anything matching `sk-ant-…`, and, when
  `ANTHROPIC_API_KEY` is set, that exact value. Local run with this machine's key: 11,807 files,
  clean. CI: build (no push), the check, healthy in demo mode, non-root.
- `E2E_BASE_URL` in `playwright.config.ts` runs the e2e suite against a running server; 8/8
  against the image.

### Stage 6 — backup video

- `tasks.py record-demo` → `scripts/record_demo.py`: seeds the guard-rejection session
  (`web_fixtures.guard_retry_steps()`, the real guard rejects +2,915) into a temporary demo
  database, serves it on :8777, runs `web/record/demo.record.ts` (its own config; never part of
  `npm run e2e`), stops the server, prints the sizes, converts to mp4 when ffmpeg is on PATH
  (else prints the command).
- **`docs/video/compass-demo-employee.webm`: 15.3 MB, 1:31. `compass-demo-rep.webm`: 0.6 MB,
  0:10.** Both committed (under 25 MB). mp4 files are git-ignored; ffmpeg is not installed here,
  so none were made. Video files are `binary` in `.gitattributes`.
- Checked frame by frame: every key moment the brief lists is there.
- Known limits: no mouse cursor in Playwright video; a short blank flash when the recorder
  switches sessions (a page reload).

### Stage 7 — README

- New top: the pitch and the main screenshot; the quickstart in three commands (clone, `data`,
  `demo`; checked from a fresh clone: data 22 s, serving after 56 s including `npm ci` and the
  build); live mode.
- How correctness is guaranteed, with the three model-independence fixes: `3b50995`,
  `079b8a0`/`b484310` and `94ef304`.
- The results block; architecture; security; links to the runbook and the video. The detailed
  sections stay below; the stale "web/ planned" layout note is fixed.
- The results block is generated: `tasks.py readme` (`compass/readme_numbers.py`) copies the
  report's summary and table verbatim and takes the counts, cost per conversation and total
  spend from the same `judges_stats()` judges mode uses. `tests/test_readme_numbers.py` fails
  when it is stale.
- **Interpretation to confirm:** "all numbers from committed files" was applied to the results
  (evals, tests, cost, spend): hand-typed metrics elsewhere were removed. Domain examples in the
  prose (+2,914, +661, +611) and configuration defaults (a 15 s heartbeat, the $30 cap) are
  still written out.
- After adding tests: `tasks.py test-counts`, then `tasks.py readme`, and commit both.

### Stage 8

- `docs/demo-runbook.md`: build the image the day before (with `COMPASS_BUILD_CA` on NetFree),
  check the video plays, the strip's new server label after the answer, the session-limit reply,
  5b (Docker fallback), 6 (the backup video as a last resort).

## Freeze

Respected: no change to `compass/agent/prompts/system_he.md`, the tool descriptions
(`compass/tools/registry.py`, `compass/tools/handlers.py`) or `evals/scenarios/`
(`git diff main..day5/polish` on those paths is empty). No eval was run today; spend is
unchanged at $3.71 of $30.

## How to run (PowerShell)

```powershell
uv run --project backend python tasks.py demo                      # the demo, no key (unchanged from Day 4)
docker compose --profile demo up --build         # the API in Docker (the image has no UI since the split)
docker compose --profile live up --build         # live, backend\.env read at run time
uv run --project backend python tasks.py record-demo               # re-record docs/video/
uv run --project backend python tasks.py readme                    # refresh the README's results block
```

## Open

- Public deployment: not in this brief (your decision).
- The single unexplained e2e failure (see "Tests and CI").
- After review: `git checkout main; git merge --no-ff day5/polish`, `git tag v1.0`,
  `git push origin main v1.0`.

Released v1.0 at 81abaa3.

Released v1.2 at 47af506 (backend/ + frontend/ split, Render Blueprint).

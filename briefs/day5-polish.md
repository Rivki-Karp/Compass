# Day 5 Brief — Polish, packaging, rehearsal assets

> **Layout note (2026-10-19, after v1.1):** the repo is now split into `backend/` and
> `frontend/` (formerly `web/`). The commands below are updated to run from the repo root
> (`uv run --project backend python tasks.py ...`); the narrative and file names describe the
> repo as it was on the day.

Branch: `day5/polish`, cut from `main` at tag `day4-complete` (plus `d9c84d2`).
Commit this file as `briefs/day5-polish.md` in the first commit.
Hard deadline: **feature freeze Tuesday 20/10 18:00.** After that only fixes to things that are broken.

## 0. Ground rules (unchanged)

- One commit per stage; run every suite after each (ruff, pytest, web lint/typecheck/vitest/build, Playwright).
- Stop and ask when something is unclear or would break an API, schema or test.
- **The freeze from HANDOFF_DAY4 holds:** no changes to `system_he.md`, the tool descriptions or `evals/scenarios/` without my explicit approval and a full eval re-run. Nothing in this brief needs them; if you think something does, stop and ask.
- No push to `main` without my review. Pushing `day5/polish` is fine.
- `.env` stays out of git and out of every image and log. No ID numbers.
- Windows PowerShell for every documented command.
- Stage explicit paths only (no `git add -A`). `/compact` after each stage commit.

## 1. Stages

### Stage 1 — Honest provenance for server comparisons

The provenance strip says "חושב בכלי compare" even when the server computed the comparison (provisional, pending recompute, settle).
- Show "חושב מחדש בשרת · בלי מודל" when `origin` is `server`, and "חושב בכלי compare" otherwise. Label text comes from the API (`view`), not a frontend string, consistent with the rest of `view`.
- Same distinction in judges mode, if not already there.
- Tests: view label per origin; the UI renders the label it receives.

### Stage 2 — Accessibility pass

- Add `@axe-core/playwright` to the e2e suite: run axe on the employee screen (empty, walkthrough finished, E-001 pending and final), `/rep` with a ticket open, judges mode, and the not-found page. Fail on serious and critical violations.
- Fix what it finds. Report what you fixed and anything you chose to leave (with the reason).
- Manual check, report only: Tab through the employee screen and `/rep` end to end; every control reachable, focus visible, order sensible in RTL.

### Stage 3 — Session safety limit (replaces `drop_block`)

- A per-session cap on agent turns (setting, default 40) and on total input tokens per session (setting, sensible default from the eval numbers). When reached, the server replies with a fixed, polite Hebrew message with no numbers ("השיחה הגיעה לאורך המרבי. אפשר להתחיל שיחה חדשה.") and stops calling the model for that session. The UI shows a "שיחה חדשה" button.
- This lives in the runner, not the prompt. Tests: cap reached → no model call, fixed message, guard not involved; a new session works.

### Stage 4 — Phone summary bar (small)

- Below 700 px wide, once a comparison exists, a compact sticky bar under the header shows the alternative's title, the signed diff and the pending/final chip. Tapping it scrolls to the hero card.
- No new data; uses the same `view`. vitest for visibility rules; one screenshot at 400 px.

### Stage 5 — Docker

- Multi-stage `Dockerfile`: a Node stage builds `web/dist`; a Python stage installs with uv from the lockfile and copies the built UI. Non-root user. One process, `--workers 1`, port 8000.
- `HEALTHCHECK` against `/api/health`.
- `.dockerignore` excludes `.env*` (except `.env.example`), `data/*.db`, `node_modules`, `web/dist` from the context, `.git`, scratch and test output.
- `docker-compose.yml` with two services or profiles: `live` (reads secrets from an `env_file: .env` at run time, a named volume for `data/`) and `demo` (`COMPASS_LLM=scripted`, its own volume, no API key needed).
- Assert no secret is baked in: a CI step builds the image and checks that no file in it contains the value pattern of an Anthropic key and that `.env` is absent. CI builds the image but does not push it anywhere.
- Document for PowerShell: `docker compose --profile demo up --build`, then the URLs.

### Stage 6 — Backup video, recorded automatically

- A Playwright script (not part of the test suite) that runs the full demo story in demo mode at human pace and records video at 1440×900: empty state → walkthrough to +2,914 with the 802 provenance strip → E-001 to +661 pending → `/rep` answers 350 (second page, recorded too) → +611 final → judges mode on the walkthrough turn and on the guard-rejection fixture.
- Pacing: visible typing in the chat input, ~1 s pauses on each key moment.
- Output: `docs/video/compass-demo-employee.webm` and `docs/video/compass-demo-rep.webm`, plus a command to convert to mp4 if ffmpeg is present. Do not commit videos over 25 MB; tell me the sizes.
- `tasks.py record-demo` runs it. Document it for PowerShell.

### Stage 7 — README final pass

Make the README the first thing a judge reads:
1. One-paragraph pitch and the main screenshot at the top.
2. Quickstart in three commands (demo mode, no key), then live mode.
3. "How correctness is guaranteed": the model proposes, the tools compute (Decimal, no intermediate rounding), the guard verifies every number, the server settles rep answers; with the three model-independence fixes as examples.
4. Results: the eval table, test counts per suite, cost per conversation, total spend.
5. Architecture in short, the event-name mapping, security notes (tokens, redaction, no ID numbers).
6. Links to the demo runbook and the backup video.
All numbers in the README must come from committed files (`evals/report.md`, `tests/counts.json`, `evals/spend.jsonl`), not typed by hand. If you script the numbers block, add a test that it's current.

### Stage 8 — Release

- Update `docs/demo-runbook.md` for Docker and the backup video.
- `briefs/HANDOFF_DAY5.md`, checked against git.
- Final report: per stage what changed, test counts, axe results, image size, video sizes, anything left open.
- Stop. After my review: merge to `main` (`--no-ff`), tag `v1.0`, push. That tag is what we present.

## 2. Out of scope

New features, prompt or scenario changes, payslip upload, the all-alternatives screen, public deployment (separate decision, see below), anything that can't be finished and tested before Tuesday 18:00.

## 3. Open decision (mine, not yours)

Public deployment is not in this brief. If I decide we need a public URL, it will come as a separate short brief after Stage 5.

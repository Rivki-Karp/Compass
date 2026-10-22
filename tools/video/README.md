# Demo video (from the LIVE site)

Nothing here changes the product. From the repository root, in PowerShell:

    uv run --project backend python tasks.py record-video --dry-run   # no recording: PASS/FAIL per scene
    uv run --project backend python tasks.py record-video             # records and edits the first cut

Passwords: set `COMPASS_VIDEO_EMPLOYEE_PASSWORD`, `COMPASS_VIDEO_REP_PASSWORD`,
`COMPASS_VIDEO_ADMIN_PASSWORD`, or leave them unset and the script asks (hidden input). They stay in
memory: never printed, saved or logged.

Needs Playwright Chromium (already installed) and ffmpeg (`winget install Gyan.FFmpeg`, then a new terminal).

Files: `record.mjs` (scenes, dry/record), `edit.py` (ffmpeg cut), `captions.mjs` + `captions.json`
(Hebrew captions as PNG overlays), `run.py` (prompts, takes).
Output in `out/` (git-ignored): `compass-demo.mp4`, `compass-demo-clean.mp4`, `frames/`, `raw/`,
`cuts.json`, `timings.json`, `dry-run.json` / `take.json`.

Cleanup after a run: `video-guest@demo.compass` and the admin's prep conversation are deleted.

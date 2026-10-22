# Brief: Record the ≤60-second demo video from the LIVE site

You are the **senior engineer** on Compass. This task records and edits a video. **It changes nothing in the product:** no code, no config, no deploy and no Render settings. All new code lives under `tools/video/` (plus a `tasks.py record-video` entry). Write a short design note first, covering the approach, the risks and how you handle them, then build. If a precondition fails, **stop and ask**.

Commit this file as `briefs/demo-video.md`, on a branch `chore/demo-video` cut from `main`.

## 0. Preconditions (check them first, and stop if any fails)

1. **The live API:** `https://compass-api-tft8.onrender.com/api/health` reports accounts, payslip, number sources and profile memory all ON. Report the version or commit it serves. If profile memory is off, tell me: scene 9 must then be dropped, and I decide.
2. **The live UI:** `https://compass-web-hcpz.onrender.com` serves the landing page.
3. **Credentials:** they come only from the process environment: `COMPASS_VIDEO_EMPLOYEE_PASSWORD`, `COMPASS_VIDEO_REP_PASSWORD` and `COMPASS_VIDEO_ADMIN_PASSWORD`. They are never written to a file, a log, a commit or the video. The accounts are `employee@demo.compass`, `rep@demo.compass` and `admin@demo.compass`.
4. **The payslip:** use `backend/tests/fixtures/payslips/11_amounts.pdf` (synthetic).
5. **Tools:** Playwright Chromium (already installed) and ffmpeg. If ffmpeg is missing, install it in the least invasive way for Windows and tell me what you did. Use the system's TLS trust store. **Never disable TLS verification** (no `ignoreHTTPSErrors`, and no `NODE_TLS_REJECT_UNAUTHORIZED=0`).
6. **A dry run:** run the whole script once against the live site **without recording**, and confirm every scene's expected state appears. Find out which alternative, in the live catalog and rules, actually creates a rep question for this profile. Use the E-001 scenario as the guide; it is ATTO 3 there. Use that car. **Don't hardcode any money number** in the script or the captions. The numbers are whatever the live system computes.

## 1. The storyboard (target 55–58 s, hard max 60 s)

**The order is fixed. The times are targets.** Waiting for the model is cut out in editing.

| # | Target | Scene | What must be on screen | Caption (Hebrew, burned in) |
|---|---|---|---|---|
| 0 | 0–3 | Opening | The landing page, with the big logo and the headline. A small line at the bottom: "הקלטה אמיתית מהאתר החי · זמני המתנה קוצרו" | "Compass · יועץ הרכב של שטראוס" |
| 1 | 3–5 | Employee login | The login form, then home: "שלום דנה, מה בודקים היום?" | "כניסה מאובטחת לעובדים" |
| 2 | 5–12 | Payslip | Click "העלאת תלוש" and pick the file. The confirmation card, with the pension row showing the derived % and "(חושב מהתלוש: … מתוך …)". Then "אישור ושמירה" | "המודל קורא, הקוד מחשב, העובדת מאשרת" |
| 3 | 12–16 | All alternatives | Type "אני מפתחת תוכנה, יש לי היום קורולה קרוס. תציג לי את כל החלופות". The all-options grid, with nets | "כל החלופות, עם הנטו של כל אחת" |
| 4 | 16–21 | Missing fact | Ask to compare with the rep-question car from the dry run. The hero card shows **"ממתינה לנציג"** and the provisional diff | "חסר נתון? לא מנחשים. שואלים נציג" |
| 5 | 21–29 | Rep, split screen | **Left:** the rep (logged in) opens the ticket and answers (participation 350). **Right:** the employee's card flips by itself to **"סופי"**, with "אושר על ידי נציג" | "הנציג עונה, והשרת מחשב מחדש בלי המודל" |
| 6 | 29–35 | Where is this number from | In the employee chat, click the diff number in the latest reply. The popover shows "חושב בשרת" and the component rows with chips | "כל מספר, עם מקור. תלחצו ותבדקו" |
| 7 | 35–40 | Judges mode | Toggle "מצב שופטים". The engine room shows the tool calls and the guard card ("… מתוך … אומתו") | "המודל לא מחשב כסף. שומר בודק כל מספר" |
| 8 | 40–46 | Memory | Click "שיחה חדשה". The card "יש לי פרטים מהשיחה מ־DD/MM", then "להשתמש בהם", then the chips "משיחה קודמת" | "זוכר אותך, רק באישור שלך" |
| 9 | 46–54 | Admin adds an employee, split screen | **Left:** the admin (logged in) invites `video-guest@demo.compass` as employee, and the one-time code dialog appears. **Right:** a fourth browser context (new guest, recorded) opens the live site, clicks "הרשמה ראשונה", and fills in the email, the code (read by the script from the admin page's dialog, never logged), the name "נועה כהן" and a password generated at run time, never printed or saved. It lands on an EMPTY home: no conversations from דנה | "המנהלת מזמינה, העובדת נרשמת. כל אחת רואה רק את שלה" |
| 10 | 54–57 | Close | The logo on navy | "Compass · כל שקל, עם מקור" |

**Checks to do in the dry run, and to report:**
- **Scene 7:** check what an *employee* sees in judges mode. If the guard card isn't visible to the employee, stop and tell me. Don't switch to admin silently.
- **Scene 6:** the number clicked must be one that has a source (the bold diff is fine after v2.1.1).

## 2. How to record

- **Browsers:** one Playwright browser context per user (employee, rep, admin, and the new guest in scene 9), each with `recordVideo` at **1440×900**, at device scale 1, in Hebrew locale, and in the Asia/Jerusalem time zone.
- **Clean state:** before scene 1, log in as the employee via the API and call `DELETE /api/profile`, so the memory card appears only in scene 8. Don't delete anything else.
- **Pacing:**
  - Wait for **UI states**, never fixed sleeps: a selector or text appearing, an SSE-driven state change.
  - Each key moment stays still ~1 s for the eye.
  - Typing is visible but fast, about 25 ms per character.
  - Mouse moves are visible (Playwright's `mouse.move` with steps).
- **Robustness:**
  - Each scene is a function with a timeout. If the live model answers differently, for example asking an extra question, the scene may answer it briefly, from a small fixed list you define in the script, and continue.
  - If a scene still fails, re-run **that scene only**, from a saved state where possible, or else the whole take. At most 3 takes.
- **Timestamps:** log the start and end of each scene's "useful" segment into `tools/video/out/cuts.json`, for editing.
- **Cost:** record the live model cost of the takes (from `/api/health` or the server ledger if visible, otherwise an estimate from the turns), and report it.

## 3. How to edit (ffmpeg)

- **Cuts:** use `cuts.json` to trim each scene to its useful segment, removing the model wait time.
- **Split screen (scenes 5 and 9):** the rep clip and the employee clip side by side (`hstack`), each scaled to 960 px wide, on a navy background, in a 1920×1080 frame.
- **Other scenes:** scale 1440×900 to fit 1920×1080, centred on navy (`#082350`).
- **Captions:** **don't use ffmpeg `drawtext` for Hebrew,** because bidi order breaks. Instead, render each caption as a transparent PNG with Playwright: a small HTML page using IBM Plex Sans Hebrew 600, white text on a rounded `rgba(4,19,43,.82)` pill, 40 px, RTL. Overlay it bottom-centre with a short fade in and out. Do the same for the scene-0 honesty line, smaller, at 22 px.
- **Transitions:** a 0.25 s crossfade between scenes, and none inside a scene.
- **Audio:** none (silent). I may add a voice-over later.
- **Output:** H.264 (yuv420p, `+faststart`), 30 fps, CRF tuned so the file is **≤ 50 MB**, and duration **≤ 60.0 s**. Assert both, and fail the task otherwise.

## 4. Deliverables (in `tools/video/out/`, git-ignored except the script)

1. `compass-demo.mp4`: with captions, ≤60 s, ≤50 MB.
2. `compass-demo-clean.mp4`: the same cut without captions, for a voice-over.
3. `frames/scene-XX.png`: one still per scene, at its key moment, for quick review.
4. `raw/`: the raw recordings per context.
5. `cuts.json` and a short `README.md` saying how to re-run: `uv run --project backend python tasks.py record-video` (PowerShell), with the env vars.

## 5. Rules

- **Nothing in the product changes.** No deploy and no Render changes.
- **After recording:**
  - Delete the user `video-guest@demo.compass` (its account and conversations), as admin, via the admin API.
  - Leave the employee's conversations and saved profile as the recording left them; they are fine for the judges.
- **Never print or save passwords or tokens.** Mask them in any log.
- **Commit only `tools/video/**` (excluding `out/`), the `tasks.py` entry and this brief.** Push `chore/demo-video`. Do not merge.
- **STOP after the first full cut.** Report:
  - the duration and size;
  - the per-scene timings;
  - the frame stills (paths);
  - any scene that needed a retry or an improvised answer;
  - the cost.

  Wait for my notes before re-editing.
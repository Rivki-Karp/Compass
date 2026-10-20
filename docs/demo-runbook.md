# Demo runbook: the final (Wed 21/10/2026)

Seven minutes, two browser windows, one laptop. The live run uses the real model; if the
network or the API fails at any point, switch to demo mode (section 5): the screens and the
numbers are the same, with no key and no network. If the laptop itself can't run the app, play
the backup video (section 6).

Fallbacks in order: live (section 3) → demo mode with `tasks.py demo` (5a) → demo mode in Docker
(5b) → the backup video (6).

Every `tasks.py` command runs from the repo root as `uv run --project backend python tasks.py ...`
(the backend's environment). The backend lives in `backend\`, the UI in `frontend\`.

## 1. Before you go on stage

The day before, in PowerShell, from the repo root:

```powershell
git pull
uv run --project backend python tasks.py data        # only if backend\data\vehicles.db is missing
uv run --project backend python tasks.py build-web   # the UI the server will serve
uv run --project backend python tasks.py test        # optional sanity check
```

Check `backend\.env` has `ANTHROPIC_API_KEY`, `COMPASS_REP_TOKEN` and `COMPASS_ADMIN_TOKEN`. An empty
token disables its screen: `/rep` and the judges-mode dialog then say "טוקן לא הוגדר בשרת", and
`tasks.py serve` prints a warning at startup naming the empty variable. To generate a token, run
this in PowerShell once per token and paste the output after the `=` in `backend\.env`:

```powershell
[guid]::NewGuid().ToString()
```

Restart the server after changing `backend\.env`. In live mode the server refuses to start while either
token is empty or a demo / placeholder value (`rep-demo`, `admin-demo`, or the `.env.example`
placeholders), and says which one; demo mode (5a, 5b) keeps its `rep-demo` / `admin-demo`. Write the two tokens on a card: you'll type them on
stage.

Build the Docker image too, while there is network (it downloads PyPI packages; on stage, `up`
without `--build` needs no network). The image is the API only; 5b serves the screens from
`frontend\` with Vite, whose packages `build-web` above already installed. On a NetFree connection, point the build at its
CA first:

```powershell
$env:COMPASS_BUILD_CA="C:\ProgramData\NetFree\CA\netfree-ca-list.crt"   # NetFree only
docker compose --profile demo build
```

Check the backup video plays: open `docs\video\compass-demo-employee.webm` in Chrome (drag the
file onto a tab). It is 1:31, the whole story in demo mode; `compass-demo-rep.webm` is the
representative's 10 seconds.

Do one full dry run of section 3 in live mode and one in demo mode (section 5).

Thirty minutes before:

1. Port 8000 is free: `Get-NetTCPConnection -LocalPort 8000` shows nothing (else stop that
   process).
2. Start the live server on a database of its own, so no earlier test session or ticket shows
   up on stage:

   ```powershell
   $env:COMPASS_APP_DB="data\final.db"
   uv run --project backend python tasks.py serve
   ```

   (Relative to `backend\`: `backend\data\final.db` is created on first use and is git-ignored.
   Delete it to start over.)
3. Open two browser windows, both at 100% zoom, side by side (or one per screen):
   - **Window A, the employee**, about 1440 px wide: http://127.0.0.1:8000/
   - **Window B, the representative**: http://127.0.0.1:8000/rep. Enter the rep token now; it is
     kept for this tab only.
4. Window A shows the "איך זה עובד" card, the pill "מחובר", and no "מצב דמו" badge (live mode).
5. Keep a PowerShell window ready for the fallback (section 5).

## 2. What the judges should take away

- The model talks and picks tools; **it never computes money**.
- Every number on the screen comes from a deterministic tool, with its source and the rules
  behind it, and **a guard checks every number** in every reply.
- When a fact only the company knows is missing, the system **asks a representative**, shows a
  provisional result, and **turns it final by itself** when the answer arrives.

## 3. The live run

Type (or paste) each employee message in Window A and press Enter. With the real model a turn
takes 5–25 seconds; the bubble says "מחשב…", then "עדיין עובד על זה" after 8 seconds. Fill
the wait by narrating what the judges can see.

### Step 1. The walkthrough: giving up the car (about 2 minutes)

| You type in Window A | The judges see |
|---|---|
| `אני מפתחת תוכנה, שכר בסיס 18,500` | The reply: the occupation maps to group ב׳, budget 3,700 ₪. It asks about commissions, pension, study fund, credit points. |
| `אין לי עמלות או בונוסים. פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. היום יש לי קורולה קרוס 2025 ואני משתתפת ב-300 ₪. מה יקרה לנטו אם אוותר על הרכב?` | The comparison card: **+2,914 ₪**, "ויתור על הרכב לעומת היום", 11,000 → 13,914; an amber notice that today's car is above group ב׳; the waterfall with five bars and the total. |

Then:

- **Click the +802 bar** (income tax). The strip below shows "חושב בכלי compare", the inputs it
  used with their sources ("לפי דבריך", "לפי העיסוק") and the rules ("מדרגות מס הכנסה ·
  קובץ הכללים"). Say: *every number can be traced to the tool, the input and the rule.*
- Scroll down: "על מה החישוב מבוסס", every input with its source chip. The chat stays in view.

### Step 2. Judges mode on the walkthrough (about 1 minute)

- Click **מצב שופטים** (top left), enter the admin token.
- The engine room shows the turn: "המודל קרא לכלי" save_profile, lookup_vehicle,
  set_current_situation, compare (open compare's card: `→ args` and the full `← result`), the
  "הכלי חישב" card, and the guard: **"3 מתוך 3 אומתו · נשלח"** with each number and its
  source (`+2,914 ✓ compare`).
- The summary on the right: eval pass rate, eval spend, test counts, cost per conversation,
  all read from the committed files.
- Click **מצב שופטים** again to turn it off.

### Step 3. E-001 with a representative (about 3 minutes)

Start a fresh conversation: in Window A press **Ctrl+T** and type `127.0.0.1:8000`. (A new tab is
a new session. Don't duplicate the tab: a duplicate continues the old conversation.)

| You type in Window A | The judges see |
|---|---|
| `אני מנהלת מוצר, שכר בסיס 18,500` | Group ג׳, budget 4,500 ₪; questions about the rest. |
| `אין לי עמלות או בונוסים. פנסיה 6%, קרן השתלמות 2.5%, 2.75 נקודות זיכוי, 2 ילדים מתחת לגיל 23. היום יש לי קורולה קרוס 2025 ואני משתתפת ב-300 ₪.` | The reply confirms the details. |
| `מה יקרה לנטו אם אעבור ל-ATTO 3? אני לא יודעת מה תהיה ההשתתפות שלי בו, אפשר לשאול את הנציג?` | A ticket opens. The card shows **+661 ₪, provisional**: dimmed, "זמני", the amber "ממתינה לנציג" chip with a clock, a dashed tile; under the ATTO 3 tile "חשמלי · קבוצה ג׳". The reply says the participation is the catalog default until the representative answers. |

Then, in **Window B**:

- The ticket appears by itself: "השתתפות עצמית · ATTO 3", "עכשיו". If more than one shows, click
  the newest ("עכשיו").
- The detail: the question, the car, the catalog default **300 ₪**, the employee's provisional
  **+661 ₪**.
- *Optional, 15 seconds:* type `-50` and click **אישור ושליחה לעובד/ת**. The server's Hebrew
  message appears next to the field: "הערך צריך להיות בין 0 ל-20,000." Clear the field.
- Type `350` and click **אישור ושליחה לעובד/ת**. The ticket leaves the list: "התשובה נשלחה.
  החישוב אצל העובד/ת מתעדכן."

Back to **Window A** (within a second, before the model has said anything):

- The card turns **+611 ₪, "סופי"**, with a green border for 2 seconds. The waterfall gains a
  **−50** bar (the participation). The participation row reads 350 ₪ "אושר על ידי נציג".
- The strip under the waterfall says **"חושב מחדש בשרת · בלי מודל"**. If the model then calls
  `compare` itself (demo mode's script does), it changes to "חושב בכלי compare" with the same
  numbers.
- Say: *the server recomputed it the moment the representative answered; it didn't wait for
  the model.*
- Then the model's message: the representative confirmed 350 ₪, net 11,032 → 11,643, +611 ₪.

### Step 4. Judges mode on the representative's turn (about 1 minute)

- Turn judges mode on and enter the admin token again (this is a new tab, and a token is kept
  per tab only). The engine room shows the latest turn,
  "תשובת הנציג": the card "הנציג ענה" with `350`, then **"השרת חישב מחדש · בלי מודל"** +611,
  then the guard verifying +611 (source `server` or `compare`).
- Turning judges mode on and off doesn't replay any animation or announcement.

## 4. If something looks wrong

- **A reply asks a question instead of computing:** answer it naturally ("זה כל המידע שיש לי"),
  or type the next message of the script.
- **The card doesn't change after the rep answers:** check Window B said "התשובה נשלחה". If the
  pill in Window A says "מתחבר מחדש…", wait 2–3 seconds; it reconnects by itself and catches up.
- **A token is rejected:** the dialog says "הטוקן שגוי."; retype it from the card.
- **The reply is "השיחה הגיעה לאורך המרבי. אפשר להתחיל שיחה חדשה."** The session hit its safety
  limit (it won't happen in a seven-minute demo). Click **שיחה חדשה** and continue.
- **Anything slower than 30 seconds, an error message, or no network:** go to section 5. Don't
  debug on stage.

## 5. Fallback: demo mode (no network, no key)

### 5a. With `tasks.py demo`

In the PowerShell window: stop the live server (Ctrl+C), then:

```powershell
uv run --project backend python tasks.py demo
```

It empties the demo database, builds the UI if needed, and serves the same URLs on port 8000. It
prints the URLs and where the tokens come from. Then:

- In both windows, reload the page (F5). Window B asks for the rep token again only in a new
  tab; in the same tab it keeps it.
- Window A shows the **"מצב דמו"** badge. Instead of typing, **click the suggestion chips**
  above the input. They are exactly the messages in section 3: the walkthrough's two, then, in a
  new tab (Ctrl+T, `127.0.0.1:8000`), E-001's three. Any other text gets a fixed reply without
  numbers.
- The representative step, judges mode and every number are the same as in section 3. Each
  turn takes about a second.

Say it plainly: *this is demo mode: the model is scripted, everything else (the tools, the
guard, the tickets, the server's recomputation) runs for real.*

### 5b. In Docker (if `uv` or the Python environment misbehaves)

Stop whatever is on port 8000, then, with the image built the day before (section 1), start
the API in one PowerShell window:

```powershell
docker compose --profile demo up
```

The image serves the API only, so start the screens in a second PowerShell window (no network
needed; Vite proxies `/api` to the container on :8000):

```powershell
cd frontend; npm run dev
```

Then use http://localhost:5173/ (employee) and http://localhost:5173/rep instead of port 8000,
with the same tokens (`rep-demo` / `admin-demo`, unless the shell sets others); the container's
health check turns "healthy" within a few seconds. Then continue as in 5a. Ctrl+C stops each. To
start from an empty demo database: `docker compose --profile demo down -v`, then `up` again.

## 6. Last resort: the backup video

If no server can run, play the recording: `docs\video\compass-demo-employee.webm` in Chrome,
full screen (F11). It shows, in demo mode at human pace: the empty state, the walkthrough to
**+2,914** with the **+802** strip, E-001 to **+661** pending, the representative's answer (350;
the representative's own screen is `compass-demo-rep.webm`), **+611** final, then judges mode on
the walkthrough (the compare call opened, the guard 3 of 3) and on a guard rejection (a **+2,915**
draft struck through, "✕ אין מקור", then "נשלח אחרי ניסוח מחדש"). Narrate it as you would
section 3.

To re-record it (demo mode, no key; about two minutes):

```powershell
uv run --project backend python tasks.py record-demo
```

## 7. After the demo

- Stop the server (Ctrl+C), or `docker compose --profile demo down`.
- `backend\data\final.db` and `backend\data\demo.db` hold only the demo's sessions; delete them
  if you like. `backend\data\app.db` was not touched. Docker's sessions live in its own volumes.

## 8. Before a public deployment (live mode)

Not deployed anywhere yet; section 9 has the steps. What the backend container already does:

- **Configuration from the environment only.** The image sets `COMPASS_ENV_ONLY=1`: no `.env`
  file is read, and none is in the image (`backend/scripts/check_image_secrets.py`, run in CI). Set
  every variable on the host: `ANTHROPIC_API_KEY`, `COMPASS_REP_TOKEN`, `COMPASS_ADMIN_TOKEN`,
  and optionally the two below.
- **Tokens.** A live server refuses to start while either token is empty or a demo / placeholder
  value (section 1).
- **A daily spend cap.** `COMPASS_DAILY_SPEND_CAP_USD` (default 5): every model call on the
  server, summed per UTC day in the session database, is checked before the next call. At the
  cap every conversation gets "השירות הגיע למכסת השימוש היומית שלו. אפשר לנסות שוב מחר." until
  midnight UTC. It is kept in the session database: on a host with a persistent disk (or Docker's
  volume) a restart doesn't reset it; on Render's free plan (no disk) every restart does, so there
  the hard limit is the Anthropic Console's workspace spend limit (section 9).
- **A per-IP rate limit** on sending messages: `COMPASS_MESSAGE_RATE_PER_MINUTE` (default 20;
  429 with `Retry-After` beyond it). It counts the socket's client IP. Behind a platform's
  reverse proxy (Render), set `COMPASS_TRUST_PROXY=1`: it then counts the rightmost
  `X-Forwarded-For` entry, the address the proxy itself saw and appended (the entries to its
  left come from the browser and can be forged, so they are ignored). Otherwise every employee
  shares the proxy's limit. Never set it without such a proxy in front: anyone could then pick
  their own key. The count is per process, which is fine: the server runs one worker.
- **CORS: one origin allowed, exactly.** The UI's static site is another origin, so the
  backend allows it by name: `COMPASS_CORS_ORIGINS`, a comma-separated list of exact origins
  (no wildcard, no trailing slash). Empty, the default, means the same origin only.

## 9. Deploy

Prepared, not deployed. Both parts run on Render, and `render.yaml` at the repo root describes
both, so one "Blueprint" creates them together:

| Service | What it is | Address |
|---|---|---|
| `compass-api` | the backend (`backend/`): the API, the agent, the session databases. A Docker web service on the **free** plan, Frankfurt | https://compass-api-tft8.onrender.com |
| `compass-web` | the UI (`frontend/`): a static site, files only, which call the backend | https://compass-web-hcpz.onrender.com |

You need about 30 minutes, a GitHub account with access to the repo, and an Anthropic Console
login. The free plan needs no credit card.

**What the free plan means, and why it is accepted:**

- **No persistent disk.** The sessions and tickets live in the container's own filesystem and
  are **lost whenever the API restarts**: a deploy, a change of an environment variable, Render
  putting an idle service to sleep (after about 15 minutes without a request; "Keep awake"
  below prevents that) or Render restarting it for maintenance.
- **The daily spend counter is lost with them.** `COMPASS_DAILY_SPEND_CAP_USD` (5) is counted in
  the session database, so every restart starts it again from zero. It still stops a runaway
  conversation within one day, but it is not a hard limit. **The hard limit is the Anthropic
  Console's spend limit** on the workspace the key belongs to (9a).
- **The first request after a sleep takes about a minute** while the API starts. The UI itself
  (the static site) never sleeps.

Neither service redeploys on a push (`autoDeployTrigger: off`): you deploy by hand.

### 9a. Before you start

1. **Set the hard spend limit.** In <https://console.anthropic.com>: **Settings** →
   **Workspaces** → the workspace the live key belongs to (create one named `compass` and a key in
   it, to keep this key's spend apart) → **Limits** → set a **spend limit**, for example $20 for
   the month. When it is reached, Anthropic refuses the key's calls and the API shows its error
   reply; no restart of ours can reset it. (The menu names may differ slightly; look for the
   workspace's limits.)
2. **Have the three secrets ready** (in a password manager, never in a file in the repo):

   | Variable | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | the live key (from the workspace above) |
   | `COMPASS_REP_TOKEN` | a new long random token (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
   | `COMPASS_ADMIN_TOKEN` | another new one, different from the rep token |

   Never reuse the demo tokens: a live server refuses to start with them (section 1).
   `render.yaml` sets everything else: `COMPASS_LLM=anthropic`, `COMPASS_TRUST_PROXY=1`,
   `COMPASS_DAILY_SPEND_CAP_USD=5`, `COMPASS_MESSAGE_RATE_PER_MINUTE=20`,
   `COMPASS_CORS_ORIGINS=https://compass-web-hcpz.onrender.com`, and for the UI `NODE_VERSION`,
   `VITE_API_BASE_URL=https://compass-api-tft8.onrender.com` (public by design: it is in the UI's
   JavaScript), the rewrite rule and the security headers.

### 9b. The Blueprint (the normal way)

1. Go to <https://dashboard.render.com> and sign up or log in. "Sign in with GitHub" is the
   simplest.
2. Top right, click **New +** → **Blueprint**.
3. Under "Connect a repository", click **Connect GitHub** (first time only), allow Render to see
   the `Compass` repository (you can choose "Only select repositories"), then pick
   `Rivki-Karp/Compass` in the list and click **Connect**.
4. **Blueprint Name:** `compass`. **Branch:** the branch to deploy (the approved one; `main` once
   it is merged). Render shows what `render.yaml` will create: the web service `compass-api` and
   the static site `compass-web`.
5. Render lists the three secrets, each with an empty box. Paste each value. Check for stray
   spaces; they are stored by Render, not in the repo.
6. Click **Apply** (or **Deploy Blueprint**). Both services build at once: the UI in 1–3
   minutes, the API in 5–10. Open each one → **Logs** to follow it; each is done when it shows
   **Live**.
7. **Check the two addresses** at the top of each service's page. Render adds a random suffix to
   each name, and this deployment's are `https://compass-api-tft8.onrender.com` and
   `https://compass-web-hcpz.onrender.com`. Each one is written into the other's settings in
   `render.yaml`, so they must match. If a new Blueprint (or a recreated service) gets different
   suffixes, change all three places in `render.yaml`, commit and push, then **Blueprints** →
   `compass` → **Manual Sync**, and redeploy `compass-web`:
   - `compass-web` `VITE_API_BASE_URL` = the API's address;
   - `compass-web` `Content-Security-Policy` header: `connect-src 'self'` followed by the API's
     address;
   - `compass-api` `COMPASS_CORS_ORIGINS` = the UI's address (`https://`, no slash at the end).

   The UI needs the redeploy because its URL is baked in at build time; the API restarts by
   itself when its environment changes.
8. Continue with "Keep awake" (9d) and "Check it from outside" (9f).

### 9c. By hand (if the Blueprint fails)

The same two services, created one at a time. **The API first:**

1. **New +** → **Web Service** → pick `Rivki-Karp/Compass` (connect GitHub as in 9b, step 3).
2. **Name:** `compass-api`. **Language:** Docker. **Branch:** the branch to deploy. **Region:**
   Frankfurt. **Root Directory:** `backend`.
3. **Dockerfile Path:** `./Dockerfile`, and the Docker build context `.` (both are inside the
   root directory: not `backend/Dockerfile`).
4. **Instance Type:** Free.
5. **Environment Variables:** the three secrets (9a) and `COMPASS_LLM=anthropic`,
   `COMPASS_TRUST_PROXY=1`, `COMPASS_DAILY_SPEND_CAP_USD=5`,
   `COMPASS_MESSAGE_RATE_PER_MINUTE=20`, `COMPASS_CORS_ORIGINS=https://compass-web-hcpz.onrender.com`.
6. **Advanced:** **Health Check Path** `/api/health`; **Auto-Deploy** Off. No disk.
7. **Create Web Service**, and wait for **Live**.

**Then the UI:**

1. **New +** → **Static Site** → pick `Rivki-Karp/Compass`.
2. **Name:** `compass-web`. **Branch:** the same one. **Root Directory:** `frontend`.
3. **Build Command:** `npm ci && npm run build`. **Publish Directory:** `dist`.
4. **Environment Variables:** `NODE_VERSION` = `22.19.0` (the version in `frontend/.nvmrc`) and
   `VITE_API_BASE_URL` = `https://compass-api-tft8.onrender.com` (no `/api`, no slash at the end).
5. **Create Static Site**, and wait for **Live**.
6. **Redirects/Rewrites** (left menu) → **Add Rule**: Source `/*`, Destination `/index.html`,
   Action **Rewrite** → **Save Changes**. Without it, opening `/rep` directly is a 404. (Files
   that exist, like the JavaScript, are served as they are; only the rest gets the page.)
7. **Headers** (left menu) → add five rules, each with Path `/*`:

   | Name | Value |
   |---|---|
   | `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://compass-api-tft8.onrender.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'` |
   | `X-Content-Type-Options` | `nosniff` |
   | `X-Frame-Options` | `DENY` |
   | `Referrer-Policy` | `strict-origin-when-cross-origin` |
   | `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` |

   **Save Changes**. (These are the values in `render.yaml`; copy them from there if in doubt.)
8. **Settings** → **Auto-Deploy**: Off.

### 9d. Keep awake

A free web service sleeps after about 15 minutes without a request, and waking it is a restart:
the sessions, the tickets and the spend counter are gone. A free monitor that calls it every five
minutes keeps it awake (the health check makes no model call, so it costs nothing):

1. Go to <https://uptimerobot.com> and sign up (the free plan is enough).
2. **New monitor** (or **+ Add New Monitor**). **Monitor type:** HTTP(s).
3. **URL:** `https://compass-api-tft8.onrender.com/api/health`. **Name:** `compass-api`.
   **Monitoring interval:** 5 minutes.
4. **Create monitor**. Within a few minutes it shows **Up**.

The static site doesn't sleep, so `compass-web` needs no monitor. One service awake all month
fits in the free plan's monthly instance hours.

### 9e. The final day: no redeploy

On the day of the final, **don't deploy and don't change any environment variable** on
`compass-api`: either restarts it, and a restart wipes every session and ticket (and the spend
counter). Deploy the day before, run 9f, and leave it running with the monitor on. If it is
restarted anyway (Render maintenance), nothing needs doing: open a new conversation. The local
fallbacks in sections 5 and 6 don't depend on Render at all.

### 9f. Check it from outside

From the repo root on your machine:

```powershell
uv run --project backend python tasks.py smoke --api https://compass-api-tft8.onrender.com --web https://compass-web-hcpz.onrender.com
```

It checks, in order: `/api/health` answers ok; a CORS preflight from the UI's origin is allowed;
a session opens; its event stream delivers the first event; and `/rep` loads from the UI's
address (the UI's page, not a 404). It ends with `smoke: OK`, or stops at the first failure and
says which step. It sends no token and prints no secret. `health: ok (llm: anthropic)` confirms
live mode. (It leaves one empty session behind; harmless. If the API was asleep, the first step
can take a minute.)

Then open https://compass-web-hcpz.onrender.com in a browser: the employee screen; send one message
to see a real reply. Open https://compass-web-hcpz.onrender.com/rep and enter the rep token.

### Later

- *Deploy a new version:* each service's page → **Manual Deploy** → **Deploy latest commit**.
  A new API version restarts it: the sessions are gone (9e).
- *Change a value* (a token, the cap): `compass-api` → **Environment** → edit → **Save
  Changes**; Render restarts the service (the sessions are gone). A change to the UI's
  `VITE_API_BASE_URL` needs a deploy of `compass-web` to take effect.
- *Stop it:* each service's page → **Settings** → bottom → **Suspend** (or **Delete**). Pause
  the UptimeRobot monitor too.

### If something fails

- *The API's build fails with `lstat /opt/render/project/src/backend/backend: no such file or
  directory`:* the Dockerfile path or build context was given from the repo root. With the root
  directory `backend`, they are `./Dockerfile` and `.`.
- *`Compass will not start in live mode`, about a token:* a token is empty or a demo value;
  fix it under **Environment**.
- *The health check times out:* look at the API's **Logs** for the error above the timeout.
- *The UI's build fails at `npm ci` or with an engine error:* check `NODE_VERSION` (22.19.0) and
  that the root directory is `frontend`.
- *The screens load but say they can't connect* (or the browser console shows "blocked by CORS
  policy"): `COMPASS_CORS_ORIGINS` on `compass-api` isn't exactly the address in the browser's
  address bar. `smoke` says the same at its CORS step.
- *The console shows "violates the Content Security Policy ... connect-src":* the API's address
  in the UI's `Content-Security-Policy` header isn't the one in `VITE_API_BASE_URL`.
- *`/rep` is a 404 on `compass-web`:* the rewrite rule is missing (9c, UI step 6).
- *Replies stop with an error and the Anthropic Console shows the workspace at its limit:* that
  is the hard spend limit doing its job; raise it in the Console only if you mean to.

## 10. The payslip upload (optional, behind a flag)

Off by default in the code (`COMPASS_PAYSLIP=0`), **on in production**: `render.yaml` sets
`COMPASS_PAYSLIP=1` for `compass-api`. Locally and in tests it stays off unless you set it.

**Before you turn it on (live)**

1. `ANTHROPIC_API_KEY` is set (the same key as the agent's); `COMPASS_PAYSLIP=1`. Without the
   key the server refuses to start and names the variable.
2. `uv run --project backend python tasks.py payslip-check`: both models exist, take a PDF and an
   image, and read the synthetic payslip (8 of 8 fields). About $0.02.
3. `uv run --project backend python tasks.py payslip-smoke`: payslips 1 to 4, including the
   injection one (it must print "base_salary was not 99999" and no group field). About $0.002.
4. Upload a real-looking payslip yourself, check the card against it, confirm, and look at the
   cards: the changed inputs carry the green **לפי התלוש** chip.
5. Remember the privacy notice names Anthropic: the payslip is sent there to be read. Use
   synthetic payslips on stage, never a real person's.

**On stage (demo mode)**: `$env:COMPASS_PAYSLIP="1"` then `tasks.py demo`. The paperclip appears
next to the message box; any PDF, JPG or PNG under 5 MB reads as the demo payslip (no key, no
network). After "אישור ושמירה" the salary and pension cards say **לפי התלוש** and the diff moves.
Judges mode shows the read: each field, its confidence and flag (and, live, the model and cost),
never the file. The scripted model answers a confirmation with one fixed line, no numbers.

**If it misbehaves**: set `COMPASS_PAYSLIP=0` and restart (Render: **Environment** → save). The
endpoints answer 404 and the button disappears. (On Render's free plan a restart also drops
every session, a pending card included.)

**Limits** (all settings, defaults): 5 MB, 3 pages, 3 uploads per session, 5 per IP per minute,
20 s per attempt and 45 s in all; an upload over the daily spend cap is refused.

## 11. Accounts (optional, behind a flag)

Off by default (`COMPASS_AUTH=0`): nothing below applies and the static rep and admin tokens work as
before. With `COMPASS_AUTH=1` the tokens are refused and everyone logs in. Users and history live
in the container's own database, so **every deploy wipes them**; the accounts in
`COMPASS_SEED_USERS` are re-created at each start.

**The three demo accounts (employee, rep, admin), without a password ever in a command line or a
file.** `tasks.py hash-password` asks for the password twice with no echo and prints only its
argon2id hash. In Windows PowerShell, from the repository root:

```powershell
$accounts = @(
  @{ email = 'employee@example.com'; name = 'Dana Levi';  role = 'employee' },
  @{ email = 'rep@example.com';      name = 'Avi Cohen';  role = 'rep' },
  @{ email = 'admin@example.com';    name = 'Admin';      role = 'admin' }
)
foreach ($account in $accounts) {
  Write-Host "Password for $($account.email) (10 to 128 characters, typed at the prompt):"
  $account.password_hash = uv run --project backend python tasks.py hash-password | Select-Object -Last 1
}
$env:COMPASS_SEED_USERS = ConvertTo-Json -Compress -InputObject @($accounts)
```

The password is typed only at the
prompt, so it is never in the shell history or in a file. The hash is not a secret you can log, but
keep it out of the repository too: set `COMPASS_SEED_USERS` in the shell (local) or in the Render
dashboard (`sync: false`, never in `render.yaml`).

A live server with `COMPASS_AUTH=1` refuses to start when `COMPASS_SEED_USERS` holds no `admin`,
or a hash that is not argon2id; it says which entry, never the value.

**Trying it locally (two commands).** From the repository root:

```powershell
uv run --project backend python tasks.py setup-demo-accounts
uv run --project backend python tasks.py serve --accounts
```

`setup-demo-accounts` asks for three passwords (employee, rep, admin; each twice, no echo) and
writes the one `COMPASS_SEED_USERS=...` line in `backend\.env` (git-ignored), hashes only. The
accounts are `employee@demo.compass`, `rep@demo.compass` and `admin@demo.compass`. It prints only
"3 demo accounts saved to backend\.env". `serve --accounts` turns `COMPASS_AUTH=1` and
`COMPASS_PAYSLIP=1` on for that process only (the file keeps its values), uses
`backend\data\accounts-local.db` (never `app.db`), rebuilds the UI if it is older than its
source, then serves http://127.0.0.1:8000 and prints "accounts: ON". Without
`COMPASS_SEED_USERS` it stops and says to run `setup-demo-accounts`. The live server still needs
`ANTHROPIC_API_KEY` for the payslip upload and non-placeholder rep and admin tokens in
`backend\.env`.

**Turning it on (Render).** Build `COMPASS_SEED_USERS` as above (one employee, one rep, one
admin), then in the `compass-api` service's **Environment**: paste it into `COMPASS_SEED_USERS`
(declared `sync: false`, so it is never in the repo), set `COMPASS_AUTH` to `1` and save. The
service restarts, creates the three accounts, and refuses to start if there is no admin or a hash
is not argon2id (it names the entry, never the value). The static `COMPASS_REP_TOKEN` and
`COMPASS_ADMIN_TOKEN` stop working while it is on. To turn it off, set `COMPASS_AUTH` back to `0`.

**What a deploy does.** The free plan has no disk, so every deploy or restart wipes the users,
their conversations and any invite; the three seeded accounts come back with their original
passwords, and anyone else must be invited again. Do not promise judges that a conversation
survives a redeploy.

**By-hand checklist (after turning it on, from outside).**

1. `/` shows the landing page, not the old chat; `/register` loads.
2. Log in as the employee: the greeting names them; send a message; the conversation appears in the
   list with a title and, after a comparison, the diff and its state.
3. Log out: back on the landing page, and the old conversation's address shows it too.
4. Log in as the admin: `/admin` lists the three accounts; invite an email, copy the code from the
   dialog (it will not be shown again), close it; register that email in a private window.
5. As the employee, open a conversation address in a second browser logged in as someone else: it
   must say the page was not found.
6. As the rep: `/rep` opens the inbox with no token to type; the admin gets "not found" on it.
7. Disable a user in `/admin` while they are logged in: their next action sends them to the
   landing page with "החיבור הסתיים, צריך להיכנס שוב".
8. Delete a conversation: it disappears from the list, and its address says not found.
9. Wrong password five times from one device: the sixth is refused with the same message and a
   "try again in a few minutes" hint; the right password from another device still works.
10. Run `uv run --project backend python tasks.py smoke --api <api> --web <web>`: it opens a session
    without a login, which must now fail (401) with the flag on, so skip this step then and rely on
    the list above.

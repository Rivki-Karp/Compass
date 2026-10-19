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
  midnight UTC. It is kept on the `/data` volume, so a restart doesn't reset it.
- **A per-IP rate limit** on sending messages: `COMPASS_MESSAGE_RATE_PER_MINUTE` (default 20;
  429 with `Retry-After` beyond it). It counts the socket's client IP. Behind a platform's
  reverse proxy (Render), set `COMPASS_TRUST_PROXY=1`: it then counts the rightmost
  `X-Forwarded-For` entry, the address the proxy itself saw and appended (the entries to its
  left come from the browser and can be forged, so they are ignored). Otherwise every employee
  shares the proxy's limit. Never set it without such a proxy in front: anyone could then pick
  their own key. The count is per process, which is fine: the server runs one worker.
- **CORS: one origin allowed, exactly.** The UI on Cloudflare Pages is another origin, so the
  backend allows it by name: `COMPASS_CORS_ORIGINS`, a comma-separated list of exact origins
  (no wildcard, no trailing slash). Empty, the default, means the same origin only.

## 9. Deploy

Prepared, not deployed. Two services, in this order:

1. **Render** runs the backend (`backend/`): the API, the agent and the session databases.
2. **Cloudflare Pages** serves the UI (`frontend/`): static files only, which call the backend.

Render goes first because the UI needs the backend's address when it is built, and the backend
needs the UI's address before it lets the browser in (CORS). You need about 40 minutes, a credit
card for Render (a persistent disk needs a paid plan: the Starter instance plus 1 GB of disk, a
few dollars a month), a free Cloudflare account, and access to the GitHub repo.

Do every step on the branch you deploy (the approved one; `main` once it is merged). Neither
service redeploys by itself on a push to it (Render: `autoDeploy: false`; Pages: you can turn
automatic deploys off in its settings, see "Later").

### 9a. Render: the backend

**What it creates:** one web service named `compass`, built from `backend/Dockerfile` with
`backend/` as the build context (no Node in it), one instance (never more: the agent keeps
per-session state in memory), in Frankfurt, with a 1 GB disk at `/data` for the session
databases. Render checks `/api/health`. `render.yaml` at the repo root describes all of it;
Render reads it when you create a "Blueprint".

**Before you start**, have these three secrets ready (in a password manager, never in a file in
the repo):

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | the live key |
| `COMPASS_REP_TOKEN` | a new long random token (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `COMPASS_ADMIN_TOKEN` | another new one, different from the rep token |

A fourth variable, `COMPASS_CORS_ORIGINS`, is the UI's address. You don't know it yet: leave it
empty now and fill it in at step 9c. `render.yaml` sets the rest: `COMPASS_LLM=anthropic`,
`COMPASS_DAILY_SPEND_CAP_USD=5`, `COMPASS_MESSAGE_RATE_PER_MINUTE=20` and `COMPASS_TRUST_PROXY=1`
(Render's proxy is in front; section 8). Never reuse the demo tokens: a live server refuses to
start with them (section 1).

**Steps:**

1. Go to <https://dashboard.render.com> and sign up or log in. "Sign in with GitHub" is the
   simplest.
2. Add a payment method: your account menu (top right) → **Billing** → add a card.
3. Top right, click **New +** → **Blueprint**.
4. Under "Connect a repository", click **Connect GitHub** (first time only), allow Render to
   see the `Compass` repository (you can choose "Only select repositories"), then pick
   `Rivki-Karp/Compass` in the list and click **Connect**.
5. **Blueprint Name:** `compass`. **Branch:** the branch to deploy. Render shows what
   `render.yaml` will create: one web service `compass` (root directory `backend`) and its disk.
6. Render lists four variables, each with an empty box. Paste the three secrets from the table.
   Check for stray spaces; they are stored by Render, not in the repo. Leave
   `COMPASS_CORS_ORIGINS` empty. (If Render insists on a value, type the address the UI will
   most likely get, `https://compass.pages.dev`, and correct it at step 9c.)
7. Click **Apply** (or **Deploy Blueprint**). The first build takes 5–10 minutes: open the
   `compass` service → **Logs** to follow it. It is done when the service shows **Live**.
8. At the top of the service page, copy its address, like `https://compass-xxxx.onrender.com`.
   This is the **backend URL**. Open `<backend URL>/api/health` in a browser: a short JSON with
   `"ok": true`. (The backend has no screens: `/` is a 404. The screens are on Pages.)

### 9b. Cloudflare Pages: the UI

The UI is built on Cloudflare from `frontend/`. Its one setting, `VITE_API_BASE_URL`, is the
backend URL; it is written into the JavaScript when the site is built, so anyone can read it.
That is fine for a URL and the reason nothing secret ever goes there (no key, no token).

1. Go to <https://dash.cloudflare.com> and sign up or log in (the free plan is enough).
2. In the left menu, click **Workers & Pages** → **Create** (or **Create application**) → the
   **Pages** tab → **Connect to Git** (or **Import an existing Git repository**).
3. Connect your GitHub account (first time only), allow Cloudflare to see the `Compass`
   repository, select `Rivki-Karp/Compass` and click **Begin setup**.
4. **Project name:** `compass`. The site's address will be `https://compass.pages.dev` (if that
   name is taken, Cloudflare adds a suffix; the address shows on the next screen). **Production
   branch:** the branch to deploy.
5. **Build settings:**
   - **Framework preset:** None (or "React (Vite)"; then check the two fields below).
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
   - **Root directory (advanced):** `frontend`
6. **Environment variables (advanced)** → add two, as plain text (not "Encrypt"):
   - `NODE_VERSION` = `22.19.0` (the version in `frontend/.nvmrc`)
   - `VITE_API_BASE_URL` = the backend URL from 9a step 8, e.g.
     `https://compass-xxxx.onrender.com` (no `/api`, no slash at the end)
7. Click **Save and Deploy**. The build takes 1–3 minutes. When it says **Success**, the site's
   address is shown: this is the **web URL**, e.g. `https://compass.pages.dev`.

The build also writes the two Pages files from `frontend/public/`: `_redirects` sends every path
to the UI (so `/rep` opens directly), and `_headers` adds the security headers and a Content
Security Policy that lets the page connect only to itself and to the backend URL.

The screens won't work yet: the backend still refuses the web URL. That is the next step.

### 9c. Back to Render: let the UI in

1. Render → the `compass` service → **Environment**.
2. Set `COMPASS_CORS_ORIGINS` to the web URL exactly, e.g. `https://compass.pages.dev`: with
   `https://`, without a slash or a path at the end. (Several origins: separate them with commas.
   A `*` is refused.)
3. **Save Changes**. Render restarts the service (about a minute, with the disk).

Only that exact address is allowed. Pages also publishes each build at its own preview address
(like `https://1a2b3c4d.compass.pages.dev`); those are refused unless you add them too.

### 9d. Check it from outside

From the repo root on your machine:

```powershell
uv run --project backend python tasks.py smoke --api https://compass-xxxx.onrender.com --web https://compass.pages.dev
```

It checks, in order: `/api/health` answers ok; a CORS preflight from the web URL's origin is
allowed; a session opens; its event stream delivers the first event; and `/rep` loads from the
web URL (the UI's page, not a 404). It ends with `smoke: OK`, or stops at the first failure and
says which step. It sends no token and prints no secret. `health: ok (llm: anthropic)` confirms
live mode. (It leaves one empty session behind; harmless.)

Then open the web URL in a browser: the employee screen; send one message to see a real reply.
Open `<web URL>/rep` and enter the rep token.

### Later

- *Deploy a new backend version:* Render service page → **Manual Deploy** → **Deploy latest
  commit**. With a disk, Render stops the old instance before it starts the new one: about a
  minute offline.
- *Deploy a new UI version:* Pages builds every push to the production branch by itself. To
  deploy only by hand: the Pages project → **Settings** → **Builds** (or **Build & deployments**)
  → turn automatic production deployments off; then **Deployments** → **Retry deployment** (or
  create one) when you want it.
- *Change the backend URL:* change `VITE_API_BASE_URL` in the Pages project's **Settings** →
  **Environment variables**, then deploy again: it is baked in at build time, so a saved value
  alone changes nothing.
- *Change a backend value* (a token, the cap, the allowed origin): Render service page →
  **Environment** → edit → **Save Changes**; Render restarts the service.
- *Stop it:* Render service page → **Settings** → bottom → **Suspend Web Service** (or
  **Delete**; the disk, with the sessions, is deleted only then). Pages: the project →
  **Settings** → **Delete project**.

### If something fails

- *Render's logs end with `sqlite3.OperationalError: unable to open database file`:* the server
  can't write to `/data`. The entrypoint gives the app user (uid 10001) the mount at every start,
  even a root-owned one (checked locally), so this means the disk is missing or not at `/data`:
  service page → **Disks**.
- *`Compass will not start in live mode`, about a token:* a token is empty or a demo value;
  fix it under **Environment**.
- *Render's health check times out:* look at **Logs** for the error above the timeout.
- *The Pages build fails at `npm ci` or with an engine error:* check `NODE_VERSION` (22.19.0) and
  that the root directory is `frontend`.
- *The screens load but say they can't connect* (or the browser console shows "blocked by CORS
  policy"): `COMPASS_CORS_ORIGINS` on Render isn't exactly the address in the browser's address
  bar. `smoke` says the same at its CORS step.
- *The console shows "violates the Content Security Policy ... connect-src":* the UI was built
  with another `VITE_API_BASE_URL`, or none. Fix it on Pages and deploy again.
- *`/rep` is a 404 on Pages:* the build output is missing `_redirects`; check the output
  directory is `dist` and the root directory `frontend`.

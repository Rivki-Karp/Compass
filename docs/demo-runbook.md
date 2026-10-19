# Demo runbook: the final (Wed 21/10/2026)

Seven minutes, two browser windows, one laptop. The live run uses the real model; if the
network or the API fails at any point, switch to demo mode (section 5): the screens and the
numbers are the same, with no key and no network. If the laptop itself can't run the app, play
the backup video (section 6).

Fallbacks in order: live (section 3) → demo mode with `tasks.py demo` (5a) → demo mode in Docker
(5b) → the backup video (6).

## 1. Before you go on stage

The day before, in PowerShell, from the repo root:

```powershell
git pull
uv run python tasks.py data          # only if data/vehicles.db is missing
uv run python tasks.py build-web     # the UI the server will serve
uv run python tasks.py test          # optional sanity check
```

Check `.env` has `ANTHROPIC_API_KEY`, `COMPASS_REP_TOKEN` and `COMPASS_ADMIN_TOKEN`. An empty
token disables its screen: `/rep` and the judges-mode dialog then say "טוקן לא הוגדר בשרת", and
`tasks.py serve` prints a warning at startup naming the empty variable. To generate a token, run
this in PowerShell once per token and paste the output after the `=` in `.env`:

```powershell
[guid]::NewGuid().ToString()
```

Restart the server after changing `.env`. In live mode the server refuses to start while either
token is empty or a demo / placeholder value (`rep-demo`, `admin-demo`, or the `.env.example`
placeholders), and says which one; demo mode (5a, 5b) keeps its `rep-demo` / `admin-demo`. Write the two tokens on a card: you'll type them on
stage.

Build the Docker image too, while there is network (it downloads npm and PyPI packages; on
stage, `up` without `--build` needs no network). On a NetFree connection, point the build at its
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
   uv run python tasks.py serve
   ```

   (`final.db` is created on first use and is git-ignored. Delete it to start over.)
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
uv run python tasks.py demo
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

Stop whatever is on port 8000, then, with the image built the day before (section 1):

```powershell
docker compose --profile demo up
```

The same URLs and the same tokens (`rep-demo` / `admin-demo`, unless `.env` sets others); the
health check turns "healthy" within a few seconds. Then continue as in 5a. Ctrl+C stops it. To
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
uv run python tasks.py record-demo
```

## 7. After the demo

- Stop the server (Ctrl+C), or `docker compose --profile demo down`.
- `data\final.db` and `data\demo.db` hold only the demo's sessions; delete them if you like.
  `data\app.db` was not touched. Docker's sessions live in its own volumes.

## 8. Before a public deployment (live mode)

Not deployed anywhere yet; section 9 has the Render steps. What the single container already does:

- **Configuration from the environment only.** The image sets `COMPASS_ENV_ONLY=1`: no `.env`
  file is read, and none is in the image (`scripts/check_image_secrets.py`, run in CI). Set
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

## 9. Deploy to Render

Prepared, not deployed. `render.yaml` at the repo root describes the service; Render reads it
when you create a "Blueprint". You need about 20 minutes, a credit card (a persistent disk needs
a paid plan: the Starter instance plus 1 GB of disk, a few dollars a month) and access to the
GitHub repo.

**What it creates:** one web service named `compass`, built from the repo's `Dockerfile`, one
instance (never more: the agent keeps per-session state in memory), in Frankfurt, with a 1 GB
disk mounted at `/data` for the session databases. Render checks `/api/health`. It does not
redeploy on a push (`autoDeploy: false`): you deploy by hand.

**Before you start**, have these three secrets ready (in a password manager, never in a file in
the repo). Render asks for them; nothing else needs typing:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | the live key |
| `COMPASS_REP_TOKEN` | a new long random token (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `COMPASS_ADMIN_TOKEN` | another new one, different from the rep token |

`render.yaml` sets the rest: `COMPASS_LLM=anthropic`, `COMPASS_DAILY_SPEND_CAP_USD=5`,
`COMPASS_MESSAGE_RATE_PER_MINUTE=20` and `COMPASS_TRUST_PROXY=1` (Render's proxy is in front;
section 8). To change one for this deployment, edit it under **Environment** after the deploy.

Never reuse the demo tokens: a live server refuses to start with them (section 1).

**Steps:**

1. Go to <https://dashboard.render.com> and sign up or log in. "Sign in with GitHub" is the
   simplest.
2. Add a payment method: your account menu (top right) → **Billing** → add a card.
3. Top right, click **New +** → **Blueprint**.
4. Under "Connect a repository", click **Connect GitHub** (first time only), allow Render to
   see the `Compass` repository (you can choose "Only select repositories"), then pick
   `Rivki-Karp/Compass` in the list and click **Connect**.
5. **Blueprint Name:** `compass`. **Branch:** the branch to deploy (the approved one; `main`
   once the fixes are merged). Render shows what `render.yaml` will create: one web service
   `compass` and its disk.
6. Render lists the three secrets above, each with an empty box. Paste each value from the
   table. Check for stray spaces. These are stored by Render, not in the repo.
7. Click **Apply** (or **Deploy Blueprint**). The first build takes 5–10 minutes: open the
   `compass` service → **Logs** to follow it. It is done when the service shows **Live**.
8. At the top of the service page, copy its address (like `https://compass-xxxx.onrender.com`).
9. From the repo on your machine, check it from outside:

   ```powershell
   uv run python tasks.py smoke --url https://compass-xxxx.onrender.com
   ```

   It checks `/api/health`, opens a session and reads its first event, and ends with
   `smoke: OK`. It sends no token and prints no secret. `health: ok (llm: anthropic)` confirms
   live mode. (It leaves one empty session behind; harmless.)
10. Open the address in a browser: the employee screen, then `/rep` with the rep token. Send one
    message to see a real reply.

**Later:**

- *Deploy a new version:* service page → **Manual Deploy** → **Deploy latest commit**. With a
  disk, Render stops the old instance before it starts the new one: about a minute offline.
- *Change a value* (a token, the cap): service page → **Environment** → edit → **Save
  Changes**; Render restarts the service.
- *Stop it:* service page → **Settings** → bottom → **Suspend Web Service** (or **Delete**). The
  disk, with the sessions, is deleted only when the service is.

**If the deploy fails:**

- *The logs end with `sqlite3.OperationalError: unable to open database file`:* the server can't
  write to `/data`. The entrypoint gives the app user (uid 10001) the mount at every start, even
  a root-owned one (checked locally), so this means the disk is missing or not at `/data`:
  service page → **Disks**.
- *`Compass will not start in live mode`, about a token:* a token is empty or a demo value;
  fix it under **Environment**.
- *The health check times out:* look at **Logs** for the error above the timeout.

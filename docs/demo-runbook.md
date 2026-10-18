# Demo runbook: the final (Wed 21/10/2026)

Seven minutes, two browser windows, one laptop. The live run uses the real model; if the
network or the API fails at any point, switch to demo mode (section 5): the screens and the
numbers are the same, with no key and no network.

## 1. Before you go on stage

The day before, in PowerShell, from the repo root:

```powershell
git pull
uv run python tasks.py data          # only if data/vehicles.db is missing
uv run python tasks.py build-web     # the UI the server will serve
uv run python tasks.py test          # optional sanity check
```

Check `.env` has `ANTHROPIC_API_KEY`, `COMPASS_REP_TOKEN` and `COMPASS_ADMIN_TOKEN`, and write
the two tokens on a card: you'll type them on stage.

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
- **Anything slower than 30 seconds, an error message, or no network:** go to section 5. Don't
  debug on stage.

## 5. Fallback: demo mode (no network, no key)

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

## 6. After the demo

- Stop the server (Ctrl+C).
- `data\final.db` and `data\demo.db` hold only the demo's sessions; delete them if you like.
  `data\app.db` was not touched.

# Brief: Judges mode for any user (admin-password unlock) + demo quick access on the landing page

You are the **senior engineer** on Compass. Act like one. Read the auth module (users, auth_sessions, seeding, lockout), the ownership guard, the judges/engine-room view and its redaction, the admin API, and the landing page before designing anything. Reuse them. Before each stage, write a short design note covering the approach, the risks and how you handle them. If something contradicts the code, or weakens an existing security guarantee, **stop and ask**.

Commit this file as `briefs/judges-and-demo-access.md` in the first commit.

## 0. Base and rules

- **Branch:** `feat/judges-demo-access`, from `main` (latest tag). Tell me which tag.
- **Flags:** `COMPASS_JUDGES_UNLOCK` and `COMPASS_DEMO_LOGIN`, both default `0` in code and `"1"` in `render.yaml`. With both off, everything is byte-identical to today.
- **Frozen:** prompts, tool descriptions, scenarios, calculations, and the guard's accept/reject logic.
- **The usual rules:** one commit per stage, the full `tasks.py check` (with Playwright) green after each, explicit paths only, PowerShell docs, and no merge, tag or deploy without me.
- **Never log, print, store in plain text, or return** a password or a token.

## 1. What we want

1. **Judges mode for any logged-in user.** An employee (or anyone) toggles "מצב שופטים". If their login isn't unlocked yet, a small dialog asks for **the admin password**. When the password is right, the **full** engine room is shown, **for that user's own conversations only**.
2. **Demo quick access on the landing page.** A section for judges and recruiters, "כניסה מהירה להתנסות", with three buttons: **עובדת · נציג · מנהלת**. Each one logs in to the matching demo account in one click, with no password to type.

## 2. Security design (non-negotiable)

### Judges unlock
- **The endpoint:** `POST /api/auth/judges-unlock` `{password}`.
  - Login is required.
  - The password is verified against **every active admin account's** argon2id hash. Verify all of them with no short-circuit, so the timing doesn't reveal which admin matched.
  - On success, mark **the current auth session** `judges_unlocked_at`.
    - It is not a new token.
    - It ends on logout, on the session's expiry, or when the user is disabled.
  - The same lockout rules as login apply, keyed by (user, IP): 5 failures lock it for 15 minutes. The error is always the generic "הסיסמה שגויה".
- **What it grants:** the **full** engine-room payload, exactly what an admin sees today for their own session, but **only for sessions the user owns**. The ownership guard is unchanged. An unlocked employee still gets 404 on anyone else's session.
- **Admins** stay as today: full view on their own sessions, no unlock needed.
- **The rep page** has no conversations, so there's no judges mode there. If you see a meaningful equivalent, propose it; don't build it.
- **Locking again:** `POST /api/auth/judges-lock`, so the user can turn it off.

### Demo login
- **Demo accounts:** seed users get a `demo: true` field in `COMPASS_SEED_USERS`. The existing three demo accounts are marked demo.
- **The endpoint:** `POST /api/auth/demo-login` `{role}`.
  - It works only when `COMPASS_DEMO_LOGIN=1`.
  - It logs in as the active demo account with that role.
  - **No password is involved or exposed.**
  - Rate-limited per IP (e.g. 10/min).
  - The resulting auth session is marked `demo_session=true`.
- **Protecting the demo from the public.** Anyone can now be the demo admin, so in **demo sessions**:
  - **Demo accounts can't be deleted, disabled or changed in role.** That is refused for everyone. A non-demo admin may do it only through an explicit flag in a future brief, not now.
  - **A demo-admin session lists and manages only demo accounts, plus users invited from a demo session** (tag the invite and the user as `demo_origin`). Real users' emails and names are never shown to a demo session.
  - Invites from demo sessions are capped (e.g. 20 per day overall) and expire as usual.
  - **Judges unlock in a demo session works exactly as in any other session:** it requires the admin password. The demo admin's password is never shown anywhere in the UI. Judges get it through the submission form only.
- **Shared demo state:** everyone using the demo employee shares its conversations and saved details. That is acceptable and documented. The memory card still asks first.

## 3. Stages

### Stage 1: Backend

- **Data:** `auth_sessions.judges_unlocked_at` and `auth_sessions.demo_session`; `users.demo`; `users.demo_origin`; `invites.demo_origin`. All additive, created at start-up.
- **Endpoints:** the three routes above, wired into the ownership/route-classification test, which must fail if one is unclassified.
- **The judges payload:** where the API decides "full vs redacted", the rule becomes "full if `role == admin` **or** `session.judges_unlocked_at`, **and** the caller owns the session".
- **The admin API:** add the demo-session scoping and the demo-account protections.
- **Tests:**
  - **unlock:** right password, wrong password, lockout per (user, IP), and timing parity (verify that all hashes are checked);
  - **scope:** the unlocked full view is on the owner's sessions only, and another user's session still returns 404; it ends on logout, expiry and disable; lock works;
  - **demo login:** each role, flag off returns 404, the rate limit, and that no password appears anywhere;
  - **demo protections:** demo accounts can't be deleted, disabled or changed in role; a demo-admin session sees only demo and demo-origin users (asserted on the response); the invite cap;
  - **flag off:** byte-identical.

**STOP after Stage 1** with the design notes, the route table and the test list.

### Stage 2: UI

- **The judges toggle:** if the session isn't unlocked, it opens a dialog with the title "מצב שופטים", the text "הזינו את סיסמת המנהל כדי לראות את חדר המנועים", a password field, and the buttons "פתיחה" and "ביטול".
  - The error is generic.
  - Focus is trapped, and Esc closes it.
  - On success, the engine room opens.
  - Turning the toggle off again offers "נעילה" (lock).
- **The landing page section "כניסה מהירה להתנסות":**
  - It sits below the login card, styled to match: three buttons, **עובדת**, **נציג** and **מנהלת**, each with a one-line hint:
    - "צ'אט, תלוש והיסטוריה"
    - "מענה לפניות"
    - "הזמנת משתמשים · מצב שופטים"
  - Under them, a small line: "חשבונות הדגמה משותפים. אל תזינו מידע אישי אמיתי."
  - It is shown only when the API reports demo login is on.
- **A demo banner after a demo login:** a thin strip, "את/ה בחשבון הדגמה משותף", with a link to log out.
- **Tests:**
  - vitest for the dialog states;
  - Playwright: demo login × 3 roles; an employee unlocks judges mode with the admin password and sees the guard card on their own conversation; a wrong password shows the generic error; a demo-admin session can't delete a demo account (the button is disabled, with a tooltip); flag off shows no section;
  - axe on the dialog and the landing section;
  - screenshots at 1440 and 400.

### Stage 3: Docs and report

- **README:** "מצב שופטים לכל משתמש" and "כניסה מהירה להדגמה", including the protections and the shared-demo note.
- **The runbook:** how to mark the seed users demo in `COMPASS_SEED_USERS`, and the env vars.
- **`render.yaml`:** both flags `"1"`.
- **Evals:** none needed, since no agent behaviour changes. Run the 8 key scenarios once to confirm, and report the cost.
- **The report covers:** per stage, what changed; test counts; screenshots; anything left open.

**STOP after Stage 3.** Push. Do not merge, tag or deploy.

## 4. Out of scope

Showing any password in the UI, judges mode on other users' sessions, a reset flow, and changes to calculations, the guard or the prompts.

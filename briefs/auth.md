# Brief: User accounts, landing page and conversation history (flag `COMPASS_AUTH`)

You are the **senior engineer** on Compass. Act like one. Read the existing code before designing anything. Reuse what is already there: settings, the session/event store and replay, redaction, the rate limiter, the spend cap, the `apiFetch` client with fetch-based SSE, the design tokens and source chips. Do not build a parallel system. Before each stage, write a short design note covering the approach, the risks and how you handle them. If something here contradicts the code, or would break an API, schema or test, **stop and ask**. Never guess on security.

Commit this file as `briefs/auth.md`, and the two design references as `briefs/design/Landing.reference.html` and `briefs/design/Home.reference.html`, in the first commit.

## 0. Base, timing and ground rules

- **Branch:** `feat/auth`, cut from `main` **after** `v1.5` (fix/payslip-ux) is merged. If `v1.5` isn't on `main` yet, stop and ask.
- **The flag:** everything is behind `COMPASS_AUTH`, default `0`.
  - With the flag off, behaviour, APIs and the UI are unchanged. The current static rep/admin tokens keep working.
  - With the flag on, the static tokens are refused.
- **Ground rules (unchanged):**
  - One commit per stage, and the full `tasks.py check` green after each stage, Playwright included.
  - Every command goes through `uv run --project backend python tasks.py …`, documented for Windows PowerShell.
  - Stage explicit paths only. No `git add -A`.
  - Never use `NODE_TLS_REJECT_UNAUTHORIZED=0`.
  - No merge, tag or deploy without my review.
- **Frozen:** `system_he.md`, `system_payslip_he.md`, tool descriptions and `evals/scenarios/` are not touched. Nothing in this brief needs them. Evals run with the flag off.
- **Never log, store in plain text, or return:** a password, an invite code, or a session token. Logs refer to users by id only, never by email.
- **No ID numbers anywhere.** The account holds email, name, role and status only.

## 1. Decisions already made (don't reopen them)

| Topic | Decision |
|---|---|
| Who can register | Only someone the admin invited. The admin adds an email and a role and gets a **one-time invite code**, shown once. The employee registers with email, code, **their own name** and a password |
| Forgot password | **There is no reset flow.** The admin deletes the user and invites them again. The old conversations are deleted with the account |
| Roles | `employee`, `rep`, `admin`, all through the same login |
| Session | A token in `sessionStorage`, sent as `Authorization: Bearer`. It ends when the browser closes, after **8 hours absolute**, or on logout. **No cookies**, because web and api are different sites. That also means no CSRF surface |
| Persistence | **None.** The Render free plan has no disk, so users and history are wiped on every deploy. The 3 demo accounts are re-seeded on every start |
| History | A list of the user's own conversations. **Opening one resumes it exactly where it stopped.** Conversations can be deleted |
| Admin privacy | The admin manages access only: email, name, role, status, created and last login. **The admin can never read any employee's conversation, profile or payslip data** |
| Rep | Sees tickets as today, plus nothing else of the employee's |

## 2. Data model (SQLite, the same `app.db`)

- **`users`:**
  - `id` (uuid)
  - `email`, unique and normalised: trimmed, NFKC, lower-case
  - `name`, 1 to 60 characters
  - `role`
  - `password_hash`, argon2id via `argon2-cffi` with library defaults
  - `status`: `active` or `disabled`
  - `created_at`, `last_login_at`
- **`invites`:**
  - `id`, `email`, `role`
  - `code_hash`: SHA-256 of the code
  - `created_by`
  - `expires_at`: default 48 h, set by `COMPASS_INVITE_TTL_HOURS`
  - `used_at`
  - One active invite per email. A new invite replaces the old one.
- **`auth_sessions`:**
  - `token_hash`: SHA-256
  - `user_id`, `created_at`, `expires_at`, `last_seen_at`, `revoked_at`
- **The existing conversation/session table:** add `owner_user_id`, nullable. It is set when a session is created with the flag on.
- **Migrations:** idempotent and additive, run at start-up. With the flag off, nothing reads the new tables.
- **Codes and tokens:**
  - Codes: 10 characters from an unambiguous alphabet (no 0/O/1/I), shown grouped as `XXXXX-XXXXX`, compared in constant time via hash lookup.
  - Tokens: `secrets.token_urlsafe(32)`.

## 3. Stages

### Stage 1: Settings, data model, hashing, seeding

- **Settings:**
  - `COMPASS_AUTH`: default `0`.
  - `COMPASS_INVITE_TTL_HOURS`: default 48.
  - `COMPASS_SESSION_TTL_HOURS`: default 8.
  - `COMPASS_SEED_USERS`: a JSON list of `{email, name, role, password_hash}`.
  - Login limits: 10 attempts per IP per minute; 5 failures per email lead to a 15-minute lock.
- **Seeding:**
  - On start, upsert every seed user (create or update name, role and hash, and activate).
  - Seed users are re-created after every wipe. This is how the judges' demo accounts survive deploys.
- **Startup refusal:** in live mode with `COMPASS_AUTH=1`, refuse to start when `COMPASS_SEED_USERS` holds no `admin`, or holds a hash that isn't argon2id.
- **`tasks.py hash-password`:**
  - It prompts with `getpass` twice, never echoes, and prints only the hash.
  - Document how to build `COMPASS_SEED_USERS` for 3 demo accounts (employee, rep, admin) **without the passwords ever being typed into a command line or a file**.
- **Tests:**
  - hashing and verification;
  - normalisation (`Dana@X.com ` equals `dana@x.com`);
  - seed upsert;
  - the startup refusal;
  - `repr` of settings never shows hashes.

### Stage 2: Auth API

All of these are under `/api/auth`. They return 404 when the flag is off.

- **`POST /register` `{email, code, name, password}`:**
  - The invite must exist for that email, be unexpired and unused.
  - The password must be 10 to 128 characters and not equal to the email.
  - On success: create the user, mark the invite used, and log in (return the token).
  - Every failure gives the same generic Hebrew message: "הקוד או המייל אינם תקינים". There is no way to probe which emails are invited.
- **`POST /login` `{email, password}`:**
  - The error is always "מייל או סיסמה שגויים".
  - When the user doesn't exist, verify against a dummy hash, so the timing looks the same.
  - Apply the limits from Stage 1. A locked account gets the same message plus a "נסו שוב בעוד כמה דקות" hint, and no lock details.
  - On success, update `last_login_at`.
- **`POST /logout`:** revokes the token.
- **`GET /me`:** returns `{name, role}` (no email needed in the UI header).
- **Auth dependency:**
  - Resolve the bearer to an active user.
  - Missing or invalid token: 401. Disabled user: 401, with all their sessions revoked.
  - Role guards: `require_role("rep")` and `require_role("admin")`.
- **CORS:** check that `Authorization` is allowed from `COMPASS_CORS_ORIGINS`. The rep flow already sends it, so confirm and test.
- **Tests:**
  - every path above;
  - the code is single-use and expires;
  - a replaced invite's old code fails;
  - the lockout and the IP limit;
  - a generic error for each failure kind (assert identical bodies);
  - no password, code or token in captured logs.

### Stage 3: Ownership on every session route (the security core)

- **With the flag on, every route that takes a session/conversation id** goes through one ownership check. That includes messages, SSE stream and replay, snapshot, payslip upload/confirm, current-car, tickets created from the session, judges data, and any other route you find.
- **One rule:** the authenticated user must be the session's owner, otherwise **404** (never 403, so existence doesn't leak). Find every route with a test that enumerates the router, so a new route can't skip the check.
- **Creating a session** requires login and sets `owner_user_id`.
- **Rep routes** require role `rep` or `admin`. **Admin routes** require `admin`.
- **Judges mode:**
  - The full engine-room view is shown to `admin` **only for the admin's own sessions**.
  - Everyone else gets the existing redacted view for their own sessions.
  - Nobody sees another user's session.
- **Per-user limits, in addition to the existing global caps:**
  - the message rate per user;
  - the existing payslip caps, counted per user per day as well as per session.
- **Tests:** an **ownership matrix** for every session route × {anonymous → 401, other user → 404, owner → 2xx, rep on the employee route → 404}. Include SSE and `Last-Event-ID` replay explicitly.

**STOP after Stage 3.** Report the route list with the ownership check per route, the matrix results, and the design decisions. Wait for my approval.

### Stage 4: Conversations API

- **`GET /api/conversations`** returns the user's own list, newest first: `{id, title, updated_at, status, diff}`.
  - **The title is built by the server from state, never by the model:** e.g. "קורולה קרוס מול ATTO 3", "ויתור על הרכב", "כל החלופות בקבוצה ב'", and "שיחה חדשה" when there is nothing yet.
  - `diff` and `status` (`final` / `pending` / `partial` / none) come from the same `view` the UI already uses. Never recompute them here.
- **Resuming:** opening a conversation uses the existing snapshot and replay. Continuing it works like any live session. Test: resume after the server restarts in the same process lifetime, and resume in a different browser with the same account.
- **`DELETE /api/conversations/{id}`:** the owner only. Delete the messages, events and pending payslip candidate. Close any open tickets for it (the rep sees them disappear) and record nothing about its content.
- **Tests:** ordering, titles for each state, the owner-only matrix, and a deleted conversation returning 404 on all its routes.

### Stage 5: Admin API

- **`GET /api/admin/users`:** id, email, name, role, status, created, last login. **Nothing else.**
- **`POST /api/admin/invites` `{email, role}`:** returns the code **once**. Re-inviting an existing user is refused with a clear message; the admin deletes the user first.
- **`PATCH /api/admin/users/{id}`:** role and status. An admin can't disable or demote themselves, or remove the last admin.
- **`DELETE /api/admin/users/{id}`:** deletes the user, their sessions and all their conversations (same as Stage 4 delete). The same last-admin guard applies.
- **Tests:**
  - admin only;
  - the guards;
  - a test that no admin route exposes conversation, profile or payslip fields (assert on the response schemas).

### Stage 6: UI, landing page and login

**The design references in `briefs/design/` are the source of truth for layout, copy and motion.** Build them with the existing tokens and components, in React and Tailwind. Do not paste the HTML.

- **Landing (`/`, flag on and logged out):**
  - **The large logo:** the compass mark in a white circle, with a pulsing blue halo and two slowly rotating compass rings.
  - **Under it:** "COMPASS", and **"יועץ הרכב של שטראוס"** in Hebrew.
  - **The headline, exactly:** "כך תוכלו לדעת בדיוק כמה נשאר בנטו, לפני שבוחרים רכב."
  - **The live demo card:** it loops between "+661 ₪ · ממתינה לנציג" and "+611 ₪ · סופי". The bars grow, and the source chips appear. The numbers are the E-001 demo values, static in the UI. This is marketing, not a calculation, so keep it in one constants file with a comment.
  - **The glass login card:** email, password, "כניסה", and "קיבלת קוד הזמנה? הרשמה ראשונה".
  - **Below:** the "המודל לא מחשב כסף. אף פעם." section with the three steps, the three feature cards, and the footer with the privacy line and "פותח במסגרת האתגר של קבוצת שטראוס".
  - **No Strauss logo.**
- **Register (`/register`):** email, invite code (auto-formats `XXXXX-XXXXX`), name, password, confirm password, and the same generic error.
- **Motion:** CSS only. Every animation is disabled under `prefers-reduced-motion`.
- **Phone width (below 700 px):** the login card moves below the headline, and the demo card follows.
- **Auth client:**
  - The token lives in `sessionStorage`. `apiFetch` adds the header.
  - Any 401 clears the token and returns the user to `/` with "החיבור הסתיים, צריך להיכנס שוב".
  - With the flag off, none of this is mounted. The UI reads the flag from the API, never from a frontend-only constant.

### Stage 7: UI, home, history, admin, rep

- **Home (after login), per `Home.reference.html`:**
  - The header shows the logo, "יועץ הרכב של שטראוס", the user's name, and "יציאה".
  - **The sidebar:** "שיחה חדשה", then the user's conversations (title, date, a diff chip, a status chip), and "רק את/ה רואה את השיחות האלה".
  - **Delete:** an icon button per conversation, with a confirmation dialog.
  - **Empty chat:** "שלום {name}, מה בודקים היום?", the payslip offer card (it already exists, so reuse it), the suggestion chips and the composer with the attach button.
- **Phone width:** the sidebar becomes a drawer, opened from the header.
- **Admin page (`/admin`, role admin):**
  - a users table and an invite form (email, role);
  - a modal that shows the code once, with a copy button and "הקוד יוצג פעם אחת בלבד";
  - controls for role and status, and delete with a confirmation dialog.
  - The page has no link to any conversation.
- **Rep page (`/rep`):** requires login with role `rep` or `admin`. With the flag on, the token-entry screen is gone.
- **Accessibility:** real buttons, links and labels. Focus is visible, RTL order is right, and numbers sit in `<bdi>`.

### Stage 8: Tests, docs, report

- **Playwright, with the flag on and scripted LLM:**
  1. landing → login (demo employee) → chat → logout → back on the landing page;
  2. the admin invites → the employee registers with the code → reaches home;
  3. **isolation:** user A's conversation id opened by user B gives the not-found view;
  4. resume a conversation from the list;
  5. delete a conversation;
  6. the rep logs in and answers a ticket, and the employee's card settles;
  7. a disabled user is logged out on the next request.
- **axe on:** landing, register, home (empty and with history), admin, and the invite-code modal. Fail on serious and critical.
- **Screenshots at 1440 px and 400 px:** landing, home, admin.
- **Evals:** with the flag off, run the 8 key scenarios once, to confirm there is no regression. Report the cost.
- **Docs:**
  - **README:** an accounts section covering roles, the invite flow, "no reset: delete and re-invite", the admin privacy rule, and **no persistence on the free plan: users and history are wiped on deploy, demo accounts are re-seeded**.
  - **`render.yaml`:** `COMPASS_AUTH "0"`, plus `COMPASS_SEED_USERS` with `sync: false`.
  - **The runbook:** how to create the 3 demo accounts and set the env, and the by-hand checklist.
- **The final report:**
  - per stage, what changed;
  - the route/ownership table;
  - test counts per suite;
  - axe results;
  - eval results and cost;
  - anything left open.
  - Also add one paragraph for the hackathon "problems we faced" section, on what was hard about adding accounts safely and how we solved it.

**STOP after Stage 8.** Push `feat/auth`. Do not merge, tag or deploy.

## 4. Out of scope

Password reset, email sending, SSO or Google login, cookies, persistent storage or a paid disk, changes to calculations, the guard, the prompt, tool descriptions or eval scenarios, and the Strauss logo.

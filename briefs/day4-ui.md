# Day 4 Brief — Compass UI (employee, representative, judges mode)

Branch: `day4/ui`, cut from `main` at tag `day3-complete`.
Commit this file as `briefs/day4-ui.md` in the first commit of the branch.
The logo is at `briefs/assets/compass-logo.png` (I put it there); in Stage 2 copy it to `web/src/assets/`.

## 0. Ground rules (unchanged)

- One commit per stage. After each stage run `ruff check` and `pytest`, and from Stage 2 on also `npm run lint`, `npm run typecheck` and `npm test` in `web/`.
- Stop and ask when something is unclear, or when a change would break an existing API, schema or test. Prefer additive changes.
- Final report before merge. **No push to `main`** without my review. Pushing `day4/ui` is fine.
- The API key lives only in `.env`, only on the server. The browser never talks to Anthropic and never sees the key.
- Never ask for, display or store an ID number.
- Rep/admin tokens are entered in the UI once and kept in `sessionStorage` (never `localStorage`, never in URLs or logs).
- Windows PowerShell: every documented command must work there (`$env:X="1"` on its own line, never `X=1 cmd`).
- Run `/compact` after each stage commit.

## 1. Guiding principle

**The frontend does no money math.** Every amount on screen comes from the API, already computed and rounded for display (`display_diff`, rounded nets, breakdown `net_effect` lines that sum to `display_diff`). The only arithmetic allowed in the browser is bar positioning for the waterfall, checked against the API totals (§7). If an invariant fails, the UI shows an error state, never a silently wrong chart.

Corollaries:
- **No count-up animations on amounts.** A number that ticks 2,800 → 2,914 shows values no tool computed. Animate with crossfade, highlight and the needle, never by interpolating digits.
- Breakdown labels come from the API, not from a frontend dictionary.

Same principle as Day 3: correctness comes from the tools, not from the model, and not from the UI.

## 2. Goal and acceptance

A Hebrew, RTL web app where:
1. The **employee** chats with the agent and sees a **live comparison card** and **waterfall** update after every comparison, with a **source chip** on every input value and a **provenance strip** for any selected breakdown line.
2. The **representative** answers open tickets; the employee's card moves from pending to final live.
3. **Judges mode** opens the "engine room": tool calls and results, the guard's verdict per number, template fallbacks, tokens and cost.
4. **Demo mode** runs the Scripted LLM: the whole demo works with no network and no API spend.

Acceptance numbers (must appear exactly):
- Walkthrough: today **11,000**, waiver **13,914**, difference **+2,914**, breakdown 1500 + 802 + 180 + 132 + 300.
- E-001: **+661** pending → rep answers 350 for `alternative_participation:CAR-10` → **+611**, chip "אושר על ידי נציג", pending state gone.

## 3. Design system (approved mockups — this section is the spec)

The mockups were made outside the repo; you cannot open them, so everything needed is written here. Where this section and your taste disagree, follow this section and note the disagreement in the report.

### 3.1 Concept

"Compass": the logo is a compass whose needle is a steering wheel's center. The UI borrows two things from it: the **navy/royal-blue palette**, and the **needle** as the indicator of direction (up = more net pay, down = less). The look is calm and light for the employee, and a dark navy "engine room" for judges mode. The contrast tells the story: the front for the employee, the engine for the judges.

Innovation comes from **provenance, not effects**: every number can be traced to the tool, input and rule that produced it.

### 3.2 Tokens (define as CSS variables, exposed through the Tailwind theme)

Brand and surfaces:

| Token | Value | Use |
|---|---|---|
| `navy` | `#082350` | brand, headings, employee bubbles, total bar, rep header |
| `royal` | `#1F5FBF` | primary actions, focus ring, selected state, rep chip |
| `steel` | `#2D5C94` | secondary text accents, tool chips |
| `mist` | `#B9CBDD` | needle outline, quiet strokes |
| `ground` | `#F4F7FB` | page background, bot bubbles |
| `surface` | `#FFFFFF` | cards |
| `ink` | `#0B1B33` | body text |
| `muted` | `#4A5B74` | secondary text (passes 4.5:1 on white) |
| `line` | `#DCE4EE` | card borders |
| `line-soft` | `#EEF2F7` | dividers inside cards |

Money direction:

| Token | Value | Use |
|---|---|---|
| `up` | `#0B7A5F` | positive diff, positive steps |
| `up-bg` | `#E3F4EE` | "סופי" chip, connected pill |
| `down` | `#B4440F` | negative diff, negative steps |
| `down-bg` | `#FBEDE4` | negative tint |

Up and down differ in lightness as well as hue, so they read apart without color.

Source chips (text on background, pill radius):

| Source | Label | Text | Background | Notes |
|---|---|---|---|---|
| `employee_input` | לפי דבריך | `#2D5C94` | `#EAF1FB` | |
| `occupation` | לפי העיסוק | `#4A3A8C` | `#EFECFA` | |
| `representative` | אושר על ידי נציג | `#1F5FBF` | `#E5EEFB` | weight 600 |
| `catalog_default` | ברירת מחדל מהקטלוג | `#4A5B74` | `#F1F3F6` | 1px border `#C7D2E0` |
| `pending_rep` | ממתינה לנציג | `#7A4B00` | `#FFF1D6` | **1px dashed** border `#C98A1B`, clock icon |

Engine room (judges mode):

| Token | Value |
|---|---|
| panel background | `#061A3A` |
| event card border | `#1C3B6B` |
| code block background | `#04132B` |
| text / muted | `#E6EEF8` / `#9FB3CF` |
| model event accent | `#B9A9F5` |
| tool result accent and border | `#8FD6BE` / `#2E8A6F` |
| guard card background / accent | `#0A2550` / `#9CC3FF`, border `#2F5FA8` |
| toggle knob when on | `#5B9BFF` |

### 3.3 Typography

- **IBM Plex Sans Hebrew** (400/500/600/700) for everything, **IBM Plex Mono** (400/500) for tool names and JSON. Both bundled via `@fontsource` (no CDN at runtime).
- `font-variant-numeric: tabular-nums` on the whole app, so updating numbers don't shift width.
- Scale: hero diff 64px/700 (52px in judges mode); card amounts 24px/600; screen titles 22px/700; section titles 15px/600; body 15px/1.6; meta 12–13px.
- The "COMPASS" wordmark is Latin: 20px/700, letter-spacing 0.04em, `direction: ltr`.

### 3.4 Shape, space, motion

- Radii: cards 16px, inner tiles 12px, controls 10–12px, chips 999px. Bubbles: bot `14 14 14 4`, employee `14 14 4 14` (tail toward the speaker's side).
- 8px spacing grid; page padding 24px vertical, 32px horizontal; gap between cards 20–24px.
- 1px borders, no gradients, no heavy shadows.
- Motion: when a new comparison arrives, the hero crossfades (200ms), the card gets a brief `royal` ring, and the needle rotates to its new direction (300ms). Pending → final: dashed border becomes solid `up`, opacity 0.75 → 1, chip swaps. All motion wrapped in `prefers-reduced-motion: no-preference`.

### 3.5 Accessibility

- Text contrast ≥ 4.5:1 (the tokens above pass on their intended backgrounds; keep it that way).
- Focus ring: 3px `royal`, offset 2px, on every interactive element.
- Touch targets ≥ 44px. Real `<button>`, `<input>` with `<label>`, `<a href>`.
- The comparison hero is an `aria-live="polite"` region, announcing e.g. "ההפרש עודכן: פלוס 2,914 שקלים".
- Icons are inline stroke SVGs (Tabler-style), `aria-hidden`, with `aria-label` on icon-only buttons. No emoji.

### 3.6 RTL rules

- `<html dir="rtl" lang="he">`. Every amount and percentage is wrapped in `<bdi>` and formatted by one helper: `Intl.NumberFormat("he-IL")` plus an explicit sign for differences (`+2,914`, `−50` with a real minus sign).
- Tool names, JSON and car ids (`CAR-10`) are `dir="ltr"` and mono.
- Layout order follows RTL: the first child sits on the right.

## 4. Screens and components

### 4.1 App header (all screens)

Logo at 48px height, then the wordmark "COMPASS" with "יועץ הרכב של Strauss" under it (13px, muted). On the other side: connection pill (green dot + "מחובר", or amber "מתחבר מחדש…"), a small "מצב דמו" badge when the Scripted LLM is on, and the **judges-mode toggle**: a real `<button aria-pressed>` with a switch graphic and the label "מצב שופטים". Off: white with `line` border. On: `navy` fill, knob `#5B9BFF`. Turning it on prompts for the admin token if none is in `sessionStorage`.

### 4.2 Employee screen (`/`)

Two columns, flex-wrap: **chat** (right, `flex: 1 1 420px`) and **comparison** (left, `flex: 999 1 640px`). Stacks on narrow screens.

**Chat panel** (white card):
- Header row: "שיחה", and on the other side "שומר המספרים פעיל" (12px muted).
- Bot bubbles: `ground` background, 1px `#E3EAF3` border, at the start (right). Employee bubbles: `navy` background, white text, at the end (left). Max width 85%.
- **Tool activity row** after each turn that used tools: small mono LTR chips on `#EAF1FB` with `steel` text, e.g. `save_profile ✓`, `compare ✓`. A failed tool shows `✕` in `down`.
- Thinking indicator between `turn_started` and `turn_finished`: three dots in a bot bubble plus "מחשב…". Latency can reach ~30s on the rep flow, so after 8s add "עדיין עובד על זה".
- Suggestion chips above the input (outlined, `royal` text, pill), e.g. "ומה אם אעבור לחשמלי?". They only send text; no special behavior.
- Input: 48px tall, 12px radius, placeholder "כתבו הודעה…", send button 48×48 `royal` with a left-pointing arrow icon. Error state with "נסו שוב" button.

**Comparison column**, top to bottom:

1. **Hero card**
   - Title row: "{alternative} לעומת היום" (e.g. "ויתור על הרכב לעומת היום", "BYD ATTO 3 לעומת היום") and a pill "קבוצה ב' · תקציב 3,700 ₪" (`steel` on `#EAF1FB`).
   - Needle icon (34×56): a diamond outlined in `mist`, with the half pointing in the direction of change filled in `up` or `down`. Zero diff: both halves `mist`.
   - Hero number: signed diff, 64px/700 in `up`/`down`, "₪" at 28px. Under it: "יותר בנטו, בכל חודש" or "פחות בנטו, בכל חודש".
   - Two tiles: "היום · {current car}" with today's net, an arrow, then the alternative's tile with its net. The alternative tile has a 1px `up`/`down` border and a faint tint.
   - Warnings (`group_mismatch_with_occupation`, etc.) as a row of amber notices under the tiles, Hebrew text from the API.
   - `partial: true` → a notice "ההפרש חלקי — חסרים: {fields}" and the hero shown at 0.75 opacity with "חלקי".
2. **Waterfall: "מאיפה מגיע ההפרש"** (see 4.3).
3. **Inputs card: "על מה החישוב מבוסס"**: a 2-column grid of rows "{label} · {value}" with the source chip on the far side, divided by `line-soft`. Footer line with a shield icon: "כל מספר במסך חושב בכלים ונבדק לפני שהוצג."

Empty state, before any comparison: the comparison column shows a quiet card "כאן יופיע החישוב ברגע שיהיה מספיק מידע", with the needle outline in `mist`.

### 4.3 Waterfall — difference only, from zero

**Do not plot absolute nets.** Bars that start at 0 and reach 11,000 make a 132 step invisible; an axis starting at 10,000 makes it visible but misleads, and money UIs must not do that. Instead the chart shows **only the difference**, from 0 to `display_diff`; today's and the alternative's nets are already in the hero tiles above.

- One floating bar per breakdown line in API order, then a **total** bar from 0 to `display_diff` in `navy`.
- Positive steps rise in `up`; negative steps fall in `down`. The y-domain is `[min(0, lowest cumulative), max(0, highest cumulative)]`, with a visible zero line, so negative and mixed cases work.
- Value label above each bar (signed, 14px/600, bar's color); category label below (12px muted, Hebrew `label` from the API). First line on the right (RTL).
- Bars are buttons: hover and focus show the value; click selects. Selected bar: 3px `royal` outline, offset 3px. Default selection: the largest absolute step.
- **Provenance strip** under the chart, for the selected line: a `#F3F7FD` box with 1px `#C9D6E8` border showing "{label} · {signed value} ₪", "חושב בכלי compare", and the input chips and rule that fed it (e.g. "3 נקודות זיכוי · לפי דבריך", "מדרגות המס · קובץ הכללים הרשמי"). Hint above the chart: "לחצו על עמודה כדי לראות את מקור המספר".
- Recharts or a small custom SVG component: your choice, state it. I lean to custom SVG for exact RTL control and styling.

For the walkthrough the expected series is: +1,500 (דמי אחזקה), +802, +180, +132, +300, total +2,914. I believe 802/180/132 are income tax, national insurance and health tax and 300 is the participation no longer paid, but **take the labels from the actual breakdown keys** and tell me in Stage 0 what they are.

### 4.4 Pending and final states

- **Pending** (`pending_rep` on any input the comparison used): hero at 0.75 opacity with "זמני" next to it; an amber "ממתינה לנציג" chip with a clock icon in the hero's title row; the input row shows the catalog default with the pending chip and a dashed amber border; the alternative tile's border is dashed.
- **Final**: when the server's recomputed comparison arrives without pending, everything turns solid: the hero card gets a 2px `up` border for 2s, the chip becomes "סופי" (`up` on `up-bg`, check icon), and the input row chip becomes "אושר על ידי נציג".

### 4.5 Judges mode

When the toggle is on, the employee screen becomes two columns:

- **Summary column** (right, light): the hero card compacted (52px number); an "איך זה עובד" card with three numbered steps — 1 "המודל מציע" (purple step badge: understands the conversation and picks tools, never computes money), 2 "הכלים מחשבים" (green: deterministic formula, exact Decimal, a source for every value), 3 "השומר בודק" (blue: every number in a reply must come from a tool, the employee or the rep); and a 2×2 stats grid (see Stage 6 for where the numbers come from).
- **Engine room** (left, `#061A3A`, radius 16, `flex: 999 1 640px`): title "חדר המנועים · תור N" with a turn selector, and stat pills (mono, LTR) for rounds, latency, tokens in/out/cache, and cost in `#8FD6BE`. Then a vertical list of event cards for the selected turn:
  - Tool call card: "המודל קרא לכלי" (model accent) and the tool name (mono, white). A collapsible LTR code block: `→ args` and `← result` (the full result from the DB).
  - The comparison result card uses the tool accent and green border with "הכלי חישב".
  - **Guard card** (`#0A2550`, blue border): shield icon, "שומר המספרים", verdict "4 מתוך 4 אומתו · נשלח", and one chip per number in the reply with its source (`2,914 ✓ compare`). A rejected draft shows the draft text struck through, the failing numbers as `down` chips, and what happened next (retry or template).
  - Template fallback card when it happened.

### 4.6 Representative screen (`/rep`)

- Header in `navy` with the logo on a white rounded tile, "COMPASS", "מסך נציג", and on the other side "מחובר כנציג · טוקן נשמר לסשן הזה בלבד". Token prompt on first visit.
- **Tickets list** (right, white card): title "טיקטים פתוחים" with an amber count badge; each ticket is a link row: Hebrew title ("השתתפות עצמית · BYD ATTO 3"), age ("לפני 2 דק'"), and the field id in mono LTR. Selected row on `#F3F7FD`. Empty text: "טיקטים חדשים יופיעו כאן אוטומטית". The list updates live.
- **Ticket detail** (left): the question as a 22px title ("מה גובה ההשתתפות העצמית ב־BYD ATTO 3?"), a muted context paragraph, three info tiles (car · catalog default · the employee's current provisional diff), and the answer form on `ground`: label "סכום ההשתתפות החודשית (₪)", a large numeric input (2px `royal` border, 22px/600), the button "אישור ושליחה לעובד/ת", and the helper text "ברגע האישור השרת מחשב מחדש, והכרטיס אצל העובד/ת מתעדכן". Validate with the same rules as `compass/tools/tickets.py`; show its error text inline.

## 5. Stack

- `web/`: React + Vite + TypeScript (strict) + Tailwind (tokens from §3.2) + shadcn/ui where it helps (dialog for token prompt, collapsible, tooltip).
- npm; Node version pinned in `web/.nvmrc` and `engines`.
- `@fontsource/ibm-plex-sans-hebrew` and `@fontsource/ibm-plex-mono`. No runtime CDN.
- vitest + @testing-library/react; Playwright for one end-to-end flow. ESLint + `tsc --noEmit`.

## 6. Stages

### Stage 0 — Inventory (no code changes except committing this brief and the logo)

Report, then stop for my approval:
- Existing HTTP endpoints (method, path, auth, request/response models).
- Event types stored per session (names, payload, `origin`), and where full tool results live. Map this brief's needs onto them: the comparison event is the existing **`comparison_ready`**, including the server-origin pending recompute from `3b50995`; do not invent a new name for it.
- Whether the comparison payload already has what §4.2–4.4 need: rounded nets, `display_diff`, breakdown with `key`, Hebrew `label` and `net_effect`, per-input `source`, `pending_rep`, warnings, `unknown_fields`/`partial`, alternative identity. **List the actual breakdown keys and labels for the walkthrough.**
- What the provenance strip (§4.3) can show per breakdown line from existing data, and the smallest additive change that would let the server attach `inputs_used` per line. If that change is not small, propose a documented static mapping from breakdown key to input fields in the frontend, and say which you recommend.
- The setting that selects the Scripted LLM, and which scripts exist.
- Your proposed **additive** API delta for Stages 1–6.

### Stage 1 — Backend for the UI (additive)

1. **SSE stream**: `GET .../sessions/{id}/events` in the existing path style. Each event has a monotonically increasing `id`; `Last-Event-ID` replays what was missed. Kinds, mapped onto existing events where they exist: `employee_message`, `assistant_message`, `tool_call`, `tool_result`, `comparison_ready`, `ticket_opened`, `ticket_answered`, `guard_verdict` (accepted, with per-number sources; and rejected, with the draft), `template_fallback`, `usage`, `turn_started`, `turn_finished`, `error`.
2. `comparison_ready` is display-ready and self-contained (fields per Stage 0). The server asserts `sum(net_effect) == display_diff` and `today_net + display_diff == alt_net` (rounded) before emitting.
3. A rep-side stream (or polling endpoint, your call) for the open-tickets list.
4. **Judges-only data** (full tool args/results, guard drafts and per-number sources, usage/cost) is sent only with the admin token. Without it those events are omitted or redacted.
5. Tests: ordering and replay, payload invariants, redaction without the admin token, walkthrough and E-001 payloads via the Scripted LLM.

### Stage 2 — Frontend scaffold and design system

- Vite app in `web/`, dev proxy to FastAPI, typed API client hand-mirrored or generated from the Pydantic models (state which; one source of truth).
- RTL root, fonts, the §3.2 tokens in the Tailwind theme, focus ring, reduced-motion handling, logo in `web/src/assets/`.
- The number/sign formatter with `<bdi>`; the source-chip component (all five variants); the needle icon component (up/down/zero).
- A typed SSE client with reconnect, and a pure reducer `(state, event) → state`, the only place session state changes.
- A `/__styleguide` dev-only route showing tokens, type scale, chips, needle states and buttons, so I can review the design system in isolation.
- vitest: formatter (signs, separators, zero, RTL wrapping), reducer (each event kind, idempotent replay by id), chip variants.

### Stage 3 — Employee screen

Header (§4.1) and the employee screen (§4.2), including the empty, thinking, error, partial and warning states, and the hero motion.

### Stage 4 — Waterfall and provenance

§4.3. A pure `buildWaterfall(payload)` returns the series and asserts both invariants; on failure the component shows an error state and logs the payload. vitest: the walkthrough series exactly, E-001 before/after, a negative-step case, a negative total, and an invariant violation.

### Stage 5 — Pending/final states and the representative screen

§4.4 and §4.6. Answering a ticket removes it from the list; the employee tab receives `ticket_answered`, then a `comparison_ready` without pending, and transitions to final.

### Stage 6 — Judges mode

§4.5. The four stats tiles: evals pass rate and spend from `evals/report.md` and `evals/spend.jsonl`, test count from the last CI run or a committed number, cost per conversation from the report. Serve them from a small admin-only endpoint that reads the committed files; if that is awkward, generate a JSON at build time. Never hard-code them in components.

### Stage 7 — Serving, demo mode, CI

- `npm run build` → FastAPI serves `web/dist` with SPA fallback, without shadowing API routes. One URL for the demo and later for Docker.
- `tasks.py web` (dev: Vite + API) and `tasks.py build-web`, documented for PowerShell.
- Demo mode: with the Scripted LLM setting on, the walkthrough and E-001 run end to end in the browser with no API key, and the "מצב דמו" badge shows.
- CI: a frontend job (npm ci, lint, typecheck, vitest, build). No API calls in CI.

### Stage 8 — End-to-end test

One Playwright test in demo mode, runnable on Windows and in CI if under ~2 minutes:
1. Walkthrough → hero shows +2,914, waterfall has 5 steps plus the total, provenance strip shows the selected step.
2. E-001 → +661 with "ממתינה לנציג" → `/rep` in a second page answers 350 → the employee page shows +611, "סופי", chip "אושר על ידי נציג", no pending chip.
3. Judges mode with the admin token shows a guard card with verified numbers; without the token the toggle asks for it and no judges data is in the network log.

Also save screenshots of the three screens from this run (light, 1440 wide) for the README.

### Stage 9 — Docs and report

- README: a "UI" section (screens, judges mode, demo mode, PowerShell commands, the screenshots).
- `briefs/HANDOFF_DAY4.md`, checked against git.
- Final report: what was built per stage, all API changes (additive?), test counts, the screenshots, every place you deviated from §3–4 and why, known gaps, and what you'd change before the final.

## 7. Invariants checklist (tests must cover each)

1. The browser never computes an amount; it only formats amounts from the API. No count-up animations.
2. `Σ net_effect == display_diff`, on the server and again in `buildWaterfall`.
3. `today_net + display_diff == alt_net` (rounded values), on the server and in the UI.
4. Every displayed input value has a source chip; pending is visually distinct (dashed, amber, clock, reduced opacity).
5. Judges-only data never reaches a client without the admin token.
6. Signs render correctly in RTL (`+2,914`, never `2,914+`).
7. The demo runs offline in demo mode (fonts and logo bundled).
8. Every interactive element is keyboard reachable with a visible focus ring.

## 8. Out of scope

Payslip upload and the "all alternatives" screen (stretch), Docker and deploy (polish day), authentication beyond the existing tokens, languages other than Hebrew, dark mode for the employee screen, mobile-first design (narrow screens must not break, nothing more).

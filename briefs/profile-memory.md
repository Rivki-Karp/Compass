# Brief: Remember the employee's details between conversations, with consent (flag `COMPASS_PROFILE_MEMORY`)

You are the **senior engineer** on Compass. Act like one. Read the slot store and its sources, the payslip confirmation flow (pending candidate → confirm → apply → agent told as data), the guard sources map, `view`/`labels.py`, chips, number sources, the conversation/empty-cleanup code and the accounts model before designing anything. **Reuse the payslip confirmation pattern; it is exactly the shape needed here.** Before each stage, write a short design note covering the approach, the risks and how you handle them. If something contradicts the code, or would change a calculation, the guard's accept/reject logic or an API contract, **stop and ask**.

Commit this file as `briefs/profile-memory.md` in the first commit.

## 0. Base, time box and rules

- **Branch:** `feat/profile-memory`. Cut it from `fix/number-source-bold` once that branch is pushed and green. Otherwise cut it from `main` at `v2.1`, and tell me which one you used.
- **Time box:** this ships only if it is green and I have tested it by hand **by 22:30 today**. If you see it won't make that, stop early and tell me. A half feature is not deployed.
- **The flag:** `COMPASS_PROFILE_MEMORY`, default `0` in code, `"1"` in `render.yaml`. It requires `COMPASS_AUTH=1`; with accounts off it is inert. **With the flag off, the events, the UI and the prompt are byte-identical to today.**
- **Frozen:** `system_he.md`, the tool descriptions, the calculation tools, and the guard's accept/reject logic. Payslip and number-source behaviour don't change.
- **Approved:** one new flag-gated prompt file, `system_profile_he.md`, added only when the flag is on (see Stage 3). Also two new eval scenarios.
- **The usual rules:** one commit per stage, the full `tasks.py check` (with Playwright) green after each, explicit paths only, and no merge, tag or deploy without me.

## 1. Principles (non-negotiable)

1. **Nothing is used silently.** Saved values enter a new conversation **only after the employee confirms them** on a card. Until then, the agent doesn't see them and the guard doesn't accept them.
2. **Every reused value shows where it came from:** a new chip, **"משיחה קודמת"**, with the date ("משיחה קודמת · 20/10"), in the cards, the waterfall and the number-source popover.
3. **Anything new in this conversation wins.** A value the employee states, a confirmed payslip value, or a rep answer replaces a reused one. Precedence: `representative` > `payslip`/`employee` (this conversation) > `previous` > catalog default.
4. **Only personal facts are remembered:**
   - occupation;
   - base salary;
   - commissions;
   - bonus;
   - pension %;
   - study fund %;
   - credit points;
   - today's car (catalog id and year).

   **Never remembered:**
   - rep answers about a specific car's participation, and the group exception (they belong to that conversation);
   - the payslip file, and anything not in this list;
   - names, IDs or bank details.
5. **The group is never stored.** It is re-derived from the occupation through the existing path, so a rules change applies.
6. **Private:** owner only. The admin and the rep never see it. Deleting the account deletes it. The employee can delete it at any time.

## 2. Stages

### Stage 1: Store and offer (backend)

- **The table `user_profiles`:**
  - `user_id`;
  - `fields`, as JSON: per field `{value (Decimal string or id), source (employee|payslip|representative), saved_at, from_session}`;
  - `updated_at`.
  - It is created additively at start-up.
- **Saving:** whenever a remembered field is **confirmed or settled** in a conversation, upsert it into the owner's profile, with its real source and time. That means employee-stated and saved, payslip-confirmed, or a rep-confirmed today's car. Pending, provisional, unknown and catalog-default values are **never** saved. "לא יודע" removes nothing; it just doesn't save.
- **Offering:** when a user with a non-empty profile opens a **new** conversation (no messages yet), the server emits one `profile_offer` event. It carries the fields, each with its value, its original source, its date and the server-side Hebrew label. It goes through the existing event pipeline, redaction and replay.
  - **The offer is a pending candidate,** exactly like the payslip's. It is not applied, not in the agent's input, and not a guard source.
  - An offer alone does **not** make a conversation non-empty for the empty-cleanup rule.
- **The endpoints** (owner-only, under the existing ownership guard, 404 when the flag is off):
  - **`POST /api/sessions/{id}/profile/apply`** `{fields: [{name, action: keep|edit|drop, value?}]}`:
    - `keep` gets source `previous`, with `previous_from` set to the original date.
    - `edit` gets source `employee`.
    - `drop` means skip.
    - The fields go through **the existing slot path and recompute**. Then the agent is told **as data**, like the payslip confirmation, e.g. "The employee confirmed these values from a previous conversation (20/10): …".
    - This counts as activity, so the conversation is no longer empty.
  - **`POST /api/sessions/{id}/profile/dismiss`:** "להתחיל מחדש", for this conversation only. Nothing is deleted.
  - **`DELETE /api/profile`:** deletes the saved profile.
- **Staleness:** the offer includes `age_days`. When it is over 30, the label adds "ייתכן שהפרטים השתנו".
- **Shared demo account:** judges may share `employee@demo.compass`, so the offer is visible to whoever logs in. This is acceptable because the account is shared on purpose, and the card always shows the date and "להתחיל מחדש". Note it in the README.
- **Tests:**
  - only confirmed values are saved (one test per source);
  - pending, provisional and default values are never saved;
  - rep participation and the group exception are never saved;
  - the group is re-derived;
  - the offer is emitted once per new conversation;
  - **the offer is not in the agent input and not a guard source** (a draft quoting an offered value is rejected until it is applied);
  - apply keep, edit and drop each go through the slot path with the right sources;
  - precedence is enforced in both directions;
  - the owner-only matrix holds;
  - delete;
  - with the flag off, everything is byte-identical.

**STOP after Stage 1** with the design notes, the event shape, an example payload, and the test list.

### Stage 2: UI

- **The offer card,** at the top of a new conversation, styled like the payslip confirmation card:
  - its title: "יש לי פרטים מהשיחה מ־{date}";
  - one row per field, showing its value, its original source chip, and the controls to edit or remove it;
  - three buttons: **"להשתמש בהם"** (keep all), **"לעדכן"** (enter edit mode, then a confirm button) and **"להתחיל מחדש"** (dismiss);
  - and a small link, "מחיקת הפרטים השמורים", with a confirmation dialog.
- **The order** at the top of an empty conversation: the profile card first, then the payslip offer.
- **The chip "משיחה קודמת · DD/MM":** add it to `chips.ts` and `labels.py` with the pin test, in a colour that passes 4.5:1 and is distinct from the existing chips. It is shown everywhere a source chip appears, including the number-source popover ("משיחה קודמת, 20/10").
- **RTL, `<bdi>` for numbers, a bottom-sheet-safe layout at 400 px, and keyboard support.**
- **Tests:**
  - vitest for the card states;
  - Playwright for two conversations:
    - the first saves its values;
    - the second shows the card; "להשתמש בהם" applies them, the result shows the chip, and a reply number's popover says "משיחה קודמת";
    - "להתחיל מחדש" shows the normal flow;
    - deleting the profile means no card next time;
  - axe on the card;
  - screenshots at 1440 and 400.

### Stage 3: Prompt, evals and docs

- **`system_profile_he.md`, loaded only when the flag is on:**
  - Values from a previous conversation arrive only as confirmed data with source "משיחה קודמת".
  - If the employee asks whether the bot remembers them, and an offer card is shown or was dismissed, the bot points to the card, or says they chose to start fresh. It never says it has no access.
  - It never uses, quotes or guesses a value that wasn't confirmed in this conversation.
  - It doesn't re-ask fields that were already confirmed.
- **Evals:** two new scenarios:
  1. **`profile_reused`:** a saved profile, then apply, then the correct diff with no re-asking.
  2. **`profile_dismissed`:** a saved profile, then dismiss. The agent asks normally, and no saved value appears in any reply.

  Then run the 8 key scenarios plus these two once, with all flags on. Report pass counts, retries, fallbacks and cost.
- **Docs:**
  - README: a "זיכרון פרטים, באישור" section covering the principles, the precedence and the privacy rules.
  - `render.yaml`: `COMPASS_PROFILE_MEMORY "1"`.
  - The runbook: a by-hand checklist.
- **The report covers:** per stage, what changed; test counts; evals and cost; screenshots; anything left open; and one paragraph for the hackathon "problems we faced" section.

**STOP after Stage 3.** Push `feat/profile-memory`. Do not merge, tag or deploy.

## 3. Out of scope

Automatic reuse without confirmation, remembering rep or ticket answers, storing payslips, cross-user sharing, persistence beyond the current database (it is still wiped on deploy), and any change to calculations or to the guard's decisions.

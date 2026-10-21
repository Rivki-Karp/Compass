# Brief: "מאיפה המספר הזה?": click any number in the chat to see its source

You are the **senior engineer** on Compass. Act like one. Read the guard, its sources map, `view`/`labels.py`, the event pipeline and the waterfall's existing provenance before designing anything. Reuse them. **This feature adds no new calculation and no new decision.** It only surfaces what the guard already verified. Before each stage, write a short design note covering the approach, the risks and how you handle them. If something contradicts the code, or would change guard behaviour, an API contract or a test, **stop and ask**.

Commit this file as `briefs/number-source.md` in the first commit.

## 0. Base, time box and rules

- **Branch:** `feat/number-source`, from `main` at tag `v2.0`. If `v2.0` doesn't exist yet, stop and ask.
- **Time box:** this ships only if it is green and I have tested it by hand **by 20:00 today**. If you see it won't make that, stop early and tell me. A half feature is not deployed.
- **The flag:** `COMPASS_NUMBER_SOURCES`, default `0` in code, set to `"1"` in `render.yaml`. With it off, the UI and the events are byte-identical to today.
- **Frozen:** `system_he.md`, `system_payslip_he.md`, tool descriptions, `evals/scenarios/`, the calculation tools, and **the guard's accept/reject logic**. You may *read* from the guard and record what it already knows. You may not change what it accepts.
- **The usual rules:** one commit per stage, the full `tasks.py check` (with Playwright) green after each, explicit paths only, PowerShell docs, and no merge, tag or deploy without me.

## 1. The behaviour

- **Clickable numbers:** every number in a **sent** assistant reply that the guard verified becomes a small clickable element: a dotted underline, a real `<button>`, and `aria-label="מאיפה המספר {value}?"`.
- **Clicking a number** opens a popover (a bottom sheet below 700 px) with:
  - **the value and what it is**, e.g. "‎+611 ₪ · הפרש בנטו לחודש";
  - **the source chip**, the same chips and colours as everywhere else ("לפי התלוש", "אושר על ידי נציג", "לפי העיסוק", "לפי דבריך", "ברירת מחדל מהקטלוג", "לפי הכללים");
  - **how it was produced:**
    - for a tool result, "חושב בכלי compare · בשרת, בלי מודל" (or the existing origin label from `view`);
    - for an employee-stated value, "לפי דבריך, בהודעה מ־HH:MM";
    - for a rep value, "אושר על ידי נציג, HH:MM";
  - **for a comparison total or diff:** its components, as compact rows with their own chips. **The rows are taken from the stored comparison view, the same data the waterfall uses. Never recompute.**
- **Numbers the guard didn't need to verify, or ignores,** render as plain text, and old messages without source data render as today. Nothing ever shows a source that wasn't recorded.
- **The template fallback reply** has no numbers, so it has nothing to show.
- **All labels come from the server** (`view` / `labels.py`), never from frontend strings, consistent with the rest of the UI.

## 2. Stages

### Stage 1: Record the sources (backend)

- **When the guard accepts a reply** (first draft or retry), record a `number_sources` list for **the exact text that is sent**:
  - `{start, end}`: character offsets in the sent text, covering the number as written, including sign, thousands separators and `%`. `₪` is outside the span.
  - `value`: a Decimal string.
  - `kind`: one of `tool`, `employee`, `representative`, `payslip`, `rule`, `catalog`, `derived`, matching the guard's existing source categories.
  - `label`: a Hebrew label, from `labels.py`.
  - `origin`: the tool name and the server/model origin label, when applicable.
  - `slot`: when applicable.
  - `ref`: a reference to the comparison view or the message/event it came from, so the UI can show components and times.
- **Attach it to the existing assistant-message event,** with no new endpoint. It goes through the existing redaction and the owner-only routes (from v2.0), and replays with `Last-Event-ID`.
- **Edge cases to test:**
  - Hebrew text around the numbers.
  - `2,914`, `+611`, `−473` (Unicode minus as well as hyphen), `6%`, `2.5%`, and `14,000 ₪`.
  - The same value appearing twice, with different sources.
  - A number inside `<bdi>`-relevant mixed text such as `ATTO 3` or `CAR-10`. These are **not** money numbers: follow exactly what the guard does with them today, and don't make them clickable unless the guard verified them.
  - The retry path: sources must describe the retry text, not the rejected draft.
- **A property test:** for every recorded span, `sent_text[start:end]` parses back to `value`.
- **Flag off:** the event payload is byte-identical to today.

**STOP after Stage 1** with a short report covering the event shape, an example payload from a real scripted turn, and the edge-case results.

### Stage 2: UI

- **Render** the assistant message text with the recorded spans wrapped as buttons. Keep the rest of the text exactly as today, including the bidi helper and `<bdi>`.
- **The popover:**
  - It opens on click, Enter or Space.
  - Esc and an outside click close it, and focus returns to the number.
  - Only one is open at a time.
  - Below 700 px it becomes a bottom sheet with a close button.
- **Components for a comparison:** reuse the waterfall's row/chip components. Clicking a row highlights the matching waterfall bar, if it's on screen. Nice to have; skip it if it costs time.
- **Judges mode:** unchanged. The engine room still shows the guard card.
- **Tests:**
  - vitest for span rendering, the plain-text fallback, and the keyboard behaviour;
  - Playwright on the walkthrough (scripted): click "+2,914", and the popover shows "compare" and its components; click a stated salary, and it shows "לפי דבריך";
  - axe on an open popover, at 1440 and at 400;
  - a screenshot of each.

### Stage 3: Evals, docs and report

- **Evals:** with the flag on, run the 8 key scenarios once. The guard is unchanged, so expect no change. Report pass counts, guard retries, template fallbacks and cost.
- **README:** a short "מאיפה המספר הזה?" paragraph in the correctness section, with one screenshot.
- **`render.yaml`:** `COMPASS_NUMBER_SOURCES "1"` on compass-api.
- **The report covers:** what changed, test counts, the eval table, the screenshots, anything left open, and one paragraph for the hackathon "problems we faced" section.

**STOP after Stage 3.** Push `feat/number-source`. Do not merge, tag or deploy.

## 3. Out of scope

Ranges or uncertainty intervals, sharing, new data, changes to the guard's decisions, the prompt or the tools, and any number that the guard did not verify.

// Records (or dry-runs) the demo storyboard against the LIVE site.
//
//   node tools/video/record.mjs --mode dry|record     (run.py starts it; passwords come in the env)
//
// Nothing here changes the product. Credentials live in memory only: they are typed into the
// login forms and sent to the login API, never printed, written or put in a file. Every log line
// goes through log(), which masks any secret value. TLS verification is never disabled.

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const require = createRequire(path.join(REPO, "frontend", "package.json"));
const { chromium, expect: baseExpect } = require("@playwright/test");
const expect = baseExpect.configure({ timeout: 30_000 }); // outside the test runner the default is 5 s

const args = process.argv.slice(2);
const MODE = args[args.indexOf("--mode") + 1] === "record" ? "record" : "dry";
const RECORD = MODE === "record";
const OUT = path.join(HERE, "out");
const RAW = path.join(OUT, "raw");
fs.mkdirSync(RAW, { recursive: true });
fs.rmSync(path.join(OUT, "debug"), { recursive: true, force: true });

const WEB = (process.env.COMPASS_VIDEO_WEB ?? "https://compass-web-hcpz.onrender.com").replace(/\/$/, "");
const API = (process.env.COMPASS_VIDEO_API ?? "https://compass-api-tft8.onrender.com").replace(/\/$/, "");
const PAYSLIP = path.join(REPO, "backend", "tests", "fixtures", "payslips", "11_amounts.pdf");
const GUEST_EMAIL = "video-guest@demo.compass";
const GUEST_NAME = "נועה כהן";
const ACCOUNTS = {
  employee: { email: "employee@demo.compass", pw: process.env.COMPASS_VIDEO_EMPLOYEE_PASSWORD ?? "" },
  rep: { email: "rep@demo.compass", pw: process.env.COMPASS_VIDEO_REP_PASSWORD ?? "" },
  admin: { email: "admin@demo.compass", pw: process.env.COMPASS_VIDEO_ADMIN_PASSWORD ?? "" },
};
const TYPING_MS = 25;
const MODEL_WAIT_MS = 180_000;
const SECRETS = new Set(Object.values(ACCOUNTS).map((a) => a.pw).filter(Boolean));

// the fixed script texts. No money number is hardcoded anywhere: the numbers are the live system's.
const ALL_OPTIONS_TEXT = "אני מפתחת תוכנה, יש לי היום קורולה רגילה 2026. תציג לי את כל החלופות";
const MG4_TEXT = "תשווה לי ל־MG4. אני לא יודעת מה ההשתתפות העצמית בו, תבדוק מול נציג";
// scene 7's conversation, created by the admin BEFORE the recording (judges mode works only on
// the admin's own sessions)
const ADMIN_PREP_TEXT =
  "מה יקרה לנטו אם אוותר על הרכב? אני מפתחת תוכנה, שכר בסיס 14,000, אין עמלות ואין בונוסים, פנסיה 6%, השתלמות 2.5%, 2.75 נקודות זיכוי, אין ילדים, יש לי היום קורולה רגילה 2026";
// today's car in the catalog picker when the model does not recognise it: COROLLA, group ב'
const PICKER_MODEL = "COROLLA";
const PICKER_GROUP = "ב";
// The fixed answers for when the live model asks one more question: matched by KEYWORD in the
// question being asked (several topics asked -> one answer each, in the order they are asked).
const CANNED = [
  { keys: /קורולה|איזו/, answer: "קורולה רגילה 2026" },
  { keys: /עמלות|בונוס/, answer: "אין עמלות ואין בונוסים" },
  { keys: /ילדים/, answer: "אין לי ילדים" },
  { keys: /פנסיה/, answer: "6%" },
  { keys: /השתלמות/, answer: "2.5%" },
  { keys: /נקודות זיכוי/, answer: "2.75" },
  { keys: /השתתפות/, answer: "לא יודעת, תבדוק מול נציג" },
];
const CANNED_OTHER = "לא יודעת";

/** The part of a reply that asks: after "צריך לדעת" / "כדי להמשיך", else the lines with a "?", else
 *  the tail. The recap at the start of a reply ("רשמתי: …") is not a question. */
function questionPart(text) {
  const marker = [...text.matchAll(/צריך לדעת|כדי להמשיך|כדי שאוכל|חסר לי|חסרים/g)].at(-1);
  if (marker) return text.slice(marker.index);
  const asking = text.split("\n").filter((line) => line.includes("?"));
  return asking.length ? asking.join("\n") : text.slice(-250);
}

function answerFor(question) {
  const part = questionPart(question);
  const hits = CANNED.map((c) => ({ at: part.search(c.keys), answer: c.answer }))
    .filter((h) => h.at >= 0)
    .sort((x, y) => x.at - y.at)
    .map((h) => h.answer);
  const unique = [...new Set(hits)];
  return unique.length ? unique.join(". ") : CANNED_OTHER;
}

// ---------------------------------------------------------------------------------- logging

function redact(text) {
  let out = String(text);
  for (const secret of SECRETS) out = out.split(secret).join("***");
  return out;
}
const log = (...parts) => console.log(redact(parts.join(" ")));

// ---------------------------------------------------------------------------------- API

async function api(method, route, { token, body, timeoutMs = 60_000 } = {}) {
  const response = await fetch(`${API}/api${route}`, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* not JSON */
  }
  return { status: response.status, json };
}

/** The first request may meet a sleeping Render service: retry the health check until it wakes. */
async function wakeUp() {
  const deadline = Date.now() + 150_000;
  for (;;) {
    try {
      const r = await api("GET", "/health", { timeoutMs: 20_000 });
      if (r.status === 200) return r.json;
    } catch {
      /* still waking */
    }
    if (Date.now() > deadline) throw new Error("the API does not answer (cold start over 150 s)");
    await new Promise((resolve) => setTimeout(resolve, 3_000));
  }
}

async function apiLogin(who) {
  const { email, pw } = ACCOUNTS[who];
  const r = await api("POST", "/auth/login", { body: { email, password: pw } });
  if (r.status !== 200) throw new Error(`login as ${who} refused (HTTP ${r.status})`);
  return r.json.token;
}

// ---------------------------------------------------------------------------------- state

const report = { mode: MODE, probes: {}, scenes: [], notes: [], improvised: [], modelTurns: 0 };
const tokens = {}; // in memory only
const contexts = {}; // name -> { context, page, t0 }
const segments = {}; // scene -> pane -> [{ctx,start,end}]
let browser;
let employeeSession = null;
let adminPrepSession = null; // scene 7's conversation (deleted in the cleanup)

const pause = (page, ms = 1_000) => page.waitForTimeout(ms);

function offset(name) {
  return (Date.now() - contexts[name].t0) / 1000;
}

/** Marks a useful segment of one context's video; returns the closer. */
function segment(scene, pane, name) {
  const start = offset(name);
  return () => {
    const end = offset(name);
    ((segments[scene] ??= [])[pane] ??= []).push({ ctx: name, start: +start.toFixed(2), end: +end.toFixed(2) });
  };
}

async function newContext(name, { video = RECORD } = {}) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
    ...(video
      ? { recordVideo: { dir: path.join(RAW, name), size: { width: 1440, height: 900 } } }
      : {}),
  });
  context.setDefaultTimeout(30_000);
  const t0 = Date.now(); // the video starts with the page
  const page = await context.newPage();
  contexts[name] = { context, page, t0 };
  return page;
}

// ---------------------------------------------------------------------------------- UI helpers

async function typeInto(page, locator, text) {
  await moveTo(page, locator);
  await page.keyboard.type(text, { delay: TYPING_MS });
}

async function moveTo(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
  await locator.click();
}

async function clickVisibly(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
  await pause(page, 250);
  await locator.click();
}

async function logInThroughForm(page, who) {
  await page.goto(WEB + "/");
  const form = page.getByRole("form", { name: "כניסה לעובדים" });
  await form.scrollIntoViewIfNeeded();
  await typeInto(page, page.getByLabel("מייל"), ACCOUNTS[who].email);
  await typeInto(page, page.getByLabel("סיסמה"), ACCOUNTS[who].pw);
  await clickVisibly(page, page.getByRole("button", { name: "כניסה", exact: true }));
  await form.waitFor({ state: "detached" }); // logged in: the form is gone
}

/** Waits for the model's turn to finish: "מחשב…" shows, then goes. */
async function waitIdle(page) {
  await page.getByText("מחשב…").first().waitFor({ timeout: 20_000 }).catch(() => {});
  await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: MODEL_WAIT_MS });
}

const hero = (page) => page.getByRole("article", { name: "תוצאת ההשוואה" });
const lastMessage = (page) => page.locator('ol[aria-label="הודעות"] > li').last();

async function sendChat(page, text) {
  const input = page.locator("#chat-input");
  await moveTo(page, input);
  await page.keyboard.type(text, { delay: TYPING_MS });
  await pause(page, 350);
  await page.keyboard.press("Enter");
}

/** If the model asks one more question, answer from the fixed list (at most twice). */
async function answerExtras(page, done, max = 2) {
  for (let i = 0; i < max; i += 1) {
    if (await done()) return;
    const question = ((await lastMessage(page).innerText().catch(() => "")) ?? "").trim();
    const reply = answerFor(question);
    report.improvised.push({ question, answer: reply });
    log(`improvised Q: ${question.replace(/\s+/g, " ")}\n           A: ${reply}`);
    await sendChat(page, reply);
    report.modelTurns += 1;
    await waitIdle(page);
  }
}

// ---------------------------------------------------------------------------------- probes

async function probes() {
  const health = await wakeUp();
  report.probes.version = { rules: health.rules?.version ?? null, rules_sha: health.rules?.sha256?.slice(0, 12) ?? null };
  report.probes.accounts = health.accounts === true ? "present" : "absent";
  report.probes.payslip = health.payslip ? "present" : "absent";

  for (const who of ["employee", "rep", "admin"]) tokens[who] = await apiLogin(who);
  report.probes.logins = "employee, rep and admin: accepted";

  // the remembered-details endpoints. DELETE /profile is also the brief's clean-state step.
  const del = await api("DELETE", "/profile", { token: tokens.employee });
  report.probes.profile_endpoints = del.status === 204 ? "present (saved details cleared)" : del.status === 404 ? "ABSENT (404)" : `unexpected HTTP ${del.status}`;

  // number sources: look for the key in the replay of the employee's latest conversations
  report.probes.number_sources = await probeNumberSources();

  // a stale guest from an earlier take would make the invite refuse (409)
  await deleteGuest();
}

async function probeNumberSources() {
  const list = await api("GET", "/conversations", { token: tokens.employee });
  const ids = (list.json ?? []).slice(0, 3).map((c) => c.id);
  for (const id of ids) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4_000);
    let seen = "";
    try {
      const response = await fetch(`${API}/api/sessions/${id}/events`, {
        headers: { authorization: `Bearer ${tokens.employee}`, accept: "text/event-stream" },
        signal: controller.signal,
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        seen += decoder.decode(value, { stream: true });
      }
    } catch {
      /* aborted on purpose */
    } finally {
      clearTimeout(timer);
    }
    if (seen.includes("event: assistant_message")) {
      return seen.includes('"number_sources"') ? "present" : "ABSENT (replies carry no sources)";
    }
  }
  return "undetermined (no earlier reply to inspect); scene 6 decides";
}

async function deleteGuest() {
  if (!tokens.admin) return;
  const users = await api("GET", "/admin/users", { token: tokens.admin });
  const guest = (users.json ?? []).find((u) => u.email === GUEST_EMAIL);
  if (!guest) return false;
  const r = await api("DELETE", `/admin/users/${guest.id}`, { token: tokens.admin });
  return r.status === 204;
}

/** Before the recording, not recorded: the admin opens one conversation with ONE message and waits
 *  for the comparison. Scene 7 then shows it in judges mode. */
async function prepAdminConversation() {
  const prep = await newContext("adminprep", { video: false });
  await logInThroughForm(prep, "admin");
  await prep.goto(WEB + "/new");
  await expect(prep.locator("#chat-input")).toBeVisible();
  adminPrepSession = new URL(prep.url()).pathname.split("/").pop();
  await sendChat(prep, ADMIN_PREP_TEXT);
  report.modelTurns += 1;
  await waitIdle(prep);
  await expect(hero(prep)).toBeVisible(); // ONE message only: nothing is answered here
  await contexts.adminprep.context.close();
  delete contexts.adminprep;
  return adminPrepSession;
}

async function deleteAdminPrep() {
  if (!adminPrepSession || !tokens.admin) return false;
  const r = await api("DELETE", `/conversations/${encodeURIComponent(adminPrepSession)}`, { token: tokens.admin });
  return r.status === 204;
}

/** The recorded admin context, logged in (the login is not part of the cut). */
async function ensureAdmin() {
  if (contexts.admin) return contexts.admin.page;
  const admin = await newContext("admin");
  await logInThroughForm(admin, "admin");
  return admin;
}

// ---------------------------------------------------------------------------------- scenes

const scenes = [];
const scene = (n, name, deps, fn) => scenes.push({ n, name, deps, fn });

scene(0, "opening", [], async () => {
  const page = contexts.employee.page;
  const end = segment(0, 0, "employee");
  await page.goto(WEB + "/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("כך תוכלו לדעת");
  await pause(page, 1_800);
  end();
  return "landing with logo and headline";
});

scene(1, "employee login", [0], async () => {
  const page = contexts.employee.page;
  const end = segment(1, 0, "employee");
  const form = page.getByRole("form", { name: "כניסה לעובדים" });
  await form.scrollIntoViewIfNeeded();
  await typeInto(page, page.getByLabel("מייל"), ACCOUNTS.employee.email);
  await typeInto(page, page.getByLabel("סיסמה"), ACCOUNTS.employee.pw);
  await clickVisibly(page, page.getByRole("button", { name: "כניסה", exact: true }));
  await expect(page.getByText(/שלום .*דנה/)).toBeVisible();
  await pause(page, 700);
  end();
  employeeSession = new URL(page.url()).pathname.split("/").pop();
  return "greeting shown";
});

scene(2, "payslip", [1], async () => {
  const page = contexts.employee.page;
  const card = page.getByRole("region", { name: "מה קראנו מהתלוש" });
  let end = segment(2, 0, "employee");
  const chooser = page.waitForEvent("filechooser");
  await clickVisibly(page, page.getByRole("button", { name: "העלאת תלוש", exact: true }));
  const notice = page.getByRole("dialog", { name: "לפני שמעלים תלוש" });
  if (await notice.waitFor({ timeout: 3_000 }).then(() => true, () => false)) {
    await pause(page, 700);
    await notice.getByRole("button", { name: "הבנתי, לבחירת קובץ" }).click();
  }
  await (await chooser).setFiles(PAYSLIP);
  end();
  report.modelTurns += 1; // the payslip reader
  await card.waitFor({ timeout: MODEL_WAIT_MS });
  end = segment(2, 0, "employee");
  const derived = card.getByText(/חושב מהתלוש: .+ מתוך .+/).first();
  const hasDerived = await derived.isVisible().catch(() => false);
  if (hasDerived) await derived.scrollIntoViewIfNeeded();
  await pause(page, 1_300);
  // a line the payslip does not have ("לא נמצא בתלוש — אין?"): the employee taps "אין"
  for (const label of ["עמלות", "בונוס"]) {
    const none = card.getByRole("listitem").filter({ hasText: label }).getByRole("button", { name: "אין", exact: true });
    if (await none.count()) {
      await clickVisibly(page, none);
      await pause(page, 300);
    }
  }
  await clickVisibly(page, card.getByRole("button", { name: "אישור ושמירה" }));
  await expect(page.getByText("הנתונים נשמרו לפי התלוש.")).toBeVisible();
  await pause(page, 500);
  end();
  report.modelTurns += 1; // the agent told about the confirmed values
  await waitIdle(page);
  if (!hasDerived) throw new Error("the pension row shows no '(חושב מהתלוש: … מתוך …)'");
  return "card read, pension derived % shown, confirmed";
});

scene(3, "all alternatives", [1], async () => {
  const page = contexts.employee.page;
  let end = segment(3, 0, "employee");
  await sendChat(page, ALL_OPTIONS_TEXT);
  end();
  report.modelTurns += 1;
  await waitIdle(page);
  const grid = page.locator("#options-title");
  const picker = page.locator("#car-picker-title");
  let pickedFromCatalog = false;
  for (let round = 0; round < 5; round += 1) {
    if (await picker.count()) {
      // the car was not recognised: today's car from the catalog picker, COROLLA of group ב'
      end = segment(3, 0, "employee");
      await pickCorolla(page);
      end();
      pickedFromCatalog = true;
      report.modelTurns += 1;
      await waitIdle(page);
      continue;
    }
    if ((await grid.count()) > 0) break;
    await answerExtras(page, async () => (await grid.count()) > 0 || (await picker.count()) > 0, 1);
  }
  await expect(grid).toBeVisible();
  if (await picker.count()) throw new Error("the car picker is still open after the pick");
  // no "today's car is above your group" warning, anywhere on the screen
  const warning = await page.getByText(/הרכב של היום .*מעל/).count();
  if (warning > 0) throw new Error("the 'today's car above your group' warning is on screen");
  end = segment(3, 0, "employee");
  await grid.scrollIntoViewIfNeeded();
  await pause(page, 1_500);
  end();
  const count = await page.locator("[data-option]").count();
  return `all-options grid with ${count} alternatives${pickedFromCatalog ? " (today's car from the catalog picker)" : " (car recognised)"}, no group warning`;
});

/** Drives the picker: the manufacturer that has the COROLLA of group ב' (from the live catalog),
 *  then the model, then the year. */
async function pickCorolla(page) {
  const catalog = (await api("GET", "/catalog")).json ?? [];
  const car = catalog.find((c) => c.commercial_name === PICKER_MODEL && c.group === PICKER_GROUP);
  if (!car) throw new Error(`the live catalog has no ${PICKER_MODEL} of group ${PICKER_GROUP}'`);
  const options = page.getByRole("list", { name: "האפשרויות" });
  await clickVisibly(page, options.getByRole("button", { name: car.manufacturer_name, exact: true }));
  await clickVisibly(page, options.getByRole("button", { name: PICKER_MODEL, exact: true }));
  await clickVisibly(page, options.getByRole("button", { name: new RegExp(`^${PICKER_MODEL} ${car.registration_year}`) }));
  await expect(page.locator("#car-picker-title")).toHaveCount(0);
}

scene(4, "missing fact", [3], async () => {
  const page = contexts.employee.page;
  let end = segment(4, 0, "employee");
  await sendChat(page, MG4_TEXT);
  end();
  report.modelTurns += 1;
  await waitIdle(page);
  const pending = async () => /ממתינה לנציג/.test(await hero(page).innerText().catch(() => ""));
  await answerExtras(page, pending);
  if (!(await pending())) {
    const text = (await hero(page).innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 160);
    throw new Error(`MG4: the card does not show "ממתינה לנציג" (it shows: ${text})`);
  }
  end = segment(4, 0, "employee");
  await hero(page).scrollIntoViewIfNeeded();
  await pause(page, 1_800);
  end();
  employeeSession = new URL(page.url()).pathname.split("/").pop();
  return 'MG4: the card shows "ממתינה לנציג" with the provisional diff';
});

scene(5, "rep, split screen", [4], async () => {
  const employee = contexts.employee.page;
  // prepare the rep's page (not part of the cut)
  const rep = await newContext("rep");
  await logInThroughForm(rep, "rep");
  await rep.goto(WEB + "/rep");
  const tickets = await api("GET", "/tickets?status=open", { token: tokens.rep });
  const ticket = (tickets.json ?? []).find((t) => t.session_id === employeeSession);
  if (!ticket) throw new Error("the rep inbox has no open ticket for this conversation");
  const link = rep.locator(`a[href="?ticket=${encodeURIComponent(ticket.id)}"]`);
  await link.waitFor();
  await pause(rep, 600);

  const endRep = segment(5, 0, "rep");
  const endEmployee = segment(5, 1, "employee");
  await clickVisibly(rep, link);
  await expect(rep.getByRole("heading", { level: 2, name: /השתתפות עצמית/ })).toBeVisible();
  await pause(rep, 700);
  const amount = rep.getByLabel(/סכום ההשתתפות החודשית/);
  await typeInto(rep, amount, "350");
  await pause(rep, 500);
  await clickVisibly(rep, rep.getByRole("button", { name: "אישור ושליחה לעובד/ת" }));
  await expect(rep.getByText("התשובה נשלחה. החישוב אצל העובד/ת מתעדכן.").first()).toBeVisible();
  await pause(rep, 400);
  endRep();
  await expect(hero(employee)).toContainText("סופי");
  await expect(hero(employee)).toContainText("אושר על ידי נציג");
  await pause(employee, 1_000);
  endEmployee();
  await waitIdle(employee);
  return "rep answered 350; the employee's card flipped to final, approved by a rep";
});

scene(6, "where is this number from", [5], async () => {
  const page = contexts.employee.page;
  const boldDiff = page.locator('strong [data-testid="number-source"]').filter({ hasText: /^[+\-−]/ });
  const anyDiff = page.getByTestId("number-source").filter({ hasText: /^[+\-−]/ });
  if ((await page.getByTestId("number-source").count()) === 0) {
    report.probes.number_sources = "ABSENT (no source buttons in the live replies)";
    throw new Error("no number in the replies is a source button (number sources are off)");
  }
  report.probes.number_sources = "present";
  const target = (await boldDiff.count()) > 0 ? boldDiff.last() : (await anyDiff.count()) > 0 ? anyDiff.last() : page.getByTestId("number-source").last();
  report.notes.push(`scene 6 clicked ${(await boldDiff.count()) > 0 ? "the bold diff" : "a diff that is not bold"}`);
  const end = segment(6, 0, "employee");
  await target.scrollIntoViewIfNeeded();
  await pause(page, 500);
  await clickVisibly(page, target);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("חושב בשרת");
  const rows = await dialog.getByRole("list").first().getByRole("listitem").count();
  await pause(page, 1_800);
  end();
  await page.keyboard.press("Escape");
  return `popover says "חושב בשרת", ${rows} component rows`;
});

scene(7, "judges mode", [], async () => {
  // judges mode works only on the admin's own sessions: the prepared conversation, as the admin
  if (!adminPrepSession) throw new Error("the admin's prepared conversation does not exist");
  const page = await ensureAdmin();
  await page.goto(`${WEB}/c/${adminPrepSession}`);
  await expect(hero(page)).toBeVisible();
  await pause(page, 600);
  const toggle = page.getByRole("button", { name: "מצב שופטים" });
  const end = segment(7, 0, "admin");
  await pause(page, 900);
  await clickVisibly(page, toggle);
  await expect(page.locator("#engine-title")).toBeVisible();
  const guard = page.locator("article", { hasText: "שומר המספרים" }).last();
  await expect(guard).toBeVisible();
  await expect(guard).toContainText("אומתו");
  await guard.scrollIntoViewIfNeeded();
  await pause(page, 1_800);
  end();
  return "admin's own conversation in judges mode: the engine room and the guard card";
});

scene(8, "memory", [2, 3], async () => {
  const page = contexts.employee.page;
  if (await page.getByRole("button", { name: "מצב שופטים", pressed: true }).count()) {
    await page.getByRole("button", { name: "מצב שופטים", pressed: true }).click();
  }
  let end = segment(8, 0, "employee");
  await clickVisibly(page, page.getByRole("link", { name: "שיחה חדשה", exact: true }));
  const card = page.getByRole("region", { name: /יש לי פרטים מהשיחה מ/ });
  await expect(card).toBeVisible();
  await pause(page, 1_500);
  await clickVisibly(page, card.getByRole("button", { name: "להשתמש בהם" }));
  end();
  report.modelTurns += 1;
  await expect(card).toHaveCount(0);
  await waitIdle(page);
  const chip = page.getByText("משיחה קודמת").first();
  await expect(chip).toBeVisible();
  end = segment(8, 0, "employee");
  await chip.scrollIntoViewIfNeeded();
  await pause(page, 1_600);
  end();
  return 'memory card offered, "להשתמש בהם", chips "משיחה קודמת" shown';
});

scene(9, "admin invites, employee registers", [], async () => {
  // prepare both pages (not part of the cut)
  const admin = await ensureAdmin();
  await admin.goto(WEB + "/admin");
  await expect(admin.getByRole("heading", { level: 1, name: "ניהול משתמשים" })).toBeVisible();
  const guest = await newContext("guest");
  await guest.goto(WEB + "/");
  await expect(guest.getByRole("heading", { level: 1 })).toContainText("כך תוכלו לדעת");
  const password = crypto.randomBytes(18).toString("base64url"); // never printed or saved
  SECRETS.add(password);
  await pause(admin, 600);

  const endAdmin = segment(9, 0, "admin");
  const endGuest = segment(9, 1, "guest");
  // left: the admin invites
  await typeInto(admin, admin.getByLabel("מייל").first(), GUEST_EMAIL);
  await admin.locator("#invite-role").selectOption("employee");
  await clickVisibly(admin, admin.getByRole("button", { name: "יצירת קוד הזמנה" }));
  const dialog = admin.getByRole("dialog", { name: "קוד הזמנה" });
  await expect(dialog).toContainText("הקוד יוצג פעם אחת בלבד");
  const code = ((await dialog.getByLabel("הקוד").textContent()) ?? "").trim();
  if (!/^[A-Z2-9]{5}-[A-Z2-9]{5}$/.test(code)) throw new Error("the invite code has an unexpected shape");
  // right: the new guest registers
  await clickVisibly(guest, guest.getByRole("link", { name: "הרשמה ראשונה" }));
  await typeInto(guest, guest.getByLabel("מייל"), GUEST_EMAIL);
  await typeInto(guest, guest.getByLabel("קוד הזמנה"), code);
  await typeInto(guest, guest.getByLabel("השם שלך"), GUEST_NAME);
  await typeInto(guest, guest.getByLabel(/^סיסמה/), password);
  await typeInto(guest, guest.getByLabel("אימות סיסמה"), password);
  await clickVisibly(guest, guest.getByRole("button", { name: "הרשמה" }));
  await expect(guest.getByText(/שלום .*נועה כהן/)).toBeVisible();
  await pause(guest, 1_000);
  endAdmin();
  endGuest();
  // the home is empty: none of דנה's conversations
  const own = guest.getByRole("complementary", { name: "השיחות שלי" }).locator('a[href^="/c/"]');
  const listed = await own.count();
  await dialog.getByRole("button", { name: "סגירה" }).click().catch(() => {});
  if (listed > 0) throw new Error(`the new employee's list shows ${listed} conversation(s), expected none`);
  return "invite -> registration -> empty home (no conversations from דנה)";
});

// ---------------------------------------------------------------------------------- runner

const SCENE_TIMEOUT_MS = 6 * 60_000;

const DEBUG = path.join(OUT, "debug");

/** The error without terminal colours: its first line and the locator it names. */
function cleanMessage(error) {
  const text = String(error?.message ?? error).replace(/\u001b\[[0-9;]*m/g, "");
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const locator = lines.find((l) => l.startsWith("Locator:"));
  return [lines[0], locator].filter(Boolean).join(" | ").slice(0, 400);
}

/** On a failure: a screenshot of every open page and the text of the last reply, into out/debug/. */
async function saveDebug(label) {
  fs.mkdirSync(DEBUG, { recursive: true });
  const saved = [];
  for (const [name, entry] of Object.entries(contexts)) {
    try {
      const base = path.join(DEBUG, `${label}-${name}`);
      await entry.page.screenshot({ path: `${base}.png` });
      const last = await lastMessage(entry.page).innerText({ timeout: 3_000 }).catch(() => "(no message on this page)");
      const hero_ = await hero(entry.page).innerText({ timeout: 2_000 }).catch(() => "(no result card)");
      fs.writeFileSync(`${base}-last-reply.txt`, redact(`last message:\n${last}\n\nresult card:\n${hero_}\n`), "utf8");
      saved.push(`${base}.png`);
    } catch {
      /* the page is gone */
    }
  }
  if (saved.length) log(`debug   ${label}: ${saved.map((p) => path.relative(REPO, p)).join(", ")} (+ -last-reply.txt)`);
  return saved.map((p) => path.relative(REPO, p));
}

async function runScene(item, failed) {
  const blocked = item.deps.find((d) => failed.has(d));
  const row = { n: item.n, name: item.name, status: "PASS", seconds: 0, note: "" };
  if (blocked !== undefined) {
    row.status = "SKIP";
    row.note = `depends on scene ${blocked}`;
    return row;
  }
  const started = Date.now();
  try {
    row.note = await Promise.race([
      item.fn(),
      new Promise((_, reject) => setTimeout(() => reject(new Error("scene timeout")), SCENE_TIMEOUT_MS)),
    ]);
  } catch (error) {
    row.status = "FAIL";
    row.note = cleanMessage(error);
    row.debug = await saveDebug(`scene-${String(item.n).padStart(2, "0")}`);
  }
  row.seconds = +((Date.now() - started) / 1000).toFixed(1);
  return row;
}

async function saveVideos() {
  const files = {};
  for (const [name, entry] of Object.entries(contexts)) {
    const video = entry.page.video();
    await entry.context.close();
    if (!video) continue;
    const target = path.join(RAW, `${name}.webm`);
    await video.saveAs(target);
    files[name] = path.relative(HERE, target).replaceAll("\\", "/");
  }
  fs.rmSync(path.join(RAW, "_"), { recursive: true, force: true });
  return files;
}

async function main() {
  for (const [who, { pw }] of Object.entries(ACCOUNTS)) {
    if (!pw) throw new Error(`no password for ${who} (run.py prompts for it)`);
  }
  log(`mode: ${MODE}   web: ${WEB}   api: ${API}`);
  await probes();
  for (const [key, value] of Object.entries(report.probes)) {
    log(`probe  ${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`);
  }
  if (/ABSENT|unexpected/.test(report.probes.profile_endpoints) || report.probes.accounts !== "present") {
    log("STOP: a precondition fails (see the probes above); nothing was run");
    report.stopped = true;
    return finish(false);
  }

  browser = await chromium.launch();
  const failed = new Set();
  try {
    try {
      await prepAdminConversation(); // not recorded
      log("prep    the admin's conversation is ready (not recorded)");
    } catch (error) {
      log(`prep    FAIL  the admin's conversation: ${cleanMessage(error)} (scene 7 will fail)`);
      await saveDebug("prep");
    }
    await newContext("employee");
    for (const item of scenes) {
      const row = await runScene(item, failed);
      if (row.status !== "PASS") failed.add(item.n);
      report.scenes.push(row);
      log(`scene ${String(item.n).padStart(2)}  ${row.status.padEnd(4)}  ${String(row.seconds).padStart(6)} s  ${item.name}: ${row.note}`);
    }
    report.scenes.push({ n: 10, name: "close", status: "PASS", seconds: 0, note: "made in editing (logo on navy)" });
    log("scene 10  PASS         0 s  close: made in editing (logo on navy)");
  } finally {
    const cleaned = await deleteGuest().catch(() => false);
    const prepDeleted = await deleteAdminPrep().catch(() => false);
    report.cleanup = `${cleaned === false ? "no guest to delete" : "video-guest deleted (account and conversations)"}; ${prepDeleted ? "admin's prep conversation deleted" : "no admin prep conversation to delete"}`;
    log(`cleanup: ${report.cleanup}`);
    const files = await saveVideos().catch(() => ({}));
    report.rawFiles = files;
    await browser.close();
  }
  const allPass = report.scenes.every((s) => s.status === "PASS");
  return finish(allPass);
}

function finish(allPass) {
  report.allPass = allPass;
  report.when = new Date().toISOString();
  const outFile = path.join(OUT, RECORD ? "take.json" : "dry-run.json");
  fs.writeFileSync(outFile, JSON.stringify(report, null, 2));
  if (RECORD && allPass) {
    const cuts = { scenes: Object.entries(segments).map(([n, panes]) => ({ n: Number(n), panes })), rawFiles: report.rawFiles };
    fs.writeFileSync(path.join(OUT, "cuts.json"), JSON.stringify(cuts, null, 2));
  }
  log("");
  log(allPass ? "RESULT: ALL SCENES PASS" : "RESULT: NOT ALL SCENES PASS");
  if (report.improvised.length) log(`improvised answers: ${report.improvised.length} (each logged in full above)`);
  log(`model turns started: ${report.modelTurns} (no live spend ledger is visible from outside)`);
  return allPass;
}

main()
  .then((ok) => process.exit(ok ? 0 : 1))
  .catch((error) => {
    log("ERROR:", error?.message ?? error);
    process.exit(2);
  });

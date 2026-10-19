/**
 * The backup demo video (Day 5 Stage 6), at human pace: visible typing, about a second on each
 * key moment. Run by `uv run --project backend python tasks.py record-demo`
 * (backend/scripts/record_demo.py), never by the test suite. Two recordings: the employee's page
 * and the representative's.
 *
 *   empty state -> the walkthrough to +2,914, the 802 line's provenance -> E-001 to +661 pending
 *   -> /rep answers 350 -> +611 final -> judges mode on the walkthrough's comparison turn, and on
 *   the guard-rejection session (seeded by the launcher: a +2,915 draft the real guard rejects)
 */

import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";

const OUT = process.env.RECORD_OUT ?? "";
const GUARD_SESSION = process.env.RECORD_GUARD_SESSION ?? "";
const REP_TOKEN = process.env.RECORD_REP_TOKEN ?? "rep-demo";
const ADMIN_TOKEN = process.env.RECORD_ADMIN_TOKEN ?? "admin-demo";
const SESSION_KEY = "compass.session";
const TYPING_MS = 45; // per character

const pause = (page: Page, ms = 1_200) => page.waitForTimeout(ms);

async function show(locator: Locator, ms = 1_200): Promise<void> {
  await locator.evaluate((el) => el.scrollIntoView({ behavior: "smooth", block: "center" }));
  await locator.page().waitForTimeout(ms);
}

/** Type into the chat like a person, send, and wait for the reply. */
async function say(page: Page, text: string): Promise<void> {
  const input = page.locator("#chat-input");
  await input.click();
  await page.keyboard.type(text, { delay: TYPING_MS });
  await pause(page, 500);
  await page.keyboard.press("Enter");
  await expect(page.getByText("מחשב…")).toBeVisible();
  await expect(page.getByText("מחשב…")).toHaveCount(0);
  await pause(page, 900);
}

async function typeToken(page: Page, label: string, token: string): Promise<void> {
  await page.getByLabel(label).click();
  await page.keyboard.type(token, { delay: 80 });
  await pause(page, 400);
  await page.getByRole("button", { name: "אישור", exact: true }).click();
}

async function openSession(page: Page, sessionId: string): Promise<void> {
  await page.evaluate(({ key, id }) => sessionStorage.setItem(key, id), {
    key: SESSION_KEY,
    id: sessionId,
  });
  await page.reload();
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
}

test("the demo, recorded", async ({ page, context, request }) => {
  expect(OUT, "RECORD_OUT").not.toBe("");
  expect(GUARD_SESSION, "RECORD_GUARD_SESSION").not.toBe("");
  const health = (await (await request.get("/api/health")).json()) as {
    llm: string;
    demo_scripts: { name: string; messages: string[] }[];
  };
  expect(health.llm).toBe("scripted");
  const script = (name: string) => health.demo_scripts.find((s) => s.name === name)?.messages ?? [];

  // 1. the empty state
  await page.goto("/");
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  await expect(page.getByText("איך זה עובד")).toBeVisible();
  await pause(page, 2_500);

  // 2. the walkthrough to +2,914, then the 802 line's provenance
  for (const text of script("walkthrough")) await say(page, text);
  const hero = page.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).toContainText("+2,914");
  await show(hero, 2_000);
  const incomeTax = page.locator('button[data-key="income_tax"]');
  await show(incomeTax, 800);
  await incomeTax.click();
  const strip = page.getByTestId("provenance");
  await expect(strip).toContainText("+802");
  await show(strip, 3_000);
  const walkthroughSession = await page.evaluate((key) => sessionStorage.getItem(key), SESSION_KEY);
  expect(walkthroughSession).toBeTruthy();

  // 3. a new conversation: E-001 to +661, pending the representative
  await page.evaluate((key) => sessionStorage.removeItem(key), SESSION_KEY);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(page, 600);
  await page.reload();
  await expect(page.getByText("איך זה עובד")).toBeVisible();
  await pause(page, 1_000);
  for (const text of script("e001")) await say(page, text);
  await expect(hero).toContainText("+661");
  await expect(hero).toContainText("זמני");
  await show(hero, 2_500);

  // 4. the representative answers 350 (a second page, recorded too)
  const rep = await context.newPage();
  await rep.goto("/rep");
  await pause(rep, 1_000);
  await typeToken(rep, "טוקן נציג", REP_TOKEN);
  await pause(rep, 1_000);
  await rep.getByRole("link").last().click();
  await expect(rep.getByRole("heading", { level: 2, name: "השתתפות עצמית · ATTO 3" })).toBeVisible();
  await pause(rep, 2_000);
  await rep.getByLabel("סכום ההשתתפות החודשית ב-ATTO 3 (₪)").click();
  await rep.keyboard.type("350", { delay: 250 });
  await pause(rep, 1_000);
  await rep.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(rep.getByText("התשובה נשלחה. החישוב אצל העובד/ת מתעדכן.").first()).toBeVisible();
  await pause(rep, 2_500);
  await rep.close();
  await rep.video()?.saveAs(path.join(OUT, "compass-demo-rep.webm"));

  // 5. the employee's card turns final: +611
  await page.bringToFront();
  await expect(hero).toContainText("+611");
  await expect(hero).toContainText("סופי");
  await show(hero, 3_000);
  await expect(page.getByText("מחשב…")).toHaveCount(0);
  await pause(page, 1_500);
  const participation = page.locator('[data-input="alternative_participation"]');
  await show(participation, 2_000);

  // 6. judges mode on the walkthrough's comparison turn (the latest one)
  await openSession(page, walkthroughSession ?? "");
  await expect(hero).toContainText("+2,914");
  await pause(page, 1_000);
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await typeToken(page, "טוקן מנהל", ADMIN_TOKEN);
  await expect(page.locator("#engine-title")).toContainText("חדר המנועים · תור");
  // the stream replays with the admin token: wait for the whole turn before opening anything
  const guard = page.locator("article", { hasText: "שומר המספרים" }).last();
  await expect(guard).toContainText("3 מתוך 3 אומתו · נשלח");
  await pause(page, 2_000);
  const compareCard = page
    .locator("article")
    .filter({ hasText: "המודל קרא לכלי" })
    .filter({ has: page.getByText("compare", { exact: true }) });
  await show(compareCard, 1_000);
  await expect(async () => {
    const details = compareCard.locator("details");
    if ((await details.getAttribute("open")) === null) await compareCard.locator("summary").click();
    await expect(details).toHaveAttribute("open", "", { timeout: 1_000 });
  }).toPass();
  await show(compareCard, 3_000);
  await show(guard, 3_000);

  // 7. judges mode on the guard rejection: the +2,915 draft struck through, then the rewrite
  await openSession(page, GUARD_SESSION);
  await expect(hero).toContainText("+2,914");
  if (await page.locator("#engine-title").count() === 0) {
    await page.getByRole("button", { name: "מצב שופטים" }).click(); // the token is remembered
  }
  await expect(page.locator("#engine-title")).toContainText("חדר המנועים · תור");
  await pause(page, 1_500);
  const draft = page.getByText("+2,915").first();
  await show(draft, 3_500);
  await show(page.getByText("נשלח אחרי ניסוח מחדש").first(), 3_000);

  await page.close();
  await page.video()?.saveAs(path.join(OUT, "compass-demo-employee.webm"));
});

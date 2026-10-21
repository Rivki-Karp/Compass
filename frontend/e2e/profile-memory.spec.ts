/**
 * Remembered details (COMPASS_PROFILE_MEMORY=1), in demo mode: the e2e config's own server
 * (PROFILE_PORT: accounts, number sources and the memory on). One account, in order:
 *
 *   1  a first conversation saves its values; a second shows the card; "להשתמש בהם" applies
 *      them and a reply number's popover says "משיחה קודמת"
 *   2  the card: axe clean and screenshots at 1440 and 400; "להתחיל מחדש" shows the normal flow
 *      and stays dismissed after a reload
 *   3  deleting the saved details (asked first) means no card next time
 */

import path from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { axe } from "./axe";
import { ACCOUNTS, E2E_PASSWORD, PROFILE_PORT, SCREENSHOTS, demoScript } from "./support";

const BASE = `http://127.0.0.1:${PROFILE_PORT}`;

test.skip(!!process.env.E2E_BASE_URL, "needs the e2e config's own profile-memory server");
test.use({ baseURL: BASE });

async function visitor(browser: Browser, viewport = { width: 1440, height: 900 }): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE, locale: "he-IL", viewport });
  return context.newPage();
}

async function logIn(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("מייל").fill(ACCOUNTS.employee.email);
  await page.getByLabel("סיסמה").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "כניסה", exact: true }).click();
  await expect(page.getByRole("button", { name: "יציאה" })).toBeVisible();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
}

const card = (page: Page) => page.getByRole("region", { name: /יש לי פרטים מהשיחה מ/ });

async function newConversation(page: Page): Promise<void> {
  const before = page.url();
  await page.getByRole("link", { name: "שיחה חדשה", exact: true }).click();
  await expect(page).not.toHaveURL(before);
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
}

test("1. a first conversation saves, a second offers; using them shows where a number came from", async ({
  browser,
}) => {
  const page = await visitor(browser);
  await logIn(page);
  await expect(card(page)).toHaveCount(0); // nothing is saved yet
  const walkthrough = await demoScript(page.request, "walkthrough");
  for (const text of walkthrough.messages) {
    await page.getByRole("button", { name: text }).click();
    await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  }

  await newConversation(page);
  await expect(card(page)).toBeVisible();
  const rows = card(page).getByRole("list", { name: "פרטים שמורים" });
  await expect(rows).toContainText("18,500");
  await expect(rows).toContainText("לפי דבריך");
  await expect(rows).toContainText("הרכב היום");
  // nothing is used until it is confirmed: no message, no comparison
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toHaveCount(0);

  await card(page).getByRole("button", { name: "להשתמש בהם" }).click();
  await expect(card(page)).toHaveCount(0);
  const reply = page.getByText("קיבלתי את הפרטים שאישרת מהשיחה הקודמת");
  await expect(reply).toBeVisible();
  await page.getByRole("button", { name: "מאיפה המספר 18,500?" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("משיחה קודמת");
  await expect(page.getByTestId("number-origin")).toContainText(/משיחה קודמת, \d\d\/\d\d/);
});

test("2. the card is accessible, and starting fresh shows the normal flow", async ({
  browser,
}, info) => {
  const page = await visitor(browser);
  await logIn(page);
  await expect(card(page)).toBeVisible(); // the account's conversation on login is offered too
  await axe(page, "profile-card", info);
  await page.screenshot({ path: path.join(SCREENSHOTS, "profile-card-1440.png") });

  const phone = await visitor(browser, { width: 400, height: 860 });
  await logIn(phone);
  await expect(card(phone)).toBeVisible();
  await axe(phone, "profile-card-400", info);
  await phone.waitForTimeout(1_500);
  await phone.screenshot({ path: path.join(SCREENSHOTS, "profile-card-400.png") });

  await card(page).getByRole("button", { name: "להתחיל מחדש" }).click();
  await expect(card(page)).toHaveCount(0);
  await expect(page.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  await page.reload();
  await expect(page.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  await expect(card(page)).toHaveCount(0); // dismissed for this conversation, also after a reload
  const again = await visitor(browser);
  await logIn(again); // a new login, a new conversation
  await expect(card(again)).toBeVisible(); // nothing was deleted
});

test("3. the saved details can be deleted, after asking, and then no card appears", async ({
  browser,
}) => {
  const page = await visitor(browser);
  await logIn(page);
  await expect(card(page)).toBeVisible();
  await card(page).getByRole("button", { name: "מחיקת הפרטים השמורים" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("למחוק את הפרטים השמורים?");
  await page.getByRole("button", { name: "ביטול" }).click();
  await expect(card(page)).toBeVisible(); // asked first: cancel changes nothing
  await card(page).getByRole("button", { name: "מחיקת הפרטים השמורים" }).click();
  await page.getByRole("button", { name: "מחיקה", exact: true }).click();
  await expect(card(page)).toHaveCount(0);
  const again = await visitor(browser);
  await logIn(again);
  await expect(again.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  await expect(card(again)).toHaveCount(0);
});

/**
 * Accounts screens: axe (serious and critical fail) on the landing page, register, home empty and
 * with history, the admin page and the invite-code dialog; and the README screenshots at 1440 and
 * 400 px: landing, home, admin (docs/screenshots/auth-*). The accounts server (AUTH_PORT).
 */

import path from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { axe } from "./axe";
import { ACCOUNTS, AUTH_PORT, E2E_PASSWORD, SCREENSHOTS, demoScript } from "./support";

const BASE = `http://127.0.0.1:${AUTH_PORT}`;

test.skip(!!process.env.E2E_BASE_URL, "needs the e2e config's own accounts server");
test.use({ baseURL: BASE });

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 400, height: 860 };

async function visitor(browser: Browser, viewport: { width: number; height: number }) {
  const context = await browser.newContext({ baseURL: BASE, locale: "he-IL", viewport });
  return context.newPage();
}

async function logIn(page: Page, who: keyof typeof ACCOUNTS): Promise<void> {
  await page.goto("/");
  await page.getByLabel("מייל").fill(ACCOUNTS[who].email);
  await page.getByLabel("סיסמה").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "כניסה", exact: true }).click();
  await expect(page.getByRole("button", { name: "יציאה" })).toBeVisible();
}

async function shot(page: Page, name: string, fullPage = false): Promise<void> {
  await page.waitForTimeout(1_500); // entrance animations have settled
  await page.screenshot({ path: path.join(SCREENSHOTS, `${name}.png`), fullPage });
}

test("axe: landing, register, home empty and with history, admin, the invite-code dialog", async ({
  browser,
}, info) => {
  const landing = await visitor(browser, DESKTOP);
  await landing.goto("/");
  await expect(landing.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
  await axe(landing, "accounts-landing", info);
  await landing.goto("/register");
  await expect(landing.getByRole("form", { name: "הרשמה ראשונה" })).toBeVisible();
  await axe(landing, "accounts-register", info);

  const home = await visitor(browser, DESKTOP);
  await logIn(home, "employee");
  await expect(home.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  await axe(home, "accounts-home-empty", info);
  const script = await demoScript(home.request, "walkthrough");
  for (const text of script.messages) {
    await home.getByRole("button", { name: text }).click();
    await expect(home.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  }
  await expect(
    home.getByRole("complementary", { name: "השיחות שלי" }).getByRole("link", { name: /ויתור על הרכב/ }).first(),
  ).toBeVisible();
  await axe(home, "accounts-home-history", info);
  await home.getByRole("button", { name: /מחיקת שיחה/ }).first().click();
  await expect(home.getByRole("alertdialog")).toBeVisible();
  await axe(home, "accounts-delete-dialog", info);

  const admin = await visitor(browser, DESKTOP);
  await logIn(admin, "admin");
  await admin.goto("/admin");
  await expect(admin.getByRole("table", { name: "משתמשים" })).toBeVisible();
  await axe(admin, "accounts-admin", info);
  await admin.getByLabel("מייל").fill(`axe-${Date.now()}@example.com`);
  await admin.getByRole("button", { name: "יצירת קוד הזמנה" }).click();
  await expect(admin.getByRole("dialog", { name: "קוד הזמנה" })).toBeVisible();
  await axe(admin, "accounts-invite-dialog", info);
});

for (const [label, viewport] of [
  ["1440", DESKTOP],
  ["400", PHONE],
] as const) {
  test(`screenshots at ${label}: landing, home, admin`, async ({ browser }) => {
    const landing = await visitor(browser, viewport);
    await landing.goto("/");
    await expect(landing.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
    await shot(landing, `auth-landing-${label}`, true);

    const home = await visitor(browser, viewport);
    await logIn(home, "employee");
    const script = await demoScript(home.request, "walkthrough");
    for (const text of script.messages) {
      await home.getByRole("button", { name: text }).click();
      await expect(home.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
    }
    if (viewport.width < 700) {
      // on a phone the list is a drawer behind the header's button
      await shot(home, `auth-home-${label}`);
      await home.getByRole("button", { name: "השיחות שלי" }).click();
      await expect(home.getByRole("dialog", { name: "השיחות שלי" })).toBeVisible();
      await shot(home, `auth-home-drawer-${label}`);
    } else {
      await shot(home, `auth-home-${label}`);
    }

    const admin = await visitor(browser, viewport);
    await logIn(admin, "admin");
    await admin.goto("/admin");
    await expect(admin.getByRole("table", { name: "משתמשים" })).toBeVisible();
    await shot(admin, `auth-admin-${label}`, true);
  });
}

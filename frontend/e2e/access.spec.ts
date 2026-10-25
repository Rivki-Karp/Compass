/**
 * Judges mode for any user and the demo quick access (COMPASS_JUDGES_UNLOCK, COMPASS_DEMO_LOGIN),
 * on the e2e config's ACCESS server (accounts, the scripted model, the real API and the build).
 *
 *   1  the quick access: one click into each of the three demo accounts, the banner, logout
 *   2  an employee unlocks judges mode with the admin password and sees the guard card; the
 *      lock turns it off; someone else's conversation is still a 404
 *   3  a wrong password: the one generic error, and no engine room
 *   4  a demo admin cannot delete, disable or demote a demo account (disabled, with the reason)
 *   5  the flag off (the accounts server without the flags): no section on the landing page
 *   6  axe: the landing section and the dialog
 *   7  screenshots at 1440 and 400
 */

import path from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { axe } from "./axe";
import {
  ACCESS_PORT,
  ACCOUNTS,
  DEMO_ACCOUNTS,
  E2E_PASSWORD,
  PROFILE_PORT,
  SCREENSHOTS,
  demoScript,
} from "./support";

const BASE = `http://127.0.0.1:${ACCESS_PORT}`;
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 400, height: 860 };

test.skip(!!process.env.E2E_BASE_URL, "needs the e2e config's own access server");
test.use({ baseURL: BASE });

async function visitor(
  browser: Browser,
  viewport = DESKTOP,
  baseURL = BASE,
): Promise<Page> {
  const context = await browser.newContext({ baseURL, locale: "he-IL", viewport });
  return context.newPage();
}

async function logIn(page: Page, who: keyof typeof ACCOUNTS): Promise<void> {
  await page.goto("/");
  await page.getByLabel("מייל").fill(ACCOUNTS[who].email);
  await page.getByLabel("סיסמה").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "כניסה", exact: true }).click();
  await expect(page.getByRole("button", { name: "יציאה" })).toBeVisible();
}

async function sendScript(page: Page, name: string): Promise<void> {
  const script = await demoScript(page.request, name);
  for (const text of script.messages) {
    await page.getByRole("button", { name: text }).click();
    await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  }
}

async function shot(page: Page, name: string, fullPage = false): Promise<void> {
  await page.waitForTimeout(1_500); // entrance animations have settled
  await page.screenshot({ path: path.join(SCREENSHOTS, `${name}.png`), fullPage });
}

const SECTION = "כניסה מהירה להתנסות";

test("1. one click into each demo account, the banner, and logout", async ({ browser }) => {
  const cases = [
    { button: /עובדת/, after: async (page: Page) => expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/) },
    {
      button: /נציג/,
      after: async (page: Page) => expect(page).toHaveURL(/\/rep$|\/$|\/c\//),
    },
    {
      button: /מנהלת/,
      after: async (page: Page) =>
        expect(page.getByRole("link", { name: "ניהול משתמשים" })).toBeVisible(),
    },
  ];
  for (const { button, after } of cases) {
    const page = await visitor(browser);
    await page.goto("/");
    const section = page.getByRole("region", { name: SECTION });
    await expect(section).toBeVisible();
    await expect(section).toContainText("חשבונות הדגמה משותפים. אל תזינו מידע אישי אמיתי.");
    await section.getByRole("button", { name: button }).click();
    await expect(page.getByRole("button", { name: "יציאה" })).toBeVisible();
    await after(page);
    // the thin strip, with its way out
    const banner = page.getByRole("region", { name: "חשבון הדגמה" });
    await expect(banner).toContainText("את/ה בחשבון הדגמה משותף");
    await banner.getByRole("button", { name: "התנתקות" }).click();
    await expect(page.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
    await expect(page.getByRole("region", { name: "חשבון הדגמה" })).toHaveCount(0);
  }
});

test("1b. the rep's demo login lands on the rep's screen", async ({ browser }) => {
  const page = await visitor(browser);
  await page.goto("/");
  await page.getByRole("region", { name: SECTION }).getByRole("button", { name: /נציג/ }).click();
  await expect(page.getByRole("link", { name: "מסך נציג" })).toBeVisible();
  await expect(page.getByRole("region", { name: "חשבון הדגמה" })).toBeVisible();
});

test("2. an employee unlocks judges mode with the admin password, and only their own", async ({
  browser,
}) => {
  const page = await visitor(browser);
  await logIn(page, "employee");
  await sendScript(page, "walkthrough");
  const own = new URL(page.url()).pathname.split("/").pop() ?? "";

  // no judges data before the unlock: the toggle asks for the admin password
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  const box = page.getByRole("dialog", { name: "מצב שופטים" });
  await expect(box).toContainText("הזינו את סיסמת המנהל כדי לראות את חדר המנועים");
  await expect(page.locator("article", { hasText: "שומר המספרים" })).toHaveCount(0);
  await box.getByLabel("סיסמת מנהל").fill(E2E_PASSWORD);
  await box.getByRole("button", { name: "פתיחה" }).click();

  // the engine room, with the guard card, in their own conversation
  const guard = page.locator("article", { hasText: "שומר המספרים" }).last();
  await expect(guard).toContainText("3 מתוך 3 אומתו · נשלח");
  await expect(guard).toContainText("+2,914");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // someone else's conversation is still not theirs, unlocked or not
  const token = await page.evaluate(
    () => (JSON.parse(sessionStorage.getItem("compass.auth") ?? "{}") as { token?: string }).token,
  );
  const other = await page.request.post("/api/auth/login", {
    data: { email: ACCOUNTS.other.email, password: E2E_PASSWORD },
  });
  const otherToken = ((await other.json()) as { token: string }).token;
  const theirs = await page.request.post("/api/sessions", {
    headers: { Authorization: `Bearer ${otherToken}` },
  });
  const theirId = ((await theirs.json()) as { id: string }).id;
  const peek = await page.request.get(`/api/sessions/${theirId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(peek.status()).toBe(404);
  const mine = await page.request.get(`/api/sessions/${own}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(mine.status()).toBe(200);

  // off again offers the lock; locking asks for the password the next time
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await expect(page.locator("article", { hasText: "שומר המספרים" })).toHaveCount(0);
  await page.getByRole("button", { name: "נעילה" }).click();
  await expect(page.getByRole("button", { name: "נעילה" })).toHaveCount(0);
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await expect(page.getByRole("dialog", { name: "מצב שופטים" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // and the server agrees: locked, the same session is the public part again
  const locked = await page.request.get(`/api/sessions/${own}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const roles = ((await locked.json()) as { messages: { role: string }[] }).messages.map(
    (m) => m.role,
  );
  expect(roles).not.toContain("tool");
});

test("3. a wrong password: the generic error, and no engine room", async ({ browser }) => {
  const page = await visitor(browser);
  await logIn(page, "other");
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  const box = page.getByRole("dialog", { name: "מצב שופטים" });
  await box.getByLabel("סיסמת מנהל").fill("not the admin password");
  await box.getByRole("button", { name: "פתיחה" }).click();
  await expect(box.getByRole("alert")).toHaveText("הסיסמה שגויה");
  await expect(box.getByLabel("סיסמת מנהל")).toHaveValue("");
  await expect(page.locator("#engine-title")).toHaveCount(0);
  await box.getByRole("button", { name: "ביטול" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "נעילה" })).toHaveCount(0);
});

test("4. a demo admin cannot delete, disable or demote a demo account", async ({ browser }) => {
  const page = await visitor(browser);
  await page.goto("/");
  await page.getByRole("region", { name: SECTION }).getByRole("button", { name: /מנהלת/ }).click();
  await page.getByRole("link", { name: "ניהול משתמשים" }).click();
  const table = page.getByRole("table", { name: "משתמשים" });
  await expect(table).toBeVisible();
  // only the demo's accounts are listed: none of the real ones
  await expect(table).toContainText(DEMO_ACCOUNTS.employee.email);
  await expect(table).not.toContainText(ACCOUNTS.employee.email);
  await expect(table).not.toContainText(ACCOUNTS.other.email);
  const row = table.getByRole("row", { name: new RegExp(DEMO_ACCOUNTS.employee.name) });
  const reason = /אי אפשר למחוק אותו/;
  for (const control of [
    row.getByRole("combobox"),
    row.getByRole("button", { name: /השבתת/ }),
    row.getByRole("button", { name: /מחיקת/ }),
  ]) {
    await expect(control).toBeDisabled();
    await expect(control).toHaveAttribute("title", reason);
  }
  // an invite from a demo session cannot be an admin
  await expect(page.locator("#invite-role option")).toHaveText(["עובד/ת", "נציג/ה"]);
});

test("5. the flag off: no quick access on the landing page", async ({ browser }) => {
  // the accounts server of the profile-memory tests runs without the new flags
  const page = await visitor(browser, DESKTOP, `http://127.0.0.1:${PROFILE_PORT}`);
  await page.goto("/");
  await expect(page.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
  await expect(page.getByRole("region", { name: SECTION })).toHaveCount(0);
  await expect(page.getByText(SECTION)).toHaveCount(0);
});

test("6. axe: the landing section and the dialog", async ({ browser }, info) => {
  const landing = await visitor(browser);
  await landing.goto("/");
  await expect(landing.getByRole("region", { name: SECTION })).toBeVisible();
  await axe(landing, "access-landing", info);

  const page = await visitor(browser);
  await logIn(page, "other");
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await expect(page.getByRole("dialog", { name: "מצב שופטים" })).toBeVisible();
  await axe(page, "access-judges-dialog", info);
});

for (const [label, viewport] of [
  ["1440", DESKTOP],
  ["400", PHONE],
] as const) {
  test(`7. screenshots at ${label}: the landing section, the dialog, a demo admin`, async ({
    browser,
  }) => {
    const landing = await visitor(browser, viewport);
    await landing.goto("/");
    await expect(landing.getByRole("region", { name: SECTION })).toBeVisible();
    await landing.getByRole("region", { name: SECTION }).scrollIntoViewIfNeeded();
    await shot(landing, `access-landing-${label}`, true);

    const dialog = await visitor(browser, viewport);
    await logIn(dialog, "other");
    await dialog.getByRole("button", { name: "מצב שופטים" }).click();
    await expect(dialog.getByRole("dialog", { name: "מצב שופטים" })).toBeVisible();
    await shot(dialog, `access-judges-dialog-${label}`);

    const admin = await visitor(browser, viewport);
    await admin.goto("/");
    await admin.getByRole("region", { name: SECTION }).getByRole("button", { name: /מנהלת/ }).click();
    await expect(admin.getByRole("button", { name: "יציאה" })).toBeVisible();
    await admin.goto("/admin");
    await expect(admin.getByRole("table", { name: "משתמשים" })).toBeVisible();
    await shot(admin, `access-admin-demo-${label}`, true);
  });
}

/**
 * Accounts (COMPASS_AUTH=1), in demo mode: the scripted model, the real API and the production
 * build, on the e2e config's own accounts server (AUTH_PORT) with five seeded accounts. Each
 * person is a browser context of their own (their own sessionStorage, as in real life).
 *
 *   1  landing -> login -> chat -> logout -> landing
 *   2  the admin invites -> the new person registers with the code -> home
 *   3  isolation: A's conversation address, opened by B, is the not-found view
 *   4  resume a conversation from the list
 *   5  delete a conversation
 *   6  the rep logs in and answers a ticket; the employee's card settles
 *   7  a disabled user is logged out on the next request
 *   8  an empty conversation is not listed, "שיחה חדשה" stays in it, and logout deletes it
 */

import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";
import { ACCOUNTS, AUTH_PORT, E2E_PASSWORD, demoScript } from "./support";

const BASE = `http://127.0.0.1:${AUTH_PORT}`;

test.skip(!!process.env.E2E_BASE_URL, "needs the e2e config's own accounts server");
test.use({ baseURL: BASE });

type Who = keyof typeof ACCOUNTS;

/** A fresh browser context with its own page, at the landing page. */
async function visitor(browser: Browser, viewport = { width: 1440, height: 900 }): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE, locale: "he-IL", viewport });
  return context.newPage();
}

async function logIn(page: Page, who: Who): Promise<void> {
  await page.goto("/");
  await page.getByLabel("מייל").fill(ACCOUNTS[who].email);
  await page.getByLabel("סיסמה").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "כניסה", exact: true }).click();
  await expect(page.getByRole("button", { name: "יציאה" })).toBeVisible();
}

/** Open the conversation at its address; the sidebar and the greeting are the home screen. */
async function home(page: Page, who: Who): Promise<void> {
  await logIn(page, who);
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
}

const conversationId = (page: Page): string => new URL(page.url()).pathname.split("/").pop() ?? "";

/** The messages of a script, one chip at a time, each until its run has finished. */
async function sendScript(page: Page, messages: string[]): Promise<void> {
  for (const text of messages) {
    await page.getByRole("button", { name: text }).click();
    await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  }
}

/** An authenticated API call for a person (the browser's own token never leaves its context). */
async function token(request: APIRequestContext, who: Who): Promise<string> {
  const reply = await request.post("/api/auth/login", {
    data: { email: ACCOUNTS[who].email, password: E2E_PASSWORD },
  });
  expect(reply.ok()).toBe(true);
  return ((await reply.json()) as { token: string }).token;
}

test("1. landing, login, chat, logout, and back on the landing page", async ({ browser }) => {
  const page = await visitor(browser);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("כך תוכלו לדעת בדיוק כמה נשאר בנטו");
  await expect(page.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();

  // a wrong password: the one generic message, and nobody is logged in
  await page.getByLabel("מייל").fill(ACCOUNTS.employee.email);
  await page.getByLabel("סיסמה").fill("not the password");
  await page.getByRole("button", { name: "כניסה", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("מייל או סיסמה שגויים");

  await home(page, "employee");
  await expect(page.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  const walkthrough = await demoScript(page.request, "walkthrough");
  await sendScript(page, walkthrough.messages);
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+2,914");

  // the token is in sessionStorage, and only there
  const stored = await page.evaluate(() => ({
    session: sessionStorage.getItem("compass.auth") !== null,
    local: localStorage.length,
    cookies: document.cookie,
  }));
  expect(stored).toEqual({ session: true, local: 0, cookies: "" });

  const id = conversationId(page);
  await page.getByRole("button", { name: "יציאה" }).click();
  await expect(page.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem("compass.auth"))).toBeNull();
  // and the address of the conversation no longer opens it
  await page.goto(`/c/${id}`);
  await expect(page.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
});

test("2. the admin invites, the invited person registers with the code and reaches home", async ({
  browser,
}) => {
  const admin = await visitor(browser);
  await logIn(admin, "admin");
  await admin.goto("/admin");
  await expect(admin.getByRole("heading", { level: 1, name: "ניהול משתמשים" })).toBeVisible();
  const email = `newhire-${Date.now()}@example.com`;
  await admin.getByLabel("מייל").fill(email);
  await admin.getByRole("button", { name: "יצירת קוד הזמנה" }).click();
  const dialog = admin.getByRole("dialog", { name: "קוד הזמנה" });
  await expect(dialog).toContainText("הקוד יוצג פעם אחת בלבד");
  const code = (await dialog.getByLabel("הקוד").textContent())?.trim() ?? "";
  expect(code).toMatch(/^[A-Z2-9]{5}-[A-Z2-9]{5}$/);
  await dialog.getByRole("button", { name: "סגירה" }).click();
  await expect(admin.getByText(code)).toHaveCount(0); // gone for good
  await expect(admin.getByRole("table", { name: "משתמשים" })).not.toContainText(code);

  const person = await visitor(browser);
  await person.goto("/register");
  await person.getByLabel("מייל").fill(email);
  await person.getByLabel("קוד הזמנה").fill(code.toLowerCase().replace("-", ""));
  await expect(person.getByLabel("קוד הזמנה")).toHaveValue(code); // formatted as typed
  await person.getByLabel("השם שלך").fill("נועה חדשה");
  await person.getByLabel(/^סיסמה/).fill(E2E_PASSWORD);
  await person.getByLabel("אימות סיסמה").fill(E2E_PASSWORD);
  await person.getByRole("button", { name: "הרשמה" }).click();
  await expect(person.getByText("שלום נועה חדשה, מה בודקים היום?")).toBeVisible();

  // the code is single-use: a second registration with it gets the one generic message
  const again = await visitor(browser);
  await again.goto("/register");
  await again.getByLabel("מייל").fill(email);
  await again.getByLabel("קוד הזמנה").fill(code);
  await again.getByLabel("השם שלך").fill("אחר");
  await again.getByLabel(/^סיסמה/).fill(E2E_PASSWORD);
  await again.getByLabel("אימות סיסמה").fill(E2E_PASSWORD);
  await again.getByRole("button", { name: "הרשמה" }).click();
  await expect(again.getByRole("alert")).toHaveText("הקוד או המייל אינם תקינים");
});

test("3. isolation: another person's conversation address is the not-found view", async ({
  browser,
}) => {
  const owner = await visitor(browser);
  await home(owner, "employee");
  const id = conversationId(owner);

  const stranger = await visitor(browser);
  await logIn(stranger, "other");
  await stranger.goto(`/c/${id}`);
  await expect(stranger.getByRole("heading", { level: 1, name: "הדף לא נמצא" })).toBeVisible();
  // still logged in (a 404 is not a logout), and nothing of the conversation is on screen
  await stranger.goto("/");
  await expect(stranger.getByRole("button", { name: "יציאה" })).toBeVisible();
  // the API says the same, to anyone but the owner
  const other = await token(stranger.request, "other");
  const reply = await stranger.request.get(`/api/sessions/${id}`, {
    headers: { Authorization: `Bearer ${other}` },
  });
  expect(reply.status()).toBe(404);
});

test("4. a conversation resumes from the list, exactly where it stopped", async ({ browser }) => {
  const page = await visitor(browser);
  await home(page, "employee");
  const walkthrough = await demoScript(page.request, "walkthrough");
  await sendScript(page, walkthrough.messages);
  const hero = page.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).toContainText("+2,914");
  const resumed = conversationId(page);

  await page.getByRole("link", { name: "שיחה חדשה", exact: true }).click();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
  expect(conversationId(page)).not.toBe(resumed);
  await expect(page.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toHaveCount(0);

  const list = page.getByRole("complementary", { name: "השיחות שלי" });
  // (the same user's other conversations are in the list too: this one, by its address)
  await list.locator(`a[href="/c/${resumed}"]`).click();
  await expect(page).toHaveURL(new RegExp(`/c/${resumed}$`));
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+2,914");
  await expect(page.getByText(walkthrough.messages[0] ?? "").first()).toBeVisible();

  // a different browser, the same account: the same conversation
  const elsewhere = await visitor(browser);
  await logIn(elsewhere, "employee");
  await elsewhere.goto(`/c/${resumed}`);
  await expect(elsewhere.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+2,914");
});

test("5. deleting a conversation asks first, and removes it for good", async ({ browser }) => {
  const page = await visitor(browser);
  await home(page, "employee");
  const walkthrough = await demoScript(page.request, "walkthrough");
  await sendScript(page, walkthrough.messages);
  const doomed = conversationId(page);
  const list = page.getByRole("complementary", { name: "השיחות שלי" });
  const mine = list.locator("li", { has: page.locator(`a[href="/c/${doomed}"]`) });
  await expect(mine).toContainText("ויתור על הרכב"); // the list caught up with the comparison

  await mine.getByRole("button", { name: /מחיקת שיחה/ }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("למחוק את השיחה?");
  await dialog.getByRole("button", { name: "ביטול" }).click();
  await expect(page).toHaveURL(new RegExp(`/c/${doomed}$`)); // cancel deletes nothing

  await mine.getByRole("button", { name: /מחיקת שיחה/ }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "מחיקה" }).click();
  await expect(page).not.toHaveURL(new RegExp(`/c/${doomed}$`)); // on to a fresh conversation
  await expect(page.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  await expect(list.locator(`a[href="/c/${doomed}"]`)).toHaveCount(0);
  const bearer = await token(page.request, "employee");
  const reply = await page.request.get(`/api/sessions/${doomed}`, {
    headers: { Authorization: `Bearer ${bearer}` },
  });
  expect(reply.status()).toBe(404);
});

test("6. the rep logs in and answers a ticket; the employee's card settles", async ({ browser }) => {
  const employee = await visitor(browser);
  await home(employee, "employee");
  const script = await demoScript(employee.request, "e001");
  await sendScript(employee, script.messages);
  const hero = employee.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).toContainText("+661");
  await expect(hero).toContainText("ממתינה לנציג");

  const rep = await visitor(browser);
  await logIn(rep, "rep");
  await rep.goto("/rep"); // no token to type: the login is enough
  await expect(rep.getByLabel("טוקן נציג")).toHaveCount(0);
  await rep.getByRole("link").filter({ hasText: /ATTO 3/ }).last().click();
  await expect(rep.getByRole("heading", { level: 2, name: "השתתפות עצמית · ATTO 3" })).toBeVisible();
  await rep.getByLabel("סכום ההשתתפות החודשית ב-ATTO 3 (₪)").fill("350");
  await rep.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(rep.getByText("התשובה נשלחה. החישוב אצל העובד/ת מתעדכן.").first()).toBeVisible();

  await expect(hero).toContainText("+611");
  await expect(hero).toContainText("סופי");
  // a rep has no way into the employee's conversation
  const id = conversationId(employee);
  const repToken = await token(rep.request, "rep");
  const peek = await rep.request.get(`/api/sessions/${id}`, {
    headers: { Authorization: `Bearer ${repToken}` },
  });
  expect(peek.status()).toBe(404);
});

test("7. a disabled user is logged out on the next request", async ({ browser }) => {
  const victim = await visitor(browser);
  await home(victim, "victim");

  const admin = await visitor(browser);
  await logIn(admin, "admin");
  const adminToken = await token(admin.request, "admin");
  const users = (await (
    await admin.request.get("/api/admin/users", { headers: { Authorization: `Bearer ${adminToken}` } })
  ).json()) as { id: string; email: string }[];
  const target = users.find((u) => u.email === ACCOUNTS.victim.email);
  expect(target).toBeTruthy();
  const disabled = await admin.request.patch(`/api/admin/users/${target?.id}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { status: "disabled" },
  });
  expect(disabled.ok()).toBe(true);

  // the victim's next request: a message
  const chips = victim.locator('[aria-label="הצעות"]');
  await chips.getByRole("button").first().click();
  await expect(victim.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
  await expect(victim.getByText("החיבור הסתיים, צריך להיכנס שוב")).toBeVisible();
  expect(await victim.evaluate(() => sessionStorage.getItem("compass.auth"))).toBeNull();

  // and they cannot log in again until the admin turns them back on
  await victim.getByLabel("מייל").fill(ACCOUNTS.victim.email);
  await victim.getByLabel("סיסמה").fill(E2E_PASSWORD);
  await victim.getByRole("button", { name: "כניסה", exact: true }).click();
  await expect(victim.getByRole("alert")).toHaveText("מייל או סיסמה שגויים");
  await admin.request.patch(`/api/admin/users/${target?.id}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { status: "active" },
  });
});

test("8. an empty conversation is not listed; new chat stays in it; logout deletes it", async ({
  browser,
}) => {
  const page = await visitor(browser);
  await home(page, "employee");
  const list = page.getByRole("complementary", { name: "השיחות שלי" });
  const first = conversationId(page);
  await expect(list.locator(`a[href="/c/${first}"]`)).toHaveCount(0); // empty: not listed

  // "שיחה חדשה" inside an empty conversation stays in it and creates nothing
  const created: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/sessions")) created.push(r.url());
  });
  await page.getByRole("link", { name: "שיחה חדשה", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/c/${first}$`));
  expect(created).toEqual([]);

  // one message: it is a conversation now, and it is listed
  await page.locator('[aria-label="הצעות"]').getByRole("button").first().click();
  await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  await expect(list.locator(`a[href="/c/${first}"]`)).toHaveCount(1);

  // a new one is made now (its address differs) and is not listed either
  await page.getByRole("link", { name: "שיחה חדשה", exact: true }).click();
  await expect(page).not.toHaveURL(new RegExp(`/c/${first}$`));
  await expect(page.getByText(`שלום ${ACCOUNTS.employee.name}, מה בודקים היום?`)).toBeVisible();
  const empty = conversationId(page);
  await expect(list.locator(`a[href="/c/${empty}"]`)).toHaveCount(0);

  // logout deletes the empty one; the one with a message survives
  await page.getByRole("button", { name: "יציאה" }).click();
  await expect(page.getByRole("form", { name: "כניסה לעובדים" })).toBeVisible();
  const bearer = await token(page.request, "employee");
  const status = async (id: string) =>
    (await page.request.get(`/api/sessions/${id}`, { headers: { Authorization: `Bearer ${bearer}` } }))
      .status();
  expect(await status(empty)).toBe(404);
  expect(await status(first)).toBe(200);
});

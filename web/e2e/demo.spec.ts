/**
 * The demo end to end (brief Stage 8), in demo mode against the real API serving the build:
 * the walkthrough, E-001 through the representative's screen, and judges mode with and without
 * the admin token. Saves the README screenshots (docs/screenshots/).
 */

import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { demoScript, enterToken, runScript, SCREENSHOTS, TOKENS } from "./support";

const HERO_REGION = "p.sr-only[aria-live=polite]";

interface Effects {
  announced: string[]; // every text the hero's live region showed
  borders: number; // how many times the settle border turned on (any hero, remounted or not)
}

/** Record the hero's effects in the page from now on. */
async function recordEffects(page: Page): Promise<() => Promise<Effects>> {
  await page.evaluate((selector) => {
    const region = document.querySelector(selector);
    if (!region) throw new Error("no live region");
    const effects: Effects = { announced: [], borders: 0 };
    (window as unknown as { __effects: Effects }).__effects = effects;
    new MutationObserver(() => {
      const text = region.textContent ?? "";
      if (text) effects.announced.push(text);
    }).observe(region, { childList: true, characterData: true, subtree: true });
    const on = new WeakSet<Element>();
    const check = () => {
      for (const border of document.querySelectorAll("[data-settled-flash]")) {
        const lit = border.getAttribute("data-settled-flash") === "on";
        if (lit && !on.has(border)) effects.borders += 1;
        if (lit) on.add(border);
        else on.delete(border);
      }
    };
    new MutationObserver(check).observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-settled-flash"],
    });
  }, HERO_REGION);
  return () => page.evaluate(() => (window as unknown as { __effects: Effects }).__effects);
}

test("walkthrough: +2,914, five steps and the total, the provenance of the selected step", async ({
  page,
  request,
}) => {
  await runScript(page, await demoScript(request, "walkthrough"));

  const hero = page.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).toContainText("+2,914");
  await expect(hero).toContainText("ויתור על הרכב לעומת היום");

  const columns = page.getByRole("group", { name: "פירוט ההפרש לפי שורות" }).getByRole("button");
  await expect(columns).toHaveCount(6); // five steps and the total
  const labels = await columns.evaluateAll((buttons) =>
    buttons.map((b) => b.getAttribute("aria-label")),
  );
  expect(labels.at(-1)).toContain("פלוס 2,914");

  const strip = page.getByTestId("provenance");
  await expect(strip).toContainText("+1,500"); // the largest step is selected by default
  await expect(strip).toContainText("חושב בכלי compare");
  await expect(strip.getByRole("list", { name: "נתונים" })).toBeVisible();

  await page.screenshot({ path: path.join(SCREENSHOTS, "employee.png") });

  // Every alternative on screen: list_options (run through the dev tools endpoint, as the model
  // would call it) puts them above the hero; selecting the second one switches every panel.
  const sid = await page.evaluate(() => sessionStorage.getItem("compass.session"));
  const listed = await request.post(`/api/sessions/${sid}/tools/list_options`, { data: {} });
  expect((await listed.json()).ok).toBe(true);
  const options = page.getByRole("radiogroup", { name: /כל החלופות שלך/ });
  const waiver = options.getByRole("radio", { name: /^ויתור על הרכב/ });
  await expect(waiver).toHaveAttribute("aria-checked", "true"); // the one the agent compared
  const second = options.getByRole("radio").nth(1);
  await expect(second).toHaveAccessibleName(/^MG4/);
  await waiver.focus();
  await page.keyboard.press("ArrowDown"); // a radio group: the arrow selects the next option
  await expect(second).toHaveAttribute("aria-checked", "true");
  await expect(second).toBeFocused();
  await expect(hero).toContainText("MG4 לעומת היום");
  await expect(hero).toContainText("+1,013");
  await expect(strip).toContainText("חושב מחדש בשרת · בלי מודל");
  await expect(page.getByRole("region", { name: "על מה החישוב מבוסס" })).toContainText(
    "הרכב בחלופה · MG4",
  );
});

test("E-001: +661 pending, the rep answers 350 in /rep, then +611 final; judges on and off do not re-announce", async ({
  page,
  context,
  request,
}) => {
  await runScript(page, await demoScript(request, "e001"));
  const hero = page.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).toContainText("+661");
  await expect(hero).toContainText("ממתינה לנציג");
  await expect(hero).toContainText("זמני");
  const effects = await recordEffects(page);

  // the representative, in a second page of the same browser
  const rep = await context.newPage();
  await rep.goto("/rep");
  await enterToken(rep, "טוקן נציג", TOKENS.rep);
  // this run's ticket is the newest (a shared demo database may hold older ones)
  await rep.getByRole("link").last().click();
  await expect(rep.getByRole("heading", { level: 2, name: "השתתפות עצמית · ATTO 3" })).toBeVisible();
  await expect(rep.getByText("+661")).toBeVisible();
  await rep.screenshot({ path: path.join(SCREENSHOTS, "representative.png") });
  await rep.getByLabel("סכום ההשתתפות החודשית ב-ATTO 3 (₪)").fill("350");
  await rep.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(rep.getByText("התשובה נשלחה. החישוב אצל העובד/ת מתעדכן.").first()).toBeVisible();

  // the employee's card turns final
  await expect(hero).toContainText("+611");
  await expect(hero).toContainText("סופי");
  await expect(hero.getByText("ממתינה לנציג")).toHaveCount(0);
  const participation = page.locator('[data-input="alternative_participation"]');
  await expect(participation).toContainText("אושר על ידי נציג");
  await expect(participation).toContainText("350");
  const settled = "ההשתתפות אושרה על ידי נציג. ההפרש עודכן: פלוס 611 שקלים";
  await expect.poll(async () => (await effects()).announced).toContain(settled);
  await expect.poll(async () => (await effects()).borders).toBe(1);
  await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 }); // the rep run ends

  // judges mode on (the stream reopens with the admin token and replays), then off
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await enterToken(page, "טוקן מנהל", TOKENS.admin);
  await expect(page.locator("#engine-title")).toContainText("חדר המנועים · תור");
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await expect(page.locator("#engine-title")).toHaveCount(0);
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+611");
  await page.waitForTimeout(1_000); // anything a replay would announce has arrived by now

  const { announced, borders } = await effects();
  expect(announced.filter((t) => t === settled)).toHaveLength(1);
  expect(announced.at(-1)).toBe(settled);
  expect(borders).toBe(1); // the settle border played once, not again on either remount
});

test("judges mode: with the admin token a guard card; without it, no judges data on the network", async ({
  page,
  request,
}) => {
  const walkthrough = await demoScript(request, "walkthrough");
  const requests: { url: string; authorization: string | undefined }[] = [];
  page.on("request", (r) =>
    requests.push({ url: r.url(), authorization: r.headers().authorization }),
  );
  await runScript(page, walkthrough);

  // without the token: the toggle asks for it; cancelling leaves judges mode off
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "ביטול" }).click();
  await expect(page.locator("#engine-title")).toHaveCount(0);
  expect(requests.filter((r) => r.url.includes("/api/admin/"))).toEqual([]);
  expect(requests.filter((r) => r.authorization)).toEqual([]);

  // and what the stream sends without a token has no judges fields
  const sessionId = await page.evaluate(() => sessionStorage.getItem("compass.session"));
  const keys = await page.evaluate(async (id) => {
    // read the replay for up to 3 s, then the payload keys per event type
    const controller = new AbortController();
    const response = await fetch(`/api/sessions/${id}/events`, { signal: controller.signal });
    const reader = (response.body as ReadableStream<Uint8Array>).getReader();
    const decoder = new TextDecoder();
    let text = "";
    const until = Date.now() + 3_000;
    while (Date.now() < until && (text.match(/"agent_finished"/g) ?? []).length < 2) {
      const { value, done } = await reader.read();
      if (done) break;
      text += decoder.decode(value);
    }
    controller.abort();
    const byType: Record<string, string[]> = {};
    for (const line of text.split(/\r?\n/)) {
      if (!line.startsWith("data:")) continue;
      const event = JSON.parse(line.slice(5)) as { type: string; payload: object };
      byType[event.type] = [
        ...new Set([...(byType[event.type] ?? []), ...Object.keys(event.payload)]),
      ].sort();
    }
    return byType;
  }, sessionId);
  // judges-only fields are absent (the server's allowlist, compass/api/redact.py)
  expect(keys.tool_call).toEqual(["name", "tool_use_id"]);
  expect(keys.tool_result).toEqual(["name", "ok", "tool_use_id"]);
  expect(keys.guard_check).toEqual(["action", "passed"]);
  expect(keys.agent_finished).toEqual(["outcome"]);

  // with the token: the engine room and a guard card with verified numbers
  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await enterToken(page, "טוקן מנהל", TOKENS.admin);
  const guard = page.locator("article", { hasText: "שומר המספרים" }).last();
  await expect(guard).toContainText("3 מתוך 3 אומתו · נשלח");
  await expect(guard).toContainText("+2,914");
  await expect(guard).toContainText("compare");
  await expect(page.getByRole("region", { name: "נתונים" })).toContainText("/"); // stats tiles
  await page.screenshot({ path: path.join(SCREENSHOTS, "judges.png"), fullPage: true });
});

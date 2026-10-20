/**
 * Today's car unknown (item 5): the server offers the catalog picker in the chat: manufacturer,
 * then model, then year, plus "not in the list" and "no car". axe clean at each step; picking a
 * catalog car sets today's car and the options get their differences (no model call).
 */

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROFILE = {
  occupation_query: "מפתחת תוכנה",
  base_salary: 18500,
  commissions: 0,
  bonus: 0,
  pension_percent: 6.5,
  study_fund_percent: 2.5,
  credit_points: 3,
};

async function tool(request: APIRequestContext, sid: string, name: string, body: unknown) {
  const result = (await (await request.post(`/api/sessions/${sid}/tools/${name}`, { data: body })).json()) as {
    ok: boolean;
  };
  expect(result.ok, `${name}: ${JSON.stringify(result)}`).toBe(true);
}

async function axe(page: Page, info: { attach: (n: string, o: { body: string; contentType: string }) => Promise<void> }, name: string) {
  await page.waitForTimeout(400);
  const results = await new AxeBuilder({ page })
    .include("section[aria-labelledby=car-picker-title]")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const blocking = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  await info.attach(name, { body: JSON.stringify(results.violations, null, 1), contentType: "application/json" });
  expect(blocking).toEqual([]);
}

test("the catalog picker: manufacturer, model, year; axe clean; the pick gives the diffs", async ({
  page,
  request,
}, info) => {
  const sid = ((await (await request.post("/api/sessions")).json()) as { id: string }).id;
  await tool(request, sid, "save_profile", PROFILE);
  await tool(request, sid, "list_options", {}); // today's car unknown: the server offers the picker

  await page.addInitScript((id) => sessionStorage.setItem("compass.session", id), sid);
  await page.goto("/");
  const picker = page.locator("section[aria-labelledby=car-picker-title]");
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("heading")).toContainText("איזה רכב צמוד יש לכם היום");
  await expect(picker.getByRole("button", { name: "הרכב שלי לא ברשימה" })).toBeVisible();
  await expect(picker.getByRole("button", { name: "אין לי רכב היום" })).toBeVisible();
  await axe(page, info, "axe-picker-manufacturers");

  await picker.getByRole("list", { name: "האפשרויות" }).getByRole("button").first().click();
  await expect(picker.getByRole("heading")).toContainText("בחרו דגם");
  await axe(page, info, "axe-picker-models");
  await picker.getByRole("list", { name: "האפשרויות" }).getByRole("button").first().click();
  await expect(picker.getByRole("heading")).toContainText("בחרו שנה");
  await expect(picker.getByRole("button", { name: "שנה אחרת — לבדיקת נציג" })).toBeVisible();
  await axe(page, info, "axe-picker-years");

  await picker.getByRole("list", { name: "האפשרויות" }).getByRole("button").first().click();
  await expect(picker).toHaveCount(0); // the server recorded it
  const options = page.getByRole("radiogroup", { name: /כל החלופות שלך/ });
  await expect(options.getByRole("radio").first()).not.toContainText("חסר הרכב של היום");
});

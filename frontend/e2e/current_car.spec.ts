/**
 * Today's car unknown (fix/current-car): the employee screen shows every eligible alternative
 * with its net and "חסר הרכב של היום" for the difference; a current_car question (opened
 * through the dev tools endpoint, as the agent would open it) is a picker over the catalog in
 * /rep, axe clean; the representative picks the car, and the employee's options get their
 * differences with no model call.
 */

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { enterToken, TOKENS } from "./support";

const PROFILE = {
  occupation_query: "מפתחת תוכנה",
  base_salary: 18500,
  commissions: 0,
  bonus: 0,
  pension_percent: 6.5,
  study_fund_percent: 2.5,
  credit_points: 3,
};
const ASK = {
  question: "העובדת לא מזהה את הרכב הצמוד שלה (כתבה 'מאזדה'). איזה רכב יש לה היום?",
  questions: [{ bound_field: "current_car", car_query: "מאזדה" }],
};
const NOTE = "חסר הרכב של היום";

async function tool(request: APIRequestContext, sid: string, name: string, body: unknown) {
  const result = (await (await request.post(`/api/sessions/${sid}/tools/${name}`, { data: body })).json()) as {
    ok: boolean;
  };
  expect(result.ok, `${name}: ${JSON.stringify(result)}`).toBe(true);
}

test("today's car unknown: options with their nets, the rep picks the car, the diffs appear", async ({
  page,
  request,
}) => {
  const sid = ((await (await request.post("/api/sessions")).json()) as { id: string }).id;
  await tool(request, sid, "save_profile", PROFILE);
  await tool(request, sid, "list_options", {});
  await tool(request, sid, "ask_representative", ASK);

  await page.addInitScript((id) => sessionStorage.setItem("compass.session", id), sid);
  await page.goto("/");
  const options = page.getByRole("radiogroup", { name: /כל החלופות שלך/ });
  await expect(options.getByRole("radio").first()).toContainText(NOTE);
  await expect(options.getByRole("radio").first()).toContainText("זמני");

  await page.goto("/rep");
  await enterToken(page, "טוקן נציג", TOKENS.rep);
  await page.getByRole("link", { name: /הרכב של היום · מאזדה/ }).click();
  const car = page.getByRole("region", { name: /הרכב של היום/ });
  await expect(car.getByRole("radio", { name: "MAZDA 3 2025 · בנזין · קבוצה ג׳" })).toBeVisible();
  await expect(car.getByRole("radio", { name: "הרכב לא בקטלוג (לפרט בהערה)" })).toBeVisible();

  await page.waitForTimeout(600);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const blocking = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(blocking.map((v) => v.id)).toEqual([]);

  await car.getByRole("searchbox").fill("corolla");
  await expect(car.getByRole("radio", { name: "COROLLA CROSS 2025 · היברידי · קבוצה ג׳" })).toBeVisible();
  await car.getByRole("radio", { name: "MAZDA 3 2025 · בנזין · קבוצה ג׳" }).check();
  await expect(car.getByText("בנזין · קבוצה ג׳", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(page.getByRole("link", { name: /הרכב של היום · מאזדה/ })).toHaveCount(0);

  await page.goto("/");
  await expect(options.getByRole("radio").first()).toBeVisible();
  await expect(options).not.toContainText(NOTE);
});

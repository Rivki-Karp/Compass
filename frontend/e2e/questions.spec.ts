/**
 * Rep questions: a ticket with an occupation question (a picker over the occupations table) and
 * a free yes/no question, opened through the dev tools endpoint as the agent would open it.
 * axe on the open ticket; then the rep answers both.
 */

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { enterToken, TOKENS } from "./support";

const PROFILE = {
  base_salary: 18500,
  commissions: 0,
  bonus: 0,
  pension_percent: 6.5,
  study_fund_percent: 2.5,
  credit_points: 3,
};
const TODAY = { today: { kind: "company_car", car_id: "CAR-09", participation: 300 } };
const ASK = {
  question: "העובד מתאר את עצמו כ'מפתח AI', עיסוק שלא מופיע בטבלה, ושואל על חניה לעובדים.",
  questions: [
    { bound_field: "occupation", occupation_query: "מפתח AI" },
    { prompt_he: "האם יש חניה לעובדים בבניין המשרדים?", type: "yes_no" },
  ],
};

test("rep questions: occupation picker and a free yes/no question, axe clean", async ({
  page,
  request,
}) => {
  const sid = ((await (await request.post("/api/sessions")).json()) as { id: string }).id;
  for (const [tool, body] of [
    ["save_profile", PROFILE],
    ["set_current_situation", TODAY],
    ["ask_representative", ASK],
  ] as const) {
    const result = (await (await request.post(`/api/sessions/${sid}/tools/${tool}`, { data: body })).json()) as {
      ok: boolean;
    };
    expect(result.ok, `${tool}: ${JSON.stringify(result)}`).toBe(true);
  }

  await page.goto("/rep");
  await enterToken(page, "טוקן נציג", TOKENS.rep);
  await page.getByRole("link", { name: /סיווג עיסוק · מפתח AI/ }).click();
  const occupation = page.getByRole("region", { name: /סיווג עיסוק/ });
  await expect(occupation.getByRole("radio", { name: "מפתח/ת תוכנה · קבוצה ב׳" })).toBeVisible();
  await expect(page.getByText("אישור חריג לקבוצה")).toHaveCount(0);

  await page.waitForTimeout(600);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const blocking = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(blocking.map((v) => v.id)).toEqual([]);

  await occupation.getByRole("searchbox").fill("מחלקה");
  await occupation.getByRole("radio", { name: "מנהל/ת מחלקה · קבוצה ד׳" }).check();
  await expect(occupation.getByText("קבוצה ד׳", { exact: true })).toBeVisible();
  await occupation.getByRole("radio", { name: "מפתח/ת תוכנה · קבוצה ב׳" }).check();
  const parking = page.getByRole("region", { name: /חניה לעובדים/ });
  await parking.getByRole("radio", { name: "כן" }).check();
  await parking.getByLabel(/^הערה/).fill("בחניון התת-קרקעי, עם תג עובד");
  await page.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(page.getByRole("link", { name: /סיווג עיסוק · מפתח AI/ })).toHaveCount(0);

  const slots = ((await (await request.get(`/api/sessions/${sid}`)).json()) as {
    slots: Record<string, { value: unknown; source: string }>;
  }).slots;
  expect(slots.occupation).toMatchObject({ value: "מפתח/ת תוכנה", source: "representative" });
  expect(slots.group).toMatchObject({ value: "ב", source: "derived" });
});

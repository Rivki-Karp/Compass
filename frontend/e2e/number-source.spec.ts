/**
 * "מאיפה המספר הזה?" end to end, in demo mode (COMPASS_NUMBER_SOURCES=1 on the main e2e server):
 * a verified number in a reply opens its source, with axe and a screenshot at 1440 and at 400,
 * and with the flag off (the payslip server) a reply has no such buttons at all.
 */

import path from "node:path";
import { expect, test } from "@playwright/test";
import { axe } from "./axe";
import { demoScript, PAYSLIP_PORT, runScript, SCREENSHOTS } from "./support";

test("walkthrough: click +2,914, the popover shows compare and the lines it adds up from", async ({
  page,
  request,
}, info) => {
  await runScript(page, await demoScript(request, "walkthrough"));

  // only the verified amounts are buttons: the nets, the diff, the group's budget
  const numbers = page.getByTestId("number-source");
  await expect(numbers).toHaveCount(4);
  const diff = page.getByRole("button", { name: "מאיפה המספר +2,914?" });
  await expect(diff).toHaveCSS("text-decoration-style", "dotted");

  await diff.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("+2,914 ₪ · הפרש בנטו לחודש");
  await expect(dialog).toContainText("חושב בשרת"); // never "לפי הכללים" for a computed number
  await expect(dialog).not.toContainText("לפי הכללים");
  await expect(page.getByTestId("number-origin")).toContainText("חושב בכלי compare");
  await expect(page.getByTestId("number-origin")).toContainText("בשרת, בלי מודל");
  const lines = dialog.getByRole("list", { name: "מרכיבי ההפרש" }).getByRole("listitem");
  await expect(lines).toHaveCount(5); // the waterfall's five steps
  await expect(lines.first()).toContainText("+1,500");

  await axe(page, "number-popover-1440", info);
  await page.screenshot({ path: path.join(SCREENSHOTS, "number-source-1440.png") });

  // Esc closes it and focus is back on the number; one popover at a time
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(diff).toBeFocused();
  await diff.click();
  await page.getByRole("button", { name: "מאיפה המספר 13,914?" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(1);
  await expect(page.getByRole("dialog")).toContainText("נטו בחודש, בחלופה");
});

test("a number the employee stated says so, with the time", async ({ page, request }) => {
  await runScript(page, await demoScript(request, "e001"));
  await page.getByRole("button", { name: "מאיפה המספר 300?" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("לפי דבריך");
  await expect(page.getByTestId("number-origin")).toContainText(/בהודעה מ־\d\d:\d\d/);
});

test("phone width: a bottom sheet with a close button, axe clean", async ({
  page,
  request,
}, info) => {
  await page.setViewportSize({ width: 400, height: 860 });
  await runScript(page, await demoScript(request, "walkthrough"));
  const number = page.getByRole("button", { name: "מאיפה המספר +2,914?" });
  await number.scrollIntoViewIfNeeded();
  await number.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet).toHaveAttribute("data-sheet", "true");
  const box = await sheet.boundingBox();
  expect(box?.width).toBe(400); // edge to edge, at the bottom of the screen
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeCloseTo(860, 0);
  await axe(page, "number-popover-400", info);
  await page.screenshot({ path: path.join(SCREENSHOTS, "number-source-400.png") });
  await sheet.getByRole("button", { name: "סגירה" }).click();
  await expect(sheet).toHaveCount(0);
  await expect(number).toBeFocused();
});

test.describe("with the flag off", () => {
  test.use({ baseURL: `http://127.0.0.1:${PAYSLIP_PORT}` });

  test("a reply's numbers are plain text, no buttons", async ({ page, request }) => {
    await runScript(page, await demoScript(request, "walkthrough"));
    await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+2,914");
    await expect(page.getByText("הפרש של +2,914 ₪").first()).toBeVisible();
    await expect(page.getByTestId("number-source")).toHaveCount(0);
  });
});

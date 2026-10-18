/**
 * The phone summary bar (Day 5 Stage 4) at 400 px: pinned under the header while the page
 * scrolls, and a tap brings the hero card back. Saves docs/screenshots/phone.png.
 */

import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { demoScript, runScript, SCREENSHOTS } from "./support";

test.use({ viewport: { width: 400, height: 860 }, hasTouch: true });

test("phone: the summary bar stays in view and taps back to the hero", async ({ page, request }) => {
  await runScript(page, await demoScript(request, "walkthrough"));
  const bar = page.getByTestId("phone-bar");
  await expect(bar).toContainText("ויתור על הרכב");
  await expect(bar).toContainText("+2,914");

  // scroll to the bottom (the inputs card): the hero is gone, the bar is still at the top
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const hero = page.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).not.toBeInViewport();
  await expect(bar).toBeInViewport();
  expect((await bar.boundingBox())?.y).toBe(0);
  await page.screenshot({ path: path.join(SCREENSHOTS, "phone.png") });

  await bar.tap();
  await expect(hero).toBeInViewport();
  await expect(hero).toBeFocused();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual(
    [],
  );
});

test("wide screens never show the bar", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await runScript(page, await demoScript(request, "walkthrough"));
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+2,914");
  await expect(page.getByTestId("phone-bar")).toHaveCount(0);
});

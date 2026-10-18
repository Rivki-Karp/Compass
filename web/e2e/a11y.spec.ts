/**
 * Accessibility (Day 5 Stage 2): axe on every screen the demo shows, in demo mode. Fails on
 * serious and critical violations; every violation (any impact) is written to
 * test-results/axe/<screen>.json and attached to the report, so minor ones can be reviewed.
 */

import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { demoScript, enterToken, runScript, TOKENS } from "./support";

const BLOCKING = new Set(["serious", "critical"]);
const OUT = path.resolve(import.meta.dirname, "..", "test-results", "axe");

async function axe(page: Page, screen: string, info: TestInfo): Promise<void> {
  // let entrance transitions finish, so colour contrast is measured on the settled screen
  await page.waitForTimeout(600);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const found = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.map((n) => ({ target: n.target.join(" "), summary: n.failureSummary })),
  }));
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, `${screen}.json`), JSON.stringify(found, null, 1));
  await info.attach(`axe-${screen}`, { body: JSON.stringify(found, null, 1), contentType: "application/json" });
  const blocking = found.filter((v) => BLOCKING.has(v.impact ?? ""));
  // soft: one run reports every screen; the test still fails if any screen has one
  expect.soft(blocking, `${screen}: serious or critical axe violations`).toEqual([]);
}

test("axe: employee screen empty, walkthrough finished, judges mode", async ({ page, request }, info) => {
  await page.goto("/");
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  await axe(page, "employee-empty", info);

  await runScript(page, await demoScript(request, "walkthrough"));
  await expect(page.getByRole("article", { name: "תוצאת ההשוואה" })).toContainText("+2,914");
  await axe(page, "employee-walkthrough", info);

  await page.getByRole("button", { name: "מצב שופטים" }).click();
  await axe(page, "judges-token-dialog", info);
  await enterToken(page, "טוקן מנהל", TOKENS.admin);
  await expect(page.locator("#engine-title")).toContainText("חדר המנועים · תור");
  await expect(page.getByRole("region", { name: "נתונים" })).toContainText("/");
  await axe(page, "judges", info);
});

test("axe: E-001 pending, /rep with the ticket open, E-001 final", async ({ page, context, request }, info) => {
  await runScript(page, await demoScript(request, "e001"));
  const hero = page.getByRole("article", { name: "תוצאת ההשוואה" });
  await expect(hero).toContainText("+661");
  await axe(page, "employee-e001-pending", info);

  const rep = await context.newPage();
  await rep.goto("/rep");
  await axe(rep, "rep-token-dialog", info);
  await enterToken(rep, "טוקן נציג", TOKENS.rep);
  await rep.getByRole("link").last().click();
  await expect(rep.getByRole("heading", { name: /ATTO 3\?/ })).toBeVisible();
  await axe(rep, "rep-ticket", info);

  // the server's own error under the input
  await rep.getByLabel("סכום ההשתתפות החודשית (₪)").fill("-50");
  await rep.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(rep.getByRole("alert").first()).toBeVisible();
  await axe(rep, "rep-ticket-error", info);

  await rep.getByLabel("סכום ההשתתפות החודשית (₪)").fill("350");
  await rep.getByRole("button", { name: "אישור ושליחה לעובד/ת" }).click();
  await expect(rep.getByText("התשובה נשלחה. החישוב אצל העובד/ת מתעדכן.").first()).toBeVisible();
  await axe(rep, "rep-answered", info);

  await expect(hero).toContainText("+611");
  await expect(hero).toContainText("סופי");
  await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  await axe(page, "employee-e001-final", info);
});

test("axe: the not-found page", async ({ page }, info) => {
  await page.goto("/no-such-page");
  await expect(page.getByText("הדף לא נמצא")).toBeVisible();
  await axe(page, "not-found", info);
});

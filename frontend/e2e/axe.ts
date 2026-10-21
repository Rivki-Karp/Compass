/** axe on a settled screen: fails on serious and critical violations, and records every one. */

import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";

const BLOCKING = new Set(["serious", "critical"]);
const OUT = path.resolve(import.meta.dirname, "..", "test-results", "axe");

export async function axe(page: Page, screen: string, info: TestInfo): Promise<void> {
  // let entrance animations finish, so colour contrast is measured on the settled screen
  await page.waitForTimeout(1_500);
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
  await info.attach(`axe-${screen}`, {
    body: JSON.stringify(found, null, 1),
    contentType: "application/json",
  });
  const blocking = found.filter((v) => BLOCKING.has(v.impact ?? ""));
  expect.soft(blocking, `${screen}: serious or critical axe violations`).toEqual([]);
}

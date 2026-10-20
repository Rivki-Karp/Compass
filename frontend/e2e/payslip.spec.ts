/**
 * The payslip upload (COMPASS_PAYSLIP=1), in demo mode: the scripted extractor reads every file
 * as the demo payslip (no key, no network). Its own server (PAYSLIP_PORT); the main e2e server
 * has the flag off, and there the attach button never shows. Saves docs/screenshots/payslip-1440
 * and payslip-400.
 */

import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { demoScript, PAYSLIP_PORT, runScript, SCREENSHOTS } from "./support";

const ON = `http://127.0.0.1:${PAYSLIP_PORT}`;

test.skip(!!process.env.E2E_BASE_URL, "needs the e2e config's own flag-on server");
test.use({ baseURL: ON });

/** A one-page PDF (invented text): its bytes, built here. */
function pdf(): Buffer {
  const stream = "BT /F1 12 Tf 72 720 Td (Synthetic payslip) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  out += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

async function attach(page: Page, file: { name: string; mimeType: string; buffer: Buffer }) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "צירוף תלוש שכר" }).click();
  const notice = page.getByRole("dialog", { name: "לפני שמעלים תלוש" });
  if (await notice.isVisible()) {
    await expect(notice).toContainText("אצל Anthropic");
    await notice.getByRole("button", { name: "הבנתי, לבחירת קובץ" }).click();
  }
  await (await chooser).setFiles(file);
}

test("upload, check, confirm: the cards update with the payslip chip", async ({ page, request }, info) => {
  await runScript(page, await demoScript(request, "walkthrough"));
  const inputs = page.getByRole("region", { name: "על מה החישוב מבוסס" });
  await expect(inputs.locator("[data-input=base_salary]")).toContainText("לפי דבריך");

  await attach(page, { name: "payslip.pdf", mimeType: "application/pdf", buffer: pdf() });
  const card = page.getByRole("region", { name: "מה קראנו מהתלוש" });
  await expect(card).toBeVisible();
  await expect(card.getByRole("textbox", { name: "שכר יסוד", exact: true })).toHaveValue("18500");
  await expect(card).toContainText("ודאות נמוכה"); // the demo's credit points read "low"

  // axe on the confirmation card, at the settled screen
  await page.waitForTimeout(600);
  const results = await new AxeBuilder({ page })
    .include("section[aria-labelledby=payslip-card-title]")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const blocking = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  await info.attach("axe-payslip-card", { body: JSON.stringify(results.violations, null, 1), contentType: "application/json" });
  expect(blocking).toEqual([]);

  await page.screenshot({ path: path.join(SCREENSHOTS, "payslip-1440.png") });
  await card.getByRole("button", { name: "אישור ושמירה" }).click();
  await expect(page.getByText("הנתונים נשמרו לפי התלוש.")).toBeVisible();
  await expect(card).toHaveCount(0);
  // the server recomputed the comparison: the salary now reads "לפי התלוש"
  await expect(inputs.locator("[data-input=base_salary]")).toContainText("לפי התלוש");
  await expect(inputs.locator("[data-input=pension_percent]")).toContainText("לפי התלוש");
  // and the agent was told, as data (demo mode: a fixed line without numbers)
  await expect(page.getByText("קיבלתי את הנתונים שאישרת מהתלוש.", { exact: false })).toBeVisible();
});

test("errors: the client's quick check, then the server's, each with a way forward", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  await attach(page, { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("אפשר להעלות רק PDF, JPG או PNG.");
  await expect(alert.getByRole("button", { name: "בחירת קובץ אחר" })).toBeVisible();

  // a renamed file: the type says PDF, the bytes do not (the server's magic-byte check)
  const chooser = page.waitForEvent("filechooser");
  await alert.getByRole("button", { name: "בחירת קובץ אחר" }).click();
  await (await chooser).setFiles({ name: "x.pdf", mimeType: "application/pdf", buffer: Buffer.from("not a pdf") });
  await expect(page.getByRole("alert")).toContainText("תוכן הקובץ לא תואם את סוג הקובץ");
});

test("phone width: the card stacks, nothing hidden", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 860 });
  await page.goto("/");
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  await attach(page, { name: "payslip.pdf", mimeType: "application/pdf", buffer: pdf() });
  const card = page.getByRole("region", { name: "מה קראנו מהתלוש" });
  await expect(card).toBeVisible();
  for (const label of ["שכר יסוד", "הפרשת עובד לפנסיה", "נקודות זיכוי"]) {
    await expect(card.getByRole("textbox", { name: label, exact: true })).toBeVisible();
  }
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(400); // no horizontal scroll
  await card.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SCREENSHOTS, "payslip-400.png") });
});

test("the flag off: no attach button at all", async ({ page }) => {
  await page.goto("http://127.0.0.1:8765/"); // the main e2e server, COMPASS_PAYSLIP=0
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "צירוף תלוש שכר" })).toHaveCount(0);
});

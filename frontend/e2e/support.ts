/** Shared by the e2e config and specs. */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const TOKENS = { rep: "rep-e2e", admin: "admin-e2e" } as const;
/** The e2e server with the payslip upload on (playwright.config.ts); the main one has it off. */
export const PAYSLIP_PORT = 8766;

/** The e2e server with accounts on (COMPASS_AUTH=1, scripted model); see playwright.config.ts. */
export const AUTH_PORT = 8767;
/** The e2e server with remembered details on (accounts, number sources); see playwright.config.ts. */
export const PROFILE_PORT = 8768;
/** The one password of the e2e accounts. A test value, public on purpose; only its hash is seeded. */
export const E2E_PASSWORD = "e2e-password-only-for-tests";
const E2E_HASH =
  "$argon2id$v=19$m=65536,t=3,p=4$RDTMi22r8zOARemy2bXa/g$Za4skWmuK9SPiHb+0pb+Z00WNgyMLxuuvap7sVmV1aY";
export const ACCOUNTS = {
  employee: { email: "dana@example.com", name: "דנה לוי", role: "employee" },
  other: { email: "avi@example.com", name: "אבי כהן", role: "employee" },
  victim: { email: "noa@example.com", name: "נועה בר", role: "employee" },
  rep: { email: "rep@example.com", name: "רותם נציגה", role: "rep" },
  admin: { email: "admin@example.com", name: "מנהל מערכת", role: "admin" },
} as const;
/** COMPASS_SEED_USERS for the accounts server: the hash only, never a password. */
export const SEED_USERS = JSON.stringify(
  Object.values(ACCOUNTS).map((a) => ({ ...a, password_hash: E2E_HASH })),
);

/** README screenshots (brief Stage 8): committed from this run. */
export const SCREENSHOTS = path.resolve(HERE, "..", "..", "docs", "screenshots");

interface DemoScript {
  name: string;
  messages: string[];
}

export async function demoScript(request: APIRequestContext, name: string): Promise<DemoScript> {
  const health = (await (await request.get("/api/health")).json()) as {
    llm: string;
    demo_scripts: DemoScript[];
  };
  expect(health.llm).toBe("scripted");
  const script = health.demo_scripts.find((s) => s.name === name);
  if (!script) throw new Error(`no demo script ${name}`);
  return script;
}

/** Open the employee screen in a fresh session and send a script's messages via its chips. */
export async function runScript(page: Page, script: DemoScript): Promise<void> {
  await page.goto("/");
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  for (const text of script.messages) {
    const chip = page.getByRole("button", { name: text });
    await chip.click();
    // the run finished: the chips come back (or, after the last message, none are left)
    await expect(page.getByText("מחשב…")).toHaveCount(0, { timeout: 60_000 });
  }
}

export async function enterToken(page: Page, label: string, token: string): Promise<void> {
  await page.getByLabel(label).fill(token);
  await page.getByRole("button", { name: "אישור", exact: true }).click();
}

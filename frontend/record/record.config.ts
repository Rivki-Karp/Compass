import { defineConfig, devices } from "@playwright/test";

/**
 * The backup demo video (Day 5 Stage 6). Not part of the test suite: `npm run e2e` never runs it
 * (testDir is e2e). `uv run --project backend python tasks.py record-demo` seeds and starts the
 * demo server, then runs this config with RECORD_BASE_URL and friends set.
 */
export default defineConfig({
  testDir: ".",
  testMatch: "*.record.ts",
  workers: 1,
  timeout: 10 * 60_000,
  expect: { timeout: 60_000 },
  reporter: [["list"]],
  outputDir: "../test-results/record",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.RECORD_BASE_URL,
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "he-IL",
    video: { mode: "on", size: { width: 1440, height: 900 } },
  },
});

import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";
import { TOKENS } from "./e2e/support";

const HERE = path.dirname(fileURLToPath(import.meta.url));

/**
 * End to end, in demo mode (brief Stage 8): the real API with the scripted model (no key, no
 * network) serving the production build, as `tasks.py demo` does. Its own port and a fresh demo
 * database per run, so it never touches a running demo or app.db.
 *
 *   npx playwright test            (from frontend/; builds the UI first)
 *
 * E2E_BASE_URL runs the same tests against a server that is already running instead (the Docker
 * image, Day 5 Stage 5): demo mode, with the rep and admin tokens from e2e/support.ts.
 */

const PORT = 8765;
const DEMO_DB = path.join(HERE, "test-results", `e2e-${Date.now()}.db`);
const EXTERNAL = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // one demo server, one story at a time
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 30_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: EXTERNAL ?? `http://127.0.0.1:${PORT}`,
    viewport: { width: 1440, height: 900 },
    locale: "he-IL",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: EXTERNAL ? undefined : {
    command: `npm run build && cd ../backend && uv run python -m uvicorn compass.api.main:app --workers 1 --port ${PORT}`,
    cwd: HERE,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      COMPASS_LLM: "scripted",
      // the e2e server only: lets a test run list_options the way the model would
      COMPASS_DEV_TOOLS: "1",
      // every test types from 127.0.0.1: not the per-IP limit under test here
      COMPASS_MESSAGE_RATE_PER_MINUTE: "1000",
      COMPASS_DEMO_DB: DEMO_DB,
      COMPASS_REP_TOKEN: TOKENS.rep,
      COMPASS_ADMIN_TOKEN: TOKENS.admin,
      COMPASS_WEB_DIST: path.join(HERE, "dist"),
    },
  },
});

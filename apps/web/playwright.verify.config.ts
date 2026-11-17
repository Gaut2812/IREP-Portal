import { defineConfig, devices } from "@playwright/test";

/**
 * Verification config: Playwright starts (and stops) its own production
 * `next start` on port 3002 from the current `.next` build, so a stale dev
 * server on :3000 never masks the code under test. Run `pnpm build` first.
 *
 *   pnpm build && pnpm exec playwright test -c playwright.verify.config.ts
 *
 * The API is expected on :8000 (reused when already running).
 */
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3002";
const PORT = new URL(BASE).port || "3002";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
    headless: true,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: '"../api/venv/Scripts/python.exe" "../api/start_api.py"',
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60000,
    },
    {
      command: `pnpm exec next start -p ${PORT}`,
      url: `${BASE}/login`,
      reuseExistingServer: !!process.env.PLAYWRIGHT_TEST_BASE_URL,
      timeout: 90000,
    },
  ],
});

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
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://localhost:3002",
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
      command: "pnpm exec next start -p 3002",
      url: "http://localhost:3002/login",
      reuseExistingServer: false,
      timeout: 90000,
    },
  ],
});

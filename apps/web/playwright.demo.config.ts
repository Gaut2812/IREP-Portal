import { defineConfig, devices } from "@playwright/test";

/**
 * Records the progress demo video (one continuous session through every
 * completed screen). Run after `pnpm build` with the API on :8001 and
 * `next start -p 3005`:
 *   pnpm exec playwright test -c playwright.demo.config.ts
 * The video is written to test-results-demo/.../video.webm
 */
export default defineConfig({
  testDir: "./e2e-demo",
  globalSetup: "./e2e/global-setup.ts",
  outputDir: "./test-results-demo",
  timeout: 20 * 60 * 1000,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3005",
    viewport: { width: 1440, height: 900 },
    video: { mode: "on", size: { width: 1440, height: 900 } },
    launchOptions: { slowMo: 150 },
    actionTimeout: 15000,
    navigationTimeout: 30000,
    headless: true,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});

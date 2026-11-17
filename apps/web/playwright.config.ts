import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  // Specs live in two folders: tests/e2e (Screen 11 courses) and e2e (Screen 24 coding)
  testDir: ".",
  testMatch: ["tests/e2e/**/*.spec.ts", "e2e/**/*.spec.ts"],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL:
      process.env.PLAYWRIGHT_BASE_URL ||
      process.env.PLAYWRIGHT_TEST_BASE_URL ||
      "http://localhost:3000",
    trace: "on-first-retry",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: '"../api/venv/Scripts/python.exe" "../api/start_api.py"',
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});

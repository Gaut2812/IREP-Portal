import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000",
    trace: "on",
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
      timeout: 60000,
    },
    {
      command: "pnpm start",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 60000,
    },
  ],
});

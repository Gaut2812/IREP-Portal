import { defineConfig, devices } from "@playwright/test";

// Local Windows dev uses the API venv; CI (Linux) sets API_PYTHON or falls back to `python`.
const apiPython =
  process.env.API_PYTHON ?? (process.platform === "win32" ? "../api/venv/Scripts/python.exe" : "python");

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
      command: `"${apiPython}" "../api/start_api.py"`,
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60000,
      // every spec signs parents in from 127.0.0.1 and audit rows outlive a run: lift the per-IP OTP
      // limits for this test server only (they are covered by apps/api/tests/test_security_review.py)
      env: { OTP_IP_REQUESTS_PER_WINDOW: "100000", OTP_IP_VERIFY_FAILS_PER_WINDOW: "100000", LOGIN_IP_FAILS_PER_WINDOW: "100000" },
    },
    {
      command: "pnpm start",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 60000,
    },
  ],
});

import { defineConfig, devices } from "@playwright/test";

/**
 * Keycloak sign-in end to end (opt-in). Needs infra/keycloak running and
 * `python apps/api/seed/sync_keycloak.py` done. Starts its own API in
 * AUTH_PROVIDER=keycloak mode, so stop any other API on :8000 first.
 *   pnpm build && pnpm exec playwright test -c playwright.keycloak.config.ts
 */
const apiPython =
  process.env.API_PYTHON ?? (process.platform === "win32" ? "../api/venv/Scripts/python.exe" : "python");

export default defineConfig({
  testDir: "./e2e-keycloak",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", headless: true },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${apiPython}" "../api/start_api.py"`,
      url: "http://localhost:8000/health",
      reuseExistingServer: false,
      timeout: 60000,
      env: { AUTH_PROVIDER: "keycloak", KEYCLOAK_URL: process.env.KEYCLOAK_URL ?? "http://localhost:8081" },
    },
    { command: "pnpm start", url: "http://localhost:3000", reuseExistingServer: true, timeout: 60000 },
  ],
});

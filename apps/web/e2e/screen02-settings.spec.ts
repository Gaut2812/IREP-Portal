import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 02 · College settings. Spec: docs/screens/02-college-settings.md */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";

test.describe("Screen 02: College settings (/college/settings)", () => {
  test("add a placement officer who then signs in to the college UI", async ({ page, browser }) => {
    await loginAs(page, "college");
    await page.goto("/college/settings");
    const email = `placement.${Date.now().toString(36)}@demo.edu`;
    await page.getByTestId("user-name").fill("Meena Placement");
    await page.getByTestId("user-email").fill(email);
    await page.getByTestId("user-role").selectOption("placement_officer");
    await page.getByTestId("user-save").click();
    const password = await page.getByTestId("user-temp-password-value").innerText();
    await expect(page.getByTestId("user-row").filter({ hasText: email })).toContainText("Placement officer");

    const ctx = await browser.newContext();
    const p2 = await ctx.newPage();
    await p2.goto("/login");
    await p2.getByTestId("role-college").click();
    await p2.getByTestId("login-identifier").fill(email);
    await p2.getByTestId("login-password").fill(password);
    await p2.getByTestId("login-submit").click();
    await p2.waitForURL("**/college");
    await ctx.close();
  });

  test("a data request raised here is completed on 48 and downloaded here", { tag: "@L27" }, async ({ page, browser }) => {
    await loginAs(page, "college");
    await page.goto("/college/settings");
    await page.getByTestId("request-student").fill("Priya");
    await page.getByTestId("student-hit").first().click();
    await page.getByTestId("request-reason").fill("Priya asked for a copy of her portal data");
    await page.getByTestId("request-save").click();
    const row = page.getByTestId("college-request").filter({ hasText: "Priya R" }).first();
    await expect(row).toContainText("Received");

    // IREP staff complete it on screen 48
    const staffCtx = await browser.newContext();
    const sp = await staffCtx.newPage();
    const { token } = await loginAs(sp, "admin");
    const queue = await (await sp.request.get(`${API}/admin/data-requests?status=received`, { headers: { Authorization: `Bearer ${token}` } })).json();
    const mine = queue.items.find((i: { student_id: string; kind: string }) => i.student_id === "std_priya_01" && i.kind === "export");
    await sp.request.post(`${API}/admin/data-requests/${mine.id}/complete`, { headers: { Authorization: `Bearer ${token}` } });
    await staffCtx.close();

    await expect(async () => {
      await page.reload();
      await expect(page.getByTestId("college-request").filter({ hasText: "Priya R" }).first().getByTestId("college-request-download")).toBeVisible({ timeout: 1000 });
    }).toPass({ timeout: 20000 });
    const download = page.waitForEvent("download");
    await page.getByTestId("college-request").filter({ hasText: "Priya R" }).first().getByTestId("college-request-download").click();
    expect((await download).suggestedFilename()).toBe("irep-export-std_priya_01.json");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "college", { lang: "ta" });
    await page.goto("/college/settings");
    await expect(page.getByTestId("user-save")).toHaveText("பயனரைச் சேர்");
  });

  test("blocks the trainer role", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/college/settings");
    await expect(page.getByTestId("users-section")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

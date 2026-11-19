import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 45 · Colleges and MoU terms. Spec: docs/screens/45-colleges-and-mou.md */
test.describe("Screen 45: Colleges and MoU terms (/admin/colleges)", () => {
  test("staff onboard a college: create, MoU, feature switch, first admin who then signs in", { tag: "@L01" }, async ({ page, browser }) => {
    const code = `E${Date.now().toString(36).slice(-6).toUpperCase()}`;
    await loginAs(page, "admin");
    await page.goto("/admin/colleges");
    await expect(page.getByTestId("college-row-DEC")).toBeVisible();

    await page.getByTestId("new-college").click();
    await page.getByTestId("college-save").click();                         // empty form: inline errors, no request
    await expect(page.getByText("Enter the college name (at least 3 characters).")).toBeVisible();
    await page.getByTestId("college-name").fill("Kongu Test Engineering College");
    await page.getByTestId("college-code").fill(code);
    await page.getByTestId("college-city").fill("Erode");
    await page.getByTestId("college-save").click();
    const row = page.getByTestId(`college-row-${code}`);
    await expect(row).toContainText("Onboarding");

    await row.getByRole("link").click();
    await expect(page.getByTestId("college-status")).toHaveText("Onboarding");
    await page.getByTestId("mou-cap").fill("420");
    await page.getByTestId("mou-save").click();
    await expect(page.getByTestId("mou-active")).toContainText("420");

    const cyber = page.getByTestId("feature-cyber_range");
    await expect(cyber).toHaveAttribute("aria-checked", "false");
    await cyber.click();
    await expect(cyber).toHaveAttribute("aria-checked", "true");

    const email = `coordinator.${code.toLowerCase()}@college.example`;
    await page.getByTestId("admin-name").fill("Dr. Lakshmi Narayanan");
    await page.getByTestId("admin-email").fill(email);
    await page.getByTestId("admin-save").click();
    const password = await page.getByTestId("temp-password-value").innerText();
    await expect(page.getByTestId("college-status")).toHaveText("Active");

    // the new admin signs in with the one-time password and lands on their own (empty) college
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

  test("IREP staff sign in from the login page", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-admin").click();
    await expect(page.getByTestId("login-identifier")).toHaveValue("staff@irep.demo");
    await page.getByTestId("login-password").fill("password123");
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/admin/colleges");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "admin", { lang: "ta" });
    await page.goto("/admin/colleges");
    await expect(page.getByRole("heading", { level: 1, name: "கல்லூரிகள் மற்றும் ஒப்பந்த விதிமுறைகள்" })).toBeVisible();
    await expect(page.getByTestId("new-college")).toContainText("புதிய கல்லூரி");
  });

  test("blocks the college admin role", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/admin/colleges");
    await expect(page.getByTestId("colleges-table")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Super admin (docs/PERMISSIONS.md): staff accounts and logged support sessions. */
test.describe("Super admin (/admin/super)", () => {
  test("super admin invites IREP staff, deactivates them, and runs a logged support session", async ({ page }) => {
    await loginAs(page, "super");
    await page.goto("/admin/colleges");
    await page.getByRole("link", { name: "Super admin" }).first().click();
    await page.waitForURL("**/admin/super");
    await expect(page.getByTestId("staff-row").filter({ hasText: "super@irep.demo" })).toContainText("you");

    const email = `ops.${Date.now().toString(36)}@irep.example`;
    await page.getByTestId("invite-send").click();                                   // empty form: inline error, no request
    await expect(page.getByTestId("super-error")).toContainText("valid email");
    await page.getByTestId("invite-name").fill("Ops Trainee");
    await page.getByTestId("invite-email").fill(email);
    await page.getByTestId("invite-send").click();
    await expect(page.getByTestId("invite-result")).toContainText(email);
    const row = page.getByTestId("staff-row").filter({ hasText: email });
    await expect(row.getByTestId("staff-role")).toHaveValue("irep_admin");
    await expect(row).toContainText("Required");                                       // two-factor
    await row.getByTestId("staff-deactivate").click();
    await expect(row.getByTestId("staff-status")).toHaveText("Deactivated");

    await page.getByTestId("session-college").selectOption({ label: "Demo Engineering College" });
    await page.getByTestId("session-minutes").selectOption("30");
    await page.getByTestId("session-reason").fill("Parent cannot see the monthly card for October");
    await page.getByTestId("session-open").click();
    const session = page.getByTestId("session-row").filter({ hasText: "monthly card for October" }).first();
    await expect(session.getByTestId("session-state")).toHaveText("Active");
    await session.getByTestId("session-end").click();
    await expect(session.getByTestId("session-state")).toHaveText("Closed");
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "super", { lang: "ta" });
    await page.goto("/admin/super");
    await expect(page.getByRole("heading", { level: 1, name: "சூப்பர் நிர்வாகி" })).toBeVisible();
    await expect(page.getByTestId("staff-section")).toContainText("IREP பணியாளர் கணக்குகள்");
    await expect(page.getByTestId("session-open")).toHaveText("அமர்வைத் தொடங்கு");
  });

  test("IREP staff do not get the page or the menu item", async ({ page }) => {
    await loginAs(page, "admin");
    await page.goto("/admin/colleges");
    await expect(page.getByRole("link", { name: "Super admin" })).toHaveCount(0);
    await page.goto("/admin/super");
    await expect(page.getByTestId("super-forbidden")).toBeVisible();
    await expect(page.getByTestId("staff-section")).toHaveCount(0);
  });

  test("staff sent back for two-factor see why, in English and Tamil", async ({ page }) => {
    await page.goto("/login?reauth=2fa");
    await expect(page.getByTestId("login-reauth-2fa")).toContainText("authenticator app");
    await expect(page.getByTestId("login-identifier")).toHaveValue("staff@irep.demo");     // IREP staff card selected
    await page.evaluate(() => localStorage.setItem("irep_lang", "ta"));
    await page.reload();
    await expect(page.getByTestId("login-reauth-2fa")).toContainText("அங்கீகரிப்புச் செயலி");
  });

  test("blocks the college admin role", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/admin/super");
    await expect(page.getByTestId("staff-section")).toHaveCount(0);
    await expect(page.getByText(/Access restricted/i)).toBeVisible();
  });
});

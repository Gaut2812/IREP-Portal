import { test, expect } from "@playwright/test";

test.describe("Keycloak single sign-on (AUTH_PROVIDER=keycloak)", () => {
  test("student signs in on the Keycloak page and lands on the dashboard", { tag: "@L01" }, async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-student").click();
    await expect(page.getByTestId("login-sso-hint")).toBeVisible();
    await expect(page.getByTestId("login-password")).toHaveCount(0);
    await page.getByTestId("login-submit").click();

    await page.waitForURL(/localhost:8081\/realms\/irep\/protocol\/openid-connect\/auth/);
    await page.locator("#username").fill("priya.r@demo.edu");
    await page.locator("#password").fill("password123");
    await page.locator("#kc-login").click();

    await page.waitForURL("**/student", { timeout: 30000 });
    await expect(page.getByText("Priya", { exact: false }).first()).toBeVisible();
    const token = await page.evaluate(() => localStorage.getItem("irep_token"));
    expect(JSON.parse(atob(token!.split(".")[0])).alg).toBe("RS256");     // a Keycloak token, not the API's
  });

  test("trainer lands on the trainer dashboard; a wrong password stays on Keycloak", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-trainer").click();
    await page.getByTestId("login-submit").click();
    await page.waitForURL(/localhost:8081/);
    await page.locator("#username").fill("arun.k@demo.edu");
    await page.locator("#password").fill("not-the-password");
    await page.locator("#kc-login").click();
    await expect(page.getByText("Invalid username or password.")).toBeVisible();
    await expect(page).toHaveURL(/localhost:8081/);
    await page.locator("#password").fill("password123");
    await page.locator("#kc-login").click();
    await page.waitForURL("**/trainer", { timeout: 30000 });
  });

  test("sign-out ends the Keycloak session too", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-college").click();
    await page.getByTestId("login-submit").click();
    await page.waitForURL(/localhost:8081/);
    await page.locator("#username").fill("admin@demo.edu");
    await page.locator("#password").fill("password123");
    await page.locator("#kc-login").click();
    await page.waitForURL("**/college", { timeout: 30000 });

    await page.getByTestId("profile-button").click();
    await page.getByTestId("sign-out").click();
    await page.waitForURL("**/login", { timeout: 30000 });
    expect(await page.evaluate(() => localStorage.getItem("irep_token"))).toBeNull();

    // signing in again must show the Keycloak form, not slip through on the old session
    await page.getByTestId("role-college").click();
    await page.getByTestId("login-submit").click();
    await page.waitForURL(/localhost:8081/);
    await expect(page.locator("#password")).toBeVisible();
  });

  test("parents still sign in with mobile OTP", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-parent").click();
    await expect(page.getByTestId("login-phone")).toBeVisible();
    await page.getByTestId("login-phone").fill("9876543214");
    await page.getByTestId("login-submit").click();
    const otp = (await page.getByTestId("demo-otp").innerText()).match(/\d{6}/)![0];
    await page.getByTestId("login-otp").fill(otp);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/parent", { timeout: 30000 });
  });
});

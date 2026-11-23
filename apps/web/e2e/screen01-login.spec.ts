import { test, expect } from "@playwright/test";

test.describe("Screen 01: Sign-in (/login)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      if (!sessionStorage.getItem("cleared")) {
        localStorage.clear();
        sessionStorage.setItem("cleared", "1");
      }
    });
  });

  for (const [role, home, heading] of [
    ["student", "/student", "priya.r@demo.edu"],
    ["trainer", "/trainer", "arun.k@demo.edu"],
    ["college", "/college", "admin@demo.edu"],
  ] as const) {
    test(`${role} signs in with a password and lands on ${home}`, async ({ page }) => {
      await page.goto("/login");
      await page.getByTestId(`role-${role}`).click();
      await expect(page.getByTestId("login-identifier")).toHaveValue(heading);
      await page.getByTestId("login-password").fill("password123");
      await page.getByTestId("login-submit").click();
      await page.waitForURL(`**${home}`);
      expect(new URL(page.url()).pathname).toBe(home);
    });
  }

  test("wrong password shows the server error and does not sign in", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-trainer").click();
    await page.getByTestId("login-identifier").fill("pooja.m@demo.edu");
    await page.getByTestId("login-password").fill("not-the-password");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("login-error")).toContainText("attempts left");
    expect(new URL(page.url()).pathname).toBe("/login");
    // a correct password clears the counter for the real sign-in
    await page.getByTestId("login-password").fill("password123");
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/trainer");
  });

  test("empty fields show inline errors", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-identifier").fill("");
    await page.getByTestId("login-password").fill("");
    await page.getByTestId("login-submit").click();
    await expect(page.getByText("Enter your register number or email")).toBeVisible();
    await expect(page.getByText("Enter your password")).toBeVisible();
  });

  test("parent signs in with mobile number and OTP", { tag: "@L01" }, async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("role-parent").click();
    await page.getByTestId("login-phone").fill("9876543214");
    await page.getByTestId("login-submit").click();
    const demo = await page.getByTestId("demo-otp").innerText();
    const otp = demo.match(/\d{6}/)![0];
    await page.getByTestId("login-otp").fill("12");
    await page.getByTestId("login-submit").click();
    await expect(page.getByText("Enter the 6-digit OTP")).toBeVisible();
    await page.getByTestId("login-otp").fill(otp);
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/parent");
  });

  test("Tamil toggle translates the sign-in card", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-lang").click();
    await expect(page.getByText("பதிவு எண் / மின்னஞ்சல்")).toBeVisible();
    await expect(page.getByText("பருவம் 2-7")).toBeVisible();
  });

  test("a student opening a trainer page sees the role guard", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-password").fill("password123");
    await page.getByTestId("login-submit").click();
    await page.waitForURL("**/student");
    await page.goto("/trainer");
    await expect(page.getByText(/Access Restricted/i).first()).toBeVisible();
  });
});

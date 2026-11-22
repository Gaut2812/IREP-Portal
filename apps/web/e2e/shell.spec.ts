import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

test.describe("App shell: profile menu, per-user notifications, mobile navigation", () => {
  test("no role switcher; the profile menu shows the user and signs out", async ({ page }) => {
    await loginAs(page, "trainer");
    await page.goto("/trainer");
    await expect(page.getByText(/View as/i)).toHaveCount(0);
    await page.getByTestId("profile-button").click();
    const menu = page.getByTestId("profile-menu");
    await expect(menu).toContainText("Arun Kumar");
    await expect(menu).toContainText("arun.k@demo.edu");
    await expect(menu).toContainText("Trainer");
    await page.getByTestId("sign-out").click();
    await page.waitForURL("**/login");
    expect(await page.evaluate(() => localStorage.getItem("irep_token"))).toBeNull();
  });

  test("signed-out visitors are sent to the login page", async ({ page }) => {
    await page.goto("/trainer");
    await page.waitForURL("**/login");
    await page.goto("/");
    await page.waitForURL("**/login");
  });

  test("each role's bell lists only that user's notifications", async ({ page, browser }) => {
    await loginAs(page, "student");
    await page.goto("/student");
    await page.getByTestId("notification-bell").click();
    const studentPanel = page.getByTestId("notification-panel");
    await expect(studentPanel).not.toContainText("Lab access request");
    await expect(studentPanel).not.toContainText("New message from");

    const trainer = await browser.newPage();
    await loginAs(trainer, "trainer");
    await trainer.goto("/trainer");
    await trainer.getByTestId("notification-bell").click();
    const trainerPanel = trainer.getByTestId("notification-panel");
    await expect(trainerPanel).toBeVisible();
    await expect(trainerPanel).not.toContainText("Mock interview booked");
    await expect(trainerPanel).not.toContainText("Interview #3 feedback is ready");
    await trainer.close();
  });

  test("an invalid session goes back to login instead of showing another user's data", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("irep_user", JSON.stringify({ id: "usr_arun_01", role: "trainer", name: "Arun Kumar", avatar: "AK", college_id: "col_demo_001" }));
      localStorage.setItem("irep_token", "expired.or.tampered.token");
    });
    await page.goto("/trainer");
    await page.waitForURL("**/login**");
  });

  test("phone width: menu button opens the navigation drawer", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAs(page, "parent");
    await page.goto("/parent");
    await page.getByTestId("open-nav").click();
    const nav = page.getByTestId("mobile-nav");
    await expect(nav).toBeVisible();
    await nav.getByRole("link", { name: "Message Trainer" }).click();
    await page.waitForURL("**/parent/messages");
    await expect(page.getByTestId("mobile-nav")).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
  });

  test("menu items for later modules show a friendly page, not a bare 404", async ({ page }) => {
    await loginAs(page, "college");
    await page.goto("/college/billing");               // billing arrives in S16
    await expect(page.getByTestId("coming-soon")).toContainText("Coming soon");
  });
});

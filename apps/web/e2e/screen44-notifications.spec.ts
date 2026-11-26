import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers/auth";

/** Screen 44 · Notification centre (every role, opened from the bell). */
const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000/api/v1";
const DEFAULTS = { email_enabled: true, sms_enabled: true, push_enabled: false, quiet_start_hour: null, quiet_end_hour: null, language: "en" };

test.describe("Screen 44: Notification centre (/notifications)", () => {
  test("opened from the bell: list, unread filter, mark all read", async ({ page }) => {
    await loginAs(page, "parent");
    await page.goto("/parent");
    await page.getByTestId("notification-bell").click();
    await page.getByTestId("notifications-see-all").click();
    await page.waitForURL("**/notifications");
    await expect(page.getByTestId("notification-item").first()).toBeVisible();
    await page.getByTestId("page-mark-all").click();
    await expect(page.getByTestId("unread-count")).toHaveText(/^0 /);
    await page.getByTestId("filter-unread").check();
    await expect(page.getByTestId("notification-item")).toHaveCount(0);
  });

  test("delivery preferences are saved", async ({ page }) => {
    const { token } = await loginAs(page, "student");
    await page.goto("/notifications");
    await page.getByTestId("pref-sms_enabled").uncheck();
    await page.getByTestId("pref-quiet-start").selectOption("21");
    await page.getByTestId("pref-quiet-end").selectOption("7");
    await page.getByTestId("prefs-save").click();
    await expect(page.getByTestId("prefs-saved")).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("pref-quiet-start")).toHaveValue("21");
    await expect(page.getByTestId("pref-sms_enabled")).not.toBeChecked();
    await page.request.put(`${API}/notifications/preferences`, { headers: { Authorization: `Bearer ${token}` }, data: DEFAULTS });
  });

  test("supports the Tamil toggle", async ({ page }) => {
    await loginAs(page, "trainer", { lang: "ta" });
    await page.goto("/notifications");
    await expect(page.getByTestId("prefs-save")).toHaveText("விருப்பங்களைச் சேமி");
    // the type under each notification is translated, not the raw kind ("info", "approval", ...)
    const kinds = await page.getByTestId("notif-kind").allInnerTexts();
    expect(kinds.length).toBeGreaterThan(0);
    for (const k of kinds) expect(k).not.toMatch(/^[a-z_]+$/);
    // saving channels or quiet hours keeps the page in Tamil (the form used to load the stored "English")
    await page.getByTestId("prefs-save").click();
    await expect(page.getByTestId("prefs-saved")).toBeVisible();
    await expect(page.getByTestId("prefs-save")).toHaveText("விருப்பங்களைச் சேமி");
  });

  test("signed-out visitors are sent to sign in", async ({ page }) => {
    await page.goto("/notifications");
    await page.waitForURL("**/login");
  });
});
